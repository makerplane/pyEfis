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

"""Single-instrument render service for the End-User Configuration Manager.

Renders ONE screen-builder instrument to a PNG, offscreen, using the real
widget code -- so the editor's palette/canvas thumbnails are faithful without
reimplementing 43 widgets in JS. It wraps the same offscreen path as the
manual screenshot harness (tests/screenshots) plus the in-memory mock FIX
database from the test fixtures, so no fix-gateway is required.

GL / Synthetic Vision widgets (and the weston compositor) do NOT initialise
under the offscreen Qt platform; those, anything carrying an `svs:` option,
unknown types, instruments missing required options, and any render that throws
all fall back to a labelled PLACEHOLDER image -- the service never crashes the
caller, it always returns a PNG.

Usage (run from the repo root)::

    python tools/render_instrument.py airspeed_tape -o asi.png
    python tools/render_instrument.py virtual_vfr -o svs.png          # placeholder
    python tools/render_instrument.py numeric_display \\
        --options '{"dbkey": "VS"}' --seed '{"VS": -350}' -o vs.png
    python tools/render_instrument.py altimeter_tape --width 200 --height 600

Exit status is 0 whether a real render or a placeholder was produced; it prints
which one. This is a dev/companion tool (it imports the test harness), not part
of the shipped runtime.
"""

import argparse
import json
import os
import subprocess
import sys
import time

# Offscreen Qt before any Qt import. Allow an override (e.g. eglfs on the Pi).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Make the repo root (for `tests`) and src (for `pyefis`) importable regardless
# of how the script is invoked.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Patch pyavtools so FIX runs in memory with no server -- exactly as conftest.py
# does, and BEFORE anything imports pyavtools.fix.client.
import tests.mock_db.client  # noqa: E402
import tests.mock_db.scheduler  # noqa: E402

sys.modules["pyavtools.fix.client"] = tests.mock_db.client
sys.modules["pyavtools.scheduler"] = tests.mock_db.scheduler

import pyavtools.fix as fix  # noqa: E402
from PyQt6.QtCore import Qt, QRect  # noqa: E402
from PyQt6.QtGui import (  # noqa: E402
    QColor, QFont, QFontDatabase, QImage, QPainter, QPen,
)
from PyQt6.QtWidgets import QApplication  # noqa: E402

from pyefis.editor import schema as eschema  # noqa: E402

# Core flight values so attitude/tapes/needles render with believable data.
_DEMO_VALUES = {
    "IAS": 110.0, "TAS": 118.0, "GS": 115.0,
    "ALT": 3500.0, "VS": -350.0, "BARO": 29.92, "OAT": 12.0,
    "HEAD": 75.0, "TRACK": 78.0, "COURSE": 80.0, "CDI": 0.3, "GSI": -0.2,
    "PITCH": -2.0, "ROLL": 4.0, "ALAT": 0.05, "ROT": 3.0,
    "LAT": 34.4275, "LONG": -119.8546,
    "HWIND": 9.0, "XWIND": -4.0,
}

# Gauges have no default FIX key (they're generic); without a dbkey they crash
# at the C++ level. When the caller supplies none, inject a demo key (seeded
# with bands in _setup_fix) so the palette still gets a representative render.
_NEEDS_DBKEY = {
    "arc_gauge", "horizontal_bar_gauge", "vertical_bar_gauge", "numeric_display",
}

# Types whose appearance is driven by an external config file (button actions,
# listbox lists) and whose conditions/state aren't meaningful as a standalone
# thumbnail -- always shown as a labelled placeholder in previews.
_CONFIG_DRIVEN = {"button", "listbox"}


def _load_fonts():
    """Register DejaVu under the offscreen platform so text isn't tofu, and
    substitute the families the widgets ask for onto whatever loaded."""
    files = {
        "DejaVu Sans Condensed": [
            "C:/Windows/Fonts/DejaVuSansCondensed.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"],
        "DejaVu Sans": [
            "C:/Windows/Fonts/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    }
    loaded = {}
    for requested, paths in files.items():
        for p in paths:
            if os.path.exists(p):
                fid = QFontDatabase.addApplicationFont(p)
                fams = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
                if fams:
                    loaded[requested] = fams[0]
                break
    for requested, actual in loaded.items():
        if requested != actual:
            QFont.insertSubstitution(requested, actual)
    fallback = loaded.get("DejaVu Sans Condensed") or loaded.get("DejaVu Sans")
    if fallback:
        for missing in ("DSEG14 Classic", "DSEG7 Classic", "DSEG7", "Open Sans"):
            QFont.insertSubstitution(missing, fallback)


def _setup_fix():
    """Initialise the in-memory FIX db, define any requested key on demand, and
    seed demonstrative values."""
    fix.initialize({"main": {"FixServer": "localhost", "FixPort": "3490"}})
    db = fix.db

    # The airspeed widgets read V-speed *aux* values off IAS and build their
    # coloured arcs/bands from them; auto-define can't know those aux names, so
    # define IAS explicitly with the V-speed aux (as conftest.py does) before
    # the generic fallback takes over.
    db.define_item("IAS", "Indicated Airspeed", "float", 0.0, 2000.0, "knots",
                   50000, "Min,Max,V1,V2,Vne,Vfe,Vmc,Va,Vno,Vs,Vs0,Vx,Vy")
    ias = db.get_item("IAS")
    ias.bad = ias.fail = ias.old = False
    for aux, value in (("Vs", 45.0), ("Vs0", 40.0), ("Vno", 125.0),
                       ("Vne", 140.0), ("Vfe", 70.0)):
        ias.set_aux_value(aux, value)

    # A demo gauge key with warning/alarm bands so a dbkey-less gauge still
    # renders a representative thumbnail (a dbkey is injected for those below).
    bands = "Min,Max,lowWarn,lowAlarm,highWarn,highAlarm"
    db.define_item("DEMOGAUGE", "Demo Gauge", "float", 0.0, 100.0, "", 50000,
                   bands)
    demo = db.get_item("DEMOGAUGE")
    db.set_value("DEMOGAUGE", 72.0)
    demo.bad = demo.fail = demo.old = False
    for aux, value in (("Min", 0.0), ("Max", 100.0), ("lowWarn", 20.0),
                       ("lowAlarm", 10.0), ("highWarn", 80.0), ("highAlarm", 90.0)):
        demo.set_aux_value(aux, value)

    if not getattr(db, "_auto_define_installed", False):
        orig = db.get_item

        # Pass *args/**kwargs through: some widgets call get_item(key, True)
        # (the "create if missing" form), and a key-only wrapper would break
        # them with a TypeError.
        def get_item(key, *args, **kwargs):
            try:
                return orig(key, *args, **kwargs)
            except Exception:
                up = str(key).upper()
                is_bool = up.startswith(("TSBTN", "BTN", "EGTBTN")) or "BUTTON" in up
                aux = "" if is_bool else bands
                db.define_item(key, key, "bool" if is_bool else "float",
                               None if is_bool else 0, None if is_bool else 100,
                               "", 50000, aux)
                it = orig(key, *args, **kwargs)
                it.bad = it.fail = it.old = False
                return it

        db.get_item = get_item
        db._auto_define_installed = True

    for key, value in _DEMO_VALUES.items():
        it = db.get_item(key)  # auto-defines if missing
        db.set_value(key, value)
        it.bad = it.fail = it.old = False


def _placeholder(text, width, height, out_path):
    """Write a labelled placeholder PNG (for GL/SVS/unknown/error cases)."""
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(QColor("#20242b"))
    p = QPainter(img)
    pen = QPen(QColor("#5a6472"))
    pen.setWidth(2)
    p.setPen(pen)
    p.drawRect(1, 1, width - 3, height - 3)
    p.setPen(QColor("#c2c9d2"))
    font = QFont("DejaVu Sans Condensed")
    font.setPixelSize(max(11, min(width, height) // 9))
    p.setFont(font)
    p.drawText(QRect(0, 0, width, height),
               Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)
    p.end()
    img.save(out_path)


def _placeholder_reason(instrument_type, options):
    """Return a reason string if this instrument can't be rendered offscreen,
    else None. May mutate `options` to fill trivial required defaults."""
    meta = eschema.build_schema()["instruments"].get(instrument_type)
    if meta is None:
        return f"{instrument_type}\n(unknown type)"
    if not meta["offscreen_renderable"]:
        return f"{instrument_type}\n(GL preview on device)"
    if "svs" in options:
        return f"{instrument_type}\n(SVS preview on device)"
    if instrument_type in _CONFIG_DRIVEN:
        return f"{instrument_type}\n(config-driven)"
    if instrument_type == "static_text" and "text" not in options:
        options["text"] = "Text"
    missing = [o for o in meta["required_options"] if o not in options]
    if missing:
        return f"{instrument_type}\n(needs: {', '.join(missing)})"
    return None


def render_instrument(instrument_type, options=None, seed=None,
                      width=320, height=320, out_path="instrument.png"):
    """Render one instrument to `out_path`. Returns ("render"|"placeholder",
    out_path)."""
    options = dict(options or {})
    app = QApplication.instance() or QApplication(sys.argv[:1])
    _load_fonts()
    _setup_fix()

    import pyefis.hmi as hmi
    if hmi.actions is None:
        hmi.initialize({})

    reason = _placeholder_reason(instrument_type, options)
    if reason:
        _placeholder(reason, width, height, out_path)
        return "placeholder", out_path

    for key, value in (seed or {}).items():
        it = fix.db.get_item(key)
        fix.db.set_value(key, value)
        it.bad = it.fail = it.old = False

    if instrument_type in _NEEDS_DBKEY and "dbkey" not in options:
        options["dbkey"] = "DEMOGAUGE"
        options.setdefault("name", "DEMO")

    instrument = {"type": instrument_type, "row": 0, "column": 0,
                  "span": {"rows": 10, "columns": 10}}
    if options:
        instrument["options"] = options
    config = {
        "main": {"screenColor": "(0,0,0)", "screenWidth": width,
                 "screenHeight": height, "nodeID": 1},
        "screens": {"TEST": {
            "module": "pyefis.screens.screenbuilder",
            "title": "render",
            "layout": {"rows": 10, "columns": 10},
            "instruments": [instrument],
        }},
    }

    from tests.screenshots import gui
    try:
        gui.initialize(config, _REPO_ROOT, {}, fullscreen=False)
        screen = gui.mainWindow.scr.object
        screen.resize(width, height)
        for _ in range(40):  # ~400 ms: let layout + first paint settle
            app.processEvents()
            time.sleep(0.01)
        ok = screen.grab().save(out_path)
        gui.mainWindow.close()
        if not ok:
            raise RuntimeError("QPixmap.save returned False")
    except Exception as exc:  # never let a quirky widget break the caller
        _placeholder(f"{instrument_type}\n(render error)", width, height, out_path)
        print(f"  render failed ({exc!r}); wrote placeholder", file=sys.stderr)
        return "placeholder", out_path
    return "render", out_path


def render_instrument_svg(instrument_type, options=None, seed=None,
                          width=320, height=240, out_path="instrument.svg"):
    """Export one instrument to SVG via QSvgGenerator, reusing the widget's real
    QPainter paint code. Returns ("svg"|"placeholder", out_path). GL widgets,
    weston, config-driven and missing-required-option cases return
    ("placeholder", ...) WITHOUT writing an SVG -- the caller falls back to the
    raster placeholder for those."""
    options = dict(options or {})
    app = QApplication.instance() or QApplication(sys.argv[:1])
    _load_fonts()
    _setup_fix()

    import pyefis.hmi as hmi
    if hmi.actions is None:
        hmi.initialize({})

    reason = _placeholder_reason(instrument_type, options)
    if reason:
        return "placeholder", out_path
    if instrument_type in _NEEDS_DBKEY and "dbkey" not in options:
        options["dbkey"] = "DEMOGAUGE"
        options.setdefault("name", "DEMO")
    for key, value in (seed or {}).items():
        it = fix.db.get_item(key)
        fix.db.set_value(key, value)
        it.bad = it.fail = it.old = False

    instrument = {"type": instrument_type, "row": 0, "column": 0,
                  "span": {"rows": 10, "columns": 10}}
    if options:
        instrument["options"] = options
    config = {
        "main": {"screenColor": "(0,0,0)", "screenWidth": width,
                 "screenHeight": height, "nodeID": 1},
        "screens": {"TEST": {
            "module": "pyefis.screens.screenbuilder",
            "title": "render",
            "layout": {"rows": 10, "columns": 10},
            "instruments": [instrument],
        }},
    }

    from tests.screenshots import gui
    from PyQt6.QtCore import QSize
    from PyQt6.QtSvg import QSvgGenerator
    try:
        gui.initialize(config, _REPO_ROOT, {}, fullscreen=False)
        screen = gui.mainWindow.scr.object
        screen.resize(width, height)
        widget = screen.instruments[0]
        widget.move(0, 0)
        widget.resize(width, height)
        for _ in range(40):
            app.processEvents()
            time.sleep(0.01)
        gen = QSvgGenerator()
        gen.setFileName(out_path)
        gen.setSize(QSize(width, height))
        gen.setViewBox(QRect(0, 0, width, height))
        painter = QPainter(gen)
        widget.render(painter)
        painter.end()
        gui.mainWindow.close()
    except Exception as exc:
        print(f"  svg failed ({exc!r})", file=sys.stderr)
        return "placeholder", out_path
    return "svg", out_path


def _write_fallback_png(out_path, width, height,
                        fill=(32, 36, 43), border=(90, 100, 114)):
    """Write a minimal solid PNG with a border using only the stdlib. Used as
    the last-resort fallback when the render subprocess crashes; deliberately
    Qt-free so the parent process can never itself crash producing it."""
    import struct
    import zlib

    fr, fg, fb = fill
    br, bg, bb = border
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # PNG filter type 0 (none) per scanline
        edge_row = y < 2 or y >= height - 2
        for x in range(width):
            if edge_row or x < 2 or x >= width - 2:
                rows += bytes((br, bg, bb))
            else:
                rows += bytes((fr, fg, fb))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(rows), 9))
    png += chunk(b"IEND", b"")
    with open(out_path, "wb") as fh:
        fh.write(png)


def safe_render(instrument_type, options=None, seed=None, width=320,
                height=320, out_path="instrument.png", timeout=45):
    """Render in an isolated subprocess so even a hard (C++/GL) crash in a
    widget degrades to a placeholder instead of taking down the caller. This is
    the entry point a render backend should use. Returns
    ("render"|"placeholder"|"fallback", out_path)."""
    cmd = [sys.executable, os.path.abspath(__file__), instrument_type,
           "-o", out_path, "--width", str(width), "--height", str(height)]
    if options:
        cmd += ["--options", json.dumps(options)]
    if seed:
        cmd += ["--seed", json.dumps(seed)]
    try:
        proc = subprocess.run(cmd, timeout=timeout, capture_output=True,
                              text=True)
        produced = os.path.exists(out_path) and os.path.getsize(out_path) > 0
        if proc.returncode == 0 and produced:
            kind = "placeholder" if "placeholder:" in proc.stdout else "render"
            return kind, out_path
    except subprocess.TimeoutExpired:
        pass
    # Worker crashed/timed out/produced nothing -> guarantee a PNG, Qt-free.
    _write_fallback_png(out_path, width, height)
    return "fallback", out_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Render one pyEfis instrument to a PNG (offscreen).")
    parser.add_argument("type", help="instrument type (see the editor schema)")
    parser.add_argument("-o", "--out", default=None,
                        help="output PNG path (default render_<type>.png)")
    parser.add_argument("--options", default=None,
                        help="JSON object of instrument options")
    parser.add_argument("--seed", default=None,
                        help="JSON object of FIX key -> value to set")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--safe", action="store_true",
                        help="render in an isolated subprocess; a crash/timeout "
                             "degrades to a placeholder")
    parser.add_argument("--svg", action="store_true",
                        help="export an SVG (QSvgGenerator) instead of a PNG")
    args = parser.parse_args(argv)

    options = json.loads(args.options) if args.options else {}
    seed = json.loads(args.seed) if args.seed else {}
    out = args.out or f"render_{args.type}.{'svg' if args.svg else 'png'}"

    if args.svg:
        renderer = render_instrument_svg
    elif args.safe:
        renderer = safe_render
    else:
        renderer = render_instrument
    kind, path = renderer(
        args.type, options=options, seed=seed,
        width=args.width, height=args.height, out_path=out)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"{kind}: wrote {path} ({args.width}x{args.height}, {size} bytes)")


if __name__ == "__main__":
    main()
