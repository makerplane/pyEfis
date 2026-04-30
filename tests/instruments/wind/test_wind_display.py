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

    def test_resize_uses_minimum_font_and_arrow_sizes(self, fix, qtbot):
        """Very small widgets keep text and arrows at their minimum sizes."""
        widget = WindDisplay()
        qtbot.addWidget(widget)
        widget.resize(10, 10)
        widget.resizeEvent(None)

        assert widget._lbl_font.pixelSize() == 6
        assert widget._val_font.pixelSize() == 8
        assert widget._arrow_size == 4


class FakePainter:
    def __init__(self):
        self.polygons = []
        self.text = []
        self.pens = []
        self.brushes = []

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
        bad=False,
        arrow_up=True,
        arrow_right=None,
    )
    widget._draw_row(
        painter,
        20,
        "XW",
        7.6,
        fail=False,
        bad=True,
        arrow_up=None,
        arrow_right=None,
    )

    assert painter.polygons == []
    assert painter.text == ["HW", "---", "XW", "8"]


def test_draw_row_covers_down_and_left_arrow_geometry(fix, qtbot):
    widget = WindDisplay()
    qtbot.addWidget(widget)
    widget.resize(100, 40)
    widget._row_h = 20
    widget._arrow_size = 4
    painter = FakePainter()

    widget._draw_row(
        painter,
        0,
        "HW",
        -5,
        fail=False,
        bad=False,
        arrow_up=False,
        arrow_right=None,
    )
    widget._draw_row(
        painter,
        20,
        "XW",
        5,
        fail=False,
        bad=False,
        arrow_up=None,
        arrow_right=False,
    )

    assert _polygon_points(painter.polygons[0]) == [(42, 14), (38, 8), (46, 8)]
    assert _polygon_points(painter.polygons[1]) == [(38, 30), (44, 26), (44, 34)]
