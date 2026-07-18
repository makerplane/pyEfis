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

"""Phase 1: read-only visual screen preview for the configuration manager.

Resolves a screen-builder screen to positioned instruments (pyefis.editor.
resolver), renders each one to a thumbnail with the Phase 0 render service
(tools/render_instrument.py -- GL/SVS widgets become placeholders), and emits a
self-contained HTML page that draws the normalised grid with each thumbnail in
its slot, in z-order. Open the HTML in a browser to see the screen.

Usage (from the repo root)::

    python tools/build_screen_preview.py                       # PFD_AI_ONLY
    python tools/build_screen_preview.py --screen PFD --width 1200
    python tools/build_screen_preview.py --config-root <tree> --out work/preview
"""

import argparse
import html
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src"),
           os.path.join(_REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pyefis.editor import resolver  # noqa: E402
import render_instrument as ri  # noqa: E402  (sibling tool: safe_render)

_MIN_PX, _MAX_PX = 8, 1200


def _clamp(value):
    return max(_MIN_PX, min(_MAX_PX, int(round(value))))


def build_preview(config_root, screen_name, width, out_dir):
    resolved = resolver.resolve_screen(config_root, screen_name)
    layout = resolved["layout"]
    canvas_w, canvas_h = resolver.canvas_size(layout, width)
    placed = resolver.place(layout, resolved["instruments"], canvas_w, canvas_h)

    assets = os.path.join(out_dir, "assets")
    os.makedirs(assets, exist_ok=True)

    tiles = []
    for index, inst in enumerate(placed):
        rect = inst["rect"]
        fname = f"{index:02d}_{inst['type']}.png"
        kind, _path = ri.safe_render(
            inst["type"], options=inst.get("options"),
            width=_clamp(rect["w"]), height=_clamp(rect["h"]),
            out_path=os.path.join(assets, fname))
        tiles.append((inst, rect, fname, kind))
        print(f"  [{index:02d}] {inst['type']:<22} {kind:<11} {fname}")

    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(_render_html(screen_name, layout, canvas_w, canvas_h, tiles))

    # Machine-readable manifest so a browser (the configurator web app) can
    # render the same grid client-side from static assets.
    manifest = {
        "screen": screen_name,
        "grid": {"rows": layout["rows"], "columns": layout["columns"]},
        "canvas": {"w": canvas_w, "h": canvas_h},
        "instruments": [
            {
                "type": inst["type"],
                "row": inst.get("row"),
                "column": inst.get("column"),
                "rect": {k: round(v, 1) for k, v in rect.items()},
                "kind": kind,
                "thumb": fname,
            }
            for (inst, rect, fname, kind) in tiles
        ],
    }
    with open(os.path.join(out_dir, "preview.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    return html_path, len(tiles)


def _render_html(screen_name, layout, canvas_w, canvas_h, tiles):
    rows, cols = layout["rows"], layout["columns"]
    parts = []
    for inst, rect, fname, kind in tiles:
        title = (f"{inst['type']}  @ row {inst.get('row')}, col "
                 f"{inst.get('column')}  ({kind})")
        parts.append(
            f'  <div class="inst {kind}" '
            f'style="left:{rect["x"]:.1f}px;top:{rect["y"]:.1f}px;'
            f'width:{rect["w"]:.1f}px;height:{rect["h"]:.1f}px" '
            f'title="{html.escape(title)}">'
            f'<img src="assets/{html.escape(fname)}" alt="{html.escape(inst["type"])}">'
            f'<span class="lbl">{html.escape(inst["type"])}</span></div>')
    instruments_html = "\n".join(parts)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pyEfis preview - {html.escape(screen_name)}</title>
<style>
  body {{ background:#111; color:#ccc; font-family:system-ui,sans-serif; margin:16px; }}
  header {{ margin-bottom:10px; }}
  header b {{ color:#eee; }}
  header small {{ color:#888; }}
  .canvas {{ position:relative; overflow:hidden; background:#000;
             border:1px solid #333; width:{canvas_w}px; height:{canvas_h}px; }}
  .inst {{ position:absolute; outline:1px solid rgba(120,140,160,.30); }}
  .inst img {{ width:100%; height:100%; display:block; }}
  .inst .lbl {{ position:absolute; left:0; top:0; font-size:9px; line-height:1.2;
               background:rgba(0,0,0,.55); color:#9fe6c4; padding:0 2px;
               pointer-events:none; opacity:0; transition:opacity .1s; }}
  .inst:hover .lbl {{ opacity:1; }}
  .inst.placeholder {{ outline-color:rgba(210,170,90,.55); }}
  .inst.fallback {{ outline-color:rgba(210,90,90,.6); }}
  label {{ color:#aaa; font-size:13px; user-select:none; }}
</style>
</head>
<body>
<header>
  <b>{html.escape(screen_name)}</b>
  <small>&middot; grid {rows} rows x {cols} cols &middot; canvas {canvas_w}x{canvas_h}
  &middot; {len(tiles)} instruments &middot; z-order = paint order
  &middot; <span style="color:#d2aa5a">amber outline</span> = placeholder</small>
  <div><label><input type="checkbox" id="labels"> always show labels</label></div>
</header>
<div class="canvas" id="canvas">
{instruments_html}
</div>
<script>
  document.getElementById('labels').addEventListener('change', function (e) {{
    document.querySelectorAll('.inst .lbl').forEach(function (l) {{
      l.style.opacity = e.target.checked ? 1 : '';
    }});
  }});
</script>
</body>
</html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a read-only HTML preview of a pyEfis screen.")
    parser.add_argument(
        "--config-root",
        default=os.path.join(_REPO_ROOT, "src", "pyefis", "config"),
        help="config tree (default: the repo's src/pyefis/config)")
    parser.add_argument("--screen", default="PFD_AI_ONLY",
                        help="screen name (default PFD_AI_ONLY)")
    parser.add_argument("--width", type=int, default=1000,
                        help="canvas width in px (height follows grid aspect)")
    parser.add_argument("--out", default=os.path.join(_REPO_ROOT, "work",
                                                      "preview"),
                        help="output directory (default work/preview)")
    parser.add_argument("--list", action="store_true",
                        help="list screens in the config tree and exit")
    args = parser.parse_args(argv)

    if args.list:
        for name in resolver.list_screens(args.config_root):
            print(name)
        return

    print(f"Resolving {args.screen} from {args.config_root} ...")
    html_path, count = build_preview(
        args.config_root, args.screen, args.width, args.out)
    print(f"\nWrote {html_path} ({count} instruments). Open it in a browser.")


if __name__ == "__main__":
    main()
