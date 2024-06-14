import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from pyefis.instruments.NumericalDisplay import NumericalDisplay
import pyavtools.fix as fix


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_numerical_display_default(qtbot):
    widget = NumericalDisplay(total_decimals=4, scroll_decimal=2)
    qtbot.addWidget(widget)
    assert widget.total_decimals == 4
    assert widget.scroll_decimal == 2
    assert widget._bad == False
    assert widget.value == 0
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.isVisible()


def test_numerical_display_decimals(qtbot):
    widget = NumericalDisplay(total_decimals=5, scroll_decimal=2, font_size=20)
    qtbot.addWidget(widget)
    widget.resize(80, 50)
    widget.show()
    widget.setValue(val=1234)
    qtbot.waitExposed(widget)
    assert widget.font_size != 20
    assert widget.pre_scroll_text.text() == "012"
    widget.setValue(val=54321)
    assert widget.pre_scroll_text.text() == "543"
    widget.setBad(True)
    widget.setValue(val=43210)
    widget.getValue()
    assert widget._bad == True
    widget.resize(85, 50)
    assert widget.pre_scroll_text.text() == ""
    assert widget.value == 43210
    assert widget.pre_scroll_text.text() != "432"
    a = widget.getValue()
    assert a == 43210
    assert widget.pre_scroll_text.text() == ""
    assert widget.getBad() == True
    widget.setOld(True)
    assert widget.getOld() == True
    widget.setOld(False)
    assert widget.getOld() == False
    widget.setFail(True)
    assert widget.getFail() == True
    widget.setFail(False)
    assert widget.getFail() == False

    widget.setBad(False)
    widget.setValue(val=54321)
    assert widget.pre_scroll_text.brush() == QBrush(QColor(Qt.white))

    widget.setValue(val=-5432)
    assert widget.pre_scroll_text.text() == "-54"
    widget.setValue(val=-52)
    assert widget.pre_scroll_text.text() == "-00"


# Not sure why line 270 is not showing as covered
# when this calls the getValue function:
def test_numerical_get_value(qtbot):
    widget = NumericalDisplay(total_decimals=5, scroll_decimal=2, font_size=20)
    qtbot.addWidget(widget)
    widget.setValue(20)
    widget.getValue()
    assert widget._value == 20
    assert widget.getValue() == 20
