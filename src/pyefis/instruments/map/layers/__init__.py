#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map layer-provider model (docs/moving_map_spec.md section 4).
#  Phase A ships the base contract + registry + the range-rings layer
#  (the provider-model proof). Terrain/airports/navaids follow in
#  phases B-D.

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPen

#: id -> layer class. Out-of-tree layers register here too.
LAYER_REGISTRY = {}


def register_layer(cls):
    LAYER_REGISTRY[cls.id] = cls
    return cls


class MapLayer:
    """One toggleable information layer.

    Contract (spec section 4): ``collect()`` runs on a worker thread,
    serialised with the SVS collectors; it must leave an immutable
    snapshot for ``paint()``, which runs on the GUI thread and may only
    blit/draw prepared data. Phase A layers are cheap enough to skip
    collect entirely.
    """

    id = "base"
    label = "Layer"
    z = 0
    default_on = True

    def __init__(self):
        self.enabled = self.default_on

    def configure(self, config):
        pass

    def collect(self, xform):
        pass

    def paint(self, painter, xform):
        raise NotImplementedError

    def on_toggle(self, on):
        self.enabled = on


@register_layer
class RangeRingsLayer(MapLayer):
    """Concentric rings at half and full range around ownship, with
    distance labels -- trivial by design: it proves the provider
    seam end to end (registry, config, toggle, paint contract)."""

    id = "range_rings"
    label = "Range rings"
    z = 20
    default_on = True

    def paint(self, p, x):
        pen = QPen(QColor(255, 255, 255, 140))
        pen.setWidthF(max(1.0, x.w * 0.002))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        f = QFont(x.font_family)
        f.setPixelSize(max(8, int(x.w * 0.025)))
        p.setFont(f)
        for frac in (0.5, 1.0):
            r_px = x.nm_to_px(x.range_nm * frac)
            p.drawEllipse(QPointF(x.cx, x.cy), r_px, r_px)
            lbl = ("%g" % (x.range_nm * frac))
            p.drawText(QRectF(x.cx + 4, x.cy - r_px, 80, f.pixelSize() + 6),
                       Qt.AlignmentFlag.AlignLeft, lbl)
