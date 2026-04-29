from unittest import mock

import pytest
from PyQt6.QtGui import QColor, QCloseEvent
from PyQt6.QtWidgets import QApplication

import pyavtools.fix as fix_module
import pyefis.hmi as hmi
from pyefis.instruments.gauges import abstract


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


@pytest.fixture
def gauge(qtbot):
    widget = abstract.AbstractGauge()
    qtbot.addWidget(widget)
    widget.resize(120, 80)
    widget.update = mock.Mock()
    return widget


def test_draw_circle_uses_arc_geometry():
    painter = mock.Mock()

    abstract.drawCircle(painter, 20, 18, 7, 3, 9)

    rect, start, end = painter.drawArc.call_args.args
    assert rect.x() == 13
    assert rect.y() == 11
    assert rect.width() == 14
    assert start == 48
    assert end == 144


def test_value_conversion_clipping_peak_and_text(gauge):
    widget = gauge
    widget.lowRange = 10
    widget.highRange = 20

    assert widget.interpolate(15, 100) == 50
    widget.highRange = 10
    assert widget.interpolate(15, 100) == 0

    widget.highRange = 20
    widget.clipping = True
    widget.conversionFunction = lambda value: value * 2
    widget.value = 20

    assert widget._rawValue == 20
    assert widget.value == 20
    assert widget.peakValue == 20

    widget.font_mask = "000.0"
    assert widget.valueText == " 20.0"
    widget.font_mask = None
    widget.decimal_places = 2
    assert widget.valueText == "20.00"

    widget.fail = True
    assert widget.valueText == "xxx"
    widget.font_mask = "00.0"
    assert widget.valueText == "XX.X"
    widget.value = 15
    assert widget.value == 0


def test_encoder_value_text_variants(gauge):
    widget = gauge
    widget.decimal_places = 1

    widget.encoder_selected = True
    widget.encoder_set_value = 42.25
    assert widget.valueText == "42.2"

    widget.encoder_num_mask = "000.0"
    widget.encoder_num_string = "123.4"
    widget.encoder_num_blink = False
    assert widget.valueText == "123.4"

    widget.encoder_num_blink = True
    widget.encoder_num_digit = 1
    assert widget.valueText == "1 3.4"

    widget.encoder_num_digit = len(widget.encoder_num_mask) - 1
    assert widget.valueText == "123. "

    widget.encoder_num_require_confirm = True
    widget.encoder_num_confirmed = True
    assert widget.valueText == "     "


def test_units_close_and_db_setup_paths(gauge, fix):
    widget = gauge
    widget.units = "psi"
    assert widget.units == "psi"
    widget.unitsOverride = "bar"
    assert widget.units == "bar"

    widget.encoder_num_blink_timer.stop = mock.Mock()
    widget.closeEvent(QCloseEvent())
    widget.encoder_num_blink_timer.stop.assert_called_once_with()
    widget.encoder_num_blink_timer.stop = mock.Mock(side_effect=RuntimeError)
    widget.closeEvent(QCloseEvent())
    del widget.encoder_num_blink_timer
    widget.closeEvent(QCloseEvent())

    widget.highlight_key = "INT"
    widget.encoder_num_mask = "000"
    widget.encoder_num_enforce_multiplier = True
    widget.encoder_multiplier = 1
    widget.calculate_selections = mock.Mock()
    fix.db.get_item("INT").fail = False
    fix.db.get_item("INT").bad = False

    widget.dbkey = "INT"

    assert widget.dbkey == "INT"
    assert widget.encoder_set_key == "INT"
    assert widget.encoder_item is fix.db.get_item("INT")
    assert widget._highlightValue == fix.db.get_item("INT").value
    assert widget.calculate_selections.call_count == 1

    widget.encoder_num_limits = {"lowRange": 1, "highRange": 2}
    widget.setupGauge()

    assert widget.calculate_selections.call_count == 2

    fix.db.set_value("INT", 67)
    assert widget.value == 67
    widget.highlight_key = "NUMOK"
    widget.setupGauge()
    fix.db.set_value("NUMOK", 60)
    assert widget._highlightValue == 60

    widget.encoder_set_key = "NUMOK"
    widget.dbkey = "INT"
    assert widget.encoder_set_key == "NUMOK"

    fix.db.define_item("ABSTRACT_BOOL", "Bool item", "bool", False, True, "", 50000, "")
    fix.db.get_item("ABSTRACT_BOOL").bad = False
    fix.db.get_item("ABSTRACT_BOOL").fail = False
    fix.db.get_item("ABSTRACT_BOOL").value = True
    widget.highlight_key = "ABSTRACT_BOOL"
    widget.dbkey = "ABSTRACT_BOOL"
    widget.setupGauge()
    assert widget.value is True


def test_aux_flags_colors_and_unit_switching(gauge, fix):
    hmi.initialize({})
    widget = gauge
    widget.dbkey = "NUMOK"
    widget.lowRange = 0
    widget.highRange = 100
    widget.value = 50

    widget.setAuxData(
        {
            "Min": 5,
            "Max": 95,
            "lowWarn": 20,
            "lowAlarm": 10,
            "highWarn": 80,
            "highAlarm": 90,
        }
    )
    assert widget.lowRange == 5
    assert widget.highRange == 95
    assert widget.lowWarn == 20
    assert widget.lowAlarm == 10
    assert widget.highWarn == 80
    assert widget.highAlarm == 90

    widget.value = 15
    assert widget.valueColor == widget.warnColor
    widget.value = 6
    assert widget.valueColor == widget.alarmColor
    widget.value = 85
    assert widget.valueColor == widget.warnColor
    widget.value = 92
    assert widget.valueColor == widget.alarmColor

    widget.selectColor = QColor("orange")
    widget.badFlag(True)
    assert widget.bad is True
    assert widget.safeColor == widget.selectColor
    widget.oldFlag(True)
    assert widget.old is True
    widget.annunciateFlag(True)
    assert widget.textColor == widget.selectColor
    widget.failFlag(True)
    assert widget.fail is True
    assert widget.value == 0
    widget.failFlag(False)
    assert widget.value == fix.db.get_item("NUMOK").value
    widget.badFlag(False)
    widget.oldFlag(False)
    widget.selectColor = None
    widget.annunciateFlag(True)
    assert widget.textColor == QColor(widget.text_annunciate_color)

    widget.resetPeak()
    assert widget.peakValue == widget.value

    widget.conversionFunction1 = lambda value: value
    widget.conversionFunction2 = lambda value: value / 2
    widget.unitsOverride1 = "A"
    widget.unitsOverride2 = "B"
    widget.unitGroup = "Numbers"
    widget.setUnitSwitching()
    widget.setUnits("OTHER:toggle")
    assert widget.unitsOverride == "A"
    widget.setUnits("Numbers:noop")
    assert widget.unitsOverride == "A"
    widget.setUnits("Numbers:toggle")
    assert widget.unitsOverride == "B"
    assert widget.value == fix.db.get_item("NUMOK").value / 2
    widget.setUnits("*:toggle")
    assert widget.unitsOverride == "A"


def test_encoder_highlight_simple_selection_and_realtime(gauge, fix):
    widget = gauge
    widget.dbkey = "NUMOK"
    widget.encoder_multiplier = 2
    widget.encoder_set_real_time = True
    encoder_item = fix.db.get_item("NUMOK")
    encoder_item.output_value = mock.Mock()

    assert widget.enc_selectable() is True
    assert widget.enc_select() is True
    assert widget.encoder_selected is True
    assert widget.encoder_revert is True
    assert widget.encoder_set_value == widget.value

    start_value = widget.value
    assert widget.enc_changed(3) is True
    assert widget.encoder_set_value == start_value + 6
    assert encoder_item.value == widget.encoder_set_value
    encoder_item.output_value.assert_called_once_with()

    widget.clipping = True
    widget.lowRange = 0
    widget.highRange = 100
    assert widget.enc_changed(1000) is True
    assert widget.encoder_set_value == 100

    assert widget.enc_clicked() is False
    assert widget.encoder_revert is False

    widget.encoder_selected = True
    widget.encoder_revert = True
    widget.encoder_start_value = 12
    widget.encoder_set_value = 34
    encoder_item.output_value.reset_mock()
    widget.enc_highlight(False)
    assert encoder_item.value == 12
    assert widget.encoder_selected is False
    encoder_item.output_value.assert_called_once_with()

    widget.encoder_selected = True
    widget.encoder_revert = False
    widget.encoder_set_value = 56
    encoder_item.output_value.reset_mock()
    widget.enc_highlight(False)
    assert encoder_item.value == 56
    encoder_item.output_value.assert_called_once_with()

    widget.enc_highlight(True)
    assert widget.selectColor == QColor("orange")
    widget.encoder_selected = False
    widget.enc_highlight(False)
    assert widget.selectColor is None


def test_encoder_mask_selection_and_blink(gauge):
    widget = gauge
    widget.lowRange = 100.0
    widget.highRange = 102.0
    widget.encoder_multiplier = 1.0
    widget.encoder_num_mask = "000.0"
    widget.decimal_places = 1
    widget.encoder_set_key = "NUMOK"
    widget.calculate_selections()

    assert widget.allowed_digits() == ["1"]
    widget.encoder_num_string = "100.0"
    widget.encoder_num_digit = 1
    assert widget.allowed_digits() == ["0"]
    widget.encoder_num_digit = 4
    assert widget.allowed_digits() == ["0"]

    widget.enc_select()
    assert widget.encoder_num_string.startswith("10")
    assert widget.encoder_num_digit_options

    widget.encoder_num_digit_options = []
    assert widget.enc_changed(1) is False

    widget.encoder_num_digit_options = ["0", "1", "2"]
    widget.encoder_num_digit_selected = 0
    assert widget.enc_changed(-1) is True
    assert widget.encoder_num_digit_selected == 2
    assert widget.enc_changed(1) is True
    assert widget.encoder_num_digit_selected == 0
    assert widget.enc_changed(1) is True
    assert widget.encoder_num_digit_selected == 1
    assert widget.enc_changed(-1) is True
    assert widget.encoder_num_digit_selected == 0
    assert widget.enc_changed(0) is True

    widget.encoder_num_digit = 1
    widget.encoder_num_string = "100.0"
    widget.encoder_num_digit_selected = 0
    widget.set_encoder_value(clicked=True)
    assert widget.encoder_num_digit > 1

    widget.encoder_num_string = "101.0"
    widget.encoder_num_digit = len(widget.encoder_num_mask) - 1
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_digit_options = ["0"]
    widget.encoder_num_require_confirm = False
    widget.encoder_num_confirmed = False
    assert widget.enc_clicked() is False
    assert widget.encoder_set_value == 101.0

    widget.encoder_revert = True
    widget.encoder_num_require_confirm = True
    widget.encoder_num_confirmed = False
    widget.encoder_num_digit = len(widget.encoder_num_mask) - 1
    assert widget.enc_clicked() is True
    assert widget.encoder_revert is True
    assert widget.encoder_num_confirmed is True
    assert widget.enc_clicked() is False

    widget.encoder_num_blink_timer.start = mock.Mock()
    widget.encoder_num_blink = False
    widget.encoder_blink_event()
    assert widget.encoder_num_blink is True
    widget.encoder_num_blink_timer.start.assert_called_with(
        widget.encoder_num_blink_time_off
    )
    widget.encoder_blink_event()
    assert widget.encoder_num_blink is False
    widget.encoder_num_blink_timer.start.assert_called_with(
        widget.encoder_num_blink_time_on
    )


def test_encoder_mask_edge_paths(gauge):
    widget = gauge
    widget.lowRange = 0
    widget.highRange = 10
    widget.encoder_num_mask = "000"
    widget.encoder_num_string = "000"
    widget.encoder_num_digit = 1
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_selectors = {"0": {"0": []}, "1": {"0": ["0"]}}

    widget.set_encoder_value()

    assert widget.encoder_num_digit == 2
    assert widget.encoder_num_digit_options == []

    widget.encoder_num_selectors = {"0": {"0": ["0", "1"]}}
    widget.encoder_num_string = "00"
    widget.encoder_num_digit = 1
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_confirmed = False
    widget.set_encoder_value(clicked=False)
    assert widget.encoder_num_confirmed is False

    widget.encoder_num_digit_options = ["0", "1", "2"]
    widget.encoder_num_digit_selected = 1
    widget.set_encoder_value = mock.Mock()
    assert widget.enc_changed(1) is True
    assert widget.encoder_num_digit_selected == 2
    assert widget.enc_changed(-1) is True
    assert widget.encoder_num_digit_selected == 1


def test_encoder_mask_click_and_digit_skip_edges(gauge):
    widget = gauge
    widget.encoder_num_mask = "00"
    widget.encoder_num_string = "00"
    widget.encoder_num_digit = 0
    widget.encoder_num_confirmed = False
    widget.encoder_num_require_confirm = False

    def confirm_selection(clicked=False):
        assert clicked is True
        widget.encoder_num_confirmed = True

    widget.set_encoder_value = mock.Mock(side_effect=confirm_selection)

    assert widget.enc_clicked() is False
    assert widget.encoder_revert is False

    widget.encoder_num_digit = 0
    widget.encoder_num_confirmed = False
    widget.encoder_revert = True
    widget.set_encoder_value = mock.Mock()

    assert widget.enc_clicked() is True
    assert widget.encoder_revert is True

    widget.set_encoder_value = abstract.AbstractGauge.set_encoder_value.__get__(
        widget,
        abstract.AbstractGauge,
    )
    widget.encoder_num_mask = "00"
    widget.encoder_num_string = "00"
    widget.encoder_num_digit = 0
    widget.encoder_num_digit_selected = 0
    widget.allowed_digits = mock.Mock(side_effect=[[], []])

    widget.set_encoder_value()

    assert widget.encoder_num_digit == 1
    assert widget.encoder_num_digit_options == []

    widget.encoder_num_mask = "00"
    widget.encoder_num_string = "00"
    widget.encoder_num_digit = 1
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_confirmed = False
    widget.allowed_digits = mock.Mock(return_value=["1", "2"])

    widget.set_encoder_value(clicked=False)

    assert widget.encoder_num_string == "01"
    assert widget.encoder_num_confirmed is False

    widget.encoder_num_string = "00"
    widget.encoder_num_digit = 0
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_confirmed = False
    widget.allowed_digits = mock.Mock(side_effect=[["0"], ["5"]])

    widget.set_encoder_value()

    assert widget.encoder_num_string == "05"
    assert widget.encoder_num_confirmed is True


def test_encoder_simple_non_realtime_and_clipped_mask_click(gauge, fix):
    widget = gauge
    widget.dbkey = "NUMOK"
    widget.encoder_multiplier = 5
    widget.encoder_set_real_time = False
    widget.enc_select()
    start_value = widget.encoder_set_value

    assert widget.enc_changed(1) is True
    assert widget.encoder_set_value == start_value + 5
    assert fix.db.get_item("NUMOK").value == start_value

    widget.encoder_num_mask = "000.0"
    widget.encoder_num_string = "999.9"
    widget.encoder_num_digit = len(widget.encoder_num_mask) - 1
    widget.encoder_num_digit_options = ["9"]
    widget.encoder_num_digit_selected = 0
    widget.encoder_num_require_confirm = False
    widget.encoder_num_confirmed = False
    widget.clipping = True
    widget.lowRange = 0
    widget.highRange = 100

    assert widget.enc_clicked() is False
    assert widget.encoder_set_value == 100


def test_frequency_channel_rounding_and_integer_selection(gauge):
    widget = gauge

    assert widget.freq_to_channel(121.500) == pytest.approx(121.505)
    assert widget.freq_to_channel(121.507) == pytest.approx(121.505)

    widget.lowRange = 1
    widget.highRange = 3
    widget.encoder_multiplier = 1
    widget.encoder_num_mask = "00"
    widget.decimal_places = 0
    widget.calculate_selections()

    assert widget.encoder_num_selectors["0"] == ["1", "2", "3"]

    widget.lowRange = 118.0
    widget.highRange = 118.025
    widget.encoder_multiplier = 0.005
    widget.encoder_num_mask = "000.000"
    widget.decimal_places = 3
    widget.encoder_num_8khz_channels = True
    widget.calculate_selections()

    assert "1" in widget.encoder_num_selectors
