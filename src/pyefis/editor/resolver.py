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

"""Resolve a screen-builder screen into a flat list of positioned instruments.

This is the data layer for the visual editor: given a config tree and a screen
name, it produces every instrument the screen will draw with its absolute grid
coordinates -- includes expanded, preferences applied, disabled instruments
dropped. It REUSES the real screen-builder expansion and layout math
(:mod:`pyefis.screens.screenbuilder_config` / ``_layout``) so the preview can
never diverge from what the screen builder actually places, and it imports no
Qt -- resolution is pure config arithmetic, so it runs anywhere (incl. CI)
without a display or the GL stack.

The companion ``tools/build_screen_preview.py`` turns the result into an HTML
preview by rendering each positioned instrument with the Phase 0 render service.
"""

import os

import yaml

import pyefis.cfg as cfg
from pyefis.screens.screenbuilder_config import InstrumentExpander, is_disabled
from pyefis.screens.screenbuilder_layout import get_instrument_geometry


def _deep_merge(base, override):
    """Recursively merge ``override`` into ``base`` (mirrors main.merge_dict)."""
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def assemble_config(config_root):
    """Load + merge preferences and assemble the full config exactly as
    pyefis.main does, so screens resolve their includes/preferences."""
    with open(os.path.join(config_root, "preferences.yaml")) as fh:
        prefs = yaml.safe_load(fh)
    custom = os.path.join(config_root, "preferences.yaml.custom")
    if os.path.exists(custom):
        with open(custom) as fh:
            _deep_merge(prefs, yaml.safe_load(fh) or {})
    config = cfg.from_yaml(os.path.join(config_root, "default.yaml"),
                           preferences=prefs)
    return config, prefs


def list_screens(config_root):
    """Return the names of the screens defined in this config tree."""
    config, _prefs = assemble_config(config_root)
    return sorted(config.get("screens", {}))


def resolve_screen(config_root, screen_name, node_id=1):
    """Resolve ``screen_name`` to ``{"screen", "layout", "instruments"}`` where
    instruments is the flat, include-expanded list, each carrying absolute
    grid ``row``/``column``/``span`` and its ``options``."""
    config, prefs = assemble_config(config_root)
    screens = config.get("screens", {})
    if screen_name not in screens:
        raise KeyError(
            f"screen '{screen_name}' not found; have: {sorted(screens)}")
    screen = screens[screen_name]
    layout = screen["layout"]

    expander = InstrumentExpander(config_root, prefs, node_id, None)
    expander.include_size_calculator = expander.calc_includes

    instruments = []
    for inst in screen.get("instruments", []):
        if is_disabled(inst, prefs):
            continue
        for resolved, _replacements, _state in expander.expand(inst):
            instruments.append(resolved)

    return {"screen": screen_name, "layout": layout, "instruments": instruments}


def place(layout, instruments, width, height):
    """Annotate each instrument with a pixel ``rect`` (x, y, w, h) for a canvas
    of ``width`` x ``height``, using the screen builder's own geometry math.
    Order is preserved -- it is the z-order (later instruments paint on top)."""
    placed = []
    for inst in instruments:
        geom = get_instrument_geometry(layout, width, height, inst, ratio=False)
        placed.append({
            **inst,
            "rect": {
                "x": geom["x"],
                "y": geom["y"],
                "w": geom["render_width"],
                "h": geom["render_height"],
            },
        })
    return placed


def canvas_size(layout, width):
    """Pick a canvas height that matches the grid aspect for a given width."""
    rows = int(layout["rows"])
    cols = int(layout["columns"])
    return width, round(width * rows / cols)
