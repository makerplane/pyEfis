import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import gauges
import pyefis.hmi as hmi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_arc_gauge(fix,qtbot):
    widget = gauges.ArcGauge(min_size=True)
    assert widget.getRatio() == 2

    # Test with no aux data first
    widget.setDbkey("NUM")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.paintEvent(None)
    assert widget._dbkey == "NUM"
    assert widget.isVisible()
    assert widget._units == "°C"
    widget.resize(200, 220)
    widget.resizeEvent(None)
    assert widget.tlcx == 0
    assert widget.tlcy == 60
    widget.resize(400, 100)
    widget.resizeEvent(None)
    assert widget.tlcx == 100
    assert widget.tlcy == 00
    assert int(widget.valueFontSize) == 33
    assert int(widget.unitsFontSize) == 25
    assert int(widget.nameFontSize) == 17
    widget.font_mask = "00"
    widget.units_font_mask = "00"
    widget.name_font_mask = "0000"
    widget.resizeEvent(None)
    assert widget.valueFontSize != 33
    assert widget.unitsFontSize != 25
    assert widget.nameFontSize != 17
    widget.name_location = "right"
    widget.resizeEvent(None)
    # Switch to NUOK with aux data to check the bar colors
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    widget.paintEvent(None)

    widget.segments = 28
    with track_calls(QPen, "setColor") as tracker:
        widget.paintEvent(None)

    assert tracker.was_called_with("setColor", QColor(Qt.black))
    assert tracker.was_called_with("setColor", QColor(0, 0, 0, widget.segment_alpha))

    widget.name_font_ghost_mask = "0000"
    with track_calls(QFontMetrics, "width") as tracker:
        with track_calls(QColor, "setAlpha") as tracker2:
            widget.paintEvent(None)

    assert tracker.was_called_with("width", "0000")
    assert tracker2.was_called_with("setAlpha", widget.font_ghost_alpha)
    widget.name_location = "top"
    widget.paintEvent(None)

    widget.name_location = "right"
    widget.name_font_mask = None
    widget.paintEvent(None)

    widget.show_units = True
    widget.paintEvent(None)

    # widget.units_font_mask = None
    with track_calls(QFontMetrics, "width") as tracker:
        widget.paintEvent(None)
        assert tracker.was_called_with("width", widget.units_font_mask)
        widget.units_font_mask = None
        widget.paintEvent(None)
        assert tracker.was_called_with("width", widget.units)

        with track_calls(QColor, "setAlpha") as tracker2:
            widget.units_font_ghost_mask = "0000"
            widget.paintEvent(None)
            assert tracker2.was_called_with("setAlpha", widget.font_ghost_alpha)
            widget.units_font_ghost_mask = None
            widget.font_ghost_mask = "0000"
            widget.paintEvent(None)
            assert tracker2.was_called_with("setAlpha", widget.font_ghost_alpha)


def test_arc_gauge_branches(fix,qtbot):
    widget = gauges.ArcGauge(min_size=False)
    assert widget.getRatio() == 2

    # Test with no aux data first
    widget.setDbkey("NUM")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.name_location = 'top'
    widget.name_font_mask = 'XXXX'
    widget.resize(100, 101)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(2000)
