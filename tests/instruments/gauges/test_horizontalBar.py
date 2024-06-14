import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, qRound
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPaintEvent, QFontMetrics
from pyefis.instruments import gauges
import pyavtools.fix as fix
import pyefis.hmi as hmi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_horizontal_bar_gauge(qtbot):
    widget = gauges.HorizontalBar()
    assert widget.getRatio() == 2
    widget.setDbkey("NUM")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resizeEvent(None)
    with track_calls(QFont, ["setPointSizeF", "setPixelSize"]) as tracker:
        widget.resizeEvent(None)
        assert tracker.was_not_called("setPointSizeF")
        widget.font_mask = "0000"
        widget.resizeEvent(None)
        assert tracker.was_called("setPointSizeF")
    widget.name_font_mask = "0000"
    widget.resizeEvent(None)
    widget.units_font_mask = "0000"
    widget.resizeEvent(None)

    with track_calls(QColor, "setAlpha") as tracker:
        widget.name_font_ghost_mask = "0000"
        widget.paintEvent(None)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)

    widget.show_units = True
    widget.name_font_ghost_mask = None
    widget.name_font_mask = None
    widget.font_mask = None
    with track_calls(QColor, "setAlpha") as tracker:
        widget.paintEvent(None)
        assert tracker.was_not_called("setAlpha")
        widget.units_font_ghost_mask = "0000"
        widget.paintEvent(None)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)

    widget.units_font_ghost_mask = None
    with track_calls(QColor, "setAlpha") as tracker:
        widget.paintEvent(None)
        assert tracker.was_not_called("setAlpha")
        widget.font_ghost_mask = "0000"
        widget.paintEvent(None)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    widget.paintEvent(None)

    widget.segments = 28
    with track_calls(QPen, "setColor") as tracker:
        widget.paintEvent(None)

    assert tracker.was_called_with("setColor", QColor(Qt.black))
