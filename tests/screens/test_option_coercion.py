"""apply_options coerces a string config value to the widget attribute's type.

A numeric option delivered as a quoted string (e.g. the configurator code pane
or a quoted YAML scalar like ``minorDiv: '5'``) must not reach the widget as a
str: several AI pitch-ladder options (minorDiv/majorDiv/numberedDiv/
visiblePitchAngle/numberedDivWidth) feed Qt/geometry math that SEGFAULTS -- not
raises -- on a str, which crashes the whole panel. _coerce_to_attr_type converts
the string to the type of the widget's existing (default) attribute.
"""

import pytest

from pyefis.screens.screenbuilder_options import _coerce_to_attr_type


class _Widget:
    def __init__(self):
        self.minorDiv = 5          # int default
        self.pitchOpacity = 0.6    # float default
        self.drawBankMarkers = True  # bool default
        self.aircraft_symbol = "classic"  # str default


@pytest.mark.parametrize("attr,value,expected,kind", [
    ("minorDiv", "5", 5, int),            # int attr <- "5"
    ("minorDiv", "10", 10, int),
    ("minorDiv", "5.0", 5, int),          # tolerant of a float-looking string
    ("pitchOpacity", "0.8", 0.8, float),  # float attr <- "0.8"
    ("drawBankMarkers", "true", True, bool),   # bool attr <- "true"
    ("drawBankMarkers", "false", False, bool),
    ("drawBankMarkers", "0", False, bool),
])
def test_coerces_string_to_attr_type(attr, value, expected, kind):
    w = _Widget()
    out = _coerce_to_attr_type(w, attr, value)
    assert out == expected
    assert type(out) is kind


def test_non_string_passes_through_unchanged():
    w = _Widget()
    assert _coerce_to_attr_type(w, "minorDiv", 7) == 7          # already int
    assert _coerce_to_attr_type(w, "pitchOpacity", 0.4) == 0.4  # already float


def test_string_attr_is_left_as_string():
    w = _Widget()
    # a str-typed attribute (aircraft_symbol) keeps the string value
    assert _coerce_to_attr_type(w, "aircraft_symbol", "garmin") == "garmin"


def test_unknown_or_uncoercible_left_as_is():
    w = _Widget()
    # unknown option (no existing attr) -> passthrough (may warn/no-effect)
    assert _coerce_to_attr_type(w, "no_such_option", "5") == "5"
    # a numeric attr but a non-numeric string -> left as-is (logged), not crash
    assert _coerce_to_attr_type(w, "minorDiv", "abc") == "abc"
