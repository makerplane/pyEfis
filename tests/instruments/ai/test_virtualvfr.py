import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, qRound
from PyQt6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPaintEvent, QFontMetrics
from PyQt6 import QtGui
from pyefis.instruments.ai.VirtualVfr import VirtualVfr
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_virtual_VFR(fix,qtbot):
    def data_values(arg):
        if   arg == 'metadata': return None
        elif arg == 'dbpath': return "/path"
        elif arg == 'indexpath': return "/indexpath"
        return None

    widget = VirtualVfr()
    widget.myparent = mock.MagicMock()
    widget.myparent.get_config_item = data_values
    qtbot.addWidget(widget)
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(3000)
