#  Copyright (c) 2026 Bill Mallard
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Tests for the visual-editor screen resolver (config -> positioned
instruments). Pure config resolution -- no Qt / rendering."""

import os

import pytest

from pyefis.editor import resolver

CONFIG_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "src", "pyefis", "config"))


def test_pfd_ai_only_resolves_to_svs_layout():
    """The SVS-only PFD expands its AHRS include into the expected instrument
    set, with the autopilot/time/HSI instruments absent (per svs.yaml)."""
    result = resolver.resolve_screen(CONFIG_ROOT, "PFD_AI_ONLY")
    types = [i["type"] for i in result["instruments"]]
    assert "virtual_vfr" in types
    assert "airspeed_tape" in types
    assert "altimeter_tape" in types
    # svs.yaml dropped the HSI for this screen.
    assert "horizontal_situation_indicator" not in types
    assert len(result["instruments"]) >= 8


def test_resolved_instruments_have_grid_coords():
    result = resolver.resolve_screen(CONFIG_ROOT, "PFD_AI_ONLY")
    for inst in result["instruments"]:
        assert "row" in inst and "column" in inst
        assert "span" in inst


def test_placement_pixels_within_canvas():
    result = resolver.resolve_screen(CONFIG_ROOT, "PFD_AI_ONLY")
    w, h = resolver.canvas_size(result["layout"], 1000)
    placed = resolver.place(result["layout"], result["instruments"], w, h)
    assert placed
    for inst in placed:
        rect = inst["rect"]
        assert rect["w"] > 0 and rect["h"] > 0
        # Top-left corner lands on the canvas (allow a 1px rounding slack).
        assert -1 <= rect["x"] <= w + 1
        assert -1 <= rect["y"] <= h + 1


def test_unknown_screen_raises():
    with pytest.raises(KeyError):
        resolver.resolve_screen(CONFIG_ROOT, "NO_SUCH_SCREEN")
