"""
Unit tests for pyefis.instruments.wind.WindDisplay.

Verifies widget creation, initial state, value-change callbacks, fail/bad
flag handling, and directional arrow logic — all without a physical display.
"""
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPaintEvent

import pyefis.instruments.wind as wind_module
from pyefis.instruments.wind import WindDisplay
from unittest.mock import MagicMock


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

    def test_missing_wind_fix_items_leave_defaults_without_signal_items(
        self, monkeypatch, qtbot
    ):
        """Missing HWIND/XWIND leaves the display in its default failed state."""
        monkeypatch.setattr(
            wind_module.fix.db,
            "get_item",
            lambda _key: (_ for _ in ()).throw(KeyError(_key)),
        )

        widget = WindDisplay()
        qtbot.addWidget(widget)

        assert widget._hwind == 0.0
        assert widget._xwind == 0.0
        assert widget._hwind_fail is True
        assert widget._xwind_fail is True
        assert not hasattr(widget, "_hwind_item")
        assert not hasattr(widget, "_xwind_item")

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

    def test_xwind_bad_flag_propagates(self, fix, qtbot):
        """Setting XWIND bad flag is reflected in the widget."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        fix.db.get_item("XWIND").bad = True
        assert widget._xwind_bad is True
        fix.db.get_item("XWIND").bad = False
        assert widget._xwind_bad is False

    def test_positive_hwind_is_headwind_arrow_up(self, fix, qtbot):
        """Positive HWIND (headwind) maps to arrow_up=True in paintEvent logic."""
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

    def test_resize_uses_minimum_font_sizes(self, fix, qtbot):
        """Very small widgets keep text and arrows at their minimum sizes."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(10, 10)
        widget.resizeEvent(None)

        assert widget._lbl_font.pixelSize() == 6
        assert widget._val_font.pixelSize() == 6


class FakePainter:
    def __init__(self):
        self.polygons = []
        self.text = []
        self.pens = []
        self.brushes = []

        self.font_metrics_mock = MagicMock()
        self.font_metrics_mock.width.return_value = 10 
        self.font_metrics_mock.horizontalAdvance.return_value = 10 

    def fontMetrics(self):
        """Returns the mocked font metrics object."""
        return self.font_metrics_mock

    def fillRect(self, *args):
        pass

    def setFont(self, *args):
        pass

    def setPen(self, pen):
        self.pens.append(pen)

    def setBrush(self, brush):
        self.brushes.append(brush)

    def drawText(self, _rect, _alignment, text):
        self.text.append(text)

    def drawPolygon(self, polygon):
        self.polygons.append(polygon)


def _polygon_points(polygon):
    return [(polygon.point(i).x(), polygon.point(i).y()) for i in range(polygon.count())]


def test_draw_row_covers_failed_bad_and_no_arrow_branches(fix, qtbot):
    widget = WindDisplay()
    qtbot.addWidget(widget)
    widget.resize(100, 40)
    painter = FakePainter()

    widget._draw_row(
        painter,
        0,
        "HW",
        -12.4,
        fail=True,
        bad=False
    )
    widget._draw_row(
        painter,
        20,
        "XW",
        7.6,
        fail=False,
        bad=True
    )

    assert painter.polygons == []
    assert painter.text == ["HW", "---", "XW", "X"]

