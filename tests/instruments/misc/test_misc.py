import pytest
import warnings
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from pyefis.instruments.misc import StaticText, ValueDisplay
import os


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_save_screenshot(fix, qtbot, request):
    widget1 = StaticText(text="Testing!")
    widget1.font_mask = "XXXXXXXX"
    widget1.color = QColor(Qt.black)
    widget1.move(0, 0)
    widget1.resize(100, 50)
    qtbot.addWidget(widget1)
    widget1.show()
    qtbot.waitExposed(widget1)
    path = qtbot.screenshot(widget1, "instruments-misc-test_misc")
    qtbot.wait(500)
    os.rename(
        path,
        request.config.rootdir
        + "/extras/extras/test_results/instruments-misc-test_misc-StaticText.png",
    )


def test_static_text_default(fix, qtbot):
    widget = StaticText(text="Testing!")
    widget.font_mask = "0.0"
    widget.font_ghost_mask = "0.0"
    qtbot.addWidget(widget)

    assert widget.text == "Testing!"
    assert widget.font_family == "DejaVu Sans Condensed"
    assert widget.color == QColor(Qt.white)
    widget.resizeEvent(None)
    widget.paintEvent(None)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.isVisible()
    assert widget.color.alpha() != 50


def test_static_text_resize(fix, qtbot):
    widget = StaticText(text="Test", fontsize=1.0)
    qtbot.addWidget(widget)

    widget.resize(200, 100)
    widget.resizeEvent(None)
    widget.paintEvent(None)
    qtbot.waitExposed(widget)
    assert widget.width() == 200
    assert widget.height() == 100


def test_value_display_default(fix, qtbot):
    widget = ValueDisplay()
    qtbot.addWidget(widget)

    assert widget.font_family == "Open Sans"
    assert widget._value == 0.0
    assert widget.fail == False
    assert widget.bad == False
    assert widget.old == False
    assert widget.annunciate == False

    widget.show()
    assert widget.isVisible()

def test_value_display_font_mask(fix, qtbot):
    widget = ValueDisplay()
    widget.font_size = 100
    widget.font_mask = "0.0"
    widget.font_ghost_mask = "0.0"
    qtbot.addWidget(widget)
    widget.resizeEvent(None)
    widget.paintEvent(None)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.isVisible()
    assert widget.font_size != 100

def test_value_display_set_value(fix, qtbot):
    widget = ValueDisplay()
    fix.db.set_value("TEST",42.0)
    fix.db.get_item("TEST").fail = False
    widget.setDbkey("TEST")
    qtbot.addWidget(widget)

    assert widget.getValue() == 42.0

    fix.db.set_value("TEST",3.14)
    assert widget.getValue() == 3.14


#@mock.patch("pyefis.instruments.misc.fix")
#def test_value_display_flags(mock_fix, qtbot):
def test_value_display_flags(fix, qtbot):
    #mock_item = mock.Mock()
    #mock_item.value = 100.0
    #mock_fix.db.get_item.return_value = mock_item
    widget = ValueDisplay()

    fix.db.set_value("TEST",100)
    widget.setDbkey("TEST")
    qtbot.addWidget(widget)

    widget.failFlag(True)
    assert widget.fail == True
    assert widget.getValue() == 0.0

    widget.failFlag(False)
    assert widget.fail == False
    assert widget.getValue() == 100.0

    widget.oldFlag(True)
    assert widget.old == True
    assert widget.getValueText() == "100.0"

    widget.badFlag(True)
    assert widget.bad == True
    assert widget.getValueText() == "100.0"

    widget.failFlag(True)
    assert widget.fail == True
    assert widget.getValueText() == "xxx"

    widget.failFlag(False)
    widget.annunciateFlag(True)
    assert widget.annunciate == True
    assert widget.textColor == widget.textAnnunciateColor

@mock.patch("pyefis.instruments.misc.fix")
def test_set_db_key(mock_fix,qtbot):
    mock_item = mock.MagicMock()
    mock_item.value = 100.0
    mock_item.fail = True
    mock_item.bad = False
    mock_fix.db.get_item.return_value = mock_item
    mock_setupGauge = mock.MagicMock()
    widget = ValueDisplay()
    qtbot.addWidget(widget)
    widget.setDbkey('TEST')
    mock_fix.db.get_item.assert_called_once_with("TEST")
    mock_item.reportReceived.connect.assert_called_once_with(widget.setupGauge)
    mock_item.annunciateChanged.connect.assert_called_once_with(widget.annunciateFlag)
    mock_item.oldChanged.connect.assert_called_once_with(widget.oldFlag)
    mock_item.badChanged.connect.assert_called_once_with(widget.badFlag)
    mock_item.failChanged.connect.assert_called_once_with(widget.failFlag)
    assert widget._dbkey == "TEST"
    # These would only match if self.setupGauge() was called:
    assert widget.fail == True
    assert widget.bad == False
#    assert mock_item.



if __name__ == "__main__":
    pytest.main()
