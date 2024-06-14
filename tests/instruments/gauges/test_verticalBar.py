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


def test_vertical_bar_gauge(qtbot):
    widget = gauges.VerticalBar()
    assert widget.getRatio() == 0.35
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
    widget.setNormalizeMode(True)
    assert widget._normalizeMode == True
    assert widget.penGoodColor == widget.normalizePenColor
    widget.setNormalizeMode(True)
    assert widget.penGoodColor == widget.normalizePenColor
    widget.setNormalizeMode(False)
    assert widget._normalizeMode == False
    widget.setPeakMode(True)
    assert widget._peakMode == True
    widget.setPeakMode(False)
    assert widget._peakMode == False
    mode = widget._normalizeMode
    widget.setMode("normalize")
    assert widget.normalizeMode != mode
    widget.setMode("normalize")
    assert widget.normalizeMode == mode
    mode = widget._peakMode
    widget.setMode("peak")
    assert widget.peakMode != mode
    widget.setMode("peak")
    assert widget.peakMode == mode
    widget.setMode("reset peak")
    assert widget.peakValue == widget.value
    widget.setMode("lean")
    assert widget.peakValue == widget.value
    assert widget.normalizeMode == True
    assert widget.peakMode == True
    widget.setMode("normal")
    assert widget.normalizeMode == False
    assert widget.peakMode == False
    assert widget.barTop != 1
    widget.show_name = False
    widget.resizeEvent(None)
    assert widget.barTop == 1
    widget.highlight_key = "NUM"
    widget.setupGauge()
    widget.paintEvent(None)
    assert widget.highlight == False
    widget.highlight_key = "NUMOK"
    widget.setupGauge()
    widget.paintEvent(None)
    assert widget.highlight == True
    widget.setPeakMode(True)
    widget.peakValue = 200
    with track_calls(QPen, "setColor") as tracker:
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor", widget.peakColor)
    with track_calls(QPen, "setColor") as tracker:
        widget.peakValue = widget.value
        widget.paintEvent(None)
        assert tracker.was_not_called_with("setColor", widget.peakColor)
    widget.units_font_mask = None
    widget.paintEvent(None)
    widget.setMode("normalize")
    widget.paintEvent(None)
    widget.normalize_range = 400
    widget.paintEvent(None)
