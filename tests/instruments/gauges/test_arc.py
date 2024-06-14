import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QPaintEvent
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

def test_arc_gauge(qtbot):
    widget = gauges.ArcGauge()
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
    assert widget.valueFontSize < 0.5
    assert widget.unitsFontSize < 0.4
    assert widget.nameFontSize < 10
    assert widget.nameFontSize > 9
    widget.name_location = 'right'
    widget.resizeEvent(None)
    assert widget.nameFontSize < 0.4
    # Switch to NUOK with aux data to check the bar colors
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    widget.paintEvent(None)

    # Many of these I'm not seeing what I could check with assert.
    # The paint event paints things based on settings
    # no global variables are set to check
    # segemnts

    #with mock.patch("PyQt5.QtGui.QPen") as patch_mock:
    widget.segments = 28
    #widget.paintEvent(None)
    #patch_mock.setWidth.assert_called_once()
    #patch_mock.setColor.assert_called_once_with(Qt.black)
    event = QPaintEvent(widget.rect())
    with track_calls(QPen, 'setColor') as tracker:
        widget.paintEvent(event)

    assert tracker.was_called_with('setColor', QColor(Qt.black))
    assert tracker.was_called_with('setColor', QColor(0, 0, 0, widget.segment_alpha))
    widget.name_font_ghost_mask = "0000"
    widget.paintEvent(None)

    widget.name_location = 'top'
    widget.paintEvent(None)

    widget.name_location = 'right'
    widget.name_font_mask = None
    widget.paintEvent(None)

    widget.show_units = True
    widget.paintEvent(None)

    widget.units_font_mask = None
    widget.paintEvent(None)

    widget.units_font_ghost_mask = "0000"
    widget.paintEvent(None)

    widget.font_ghost_mask = "0000"
    widget.paintEvent(None)

    return
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    widget.resize(201, 200)
    widget.font_mask = "0000"
    widget.units_font_mask = "00"
    widget.name_font_mask = "0000"
    widget.paintEvent(None)
    widget.name_font_ghost_mask = "0000"
    widget.paintEvent(None)
    widget.resize(300, 100)
    widget.name_location = 'right'
    widget.resize(301,100)
    widget.segments = 28
    widget.paintEvent(None)
    widget.name_font_mask = None
    widget.paintEvent(None)
    widget.setAuxData({"lowWarn": None})
    widget.paintEvent(None)
    #widget.setValue(15)
    #fix.db.set_value("NUMOK", 15.00)

    qtbot.wait(5000)

