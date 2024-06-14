import pytest
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QPen, QPaintEvent, QFontMetrics
from pyefis.instruments.gauges import numeric
import pyefis.hmi as hmi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_numeric_gauge(fix,qtbot):
    widget = numeric.NumericDisplay()
    widget.setDbkey("NUM")
    widget.setupGauge()
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resizeEvent(None)
    assert widget.font_size == 200
    widget.font_mask = "0000"
    widget.resizeEvent(None)
    assert widget.font_size != 200
    oldvalueTextRect = widget.valueTextRect
    widget.show_units = True
    widget.resizeEvent(None)
    assert oldvalueTextRect != widget.valueTextRect
    widget.font_ghost_mask = "0000"
    with track_calls(QColor, "setAlpha") as tracker:
        widget.paintEvent(None)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)
        widget.font_ghost_mask = None
        widget.units_font_ghost_mask = "0000"
        widget.paintEvent(None)
        assert tracker.was_called_with("setAlpha", widget.font_ghost_alpha)
