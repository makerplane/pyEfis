import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from pyefis.instruments import airspeed  # import Airspeed, Airspeed_Tape, Airspeed_Box
import pyavtools.fix as fix
import pyefis.hmi as hmi


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_numerical_airspeed(qtbot):
    fix.db.get_item("IAS").set_aux_value("Vs", 45.0)
    fix.db.get_item("IAS").set_aux_value("Vs0", 40.0)
    fix.db.get_item("IAS").set_aux_value("Vno", 125.0)
    fix.db.get_item("IAS").set_aux_value("Vne", 140.0)
    fix.db.get_item("IAS").set_aux_value("Vfe", 70.0)
    fix.db.set_value("IAS", "100")
    widget = airspeed.Airspeed()
    assert widget.getRatio() == 1
    qtbot.addWidget(widget)
    widget.resize(201, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(500)
    assert widget.item.key == "IAS"
    assert widget.Vs == 45
    fix.db.get_item("IAS").fail = True
    fix.db.get_item("IAS").fail = False
    fix.db.get_item("IAS").old = True
    fix.db.get_item("IAS").old = False
    fix.db.set_value("IAS", "20")
    widget.setAsOld(True)
    widget.setAsBad(True)
    widget.setAsFail(True)
    assert widget.getAirspeed() == 20
    qtbot.wait(200)


def test_numerical_airspeed_tape(qtbot):
    widget = airspeed.Airspeed_Tape(font_percent=0.5)
    qtbot.addWidget(widget)
    widget.redraw()
    widget.resize(50, 200)
    widget.show()
    assert widget.Vs0 == 40
    assert widget.getAirspeed() == 20
    widget.setAirspeed(40)  # redraw()
    widget.keyPressEvent(None)
    widget.wheelEvent(None)


def test_numerical_airspeed_box(qtbot):
    hmi.initialize({})
    widget = airspeed.Airspeed_Box()
    qtbot.addWidget(widget)
    widget.resize(50, 50)
    widget.show()
    fix.db.set_value("TAS", 100)
    widget.setMode(1)
    widget.setMode(0)
    assert widget.modeText == "TAS"
    assert widget.valueText == "100"
    fix.db.set_value("GS", 80)
    widget.setMode(1)
    assert widget.modeText == "GS"
    assert widget.valueText == "80"
    assert widget._modeIndicator == 1
    fix.db.set_value("IAS", 140)
    widget.setMode(2)
    assert widget.modeText == "IAS"
    assert widget.valueText == "140"
    widget.setMode("")
    assert widget._modeIndicator == 0

    fix.db.get_item("TAS").fail = True
    fix.db.set_value("TAS", 101)
    assert widget.valueText == "XXX"
    fix.db.get_item("TAS").fail = False
    fix.db.get_item("TAS").bad = True
    fix.db.set_value("TAS", 102)
    assert widget.valueText == ""

