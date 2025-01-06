import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication
from pyefis.instruments import ai
import pyefis.hmi as hmi
from tests.utils import track_calls

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_ai(fix,qtbot):
    widget = ai.AI()
    qtbot.addWidget(widget)
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(3000)
