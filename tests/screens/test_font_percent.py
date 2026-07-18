"""font_percent accepts a whole-number percent or a legacy decimal fraction.

normalize_font_percent is the single source of truth used by both the
constructor path (screenbuilder_preferences.apply_preferences) and the
option-apply path (screenbuilder_options.apply_options).
"""

import pytest

from pyefis.screens.screenbuilder_preferences import normalize_font_percent


@pytest.mark.parametrize("value,expected", [
    (40, 0.40),      # whole-number percent
    (90, 0.90),
    (100, 1.00),     # full height as a percent
    (0.40, 0.40),    # legacy decimal fraction is unchanged
    (0.90, 0.90),
    (1.0, 1.0),      # boundary: 1.0 stays a fraction (100%), not 1%
    (None, None),    # unset -> let the widget use its own default
])
def test_normalize_font_percent(value, expected):
    assert normalize_font_percent(value) == expected
