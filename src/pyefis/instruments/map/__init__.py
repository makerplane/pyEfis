#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map instrument -- Phase A skeleton (docs/moving_map_spec.md).
#  Top-down view: MapTransform owns ALL world->screen math, layers from
#  the provider registry paint in z order, ownship rides a configurable
#  screen anchor. Plain QWidget/QPainter: renders offscreen, no GL.

import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QPinchGesture, QWidget

import pyavtools.fix as fix

from pyefis.instruments.ai.camera import M_PER_DEG_LAT
from pyefis.instruments.map import layers as map_layers
from pyefis.instruments.live_binding import LiveBind, LiveBindingMixin

NM_M = 1852.0


class MapTransform:
    """World (lat/lon) -> screen (px). Local azimuthal-equidistant about
    the ownship position; rotation = track when track_up. The ONE owner
    of projection math -- layers never do their own (spec section 3)."""

    def __init__(self, lat, lon, range_nm, rot_deg, w, h, anchor_frac,
                 font_family="DejaVu Sans Condensed"):
        self.lat0, self.lon0 = lat, lon
        self.range_nm = range_nm
        self.rot = math.radians(rot_deg)
        self.w, self.h = w, h
        self.cx = w / 2.0
        self.cy = h * (1.0 - anchor_frac)   # ownship anchor (% up from bottom)
        self.font_family = font_family
        # range_nm = ownship anchor -> top edge
        self._px_per_m = max(1.0, self.cy) / max(1.0, range_nm * NM_M)
        self._coslat = math.cos(math.radians(lat))

    def nm_to_px(self, nm):
        return nm * NM_M * self._px_per_m

    def to_screen(self, lat, lon):
        de = (lon - self.lon0) * M_PER_DEG_LAT * self._coslat
        dn = (lat - self.lat0) * M_PER_DEG_LAT
        if self.rot:
            c, s = math.cos(self.rot), math.sin(self.rot)
            de, dn = de * c - dn * s, de * s + dn * c
        return QPointF(self.cx + de * self._px_per_m,
                       self.cy - dn * self._px_per_m)


class MovingMap(LiveBindingMixin, QWidget):
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(MovingMap, self).__init__(parent)
        self.setStyleSheet("background: transparent; border: 0px")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Touch input: pinch to zoom the range (two-finger drag to pan is Phase
        # 2). A single PinchGesture reports both scaleFactor and centerPoint, so
        # one handler covers both. Grab it unconditionally; the handler honours
        # the touch_gestures option (set later by the screenbuilder).
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.font_family = font_family
        # Options (screenbuilder setattrs; defaults per the spec):
        self.range_nm = 10.0
        self.range_ladder = "2,5,10,20,40,80,160"
        self.orientation = "track_up"          # or "north_up"
        self.touch_gestures = True             # pinch-zoom / two-finger pan
        self.ownship_position = 50             # percent up from bottom
        self.symbol_color = "yellow"
        self.layer_range_rings = True
        self.layer_terrain = True
        self.tile_path = ""                    # GLO-30/SRTM HGT tree
        self.terrain_mode = "relief"           # or "caution"
        self.water_db_path = ""                # water.sqlite (#91)
        self.water_max_vertices = 512          # per-polygon raster cap
        self.layer_roads = True
        self.highway_db_path = ""              # highways.sqlite (SVS pack)
        self.road_color = "#c0c0c0"
        self.layer_rivers = True
        self.river_db_path = ""                # rivers.sqlite (highways schema, #92)
        self.river_color = "#4a6d8c"
        self.layer_airports = True
        self.nasr_db_path = ""                 # NASR airports.sqlite
        self.layer_navaids = True
        self.layer_fixes = False
        self.layer_airways = False
        self.navaid_db_path = ""               # navaids.sqlite (Phase D)
        # Control-binding keys (control_bindings.md): when an <x>_key option
        # names a FIX key, a control (button/knob) drives that setting at
        # runtime. Empty = the setting stays a static config option.
        self.range_key = ""
        self.orientation_key = ""
        self._layers = []
        self._layers_built = False

        self._lat = self._lon = 0.0
        self._track = 0.0
        self._alt_ft = 0.0
        self._old = {}
        # Frame clock (#89, mirrors the AI's P4 pattern): inputs only
        # store values; the clock repaints at a bounded rate and only
        # when the pose moved enough to change pixels. X-Plane/GPS can
        # deliver LAT/LONG/TRACKM/ALT at tens of Hz each -- routing
        # every update through QWidget.update() repainted the whole
        # map (rotated terrain blit included) at the data rate.
        self._frame_rate = 10.0
        self._frame_last_pose = None
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._frame_tick)
        self._frame_timer.start(int(round(1000.0 / self._frame_rate)))
        for key, attr in (("LAT", "_lat"), ("LONG", "_lon"),
                          ("TRACKM", "_track"), ("ALT", "_alt_ft")):
            try:
                item = fix.db.get_item(key)
                item.valueChanged[float].connect(
                    lambda v, a=attr: setattr(self, a, v))
                item.oldChanged[bool].connect(
                    lambda o, k=key: (self._old.__setitem__(k, o),
                                      self.update()))
                setattr(self, attr, item.value)
                self._old[key] = item.old
            except KeyError:
                # Graceful missing-key pattern: run with what exists.
                self._old[key] = True

    # --- frame clock (#89) --------------------------------------------------
    @property
    def frame_rate(self):
        return self._frame_rate

    @frame_rate.setter
    def frame_rate(self, fps):
        """Screenbuilder option: map repaint clock in Hz (clamped 1-30)."""
        self._frame_rate = max(1.0, min(30.0, float(fps)))
        self._frame_timer.start(int(round(1000.0 / self._frame_rate)))

    def _frame_tick(self):
        """Repaint at most at the clock rate, and only when the pose
        changed enough to move pixels: position by ~half a screen px,
        track by 0.25 deg (rotation), altitude by 100 ft (caution
        tint). Explicit UI actions (range, orientation, layer toggles)
        and async layer completions still call update() directly."""
        if not self.isVisible():
            return
        m_per_px = (float(self.range_nm) * NM_M) / max(1.0, self.height() / 2.0)
        q = max(1e-7, (0.5 * m_per_px) / M_PER_DEG_LAT)  # deg per half-px
        pose = (round(self._lat / q), round(self._lon / q),
                round(self._track * 4.0), round(self._alt_ft / 100.0),
                self.orientation, float(self.range_nm))
        if pose == self._frame_last_pose:
            return
        self._frame_last_pose = pose
        self.update()

    # --- layer plumbing ---------------------------------------------------
    def _build_layers(self):
        from pyefis.instruments.map.layers import airports  # noqa: F401
        from pyefis.instruments.map.layers import navaids  # noqa: F401
        from pyefis.instruments.map.layers import rivers  # noqa: F401
        from pyefis.instruments.map.layers import roads  # noqa: F401
        from pyefis.instruments.map.layers import terrain  # noqa: F401
        self._layers = []
        for lid, cls in sorted(map_layers.LAYER_REGISTRY.items(),
                               key=lambda kv: kv[1].z):
            layer = cls()
            layer.enabled = bool(getattr(self, "layer_" + lid,
                                         cls.default_on))
            layer.configure(self)
            self._layers.append(layer)
        self._layers_built = True

    def set_layer(self, layer_id, on=None):
        """HMI hook: toggle (or set) a layer at runtime."""
        for layer in self._layers:
            if layer.id == layer_id:
                layer.on_toggle((not layer.enabled) if on is None else on)
                self.update()
                return True
        return False

    # --- HMI hooks (bound to buttons/encoder in screen YAML later) --------
    def _ladder(self):
        try:
            vals = [float(v) for v in str(self.range_ladder).split(",") if v]
            return vals or [10.0]
        except ValueError:
            return [10.0]

    def range_up(self):
        lad = self._ladder()
        self.range_nm = next((v for v in lad if v > self.range_nm), lad[-1])
        self.update()

    def range_down(self):
        lad = self._ladder()
        self.range_nm = next((v for v in reversed(lad)
                              if v < self.range_nm), lad[0])
        self.update()

    def _live_binding_specs(self):
        """Runtime control bindings (control_bindings.md). Each fires only if its
        ``<x>_key`` option names a FIX key; otherwise the setting stays static.
        range = index over the ladder, orientation = enum index -- both plain
        attributes the frame timer already polls, so applying them from the
        (non-GUI) FIX thread is safe.

        Layer bindings (e.g. terrain via set_layer) are DEFERRED: toggling a live
        layer is a Qt call that must run on the GUI thread, which needs marshaling
        the FIX callback across threads. See control_bindings.md / #96."""
        return [
            LiveBind("range_nm", "index_ladder", "range_key",
                     ladder_option="range_ladder"),
            LiveBind("orientation", "enum", "orientation_key",
                     enum=("track_up", "north_up")),
        ]

    def toggle_orientation(self):
        self.orientation = ("north_up" if self.orientation == "track_up"
                            else "track_up")
        self.update()

    # --- touch / pointer zoom ---------------------------------------------
    def _range_bounds(self):
        lad = self._ladder()
        return min(lad), max(lad)

    def zoom_by(self, factor):
        """Scale the view continuously by ``factor`` (>1 = zoom IN = smaller
        ``range_nm``). Pinch-spread and wheel-up both zoom in. Clamped to the
        range-ladder span; ``range_up``/``range_down`` still do the discrete
        button/knob stepping. Returns the new range."""
        try:
            factor = float(factor)
        except (TypeError, ValueError):
            return self.range_nm
        if factor <= 0.0:
            return self.range_nm
        lo, hi = self._range_bounds()
        self.range_nm = max(lo, min(hi, float(self.range_nm) / factor))
        self.update()
        return self.range_nm

    def event(self, e):
        if (e.type() == QEvent.Type.Gesture
                and getattr(self, "touch_gestures", True)):
            g = e.gesture(Qt.GestureType.PinchGesture)
            if g is not None:
                cf = QPinchGesture.ChangeFlag.ScaleFactorChanged
                if g.changeFlags() & cf:
                    self.zoom_by(g.scaleFactor())
                # two-finger drag (g.centerPoint() delta) -> pan: Phase 2
                return True
        return super().event(e)

    def wheelEvent(self, e):
        """Desktop / configurator zoom, mirroring pinch (wheel-up = zoom in).
        One notch (120 eighths-of-a-degree) = 1.25x."""
        if getattr(self, "touch_gestures", True):
            dy = e.angleDelta().y()
            if dy:
                self.zoom_by(1.25 ** (dy / 120.0))
        e.accept()

    # --- painting ----------------------------------------------------------
    def _transform(self):
        rot = self._track if self.orientation == "track_up" else 0.0
        anchor = max(0.0, min(100.0,
                              float(self.ownship_position))) / 100.0
        return MapTransform(self._lat, self._lon, float(self.range_nm),
                            rot, self.width(), self.height(), anchor,
                            self.font_family)

    def paintEvent(self, event):
        if not self._layers_built:
            self._build_layers()
            # Options are applied by now; wire runtime control bindings once, but
            # DEFER out of the paint. Binding init writes the seed values (FIX
            # emissions) and can touch layers; doing that inside paintEvent risks
            # re-entering the painter. singleShot(0) runs it after this paint.
            QTimer.singleShot(0, self._init_live_bindings_once)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(16, 24, 32))
        x = self._transform()
        for layer in self._layers:
            if layer.enabled:
                p.save()
                layer.paint(p, x)
                p.restore()

        # Ownship: top-down aircraft arrow at the anchor, up = track
        # (track_up) or rotated to track (north_up).
        stale = self._old.get("LAT", True) or self._old.get("LONG", True)
        col = QColor(Qt.GlobalColor.gray) if stale \
            else QColor(self.symbol_color)
        if not col.isValid():
            col = QColor(Qt.GlobalColor.yellow)
        s = max(8.0, self.width() * 0.025)
        p.save()
        p.translate(x.cx, x.cy)
        if self.orientation == "north_up":
            p.rotate(self._track)
        p.setPen(QPen(QColor(Qt.GlobalColor.black), 1))
        p.setBrush(QBrush(col))
        p.drawPolygon(QPolygonF([
            QPointF(0, -s), QPointF(s * 0.6, s * 0.8),
            QPointF(0, s * 0.35), QPointF(-s * 0.6, s * 0.8)]))
        p.restore()

        # Status chip: range + orientation (+ NO POS when stale).
        f = QFont(self.font_family)
        f.setPixelSize(max(9, int(self.width() * 0.03)))
        p.setFont(f)
        p.setPen(QPen(QColor(255, 255, 255, 200)))
        mode = "TRK UP" if self.orientation == "track_up" else "NORTH UP"
        chip = "%g NM  %s" % (float(self.range_nm), mode)
        if stale:
            chip += "  NO POS"
        p.drawText(QRectF(6, 4, self.width() - 12, f.pixelSize() + 6),
                   Qt.AlignmentFlag.AlignLeft, chip)

    def _init_live_bindings_once(self):
        self.init_live_bindings(self._live_binding_specs())
