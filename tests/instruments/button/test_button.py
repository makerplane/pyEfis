import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, qRound
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPaintEvent, QFontMetrics
from pyefis.instruments import button
import pyefis.hmi as hmi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

@pytest.fixture
def mock_parent_widget():
    real_parent = QWidget()  # Create a real QWidget instance
    real_parent.screenName = "TEST"
    real_parent.parent = mock.Mock()
    real_parent.parent.nodeID = 1
    return real_parent

def test_simple_button(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/simple.yaml")
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(200,200)
    mock_parent_widget.show()
    widget.resize(100,80)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget._title == "Units"
    assert widget.config['dbkey'] == 'TSBTN{id}0'
    assert widget._toggle == False
    assert widget._button.isCheckable() == False
    fix.db.get_item("HIDEBUTTON").value = True
    assert widget._title == "Show\nMenu"
    qtbot.mouseClick(widget._button, Qt.LeftButton)
    assert widget._title == "Units"
    with qtbot.waitSignal(hmi.actions.setInstUnits, timeout=2000):
        qtbot.mouseClick(widget._button, Qt.LeftButton)



def test_toggle_button(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/toggle.yaml")
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(200,200)
    mock_parent_widget.show()
    widget.resize(100,80)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget._title == "AP\nAdjust"
    assert widget.config['dbkey'] == 'TSBTN{id}2'
    assert widget._toggle == True
    assert widget._button.isCheckable() == True
    assert widget._style['bg'] == QColor("#5d5b59")
    assert widget.isEnabled() == False
    #qtbot.wait(2000)


def test_repeat_button(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/repeat.yaml")
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(200,200)
    mock_parent_widget.show()
    widget.resize(100,80)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget._title == "+"
    assert widget.config['dbkey'] == 'TSBTN{id}3'
    assert widget._toggle == False
    assert widget._repeat == True
    assert widget._button.isCheckable() == False
    assert widget._style['transparent'] == True
    assert widget._button.autoRepeatInterval() == 200
    baro = fix.db.get_item("BARO")
    before = baro.value
    qtbot.mouseClick(widget._button, Qt.LeftButton)
    assert baro.value == before + 0.01
    before = baro.value
    fix.db.get_item("TSBTN13").value = True
    qtbot.wait(1000)
    fix.db.get_item("TSBTN13").value = False
    assert round(baro.value,2) >= round(before + 0.03,2)
