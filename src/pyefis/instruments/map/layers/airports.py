#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map airports layer (spec 5.2, Phase C).
#
#  FAA sectional symbology from the NASR airports.sqlite (the same db
#  the SVS uses): hard-surface airports 1500-8069 ft draw the classic
#  circle with real-orientation runway strips inside; >8069 ft draw
#  the runway strips alone (no circle); non-hard fields draw a plain
#  circle. All magenta until tower (TWR) data joins the pack -- then
#  towered fields turn blue (spec decision 3). Ident labels and a
#  deterministic grid declutter keep the picture stable by zoom.
#
#  Same async contract as the terrain layer: a worker snapshots the
#  window's airports; paint() only projects and draws.

import math
import threading

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen

from pyefis.instruments.map.layers import MapLayer, register_layer

MAGENTA = QColor(197, 36, 125)

#: ranges (NM): idents shown at/below the first, symbols at/below the second
_IDENT_RANGE = 40.0
_SYMBOL_RANGE = 80.0


@register_layer
class AirportsLayer(MapLayer):
    id = "airports"
    label = "Airports"
    z = 30
    default_on = True

    _SNAP_FRAC = 0.25       # window re-anchor hysteresis

    def __init__(self):
        super(AirportsLayer, self).__init__()
        self._db_all = None
        self._db_paved = None
        self._snap = None       # (key, [airport dicts])
        self._job = None
        self._worker = None
        self._lock = threading.Lock()

    def configure(self, owner):
        self._owner = owner
        path = str(getattr(owner, "nasr_db_path", "") or "")
        if path:
            from pyefis.instruments.ai.airport_db import NASRAirportDB
            self._db_all = NASRAirportDB(path, paved_only=False)
            self._db_paved = NASRAirportDB(path, paved_only=True)

    def _key(self, x):
        snap = max(1.0, x.range_nm * self._SNAP_FRAC)
        return (round(x.lat0 * 60.0 / snap), round(x.lon0 * 60.0 / snap),
                round(x.range_nm, 1))

    def paint(self, p, x):
        if self._db_all is None or not self._db_all.ready \
                or x.range_nm > _SYMBOL_RANGE:
            return
        key = self._key(x)
        with self._lock:
            snap = self._snap
            have = snap is not None and snap[0] == key
        if not have:
            with self._lock:
                # Same-key reposts must not refresh the in-flight job:
                # the raw pose in the tuple would make the worker's
                # latest-wins check discard every finished snapshot
                # while the aircraft is moving (#89).
                if self._job is None or self._job[0] != key:
                    self._job = (key, x.lat0, x.lon0, x.range_nm)
                if self._worker is None:
                    self._worker = threading.Thread(
                        target=self._worker_loop, name="map-airports",
                        daemon=True)
                    self._worker.start()
        if snap is None:
            return
        show_ident = x.range_nm <= _IDENT_RANGE
        # Symbol radius: ~9 px at 500 px width, clamped sane.
        r = max(6.0, min(14.0, x.w * 0.018))
        f = QFont(x.font_family)
        f.setPixelSize(max(8, int(x.w * 0.022)))
        p.setFont(f)
        for a in snap[1]:
            c = x.to_screen(a["lat"], a["lon"])
            if not (-r < c.x() < x.w + r and -r < c.y() < x.h + r):
                continue
            pen = QPen(MAGENTA)
            pen.setWidthF(max(1.2, r * 0.16))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            if a["hard"] and a["longest"] > 8069:
                self._runway_strips(p, x, a, r * 1.6)
            elif a["hard"]:
                p.drawEllipse(c, r, r)
                p.save()
                clip = QPainterPath()
                clip.addEllipse(c, r, r)
                p.setClipPath(clip)
                self._runway_strips(p, x, a, r)
                p.restore()
            else:
                p.drawEllipse(c, r, r)
            if show_ident and a["icao"]:
                p.setPen(QPen(QColor(255, 255, 255, 230)))
                p.drawText(
                    QRectF(c.x() - 60, c.y() + r + 1, 120,
                           f.pixelSize() + 4),
                    Qt.AlignmentFlag.AlignHCenter, a["icao"])

    def _runway_strips(self, p, x, a, half_len_px):
        """Runway strips at TRUE orientation: white fill, magenta edge,
        centred on the airport, length capped to the symbol scale."""
        c = x.to_screen(a["lat"], a["lon"])
        for (la1, lo1, la2, lo2) in a["rwys"]:
            e1 = x.to_screen(la1, lo1)
            e2 = x.to_screen(la2, lo2)
            dx, dy = e2.x() - e1.x(), e2.y() - e1.y()
            d = math.hypot(dx, dy)
            if d < 1e-3:
                continue
            ux, uy = dx / d, dy / d
            L = min(half_len_px, max(half_len_px * 0.55, d / 2.0))
            wpx = max(1.6, half_len_px * 0.22)
            p.save()
            p.translate(c)
            p.rotate(math.degrees(math.atan2(uy, ux)))
            p.setPen(QPen(MAGENTA, 1))
            p.setBrush(QBrush(QColor(255, 255, 255)))
            p.drawRect(QRectF(-L, -wpx / 2.0, 2 * L, wpx))
            p.restore()

    # --- worker -------------------------------------------------------------
    def _worker_loop(self):
        import time
        last = None
        while True:
            with self._lock:
                job = self._job
            if job is None or job == last:
                time.sleep(0.05)
                continue
            try:
                snap = self._collect(job)
                with self._lock:
                    if self._job == job:
                        self._snap = (job[0], snap)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "map airports collect failed")
                with self._lock:
                    if self._job == job:
                        self._job = None   # let the next paint re-request
            last = job
            try:
                self._owner.update()
            except RuntimeError:
                return

    def _collect(self, job):
        key, lat0, lon0, range_nm = job
        # Window covers the rotated view generously.
        radius = range_nm * 2.2
        hard_ids = {a.icao for a in
                    self._db_paved.airports_in_range(lat0, lon0, radius)}
        out = []
        for a in self._db_all.airports_in_range(lat0, lon0, radius):
            longest = max((r.length_ft for r in a.runways), default=0.0)
            out.append({
                "icao": a.icao, "lat": a.ref_lat, "lon": a.ref_lon,
                "longest": longest, "hard": a.icao in hard_ids,
                "rwys": [(r.thr1_lat, r.thr1_lon, r.thr2_lat, r.thr2_lon)
                         for r in a.runways][:4],
            })
        # Deterministic declutter: grid buckets (~1/8 of the range),
        # keep the two longest-runway airports per bucket.
        cell = max(2.0, range_nm / 4.0) / 60.0     # degrees
        buckets = {}
        for a in out:
            b = (round(a["lat"] / cell), round(a["lon"] / cell))
            buckets.setdefault(b, []).append(a)
        kept = []
        for b in buckets.values():
            b.sort(key=lambda a: -a["longest"])
            kept.extend(b[:2])
        return kept
