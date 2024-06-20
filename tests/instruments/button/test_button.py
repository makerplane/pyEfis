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
    widget.enc_highlight(True)
    assert widget._style['bg_override'] == QColor('orange')
    with qtbot.waitSignal(hmi.actions.setInstUnits, timeout=2000):
        widget.enc_select()
    fix.db.set_value("HIDEBUTTON", True)
    assert fix.db.get_item("HIDEBUTTON").value == True
    assert widget._buttonhide == True
    widget.enterEvent(None)
    assert fix.db.get_item("HIDEBUTTON").value == False
    fix.db.get_item("INT").old = True
    assert widget._db_data["INT.old"] == True
    fix.db.get_item("INT").bad = False
    assert widget._db_data["INT.bad"] == False
    fix.db.get_item("INT").value = 66
    assert widget._db_data["INT"] == 66
    fix.db.get_item("TSBTN10").bad = True
    fix.db.get_item("TSBTN10").value = True
    assert widget._dbkey.bad == True
    widget.hide()
    fix.db.get_item("TSBTN10").bad = False
    fix.db.get_item("TSBTN10").value = False
    assert widget.isVisible() == False
    widget.show()
    fix.db.get_item("INT").fail = False
    assert widget._db_data["INT.fail"] == False
    fix.db.get_item("INT").annunciate = True
    assert widget._db_data["INT.annunciate"] == True
    fix.db.get_item("NUMOK").set_aux_value("highAlarm", 95)
    assert widget._db_data["NUMOK.aux.highAlarm"] == 95
    assert widget.getTitle() == widget._title
    fix.db.get_item("NUMOK").value = 33.3
    assert widget._db_data["NUMOK"] == 33.3
    fix.db.set_value("TSBTN10", True)
    fix.db.set_value("TSBTN10", True)
    assert fix.db.get_item("TSBTN10").value == False
    assert widget._dbkey.value == False
    widget.dbkeyChanged(False)
    widget.font_mask = "XXXX"
    fix.db.set_value("TSBTN10", True)
    assert widget.font_size != None
    #qtbot.wait(2000)


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
    widget.enterEvent(None)
    assert widget._title == "AP\nAdjust"
    assert widget.config['dbkey'] == 'TSBTN{id}2'
    assert widget._toggle == True
    assert widget._button.isCheckable() == True
    assert widget._style['bg'] == QColor("#5d5b59")
    assert widget.isEnabled() == False
    fix.db.set_value("MAVMODE","HH")
    fix.db.set_value("MAVSTATE","ARMED")
    widget.enc_highlight(True)
    assert widget._style['bg_override'] == QColor('orange')
    widget.enc_select()
    assert widget._style['bg'] == QColor('yellow')
    fix.db.set_value("MAVADJ",True)
    assert widget._style['bg'] == QColor('green')
    widget.enc_highlight(False)
    assert widget._style['bg_override'] == None
    assert widget.enc_selectable() == True
    assert widget._button.isChecked() == True
    fix.db.set_value('TSBTN12', True)
    assert widget._dbkey.value == True
    # Test that when already set true, setting True does nothing
    widget._db_data['CLICKED'] = False
    widget._button.setChecked(False)
    widget.dbkeyChanged(True)
    assert widget._db_data['CLICKED'] == True
    widget._db_data['CLICKED'] = False
    widget.dbkeyChanged(True)
    assert widget._db_data['CLICKED'] == False
    # End already set test
    #fix.db.set_value('TSBTN12', True)
    #qtbot.wait(2000)


def test_toggle_button2(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/toggle2.yaml")
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(200,200)
    mock_parent_widget.show()
    widget.resize(100,80)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget._title == "False" 
    fix.db.set_value("TSBTN13", True)
    assert widget._title == "True"
    fix.db.set_value("TSBTN13", False)
    fix.db.set_value("MAVMODE", "checked")
    assert widget._button.isChecked()
    fix.db.set_value("MAVMODE", "unchecked")
    assert widget._button.isChecked() == False
    widget.hide()
    fix.db.set_value("TSBTN13", True)
    widget.buttonToggled()
    assert widget.isVisible() == False
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
    #qtbot.wait(1000)
    fix.db.get_item("TSBTN13").value = False
    assert round(baro.value,2) >= round(before + 0.03,2)
    widget.dataChanged("t","unknown")

def test_unknown_button_type(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    with pytest.raises(SyntaxError):
        widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/unknown.yaml")

def test_unknown_button_condition(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    with pytest.raises(SyntaxError):
        widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/unknown_condition.yaml")

def test_unknown_button_condition2(fix,mock_parent_widget,qtbot):
    hmi.initialize({})
    with pytest.raises(SyntaxError):
        widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/unknown_condition2.yaml")

