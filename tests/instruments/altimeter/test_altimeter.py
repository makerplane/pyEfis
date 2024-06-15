import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, qRound
from PyQt5.QtGui import QColor, QBrush, QPen, QFont, QPaintEvent, QFontMetrics
from pyefis.instruments import altimeter
import pyefis.hmi as hmi
from tests.utils import track_calls


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
    qtbot.wait(3000)
