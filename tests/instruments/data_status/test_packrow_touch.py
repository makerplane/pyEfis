"""Tap-vs-scroll discrimination for the data-pack picker rows.

The pack-selection list lives on the eglfs touchscreen. A single-finger tap on a
row must toggle its checkbox; a two-finger scroll (which the driver delivers as a
synthesized pointer that drags across a row while the content scrolls) must NOT.
The row settles that by toggling on release only when the pointer barely moved.
"""

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QApplication, QCheckBox

from pyefis.instruments.data_status import _PackRow


@pytest.fixture
def app(qtbot):
    return QApplication.instance() or QApplication([])


class _Evt:
    """Minimal stand-in for QMouseEvent: the handlers only use position()/accept()."""
    def __init__(self, x, y):
        self._p = QPointF(x, y)

    def position(self):
        return self._p

    def accept(self):
        pass


def _row(app, qtbot, checked=False):
    cb = QCheckBox()
    cb.setChecked(checked)
    row = _PackRow(cb)
    qtbot.addWidget(row)
    return row, cb


def test_tap_toggles(app, qtbot):
    """Press and release on roughly the same spot = a tap = toggle."""
    row, cb = _row(app, qtbot, checked=False)
    row.mousePressEvent(_Evt(10, 10))
    row.mouseReleaseEvent(_Evt(12, 11))          # within _TAP_SLOP
    assert cb.isChecked() is True


def test_scroll_drag_does_not_toggle(app, qtbot):
    """A move past the slop (a scroll gesture) drops the press; release no-ops."""
    row, cb = _row(app, qtbot, checked=False)
    row.mousePressEvent(_Evt(10, 10))
    row.mouseMoveEvent(_Evt(10, 60))             # 50 px > _TAP_SLOP
    row.mouseReleaseEvent(_Evt(10, 62))
    assert cb.isChecked() is False               # unchanged


def test_release_far_without_move_event_does_not_toggle(app, qtbot):
    """Even with no intermediate move event, a release far from the press is a
    drag, not a tap, and must not flip the box."""
    row, cb = _row(app, qtbot, checked=True)
    row.mousePressEvent(_Evt(5, 5))
    row.mouseReleaseEvent(_Evt(45, 5))           # 40 px > _TAP_SLOP
    assert cb.isChecked() is True                # unchanged


def test_release_without_press_is_noop(app, qtbot):
    """A stray release (press was consumed elsewhere) must not toggle."""
    row, cb = _row(app, qtbot, checked=False)
    row.mouseReleaseEvent(_Evt(10, 10))
    assert cb.isChecked() is False
