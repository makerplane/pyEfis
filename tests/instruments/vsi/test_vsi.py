import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import vsi
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_vsi(fix,qtbot):
    widget = vsi.VSI_Dial()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)


def test_vsi_pfd(fix,qtbot):
    widget = vsi.VSI_PFD()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

def test_vsi_as_trend_tape(fix,qtbot):
    widget = vsi.AS_Trend_Tape()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

def test_vsi_alt_trend_tape(fix,qtbot):
    def data_values(arg):
        if   arg == 'update_period': return None
        elif arg == 'update_period2': return None
        return None
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = mock.MagicMock()
    widget.myparent.get_config_item = data_values
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

