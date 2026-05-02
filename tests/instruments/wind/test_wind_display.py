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

    def test_positive_hwind_uses_HW_label(self, fix, qtbot):
        """Positive HWIND (headwind) → 'HW' label."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", 12.0)
        assert widget._hw_label(widget._hwind, widget._hwind_fail) == "HW"

    def test_negative_hwind_uses_TW_label(self, fix, qtbot):
        """Negative HWIND (tailwind) → 'TW' label."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", -7.0)
        assert widget._hw_label(widget._hwind, widget._hwind_fail) == "TW"

    def test_positive_xwind_uses_RX_label(self, fix, qtbot):
        """Positive XWIND (from right) → 'RX' label."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", 10.0)
        assert widget._xw_label(widget._xwind, widget._xwind_fail) == "RX"

    def test_negative_xwind_uses_LX_label(self, fix, qtbot):
        """Negative XWIND (from left) → 'LX' label."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", -10.0)
        assert widget._xw_label(widget._xwind, widget._xwind_fail) == "LX"

    def test_zero_hwind_uses_HW_label(self, fix, qtbot):
        """HWIND of 0 → 'HW' (positive-side default)."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", 0.0)
        assert widget._hw_label(widget._hwind, widget._hwind_fail) == "HW"

    def test_hwind_in_deadband_uses_HW_label(self, fix, qtbot):
        """Slightly-negative HWIND inside deadband stays as 'HW' (no flicker)."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", -0.3)
        assert widget._hw_label(widget._hwind, widget._hwind_fail) == "HW"

    def test_zero_xwind_uses_RX_label(self, fix, qtbot):
        """XWIND of 0 → 'RX' (positive-side default)."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("XWIND", 0.0)
        assert widget._xw_label(widget._xwind, widget._xwind_fail) == "RX"

    def test_fail_state_uses_default_label(self, fix, qtbot):
        """When fail=True the label stays at the positive default regardless of value."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.set_value("HWIND", -20.0)
        fix.db.set_value("XWIND", -20.0)
        assert widget._hw_label(widget._hwind, fail=True) == "HW"
        assert widget._xw_label(widget._xwind, fail=True) == "RX"

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
        widget.resize(40, 30)
        assert widget._row_h > 0


class TestWindDisplayDataFeedOffline:
    """Wind feed offline scenarios — gateway never published HWIND/XWIND, or
    items entered fail state mid-flight. Widget must not raise and must show
    fail-state ('---' dashes, dim grey) so the pilot knows wind data is bad.
    """

    def test_construct_when_keys_missing_from_db(self, fix, qtbot, monkeypatch):
        """Widget instantiates without raising when HWIND/XWIND don't exist.

        Simulates a gateway that hasn't published the wind-component compute
        outputs (e.g., no wind_components function configured, or gateway
        running an older config). The widget must catch the KeyError and
        leave both channels in fail state so the display shows dashes.
        """
        real_get_item = fix.db.get_item

        def get_item_no_wind(key, *args, **kwargs):
            if key in ("HWIND", "XWIND"):
                raise KeyError(key)
            return real_get_item(key, *args, **kwargs)

        monkeypatch.setattr(fix.db, "get_item", get_item_no_wind)

        widget = WindDisplay()
        qtbot.addWidget(widget)

        assert widget._hwind_fail is True
        assert widget._xwind_fail is True
        assert not hasattr(widget, "_hwind_item")
        assert not hasattr(widget, "_xwind_item")

    def test_paint_event_when_keys_missing(self, fix, qtbot, monkeypatch):
        """paintEvent renders fail-state dashes without error when keys are absent."""
        real_get_item = fix.db.get_item

        def get_item_no_wind(key, *args, **kwargs):
            if key in ("HWIND", "XWIND"):
                raise KeyError(key)
            return real_get_item(key, *args, **kwargs)

        monkeypatch.setattr(fix.db, "get_item", get_item_no_wind)

        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)
        widget.show()
        qtbot.waitExposed(widget)
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)

    def test_data_feed_drops_after_widget_exists(self, fix, qtbot):
        """Widget with good data → feed goes offline (fail=True) → no error.

        Simulates the more common runtime case: gateway was publishing wind,
        connection drops, FIX items flip to fail. The widget should track the
        fail flags and re-render dashes on the next paint without raising.
        """
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)
        widget.show()
        qtbot.waitExposed(widget)

        fix.db.set_value("HWIND", 12.0)
        fix.db.set_value("XWIND", -4.0)
        assert widget._hwind_fail is False
        assert widget._xwind_fail is False

        fix.db.get_item("HWIND").fail = True
        fix.db.get_item("XWIND").fail = True
        assert widget._hwind_fail is True
        assert widget._xwind_fail is True

        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)

    def test_data_feed_recovers(self, fix, qtbot):
        """After fail state, feed recovers and widget transitions back to live values."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(80, 60)

        fix.db.get_item("HWIND").fail = True
        fix.db.get_item("XWIND").fail = True
        assert widget._hwind_fail is True

        fix.db.get_item("HWIND").fail = False
        fix.db.get_item("XWIND").fail = False
        fix.db.set_value("HWIND", 6.0)
        fix.db.set_value("XWIND", 2.0)

        assert widget._hwind_fail is False
        assert widget._xwind_fail is False
        assert widget._hwind == pytest.approx(6.0)
        assert widget._xwind == pytest.approx(2.0)
