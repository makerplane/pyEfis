"""
Headless unit tests for pyefis.screens.screenbuilder.Screen.

Tests verify that init_screen() correctly:
  - Populates the instruments dict from a YAML layout
  - Handles disabled instruments
  - Handles static_text, heading_display, and value_text instrument types

All tests run in the offscreen Qt platform (no physical display required).
The pyavtools.fix mock from conftest.py is used so no FIX server is needed.
"""
import pytest
import time
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

import pyefis.hmi as hmi
from pyefis.screens import screenbuilder
from pyefis.screens.screenbuilder import Screen


# ── Minimal QWidget parent ────────────────────────────────────────────────────

class _TestParent(QWidget):
    """A real QWidget with the interface that screenbuilder.Screen needs."""

    def __init__(self, screen_config: dict, config_path: str = "", preferences=None):
        super().__init__()
        self._screen_config = screen_config
        self.config_path = config_path
        self.nodeID = 1
        self.preferences = {
            "style": {"basic": True, "dseg": False, "segmented": False, "ghost": False},
            "styles": {},
            "gauges": {},
            "enabled": {},
            "includes": {},
            "buttons": {},
        }
        if preferences:
            for key, value in preferences.items():
                if isinstance(value, dict) and isinstance(self.preferences.get(key), dict):
                    self.preferences[key].update(value)
                else:
                    self.preferences[key] = value

    def get_config_item(self, child, key):
        return self._screen_config.get(key)

    def getRunningScreen(self):
        return "TEST"

    def palette(self):
        return super().palette()


# ── Minimal config helpers ────────────────────────────────────────────────────

_MINIMAL_LAYOUT = {
    "rows": 10,
    "columns": 10,
}


def _config_with_instruments(instruments: list) -> dict:
    return {
        "layout": _MINIMAL_LAYOUT,
        "instruments": instruments,
        "encoder": None,
        "encoder_button": None,
        "encoder_timeout": None,
    }


@pytest.fixture(autouse=True)
def hmi_actions():
    """Real HMI signal object used by widgets that subscribe during construction."""
    hmi.initialize({})
    yield


class _SelectableWidget(QWidget):
    """Small real QWidget used to exercise Screen's encoder routing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_calls = []
        self.changed_calls = []
        self.clicked_calls = 0
        self.select_calls = 0
        self.changed_return = False
        self.clicked_return = False
        self.select_return = False

    def enc_selectable(self):
        return True

    def enc_highlight(self, onoff):
        self.highlight_calls.append(onoff)

    def enc_changed(self, value):
        self.changed_calls.append(value)
        return self.changed_return

    def enc_clicked(self):
        self.clicked_calls += 1
        return self.clicked_return

    def enc_select(self):
        self.select_calls += 1
        return self.select_return


class _RatioWidget(QWidget):
    """Small real QWidget used to verify layout math without a gauge dependency."""

    def __init__(self, parent=None, ratio=1):
        super().__init__(parent)
        self.ratio = ratio
        self.setup_gauge_calls = 0

    def getRatio(self):
        return self.ratio

    def setupGauge(self):
        self.setup_gauge_calls += 1


class _FakeTimer:
    def __init__(self, interval):
        self.interval = interval
        self.callbacks = []
        self.started = False

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def start(self):
        self.started = True


class _FakeSchedulerState:
    def __init__(self):
        self.timers = []

    def getTimer(self, interval):
        for timer in self.timers:
            if timer.interval == interval:
                return timer
        return None


class _FakeSchedulerModule:
    IntervalTimer = _FakeTimer

    def __init__(self):
        self.scheduler = _FakeSchedulerState()
        self.initialized = False

    def initialize(self):
        self.initialized = True


class _FakeWeston(QWidget):
    """Captures Weston construction arguments without starting an external compositor."""

    calls = []

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self.kwargs = kwargs
        self.calls.append(kwargs)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestScreenBuilderInit:

    def test_empty_screen_no_instruments(self, fix, qtbot):
        """A screen with an empty instrument list initialises without error."""
        config = _config_with_instruments([])
        parent = _TestParent(config)

        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert screen.init is True
        assert len(screen.instruments) == 0

    def test_static_text_instrument_loaded(self, fix, qtbot):
        """A static_text instrument populates instruments dict at index 0."""
        config = _config_with_instruments([
            {
                "type": "static_text",
                "row": 0,
                "column": 0,
                "options": {"text": "MAOS"},
            }
        ])
        parent = _TestParent(config)

        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert screen.init is True
        assert 0 in screen.instruments

    def test_instrument_count_matches_config(self, fix, qtbot):
        """Three instruments → instruments dict has three entries."""
        config = _config_with_instruments([
            {"type": "static_text", "row": 0, "column": 0,
             "options": {"text": "A"}},
            {"type": "static_text", "row": 0, "column": 5,
             "options": {"text": "B"}},
            {"type": "static_text", "row": 5, "column": 0,
             "options": {"text": "C"}},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert len(screen.instruments) == 3

    def test_disabled_bool_true_instrument_skipped(self, fix, qtbot):
        """An instrument with disabled: true is not added to instruments."""
        config = _config_with_instruments([
            {"type": "static_text", "row": 0, "column": 0,
             "options": {"text": "Visible"}},
            {"type": "static_text", "row": 0, "column": 5,
             "disabled": True,
             "options": {"text": "Hidden"}},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert len(screen.instruments) == 1

    def test_disabled_bool_false_instrument_included(self, fix, qtbot):
        """An instrument with disabled: false is included."""
        config = _config_with_instruments([
            {"type": "static_text", "row": 0, "column": 0,
             "disabled": False,
             "options": {"text": "Visible"}},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert len(screen.instruments) == 1

    def test_heading_display_instrument_loaded(self, fix, qtbot):
        """A heading_display instrument is created and added to instruments."""
        config = _config_with_instruments([
            {"type": "heading_display", "row": 0, "column": 0},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert 0 in screen.instruments
        # Verify it's not None — was instantiated
        assert screen.instruments[0] is not None

    def test_value_text_instrument_loaded(self, fix, qtbot):
        """A value_text instrument is created and added to instruments."""
        config = _config_with_instruments([
            {"type": "value_text", "row": 0, "column": 0},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert 0 in screen.instruments
        assert screen.instruments[0] is not None

    def test_init_flag_is_false_before_init_screen(self, fix, qtbot):
        """init attribute starts False and is set True by init_screen()."""
        config = _config_with_instruments([])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        assert screen.init is False
        screen.init_screen()
        assert screen.init is True

    def test_wind_display_instrument_loaded(self, fix, qtbot):
        """A wind_display instrument is created and added to instruments."""
        config = _config_with_instruments([
            {"type": "wind_display", "row": 0, "column": 0},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()

        assert 0 in screen.instruments
        assert screen.instruments[0] is not None

    def test_initscreen_idempotent_via_resize(self, fix, qtbot):
        """Calling initScreen() twice (via resize) does not raise an exception."""
        config = _config_with_instruments([
            {"type": "static_text", "row": 0, "column": 0,
             "options": {"text": "MAOS"}},
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.init_screen()
        # A second call to init_screen when already init should be safe
        screen.initScreen()  # This is the public alias that guards with `if not self.init`
        assert screen.init is True

    @pytest.mark.parametrize(
        "instrument",
        [
            {"type": "airspeed_dial", "row": 0, "column": 0},
            {"type": "airspeed_box", "row": 0, "column": 0},
            {"type": "airspeed_tape", "row": 0, "column": 0},
            {"type": "airspeed_trend_tape", "row": 0, "column": 0},
            {"type": "altimeter_dial", "row": 0, "column": 0},
            {"type": "altimeter_tape", "row": 0, "column": 0},
            {"type": "altimeter_trend_tape", "row": 0, "column": 0},
            {"type": "atitude_indicator", "row": 0, "column": 0},
            {"type": "heading_tape", "row": 0, "column": 0},
            {"type": "horizontal_situation_indicator", "row": 0, "column": 0},
            {"type": "numeric_display", "row": 0, "column": 0},
            {"type": "turn_coordinator", "row": 0, "column": 0},
            {"type": "vsi_dial", "row": 0, "column": 0},
            {"type": "vsi_pfd", "row": 0, "column": 0},
            {"type": "arc_gauge", "row": 0, "column": 0},
            {"type": "horizontal_bar_gauge", "row": 0, "column": 0},
            {"type": "vertical_bar_gauge", "row": 0, "column": 0},
            {
                "type": "button",
                "row": 0,
                "column": 0,
                "options": {"config": "simple.yaml"},
            },
        ],
    )
    def test_common_real_instrument_types_are_constructed(self, fix, qtbot, instrument):
        """Screenbuilder can instantiate the core flight/gauge widgets from config."""
        config = _config_with_instruments([instrument])
        config_path = "tests/data/buttons" if instrument["type"] == "button" else ""
        parent = _TestParent(config, config_path=config_path)
        screen = Screen(parent)
        if instrument["type"] == "button":
            screen.screenName = "TEST"
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert 0 in screen.instruments
        parent_ref = screen.instruments[0].parent
        if callable(parent_ref):
            parent_ref = parent_ref()
        assert parent_ref is screen

    def test_real_listbox_instrument_is_constructed_from_configured_list(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "listbox",
                "row": 0,
                "column": 0,
                "options": {
                    "lists": [
                        {"name": "Radio", "file": "tests/data/listbox/list1.yaml"},
                    ]
                },
            }
        ])
        screen = Screen(_TestParent(config, config_path="."))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.instruments[0].active_list == "Radio"
        assert screen.instruments[0].rows > 0


class TestScreenBuilderIncludes:

    def test_include_file_applies_replacements_and_relative_grid(self, fix, qtbot, tmp_path):
        include_file = tmp_path / "include.yaml"
        include_file.write_text(
            """
instruments:
  - type: static_text
    row: 1
    column: 2
    span:
      rows: 2
      columns: 3
    options:
      text: "{label}-{id}"
""",
            encoding="utf-8",
        )
        config = _config_with_instruments([
            {
                "type": "include,include.yaml",
                "row": 3,
                "column": 4,
                "span": {"rows": 4, "columns": 6},
                "replace": {"label": "ALT"},
            }
        ])
        parent = _TestParent(
            config,
            config_path=str(tmp_path),
            preferences={"includes": {"missing.yaml": None}},
        )
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.instruments[0].text == "ALT-1"
        assert screen.insturment_config[0]["row"] == pytest.approx(3 + (1 * 4 / 3))
        assert screen.insturment_config[0]["column"] == pytest.approx(4 + (2 * 6 / 5))
        assert screen.insturment_config[0]["span"]["rows"] == pytest.approx(2 * 4 / 3)
        assert screen.insturment_config[0]["span"]["columns"] == pytest.approx(3 * 6 / 5)

    def test_include_can_be_resolved_from_preferences(self, fix, qtbot, tmp_path):
        include_file = tmp_path / "aliased.yaml"
        include_file.write_text(
            """
instruments:
  - type: static_text
    row: 0
    column: 0
    options:
      text: Included
""",
            encoding="utf-8",
        )
        config = _config_with_instruments([
            {"type": "include,shared-panel", "row": 0, "column": 0}
        ])
        parent = _TestParent(
            config,
            config_path=str(tmp_path),
            preferences={"includes": {"shared-panel": "aliased.yaml"}},
        )
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.instruments[0].text == "Included"

    def test_nested_include_without_span_contributes_to_parent_scaling(self, fix, qtbot, tmp_path):
        grandchild = tmp_path / "grandchild.yaml"
        grandchild.write_text(
            """
instruments:
  - type: static_text
    row: 1
    column: 1
    span:
      rows: 3
      columns: 2
    options:
      text: Nested
""",
            encoding="utf-8",
        )
        child = tmp_path / "child.yaml"
        child.write_text(
            """
instruments:
  - type: include,grandchild.yaml
    row: 2
    column: 1
""",
            encoding="utf-8",
        )
        config = _config_with_instruments([
            {
                "type": "include,child.yaml",
                "row": 0,
                "column": 0,
                "span": {"rows": 10, "columns": 8},
            }
        ])
        screen = Screen(_TestParent(config, config_path=str(tmp_path)))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.instruments[0].text == "Nested"
        assert screen.calc_includes({"type": "include,child.yaml"}, 10, 8) == [6, 4]
        assert screen.insturment_config[0]["row"] == pytest.approx(4.833333333333334)
        assert screen.insturment_config[0]["column"] == pytest.approx(3.333333333333333)

    def test_missing_include_raises_clear_error(self, fix, qtbot, tmp_path):
        config = _config_with_instruments([
            {"type": "include,missing.yaml", "row": 0, "column": 0}
        ])
        parent = _TestParent(
            config,
            config_path=str(tmp_path),
            preferences={"includes": {"missing.yaml": None}},
        )
        screen = Screen(parent)
        qtbot.addWidget(screen)

        with pytest.raises(Exception, match="Include file 'missing.yaml' not found"):
            screen.init_screen()

    def test_disabled_include_does_not_create_children(self, fix, qtbot, tmp_path):
        include_file = tmp_path / "disabled.yaml"
        include_file.write_text(
            """
instruments:
  - type: static_text
    row: 0
    column: 0
    options:
      text: Hidden
""",
            encoding="utf-8",
        )
        config = _config_with_instruments([
            {"type": "include,disabled.yaml", "disabled": True, "row": 0, "column": 0}
        ])
        parent = _TestParent(config, config_path=str(tmp_path))
        screen = Screen(parent)
        qtbot.addWidget(screen)

        screen.init_screen()

        assert screen.instruments == {}


class TestScreenBuilderPreferencesAndOptions:

    def test_disabled_preference_string_controls_instrument_creation(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "static_text",
                "disabled": "hidden-feature",
                "row": 0,
                "column": 0,
                "options": {"text": "Hidden"},
            },
            {
                "type": "static_text",
                "disabled": "not enabled-feature",
                "row": 0,
                "column": 0,
                "options": {"text": "Also hidden"},
            },
            {
                "type": "static_text",
                "disabled": "shown-feature",
                "row": 0,
                "column": 0,
                "options": {"text": "Visible"},
            },
        ])
        parent = _TestParent(
            config,
            preferences={
                "enabled": {
                    "hidden-feature": False,
                    "enabled-feature": True,
                    "shown-feature": True,
                }
            },
        )
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert [instrument.text for instrument in screen.instruments.values()] == ["Visible"]

    def test_gauge_preferences_and_enabled_styles_are_merged_into_options(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "static_text",
                "preferences": "engine-1",
                "row": 0,
                "column": 0,
                "options": {"text": "EGT"},
            }
        ])
        parent = _TestParent(
            config,
            preferences={
                "style": {"basic": True, "night": True},
                "styles": {
                    "engine": {
                        "basic": {"font_family": "Liberation Sans"},
                    }
                },
                "gauges": {
                    "engine-1": {
                        "font_percent": 0.5,
                        "styles": {"night": {"alignment": "AlignRight"}},
                    }
                },
            },
        )
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        widget = screen.instruments[0]
        assert widget.font_family == "Liberation Sans"
        assert widget.font_percent == 0.5
        assert widget.alignment == "AlignRight"

    def test_temperature_option_configures_numeric_unit_switching(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "numeric_display",
                "row": 0,
                "column": 0,
                "options": {"dbkey": "NUMOK", "temperature": True},
            }
        ])
        parent = _TestParent(config)
        screen = Screen(parent)
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        widget = screen.instruments[0]
        assert widget.unitGroup == "Temperature"
        assert widget.unitsOverride1 == "°F"
        assert widget.unitsOverride2 == "°C"
        assert widget.conversionFunction1(0) == 32

    @pytest.mark.parametrize(
        "option,unit_group,unit1,unit2,converted",
        [
            ("pressure", "Pressure", "inHg", "hPa", pytest.approx(33.863889532610884)),
            ("altitude", "Altitude", "Ft", "M", pytest.approx(0.3047999902464003)),
        ],
    )
    def test_pressure_and_altitude_options_configure_numeric_unit_switching(
        self, fix, qtbot, option, unit_group, unit1, unit2, converted
    ):
        config = _config_with_instruments([
            {
                "type": "numeric_display",
                "row": 0,
                "column": 0,
                "options": {"dbkey": "NUMOK", option: True},
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        widget = screen.instruments[0]
        assert widget.unitGroup == unit_group
        assert widget.unitsOverride1 == unit1
        assert widget.unitsOverride2 == unit2
        assert widget.conversionFunction2(1) == converted

    def test_dbkey_option_sets_plain_attribute_when_widget_has_no_setter(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "static_text",
                "row": 0,
                "column": 0,
                "options": {"text": "Plain", "dbkey": "SYNTHETIC"},
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.instruments[0].dbkey == "SYNTHETIC"

    def test_encoder_order_option_registers_selectable_instrument(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "numeric_display",
                "row": 0,
                "column": 0,
                "options": {"dbkey": "NUMOK", "encoder_order": 2},
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.encoder_list == [{"inst": 0, "order": 2}]

    def test_encoder_order_is_ignored_for_display_state_widgets(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "numeric_display",
                "display_state": 1,
                "row": 0,
                "column": 0,
                "options": {"dbkey": "NUMOK", "encoder_order": 2},
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert screen.encoder_list == []

    def test_unknown_instrument_type_raises_useful_error(self, fix, qtbot):
        config = _config_with_instruments([
            {"type": "flux_capacitor", "row": 0, "column": 0}
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)

        with pytest.raises(ValueError, match="Unknown instrument type 'flux_capacitor'"):
            screen.init_screen()

    def test_button_without_config_raises_useful_error(self, fix, qtbot):
        config = _config_with_instruments([
            {"type": "button", "row": 0, "column": 0, "options": {}}
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)

        with pytest.raises(ValueError, match="button must specify options: config:"):
            screen.init_screen()

    def test_lookup_and_default_helpers_document_current_defaults(self, fix, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)

        assert screen.lookup_mapping("IAS", {"IAS": "Airspeed"}) == "Airspeed"
        assert screen.lookup_mapping("ALT", {"IAS": "Airspeed"}) == "ALT"
        assert screen.get_instrument_defaults("airspeed_box") == ["IAS", "GS", "TAS"]
        assert screen.get_instrument_defaults("heading_tape") == ["HEAD"]
        assert screen.get_instrument_defaults("turn_coordinator") == ["ROT", "ALAT"]
        assert screen.get_instrument_default_options("heading_display") == {"font_size": 17}
        assert screen.get_instrument_default_options("static_text") is False
        assert screen.signal_mapping({}) is None


class TestScreenBuilderLayout:

    def test_grid_coordinates_honor_margins(self, fix, qtbot):
        config = _config_with_instruments([])
        config["layout"] = {
            "rows": 10,
            "columns": 20,
            "margin": {"top": 10, "bottom": 20, "left": 5, "right": 15},
        }
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(1000, 500)
        screen.layout = config["layout"]

        top, left, right, bottom = screen.get_grid_margins()
        grid_x, grid_y, grid_width, grid_height = screen.get_grid_coordinates(2, 3)

        assert (top, left, right, bottom) == pytest.approx((50, 25, 75, 100))
        assert (grid_x, grid_y, grid_width, grid_height) == pytest.approx((115, 155, 45, 35))

    def test_grid_layout_applies_span_shrink_and_justification(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "static_text",
                "row": 0,
                "column": 0,
                "span": {"rows": 2, "columns": 4},
                "move": {"shrink": 50, "justify": ["right", "bottom"]},
                "options": {"text": "Sized"},
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(1000, 500)

        screen.init_screen()

        assert screen.instruments[0].geometry().getRect() == (200, 50, 200, 50)

    def test_grid_layout_raises_for_invalid_shrink(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "static_text",
                "row": 0,
                "column": 0,
                "move": {"shrink": 100},
                "options": {"text": "Bad"},
            }
        ])
        config["layout"] = {"rows": 1, "columns": 1}
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(1000, 500)

        with pytest.raises(Exception, match="shrink must be a valid number"):
            screen.init_screen()

    def test_grid_layout_centers_ratio_limited_widgets_and_calls_setup(self, fix, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)
        screen.resize(300, 100)
        screen.layout = {"rows": 1, "columns": 1}
        widget = _RatioWidget(screen, ratio=1)
        screen.instruments = {0: widget}
        screen.insturment_config = {0: {"type": "ratio_widget", "row": 0, "column": 0}}

        screen.grid_layout()

        assert widget.geometry().getRect() == (100, 0, 100, 100)
        assert widget.setup_gauge_calls == 1

    @pytest.mark.parametrize(
        "width,height,ratio,expected",
        [
            (100, 300, 2, (100, 50, 10, 145)),
            (300, 100, 2, (200, 100, 60, 20)),
        ],
    )
    def test_get_bounding_box_keeps_requested_ratio(self, fix, qtbot, width, height, ratio, expected):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)

        assert screen.get_bounding_box(width, height, 10, 20, ratio) == pytest.approx(expected)

    def test_resize_event_reflows_only_when_width_and_height_change(self, fix, qtbot):
        config = _config_with_instruments([
            {"type": "static_text", "row": 0, "column": 0, "options": {"text": "Resize"}}
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(100, 100)
        screen.init_screen()
        screen.grid_layout_calls = 0
        original_grid_layout = screen.grid_layout

        def counted_grid_layout():
            screen.grid_layout_calls += 1
            original_grid_layout()

        screen.grid_layout = counted_grid_layout

        screen.resize(200, 100)
        screen.resizeEvent(None)
        assert screen.grid_layout_calls == 0

        screen.resize(300, 200)
        screen.resizeEvent(None)
        assert screen.grid_layout_calls == 1

    def test_horizontal_ganged_layout_places_grouped_widgets(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "ganged_static_text",
                "gang_type": "horizontal",
                "row": 0,
                "column": 0,
                "span": {"rows": 1, "columns": 1},
                "groups": [
                    {"instruments": [{"options": {"text": "A"}}]},
                    {"instruments": [{"options": {"text": "B"}}]},
                ],
            }
        ])
        config["layout"] = {"rows": 1, "columns": 1}
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(400, 100)

        screen.init_screen()

        assert [screen.instruments[index].text for index in range(2)] == ["A", "B"]
        assert screen.instruments[0].geometry().getRect() == (0, 0, 196, 100)
        assert screen.instruments[1].geometry().getRect() == (204, 0, 196, 100)

    def test_vertical_ganged_layout_places_grouped_widgets(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "ganged_static_text",
                "gang_type": "vertical",
                "row": 0,
                "column": 0,
                "span": {"rows": 1, "columns": 1},
                "groups": [
                    {"instruments": [{"options": {"text": "Top"}}]},
                    {"instruments": [{"options": {"text": "Bottom"}}]},
                ],
            }
        ])
        config["layout"] = {"rows": 1, "columns": 1}
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(400, 100)

        screen.init_screen()

        assert [screen.instruments[index].text for index in range(2)] == ["Top", "Bottom"]
        assert screen.instruments[0].geometry().getRect() == (0, 0, 400, 47)
        assert screen.instruments[1].geometry().getRect() == (0, 53, 400, 47)

    def test_ganged_instrument_requires_gang_type(self, fix, qtbot):
        config = _config_with_instruments([
            {
                "type": "ganged_static_text",
                "row": 0,
                "column": 0,
                "groups": [{"instruments": [{"options": {"text": "A"}}]}],
            }
        ])
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)

        with pytest.raises(Exception, match="must also have 'gang_type:'"):
            screen.init_screen()

    def test_draw_grid_creates_overlay_that_can_render(self, fix, qtbot):
        config = _config_with_instruments([])
        config["layout"] = {
            "rows": 20,
            "columns": 20,
            "draw_grid": True,
            "margin": {"top": 5, "bottom": 5, "left": 5, "right": 5},
        }
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(400, 240)

        screen.init_screen()
        pixmap = QPixmap(screen.grid.size())
        pixmap.fill()
        screen.grid.render(pixmap)

        assert screen.grid.geometry().getRect() == (0, 0, 400, 240)
        assert screen.grid.textRect.width() > 0


class TestScreenBuilderExternalWidgets:

    @pytest.mark.parametrize(
        "instrument,expected",
        [
            (
                {
                    "type": "weston",
                    "row": 1,
                    "column": 2,
                    "span": {"rows": 2, "columns": 3},
                    "options": {
                        "socket": "wayland-test",
                        "ini": "weston.ini",
                        "command": "waydroid",
                        "args": ["show-full-ui"],
                    },
                },
                {"wide": 240, "high": 96},
            ),
            (
                {
                    "type": "weston",
                    "row": 0,
                    "column": 0,
                    "options": {
                        "socket": "wayland-test",
                        "ini": "weston.ini",
                        "command": "waydroid",
                        "args": [],
                    },
                },
                {},
            ),
        ],
    )
    def test_weston_config_is_translated_without_launching_weston(
        self, fix, qtbot, monkeypatch, instrument, expected
    ):
        _FakeWeston.calls = []
        monkeypatch.setattr(screenbuilder.weston, "Weston", _FakeWeston)
        config = _config_with_instruments([instrument])
        screen = Screen(_TestParent(config, config_path=str(Path.cwd())))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        kwargs = _FakeWeston.calls[0]
        assert kwargs["socket"] == "wayland-test"
        assert kwargs["ini"].endswith("weston.ini")
        assert kwargs["command"] == "waydroid"
        assert kwargs["args"] == instrument["options"]["args"]
        for key, value in expected.items():
            assert kwargs[key] == value


class TestScreenBuilderDisplayStates:

    def test_display_state_timer_groups_visibility_and_callbacks(self, fix, qtbot, monkeypatch):
        fake_scheduler = _FakeSchedulerModule()
        monkeypatch.setattr(screenbuilder, "scheduler", fake_scheduler)
        config = _config_with_instruments([
            {
                "type": "static_text",
                "display_state": 1,
                "row": 0,
                "column": 0,
                "options": {"text": "State 1"},
            },
            {
                "type": "static_text",
                "display_state": 2,
                "row": 0,
                "column": 0,
                "options": {"text": "State 2"},
            },
        ])
        config["layout"] = {"rows": 10, "columns": 10, "display_state": {"interval": 250, "states": 2}}
        screen = Screen(_TestParent(config))
        qtbot.addWidget(screen)
        screen.resize(800, 480)

        screen.init_screen()

        assert fake_scheduler.initialized is True
        assert screen.timer.callbacks == [screen.change_display_states]
        assert screen.display_state_inst[1] == [0]
        assert screen.display_state_inst[2] == [1]
        assert screen.instruments[0].isHidden() is False
        assert screen.instruments[1].isHidden() is True

        screen.change_display_states()

        assert screen.display_state_current == 2
        assert screen.instruments[0].isHidden() is True
        assert screen.instruments[1].isHidden() is False

    def test_change_display_states_is_noop_with_less_than_two_states(self, fix, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)
        screen.display_states = 1
        screen.display_state_current = 1

        screen.change_display_states()

        assert screen.display_state_current == 1


class TestScreenBuilderEncoder:

    def _screen_with_encoder_widgets(self, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)
        screen.resize(800, 480)
        screen.show()
        qtbot.waitExposed(screen)
        screen.isVisible = lambda: True
        widgets = [_SelectableWidget(screen), _SelectableWidget(screen)]
        screen.instruments = {0: widgets[0], 1: widgets[1]}
        screen.encoder_list_sorted = [0, 1]
        screen.encoder_current_selection = 0
        screen.encoder_timeout = 10_000
        screen.encoder_timestamp = time.time_ns() // 1_000_000
        screen.encoder_control = False
        return screen, widgets

    def test_encoder_moves_highlight_to_next_enabled_widget(self, fix, qtbot):
        screen, widgets = self._screen_with_encoder_widgets(qtbot)

        screen.encoderChanged(1)

        assert screen.encoder_current_selection == 1
        assert widgets[0].highlight_calls == [False]
        assert widgets[1].highlight_calls == [True]
        assert screen.encoder_timer.isActive() is True

    def test_encoder_skips_disabled_widgets(self, fix, qtbot):
        screen, widgets = self._screen_with_encoder_widgets(qtbot)
        widgets[1].setEnabled(False)

        screen.encoderChanged(1)

        assert screen.encoder_current_selection == 0
        assert widgets[0].highlight_calls == [False, True]
        assert widgets[1].highlight_calls == []

    def test_encoder_timeout_clears_highlight_and_control(self, fix, qtbot):
        screen, widgets = self._screen_with_encoder_widgets(qtbot)
        screen.encoder_timestamp = 1
        screen.encoder_control = True

        screen.encoderChanged(0)

        assert widgets[0].highlight_calls == [False]
        assert screen.encoder_control is False
        assert screen.encoder_timestamp == 0

    def test_encoder_button_transfers_and_releases_control(self, fix, qtbot):
        screen, widgets = self._screen_with_encoder_widgets(qtbot)
        widgets[0].select_return = True
        widgets[0].changed_return = False

        screen.encoderButtonChanged(True)
        screen.encoderChanged(2)

        assert widgets[0].select_calls == 1
        assert widgets[0].changed_calls == [2]
        assert widgets[0].highlight_calls == [False]
        assert screen.encoder_control is False

    def test_encoder_button_ignores_clicks_when_screen_is_hidden(self, fix, qtbot):
        screen, widgets = self._screen_with_encoder_widgets(qtbot)
        screen.isVisible = lambda: False

        screen.encoderButtonChanged(True)

        assert widgets[0].select_calls == 0


class TestScreenBuilderClose:

    def test_close_event_closes_each_instrument(self, fix, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)
        widgets = [_SelectableWidget(screen), _SelectableWidget(screen)]
        screen.instruments = {0: widgets[0], 1: widgets[1]}
        for widget in widgets:
            widget.closed = False
            widget.close = lambda checked_widget=widget: setattr(checked_widget, "closed", True)

        screen.closeEvent(None)

        assert [widget.closed for widget in widgets] == [True, True]

    def test_close_event_logs_instrument_close_failures(self, fix, qtbot, caplog):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)
        widget = _SelectableWidget(screen)

        def close_with_error():
            raise RuntimeError("close failed")

        widget.close = close_with_error
        screen.instruments = {7: widget}

        screen.closeEvent(None)

        assert "Error closing instrument 7" in caplog.text

    def test_close_event_before_init_is_safe(self, fix, qtbot):
        screen = Screen(_TestParent(_config_with_instruments([])))
        qtbot.addWidget(screen)

        screen.closeEvent(None)
