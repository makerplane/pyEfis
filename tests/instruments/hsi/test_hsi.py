import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import hsi
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_hsi(fix,qtbot):
    widget = hsi.HSI()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

def test_heading_display(fix,qtbot):
    widget = hsi.HeadingDisplay()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

def test_dg_tape(fix,qtbot):
    widget = hsi.DG_Tape()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

