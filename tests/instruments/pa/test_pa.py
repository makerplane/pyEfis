import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import pa
import pyefis.hmi as hmi
from tests.utils import track_calls
@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_pa(fix,qtbot):
    widget = pa.Panel_Annunciator()
    qtbot.addWidget(widget)
    widget.setWARNING_Name("Pull UP!")
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.setState(0)
    qtbot.wait(1000)

