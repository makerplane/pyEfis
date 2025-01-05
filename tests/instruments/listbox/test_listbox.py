import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments import listbox
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
    real_parent.parent = mock.Mock()
    real_parent.parent.config_path = "tests/data/listbox/"
    return real_parent

def test_listbox(mock_parent_widget,fix,qtbot):
    lists = [
      {"name": "List 1", "file": "list1.yaml"},
      {"name": "List 2", "file": "list2.yaml"},
    ]
    widget = listbox.ListBox(mock_parent_widget, lists=lists)
    mock_parent_widget.show()
    mock_parent_widget.resize(1000,1000)
    widget.show()
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    widget.resize(500,300)
    widget.resizeEvent(None)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.isVisible() == True
    qtbot.wait(3000)    
