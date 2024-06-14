import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from pyefis.instruments import gauges
import pyavtools.fix as fix
import pyefis.hmi as hmi


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_arc_gauge(qtbot):
    widget = gauges.ArcGauge()
    assert widget.getRatio() == 2
    widget.setDbkey("NUMOK")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.resize(201, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resize(200, 220)
    widget.resizeEvent(None)
    assert widget.tlcx == 0
    assert widget.tlcy == 60
    widget.resize(400, 100)
    widget.resizeEvent(None)
    assert widget.tlcx == 100
    assert widget.tlcy == 00
    widget.font_mask = "0000"

    qtbot.wait(5000)

