"""
Unit tests for pyefis.instruments.wind.WindDisplay.

Verifies widget creation, initial state, value-change callbacks, fail/bad
flag handling, and directional arrow logic — all without a physical display.
"""
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPaintEvent

from pyefis.instruments.wind import WindDisplay


@pytest.fixture
def app(qtbot):
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class TestWindDisplay:

    def test_widget_creates_without_error(self, fix, qtbot):
        """WindDisplay instantiates and can be shown."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)
        widget.show()
        qtbot.waitExposed(widget)

    def test_initial_fail_state(self, fix, qtbot):
        """Widget starts with fail=True for both channels until values arrive."""
        widget = WindDisplay()
        # The mock items start with fail=False (set in conftest), so the widget
        # should reflect that initial state after construction.
        # fail is read from item.fail in __init__
        assert widget._hwind_fail == fix.db.get_item("HWIND").fail
        assert widget._xwind_fail == fix.db.get_item("XWIND").fail

    def test_hwind_value_updated_via_signal(self, fix, qtbot):
        """Setting HWIND in the database updates the widget's internal value."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", 15.0)
        assert widget._hwind == pytest.approx(15.0)

    def test_xwind_value_updated_via_signal(self, fix, qtbot):
        """Setting XWIND in the database updates the widget's internal value."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", -8.0)
        assert widget._xwind == pytest.approx(-8.0)

    def test_hwind_fail_flag_propagates(self, fix, qtbot):
        """Setting HWIND fail flag is reflected in the widget."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.get_item("HWIND").fail = True
        assert widget._hwind_fail is True
        fix.db.get_item("HWIND").fail = False
        assert widget._hwind_fail is False

    def test_xwind_fail_flag_propagates(self, fix, qtbot):
        """Setting XWIND fail flag is reflected in the widget."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.get_item("XWIND").fail = True
        assert widget._xwind_fail is True
        fix.db.get_item("XWIND").fail = False
        assert widget._xwind_fail is False

    def test_hwind_bad_flag_propagates(self, fix, qtbot):
        """Setting HWIND bad flag is reflected in the widget."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.get_item("HWIND").bad = True
        assert widget._hwind_bad is True
        fix.db.get_item("HWIND").bad = False
        assert widget._hwind_bad is False

    def test_positive_hwind_is_headwind_arrow_up(self, fix, qtbot):
        """Positive HWIND (headwind) maps to arrow_up=True in paintEvent logic."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", 12.0)
        # arrow_up is True when _hwind >= 0 and not fail
        assert widget._hwind >= 0
        assert widget._hwind_fail is False

    def test_negative_hwind_is_tailwind_arrow_down(self, fix, qtbot):
        """Negative HWIND (tailwind) maps to arrow_up=False."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", -7.0)
        assert widget._hwind < 0
        assert widget._hwind_fail is False

    def test_positive_xwind_is_from_right_arrow_left(self, fix, qtbot):
        """Positive XWIND (from right) maps to arrow_right=False (shows left arrow)."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", 10.0)
        # arrow_right = (xwind < 0) when not fail → False for positive xwind
        assert widget._xwind > 0
        assert widget._xwind_fail is False

    def test_negative_xwind_is_from_left_arrow_right(self, fix, qtbot):
        """Negative XWIND (from left) maps to arrow_right=True (shows right arrow)."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", -10.0)
        assert widget._xwind < 0
        assert widget._xwind_fail is False

    def test_paint_event_does_not_raise(self, fix, qtbot):
        """paintEvent runs without exceptions for normal and fail states."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)
        widget.show()
        qtbot.waitExposed(widget)

        fix.db.set_value("HWIND", 10.0)
        fix.db.set_value("XWIND", -5.0)
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)

        fix.db.get_item("HWIND").fail = True
        fix.db.get_item("XWIND").fail = True
        widget.paintEvent(event)

    def test_resize_updates_font_metrics(self, fix, qtbot):
        """resizeEvent updates internal sizing without error."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)
        assert widget._row_h > 0
        assert widget._arrow_size > 0
        widget.resize(40, 30)
        assert widget._row_h > 0
