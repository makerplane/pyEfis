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
from PyQt6.QtWidgets import QApplication, QWidget

from pyefis.screens.screenbuilder import Screen


# ── Minimal QWidget parent ────────────────────────────────────────────────────

class _TestParent(QWidget):
    """A real QWidget with the interface that screenbuilder.Screen needs."""

    def __init__(self, screen_config: dict, config_path: str = ""):
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

    def get_config_item(self, child, key):
        return self._screen_config.get(key)

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
