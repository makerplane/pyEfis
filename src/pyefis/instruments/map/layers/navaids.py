#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map navaid / fix / airway layers (spec 5.3, Phase D).
#
#  Reads navaids.sqlite (tools/build_navaid_db.py from NASR NAV/FIX/
#  AWY). Sectional-style symbols: VOR family = compass-rose hexagon
#  with a centre dot (VORTAC/VOR-DME share it v1), NDB = stippled
#  disc, fixes = open triangles, airways = light blue lines with the
#  ident at segment midpoints. Same async snapshot contract as the
#  other layers. Defaults per the spec: navaids on, airways off,
#  fixes off (70k fixes need range-gating, <=20 NM only).

import math
import sqlite3
import threading

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF

from pyefis.instruments.map.layers import MapLayer, register_layer

BLUE = QColor(70, 110, 200)
DARKBLUE = QColor(40, 60, 130)


class _DbLayer(MapLayer):
    """Shared windowed-sqlite snapshot machinery."""

    _SNAP_FRAC = 0.25

    def __init__(self):
        super(_DbLayer, self).__init__()
        self._path = ""
        self._snap = None
        self._job = None
        self._worker = None
        self._lock = threading.Lock()

    def configure(self, owner):
        self._owner = owner
        self._path = str(getattr(owner, "navaid_db_path", "") or "")

    def _key(self, x):
        snap = max(1.0, x.range_nm * self._SNAP_FRAC)
        return (round(x.lat0 * 60.0 / snap), round(x.lon0 * 60.0 / snap),
                round(x.range_nm, 1))

    def _snapshot(self, x, max_range):
        if not self._path or x.range_nm > max_range:
            return None
        key = self._key(x)
        with self._lock:
            snap = self._snap
            if snap is not None and snap[0] == key:
                return snap[1]
            # Don't refresh an in-flight job for the same window: the
            # tuple carries the raw pose, so a same-key repost makes
            # the worker's latest-wins check discard the finished
            # snapshot every time the aircraft is moving (#89).
            if self._job is None or self._job[0] != key:
                self._job = (key, x.lat0, x.lon0, x.range_nm)
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._worker_loop,
                    name="map-" + self.id, daemon=True)
                self._worker.start()
        return snap[1] if snap else None

    def _worker_loop(self):
        import time
        last = None
        con = None
        while True:
            with self._lock:
                job = self._job
            if job is None or job == last:
                time.sleep(0.05)
                continue
            try:
                if con is None:
                    con = sqlite3.connect(self._path)
                rows = self._query(con, *job[1:])
                with self._lock:
                    if self._job == job:
                        self._snap = (job[0], rows)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "map %s collect failed", self.id)
                with self._lock:
                    if self._job == job:
                        self._job = None   # let the next paint re-request
            last = job
            try:
                self._owner.update()
            except RuntimeError:
                return

    @staticmethod
    def _bbox(lat0, lon0, range_nm):
        d = range_nm * 2.2 / 60.0
        dl = d / max(0.2, math.cos(math.radians(lat0)))
        return lat0 - d, lat0 + d, lon0 - dl, lon0 + dl


@register_layer
class NavaidsLayer(_DbLayer):
    id = "navaids"
    label = "Navaids"
    z = 40
    default_on = True

    def _query(self, con, lat0, lon0, range_nm):
        a, b, c, d = self._bbox(lat0, lon0, range_nm)
        return con.execute(
            "SELECT id, type, freq, lat, lon FROM navaids "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (a, b, c, d)).fetchall()

    def paint(self, p, x):
        rows = self._snapshot(x, 160.0)
        if not rows:
            return
        r = max(5.0, min(12.0, x.w * 0.014))
        f = QFont(x.font_family)
        f.setPixelSize(max(8, int(x.w * 0.022)))
        p.setFont(f)
        show_freq = x.range_nm <= 40
        for nid, ntype, freq, lat, lon in rows:
            c = x.to_screen(lat, lon)
            if not (-r < c.x() < x.w + r and -r < c.y() < x.h + r):
                continue
            pen = QPen(BLUE)
            pen.setWidthF(max(1.2, r * 0.18))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            t = (ntype or "").upper()
            if "NDB" in t:
                p.setPen(QPen(BLUE, 1))
                for ring, npts in ((r * 0.55, 8), (r, 12)):
                    for i in range(npts):
                        ang = 2 * math.pi * i / npts
                        p.drawEllipse(
                            QPointF(c.x() + ring * math.cos(ang),
                                    c.y() + ring * math.sin(ang)),
                            r * 0.07, r * 0.07)
                p.setBrush(QBrush(BLUE))
                p.drawEllipse(c, r * 0.14, r * 0.14)
            else:
                # VOR family: hexagon + centre dot.
                hexa = QPolygonF([
                    QPointF(c.x() + r * math.cos(math.radians(a2)),
                            c.y() + r * math.sin(math.radians(a2)))
                    for a2 in range(0, 360, 60)])
                p.drawPolygon(hexa)
                p.setBrush(QBrush(BLUE))
                p.drawEllipse(c, r * 0.14, r * 0.14)
            label = nid + ((" " + freq) if (show_freq and freq) else "")
            p.setPen(QPen(QColor(220, 230, 255)))
            p.drawText(QRectF(c.x() - 70, c.y() + r + 1, 140,
                              f.pixelSize() + 4),
                       Qt.AlignmentFlag.AlignHCenter, label)


@register_layer
class FixesLayer(_DbLayer):
    id = "fixes"
    label = "Waypoints"
    z = 38
    default_on = False

    def _query(self, con, lat0, lon0, range_nm):
        a, b, c, d = self._bbox(lat0, lon0, range_nm)
        return con.execute(
            "SELECT id, lat, lon FROM fixes "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? "
            "LIMIT 400", (a, b, c, d)).fetchall()

    def paint(self, p, x):
        rows = self._snapshot(x, 20.0)     # range-gated: fixes are dense
        if not rows:
            return
        s = max(3.0, x.w * 0.008)
        f = QFont(x.font_family)
        f.setPixelSize(max(7, int(x.w * 0.018)))
        p.setFont(f)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for fid, lat, lon in rows:
            c = x.to_screen(lat, lon)
            if not (0 < c.x() < x.w and 0 < c.y() < x.h):
                continue
            p.setPen(QPen(DARKBLUE, 1.2))
            p.drawPolygon(QPolygonF([
                QPointF(c.x(), c.y() - s),
                QPointF(c.x() + s * 0.87, c.y() + s * 0.5),
                QPointF(c.x() - s * 0.87, c.y() + s * 0.5)]))
            p.setPen(QPen(QColor(200, 210, 235, 220)))
            p.drawText(QRectF(c.x() - 50, c.y() + s + 1, 100,
                              f.pixelSize() + 4),
                       Qt.AlignmentFlag.AlignHCenter, fid)


@register_layer
class AirwaysLayer(_DbLayer):
    id = "airways"
    label = "Airways"
    z = 25
    default_on = False

    def _query(self, con, lat0, lon0, range_nm):
        a, b, c, d = self._bbox(lat0, lon0, range_nm)
        return con.execute(
            "SELECT awy_id, lat1, lon1, lat2, lon2 FROM awy_segments "
            "WHERE (lat1 BETWEEN ? AND ? AND lon1 BETWEEN ? AND ?) "
            "   OR (lat2 BETWEEN ? AND ? AND lon2 BETWEEN ? AND ?)",
            (a, b, c, d, a, b, c, d)).fetchall()

    def paint(self, p, x):
        rows = self._snapshot(x, 160.0)
        if not rows:
            return
        pen = QPen(QColor(90, 130, 210, 170))
        pen.setWidthF(max(1.0, x.w * 0.003))
        f = QFont(x.font_family)
        f.setPixelSize(max(7, int(x.w * 0.018)))
        p.setFont(f)
        labelled = set()
        for awy, la1, lo1, la2, lo2 in rows:
            p.setPen(pen)
            e1 = x.to_screen(la1, lo1)
            e2 = x.to_screen(la2, lo2)
            p.drawLine(e1, e2)
            if awy not in labelled and x.range_nm <= 80:
                labelled.add(awy)
                mx, my = (e1.x() + e2.x()) / 2, (e1.y() + e2.y()) / 2
                if 0 < mx < x.w and 0 < my < x.h:
                    p.setPen(QPen(QColor(150, 180, 240)))
                    p.drawText(QRectF(mx - 30, my - f.pixelSize() - 2,
                                      60, f.pixelSize() + 4),
                               Qt.AlignmentFlag.AlignHCenter, awy)
