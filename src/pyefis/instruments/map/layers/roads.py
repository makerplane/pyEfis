#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map roads layer -- major roads from the highways pack (the
#  same highways.sqlite the SVS reads, via HighwayDB).
#
#  Same contract as the terrain layer: a WORKER renders a NORTH-UP
#  transparent overlay image for the snapped window (oversized so
#  track-up rotation never shows edges); paint() only rotate-blits.
#  Rendering polylines per frame would cost tens of thousands of
#  Python->QPointF conversions at the frame clock rate -- the exact
#  per-vertex-Python failure mode of SVS #74 -- so all vertex work
#  happens once per window change, off the paint path.
#
#  LOD (docs/map_layers_roadmap.md section 1): the class set drawn scales
#  with range -- interstates alone when zoomed out, arterials added as you
#  zoom in. The class filter is pushed into the DB query so the worker only
#  fetches what it will draw. The rivers layer (#92) shares this machinery
#  and the highways sqlite schema -- it is just a subclass with its own
#  class bands + colour (map/layers/rivers.py).

import math
import threading

import numpy as np
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from pyefis.instruments.ai.camera import M_PER_DEG_LAT
from pyefis.instruments.map.layers import MapLayer, register_layer

#: per-window vertex budget (worker-side; metro windows are dense)
_MAX_VERTICES = 150000


def _with_links(bases):
    """Expand base road classes to include their ``_link`` ramps."""
    out = []
    for c in bases:
        out.append(c)
        out.append(c + "_link")
    return tuple(out)


@register_layer
class RoadsLayer(MapLayer):
    id = "roads"
    label = "Roads"
    z = 10
    default_on = True

    # --- config option names (subclasses point these elsewhere) ----------
    _DB_OPTION = "highway_db_path"
    _COLOR_OPTION = "road_color"
    _DEFAULT_COLOR = "#c0c0c0"

    # LOD bands: (max range NM, base classes drawn at/below it). Cumulative
    # and coarsest-last; above the last band the layer is hidden. Each base
    # class also matches its _link ramp. Keep in sync with
    # tools/build_highway_db.py PRESETS["roads"].
    _BAND_BASE = (
        (5.0, ("motorway", "trunk", "primary", "secondary")),
        (20.0, ("motorway", "trunk", "primary")),
        (40.0, ("motorway", "trunk")),
        (80.0, ("motorway",)),
    )
    #: base class -> pen tier (0 = boldest). Unknown classes fall to the
    #: thinnest tier.
    _TIER = {"motorway": 0, "trunk": 0, "primary": 1, "secondary": 2}
    #: tier -> (width px, alpha). Interstates boldest; arterials thin/faint.
    _TIER_PEN = {0: (1.8, 255), 1: (1.3, 220), 2: (1.0, 170)}
    #: roads carry _link ramps; waterway subclasses (rivers) do not.
    _EXPAND_LINKS = True

    #: metres of travel before the window re-anchors (hysteresis)
    _SNAP_FRAC = 0.15

    def __init__(self):
        super(RoadsLayer, self).__init__()
        self._db = None
        self._color = self._DEFAULT_COLOR
        self._img = None            # (QImage, key, meta)
        self._job = None
        self._worker = None
        self._lock = threading.Lock()

    def configure(self, owner):
        self._owner = owner
        self._color = str(getattr(owner, self._COLOR_OPTION, "")
                          or self._DEFAULT_COLOR)
        path = str(getattr(owner, self._DB_OPTION, "") or "")
        if path:
            try:
                from pyefis.instruments.ai.highway_db import HighwayDB
                self._db = HighwayDB(path)   # own connection, not the SVS's
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "map %s db unavailable", self.id)

    # --- LOD ---------------------------------------------------------------
    def _classes_for_range(self, range_nm):
        """fclass set to draw at ``range_nm`` (with _link ramps), or None
        when the layer is hidden (zoomed out past the coarsest band)."""
        for max_r, bases in self._BAND_BASE:
            if range_nm <= max_r:
                return _with_links(bases) if self._EXPAND_LINKS else tuple(bases)
        return None

    def _tier_for(self, fclass):
        base = (fclass or "")
        if base.endswith("_link"):
            base = base[:-5]
        return self._TIER.get(base, 2)

    # --- window key: snapped centre + range bucket (terrain pattern) -----
    def _key(self, x):
        span_m = x.range_nm * 1852.0 * 2.0
        snap = span_m * self._SNAP_FRAC
        return (round(x.lat0 * M_PER_DEG_LAT / snap),
                round(x.lon0 * M_PER_DEG_LAT / snap),
                round(x.range_nm, 2), round(x.w), round(x.h))

    def paint(self, p, x):
        if self._db is None or not self._db.ready \
                or self._classes_for_range(x.range_nm) is None:
            return
        key = self._key(x)
        with self._lock:
            img = self._img
            have = img is not None and img[1] == key
        if not have:
            self._request(key, x)
        if img is None:
            return
        qimg, _, (clat, clon, mpp) = img
        c = x.to_screen(clat, clon)
        p.save()
        p.translate(c)
        if x.rot:
            # north-up image onto an R(+rot) screen: painter -rot (#90)
            p.rotate(-math.degrees(x.rot))
        s = mpp * x._px_per_m
        w = qimg.width() * s
        h = qimg.height() * s
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(-w / 2.0, -h / 2.0, w, h), qimg)
        p.restore()

    # --- async build ------------------------------------------------------
    def _request(self, key, x):
        job = (key, x.lat0, x.lon0, x.range_nm, x.w, x.h, x.cy)
        with self._lock:
            # same-key reposts must not refresh the in-flight job (#89)
            if self._job is not None and self._job[0] == key:
                return
            self._job = job
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._worker_loop, name="map-" + self.id,
                    daemon=True)
                self._worker.start()

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
                img, meta = self._render(job)
                with self._lock:
                    if self._job == job:      # latest wins
                        self._img = (img, job[0], meta)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "map %s render failed", self.id)
                with self._lock:
                    if self._job == job:
                        self._job = None   # let the next paint re-request
            last = job
            try:
                self._owner.update()
            except RuntimeError:
                return                        # widget destroyed

    def _pens(self):
        """Build one QPen per tier from the layer colour (cached per render)."""
        pens = {}
        for tier, (width, alpha) in self._TIER_PEN.items():
            col = QColor(self._color)
            if not col.isValid():
                col = QColor(self._DEFAULT_COLOR)
            col.setAlpha(alpha)
            pen = QPen(col)
            pen.setWidthF(width)
            pens[tier] = pen
        return pens

    def _render(self, job):
        key, lat0, lon0, range_nm, w, h, cy = job
        # Same window geometry as the terrain layer, so the overlay
        # registers exactly with the relief underneath.
        px_per_m = max(1.0, cy) / max(1.0, range_nm * 1852.0)
        half_diag_m = 0.5 * math.hypot(w, h) / px_per_m * 1.25
        n = int(min(1024, max(64, 2 * half_diag_m * px_per_m)))
        mpp = 2 * half_diag_m / n
        lat_cos = math.cos(math.radians(lat0))
        half = (n - 1) / 2.0
        px_per_deg_lat = M_PER_DEG_LAT / mpp
        px_per_deg_lon = M_PER_DEG_LAT * lat_cos / mpp

        img = QImage(n, n, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pens = self._pens()

        classes = self._classes_for_range(range_nm)   # LOD-filtered fetch
        query_nm = half_diag_m / 1852.0
        budget = _MAX_VERTICES
        try:
            for line in self._db.polylines_in_range(lat0, lon0, query_nm,
                                                    classes=classes):
                v = line.vertices
                if budget <= 0:
                    break
                budget -= len(v)
                xs = (v[:, 1] - lon0) * px_per_deg_lon + half
                ys = (lat0 - v[:, 0]) * px_per_deg_lat + half
                # off-window polylines: bbox reject before QPointF cost
                if (xs.max() < 0 or xs.min() > n
                        or ys.max() < 0 or ys.min() > n):
                    continue
                p.setPen(pens[self._tier_for(line.fclass)])
                p.drawPolyline(QPolygonF(
                    [QPointF(float(a), float(b))
                     for a, b in zip(xs, ys)]))
        finally:
            p.end()
        return img, (lat0, lon0, mpp)
