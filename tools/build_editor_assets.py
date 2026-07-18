#!/usr/bin/env python3
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

"""Build the configuration manager's static editor-asset bundle:

    <out>/schema.json            the enriched instrument schema (palette + props)
    <out>/palette/<type>.png     one thumbnail per instrument type

Upload the result to R2 under assets/editor/ (served by the configurator Worker
at /assets/editor/...). This is the pyEfis-side "CI -> R2 bridge": nothing Qt
runs at the edge; the browser editor consumes these static files.

Usage (from the repo root)::

    python tools/build_editor_assets.py --out work/editor_assets
"""

import argparse
import os
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src"),
           os.path.join(_REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pyefis.editor import groups as egroups  # noqa: E402
from pyefis.editor import schema as eschema  # noqa: E402

_RENDER = os.path.join(_REPO_ROOT, "tools", "render_instrument.py")


def _placeholder_svg(out_path, label, w, h):
    """A small labelled placeholder SVG for GL / config-driven types."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="#20242b" '
        f'stroke="#5a6472" stroke-width="2"/>'
        f'<text x="{w // 2}" y="{h // 2}" fill="#c2c9d2" font-family="sans-serif" '
        f'font-size="13" text-anchor="middle" dominant-baseline="middle">'
        f'{label}</text></svg>')
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)


def build(out_dir, width, height):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "schema.json"), "w", encoding="utf-8") as fh:
        fh.write(eschema.to_json() + "\n")
    with open(os.path.join(out_dir, "groups.json"), "w", encoding="utf-8") as fh:
        fh.write(egroups.to_json() + "\n")

    palette_dir = os.path.join(out_dir, "palette")
    os.makedirs(palette_dir, exist_ok=True)

    types = sorted(eschema.build_schema()["instruments"])
    for instrument_type in types:
        out = os.path.join(palette_dir, f"{instrument_type}.svg")
        if os.path.exists(out):
            os.remove(out)
        # One subprocess per type: the SVG export builds a Qt screen, and a
        # fresh process avoids cross-instrument state and keeps a hard crash
        # from taking the whole build down.
        subprocess.run(
            [sys.executable, _RENDER, instrument_type, "--svg", "-o", out,
             "--width", str(width), "--height", str(height)],
            capture_output=True, text=True, timeout=60)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            print(f"  {instrument_type:<34} svg")
        else:
            _placeholder_svg(out, instrument_type, width, height)
            print(f"  {instrument_type:<34} placeholder")
    return len(types)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the editor schema + palette thumbnail bundle.")
    parser.add_argument(
        "--out", default=os.path.join(_REPO_ROOT, "work", "editor_assets"),
        help="output directory (default work/editor_assets)")
    parser.add_argument("--width", type=int, default=220)
    parser.add_argument("--height", type=int, default=150)
    args = parser.parse_args(argv)

    print(f"Building editor assets into {args.out} ...")
    count = build(args.out, args.width, args.height)
    print(f"\nWrote schema.json + {count} palette thumbnails. Upload to R2 "
          f"under assets/editor/.")


if __name__ == "__main__":
    main()
