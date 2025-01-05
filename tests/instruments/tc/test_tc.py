import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import tc
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app

def test_tc(fix,qtbot):
    def data_values(arg):
        if   arg == 'alat_filter_depth': return None
        elif arg == 'alat_multiplier': return None
        return None
    widget = tc.TurnCoordinator()
    widget.myparent = mock.MagicMock()
    widget.myparent.get_config_item = data_values
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)


def test_tc_tape(fix,qtbot):
    widget = tc.TurnCoordinator_Tape()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(1000)

