#  SPDX-License-Identifier: GPL-2.0-or-later
"""Edge-fade helper (#93): the cached-strip fast path must match the
reference per-frame render, reuse its cache across paints, and drop it
when the scene is rebuilt."""
import numpy as np
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter

from pyefis.instruments import helpers


def _reference_render(view, fade_percent):
    """The pre-#93 per-frame implementation, kept verbatim as the
    correctness oracle."""
    vp = view.viewport()
    f = max(0.0, min(45.0, float(fade_percent))) / 100.0
    img = QImage(vp.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.scene.render(
        p, QRectF(0, 0, img.width(), img.height()),
        view.mapToScene(vp.rect()).boundingRect())
    grad = QLinearGradient(0, 0, 0, img.height())
    grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    grad.setColorAt(f, QColor(0, 0, 0, 255))
    grad.setColorAt(1.0 - f, QColor(0, 0, 0, 255))
    grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.fillRect(img.rect(), grad)
    p.end()
    return img


def _to_np(img):
    b = img.constBits()
    b.setsize(img.sizeInBytes())
    a = np.frombuffer(b, np.uint8).reshape(
        img.height(), img.bytesPerLine() // 4, 4)
    return a[:, :img.width(), :].astype(np.int16)


def _tape(qtbot):
    from pyefis.instruments import airspeed
    a = airspeed.Airspeed_Tape()
    a.edge_fade = True
    qtbot.addWidget(a)
    a.resize(120, 600)
    a.show()
    qtbot.waitExposed(a)
    return a


def test_edge_fade_matches_reference(fix, qtbot):
    a = _tape(qtbot)
    for v in (40.0, 87.3, 121.0, 155.5):
        a.setAirspeed(v)
        ref = _to_np(_reference_render(a, 15.0))
        helpers.render_view_edge_faded(a, 15.0)
        new = _to_np(a._edge_fade_buf)
        assert ref.shape == new.shape
        assert float(np.abs(ref - new).mean()) < 2.0
        # top/bottom rows are actually faded out
        assert new[0, :, 3].max() < 40
        assert new[-1, :, 3].max() < 40


def test_edge_fade_strip_cache_reused_and_invalidated(fix, qtbot):
    from PyQt6.QtWidgets import QGraphicsScene

    a = _tape(qtbot)
    a.setAirspeed(100.0)
    helpers.render_view_edge_faded(a, 15.0)
    strip1 = a._edge_fade_strip[2]
    a.setAirspeed(101.0)
    helpers.render_view_edge_faded(a, 15.0)
    assert a._edge_fade_strip[2] is strip1     # scrolling reuses the strip
    # Simulate what resizeEvent does: replace the scene wholesale (the
    # tapes never mutate scene items in place). Same-geometry rebuilds
    # must still invalidate -- the cache compares scene identity.
    old = a.scene
    r = old.sceneRect()
    a.scene = QGraphicsScene(r.x(), r.y(), r.width(), r.height())
    helpers.render_view_edge_faded(a, 15.0)
    assert a._edge_fade_strip[2] is not strip1  # rebuild invalidates
    assert old is not a._edge_fade_strip[0]
