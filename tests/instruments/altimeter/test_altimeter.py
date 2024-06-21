import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, qRound
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPaintEvent, QFontMetrics
from PyQt5 import QtGui
from pyefis.instruments import altimeter
import pyefis.hmi as hmi
from tests.utils import track_calls

funcAltitudeMeters = lambda x: x / 3.28084 
funcAltitudeFeet = lambda x: x             


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_altimeter(fix,qtbot):
    widget = altimeter.Altimeter()
    assert widget.getRatio() == 1
    qtbot.addWidget(widget)
    assert widget.item.value == 0
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    with track_calls(QPen, "setColor") as tracker:
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.white))
        fix.db.get_item("ALT").bad = True
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.gray))
        fix.db.get_item("ALT").bad = False
        fix.db.get_item("ALT").old = True
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.gray))
        fix.db.get_item("ALT").old = False
        fix.db.get_item("ALT").fail = True
        with track_calls(QPainter, "setBrush") as tracker2:
            widget.paintEvent(None)
            assert tracker2.was_called_with("setBrush",QBrush(QColor(Qt.red)))

def test_altimeter_unit_switching(fix,qtbot):
    hmi.initialize({})
    widget = altimeter.Altimeter()
    qtbot.addWidget(widget)
    assert widget.conversionFunction1(100) == 100
    assert widget.conversionFunction2(100) == 100
    assert widget.conversionFunction(100) == 100

    widget.conversionFunction1 = funcAltitudeFeet
    widget.unitsOverride1 = 'Ft'
    widget.conversionFunction2 = funcAltitudeMeters
    widget.unitsOverride2 = 'M'
    widget.unitGroup = 'Altitude'
    widget.setUnitSwitching()
    fix.db.get_item("ALT").value = 1100
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.paintEvent(None)
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    widget.paintEvent(None)
    assert widget._altimeter != 1100
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    assert widget._altimeter == 1100
    # Test branches that should do nothing:
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggl")
    hmi.actions.trigger("Set Instrument Units","IAS:Toggle")

    assert widget.getAltimeter() == 1100


def test_altimeter_tape(fix,qtbot):
    widget = altimeter.Altimeter_Tape()
    widget.redraw()
    qtbot.addWidget(widget)
    assert widget.item.value == 0
    assert widget.pph == 0.3
    widget = altimeter.Altimeter_Tape(font_percent=0.5)
    qtbot.addWidget(widget)
    assert widget.pph != 0.3
    widget.resize(100,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.font_mask = None
    widget.resize(90,200)
    #widget.paintEvent(None)


def test_altimeter_tape_unit_switching(fix,qtbot):
    hmi.initialize({})
    widget = altimeter.Altimeter_Tape()
    qtbot.addWidget(widget)
    assert widget.conversionFunction1(100) == 100
    assert widget.conversionFunction2(100) == 100
    assert widget.conversionFunction(100) == 100

    widget.conversionFunction1 = funcAltitudeFeet
    widget.unitsOverride1 = 'Ft'
    widget.conversionFunction2 = funcAltitudeMeters
    widget.unitsOverride2 = 'M'
    widget.unitGroup = 'Altitude'
    fix.db.get_item("ALT").value = 1100
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.setUnitSwitching()
    event = QPaintEvent(widget.rect())
    widget.paintEvent(event)
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    widget.paintEvent(event)
    assert widget._altimeter != 1100
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    assert widget._altimeter == 1100
    # Test branches that should do nothing:
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggl")
    hmi.actions.trigger("Set Instrument Units","IAS:Toggle")

    assert widget.getAltimeter() == 1100
    widget.paintEvent(event)
    widget.setUnitSwitching()
    widget.keyPressEvent(None)
    widget.wheelEvent(None)
    widget.hide()
    widget.setUnitSwitching()
