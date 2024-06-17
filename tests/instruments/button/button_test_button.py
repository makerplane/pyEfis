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
    real_parent.parent.config_path = "tests/data/listbox/"
    return real_parent

def test_simple_button(fix,mock_parent_widget,qtbot):
    widget = button.Button(mock_parent_widget, config_file="tests/data/buttons/simple.yaml")
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(200,200)
    mock_parent_widget.show()
    widget.resize(100,80)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(2000)

