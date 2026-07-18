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

"""Pre-configured element groups for the editor palette (issue #68).

A group is a cluster of instruments dragged in as one unit -- e.g. a 4-cylinder
CHT/EGT bar cluster -- that scales as a group and can be ungrouped into its
individual instruments for editing. Each group has a local grid; the editor
maps it onto the placed box and (on ungroup) flattens the children to absolute
positions.

These are hand-authored to match the patterns in the shipped pyEfis includes
(includes/bars/vertical/4_CHT.yaml etc.). Auto-generating the catalog from
those include files (with ganged expansion + preferences resolution) is the
productization tracked in #68.
"""

import json

_GRID = {"rows": 100, "columns": 100}


def _bars(keys, row=2, height=96):
    """N vertical bar gauges evenly spaced across the 100-wide local grid."""
    n = len(keys)
    cell = 100.0 / n
    bar = cell * 0.78
    out = []
    for i, key in enumerate(keys):
        out.append({
            "type": "vertical_bar_gauge",
            "row": row,
            "column": round(i * cell + (cell - bar) / 2, 1),
            "span": {"rows": height, "columns": round(bar, 1)},
            "options": {"dbkey": key, "name": str(i + 1)},
        })
    return out


def _combo(cht, egt):
    """CHT row (top half) + EGT row (bottom half)."""
    return _bars(cht, row=2, height=46) + _bars(egt, row=52, height=46)


GROUPS = [
    {"id": "cht-4cyl", "label": "CHT — 4 cyl", "category": "engine",
     "grid": _GRID, "defaultSpan": {"rows": 45, "columns": 55},
     "instruments": _bars(["CHT11", "CHT12", "CHT13", "CHT14"])},
    {"id": "egt-4cyl", "label": "EGT — 4 cyl", "category": "engine",
     "grid": _GRID, "defaultSpan": {"rows": 45, "columns": 55},
     "instruments": _bars(["EGT11", "EGT12", "EGT13", "EGT14"])},
    {"id": "cht-2cyl", "label": "CHT — 2 cyl", "category": "engine",
     "grid": _GRID, "defaultSpan": {"rows": 45, "columns": 30},
     "instruments": _bars(["CHT11", "CHT12"])},
    {"id": "egt-2cyl", "label": "EGT — 2 cyl", "category": "engine",
     "grid": _GRID, "defaultSpan": {"rows": 45, "columns": 30},
     "instruments": _bars(["EGT11", "EGT12"])},
    {"id": "engine-4cyl", "label": "Engine — 4 cyl (CHT+EGT)", "category": "engine",
     "grid": _GRID, "defaultSpan": {"rows": 60, "columns": 55},
     "instruments": _combo(["CHT11", "CHT12", "CHT13", "CHT14"],
                           ["EGT11", "EGT12", "EGT13", "EGT14"])},
]


def build_groups():
    return {"version": 1, "groups": GROUPS}


def to_json(indent=2):
    return json.dumps(build_groups(), indent=indent)
