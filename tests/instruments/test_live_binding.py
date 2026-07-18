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

"""The control-bindings read side (docs/control_bindings.md, Phase 1), proven on
the moving map: a control writes a FIX key, the widget derives the setting. The
range case uses the real ``changeValueWrap`` the button's "change value wrap"
action calls, so this is the end-to-end "cycle the map range with a button" path
minus the button widget itself."""

import pytest

import pyefis.hmi.functions as functions
from pyefis.instruments.map import MovingMap


def _define(fix, key, dtype, mn, mx, value):
    fix.db.define_item(key, key, dtype, mn, mx, "", 50000, "")
    fix.db.set_value(key, value)
    item = fix.db.get_item(key)
    item.bad = False
    item.fail = False
    return item


@pytest.fixture
def bound_map(fix, qtbot):
    # range_ladder has 7 steps, so the index key spans 0..7 (max = len): the
    # changeValueWrap span (max-min) is then 7 and wrap cycles all 7 indices.
    _define(fix, "MAPRANGE", "int", 0, 7, 0)
    _define(fix, "MAPORIENT", "int", 0, 2, 0)
    fix.db.define_item("MAPTERRAIN", "MAPTERRAIN", "bool",
                       None, None, "", 50000, "")
    fix.db.set_value("MAPTERRAIN", True)
    fix.db.get_item("MAPTERRAIN").bad = False
    fix.db.get_item("MAPTERRAIN").fail = False

    m = MovingMap(None)
    qtbot.addWidget(m)
    m.range_key = "MAPRANGE"
    m.orientation_key = "MAPORIENT"
    m.terrain_key = "MAPTERRAIN"
    m.init_live_bindings(m._live_binding_specs())
    return m, fix


def test_seed_writes_config_default_to_key(bound_map):
    """Phase 1 startup policy: the config default seeds the key. range_nm=10 is
    ladder index 2, so the key reads 2 and the setting stays 10."""
    m, fix = bound_map
    assert fix.db.get_item("MAPRANGE").value == 2
    assert m.range_nm == 10.0


def test_range_follows_key_and_clamps(bound_map):
    m, fix = bound_map
    fix.db.set_value("MAPRANGE", 0)
    assert m.range_nm == 2
    fix.db.set_value("MAPRANGE", 4)
    assert m.range_nm == 40
    fix.db.set_value("MAPRANGE", 99)   # out of range -> clamp to last step
    assert m.range_nm == 160


def test_change_value_wrap_cycles_all_steps(bound_map):
    """The button's 'change value wrap' verb -> functions.changeValueWrap. It must
    step the range through every ladder entry and wrap 160 -> 2."""
    m, fix = bound_map
    fix.db.set_value("MAPRANGE", 0)
    seen = []
    for _ in range(8):
        seen.append(m.range_nm)
        functions.changeValueWrap("MAPRANGE,1")
    assert seen == [2, 5, 10, 20, 40, 80, 160, 2]


def test_orientation_enum_binding(bound_map):
    m, fix = bound_map
    fix.db.set_value("MAPORIENT", 1)
    assert m.orientation == "north_up"
    fix.db.set_value("MAPORIENT", 0)
    assert m.orientation == "track_up"


def test_unbound_setting_stays_static(fix, qtbot):
    """No <x>_key set -> no subscription; the setting keeps its config value and
    is untouched by the (unrelated) key traffic."""
    m = MovingMap(None)
    qtbot.addWidget(m)
    m.init_live_bindings(m._live_binding_specs())
    assert m.range_nm == 10.0
    assert not m._live_binds
