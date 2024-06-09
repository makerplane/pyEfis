import pytest
import warnings
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from pyefis.instruments.misc import StaticText, ValueDisplay
import time
import subprocess
import os


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_save_screenshot(qtbot, request):
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


def test_static_text_default(qtbot):
    widget = StaticText(text="Testing!")
    qtbot.addWidget(widget)

    assert widget.text == "Testing!"
    assert widget.font_family == "DejaVu Sans Condensed"
    assert widget.color == QColor(Qt.white)

    widget.show()
    assert widget.isVisible()


def test_static_text_resize(qtbot):
    widget = StaticText(text="Test", fontsize=1.0)
    qtbot.addWidget(widget)

    widget.resize(200, 100)
    qtbot.waitExposed(widget)
    assert widget.width() == 200
    assert widget.height() == 100


def test_value_display_default(qtbot):
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


def test_value_display_set_value(qtbot):
    widget = ValueDisplay()
    qtbot.addWidget(widget)

    widget.setValue(42.0)
    assert widget.getValue() == 42.0

    widget.setValue(-3.14)
    assert widget.getValue() == -3.14


@mock.patch("pyefis.instruments.misc.fix")
def test_value_display_flags(mock_fix, qtbot):
    mock_item = mock.Mock()
    mock_item.value = 100.0
    mock_fix.db.get_item.return_value = mock_item

    widget = ValueDisplay()
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

    widget.annunciateFlag(True)
    assert widget.annunciate == True


if __name__ == "__main__":
    pytest.main()
