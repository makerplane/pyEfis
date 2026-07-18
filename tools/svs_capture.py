"""Deterministic SVS frame capture.

Renders the AI/SVS at one commanded pose, waits until the scene is genuinely
*settled*, writes a PNG, and exits. Intended for golden-image regression tests and
for any automated tool that needs to judge a frame rather than look at one.

Why this exists (and why ``SVS_SCREENSHOT`` is not enough)
---------------------------------------------------------
``tests/visual_svs_test.py`` already has a capture hook, and it is not safe to
regress against. Three defects compound:

1. **The scene is racy.** Water, highways, obstacles and airports are each built on
   a daemon thread, serialised behind a single ``_collect_slot``, and their results
   are promoted into the render *only on a subsequent paint* -- there is no signal,
   callback or timer anywhere that says "done". Whatever happens to have landed by
   the deadline is what you capture.

2. **Repaints stop at t ~= 2.0 s, so a longer delay does not help.** With a static
   pose the only thing driving repaints is dead reckoning, and ``PoseSource`` caps
   extrapolation at ``extrap_cap_s = 2.0``. Past that the pose stops changing,
   ``_frame_tick`` short-circuits, painting ceases, and the scene freezes
   **half-loaded, permanently**. The default ``SVS_SCREENSHOT_DELAY_MS`` of 2000 sits
   exactly on that knife-edge.

3. **The captured aircraft is not where you put it.** That same dead reckoning runs
   the seeded ``GS = 120 kt`` forward for two seconds before it saturates, so the
   rendered position is displaced ~124 m downtrack of the commanded lat/lon. Every
   committed golden carries the error.

And the capture is a *screen* grab (``QScreen.grabWindow``), so anything overlapping
the window -- a notification, a second harness window, a locked session -- lands in
the PNG.

What this tool does instead
---------------------------
* **Pins the pose** (``extrap_cap_s = 0``), so the render is at the exact commanded
  lat/lon/alt.
* **Drives the repaints itself**, since nothing else will once the pose is static.
* **Waits on the settled predicate** -- every collector has finished, promoted, and
  is idle, and terrain has actually drawn -- rather than on a stopwatch. Timing out
  is a hard failure, not a silently half-drawn frame.
* **Reads the pixels back inside the paint**, where the widget's FBO holds the fully
  composited frame. This is why ``grabFramebuffer()`` cannot work here:
  ``QOpenGLWidget::grabFramebuffer()`` re-renders through ``paintGL()``, and as a
  ``QGraphicsView`` *viewport* the widget never paints through ``paintGL()`` -- so it
  hands back an empty user-paint. Reading at the end of ``paintEvent`` sidesteps it,
  and needs no visible window.
* **Disables MSAA**, because ``glReadPixels`` on a multisample FBO is invalid -- and
  because the sample pattern is driver-specific, which a golden should not be.

Exit codes: 0 ok, 2 never settled (timeout), 3 GL unavailable, 4 PNG write failed.

Usage::

    python tools/svs_capture.py --lat 24.5561 --lon -81.7595 --alt 500 \\
        --heading 270 --range 15 --out frame.png

    # flat, unlit terrain -- for automated pixel classification
    python tools/svs_capture.py ... --flat --terrain-only
"""

import argparse
import sys
from pathlib import Path

# Dependencies live in C:\pylib on the Windows dev box, not site-packages.
if r"C:\pylib" not in sys.path:
    sys.path.insert(0, r"C:\pylib")

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests"))

# Run against the mock FIX db, exactly as the visual harness does -- no gateway.
import mock_db.client  # noqa: E402
import mock_db.scheduler  # noqa: E402

sys.modules["pyavtools.fix.client"] = mock_db.client
sys.modules["pyavtools.scheduler"] = mock_db.scheduler

import pyavtools.fix as fix  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QImage  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from pyefis.instruments.ai import AI  # noqa: E402

EXIT_OK = 0
EXIT_NOT_SETTLED = 2
EXIT_GL_FAILED = 3
EXIT_SAVE_FAILED = 4

PUMP_INTERVAL_MS = 16
CONFIRM_FRAMES = 2  # settled must hold this many paints running


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", required=True, help="PNG path to write")

    pose = p.add_argument_group("pose")
    pose.add_argument("--lat", type=float, required=True)
    pose.add_argument("--lon", type=float, required=True)
    pose.add_argument("--alt", type=float, required=True, help="feet MSL")
    pose.add_argument("--heading", type=float, default=0.0, help="degrees")
    pose.add_argument("--pitch", type=float, default=0.0, help="degrees")
    pose.add_argument("--roll", type=float, default=0.0, help="degrees")

    view = p.add_argument_group("view")
    view.add_argument("--range", type=float, default=30.0, dest="range_nm")
    view.add_argument(
        "--auto-range",
        action="store_true",
        help="let the renderer shrink range with altitude (off by default here: a "
        "capture should render the range it was asked for)",
    )
    view.add_argument("--width", type=int, default=800)
    view.add_argument("--height", type=int, default=600)

    look = p.add_argument_group("appearance")
    look.add_argument(
        "--flat",
        action="store_true",
        help="disable haze, ground texture and the grid. Terrain and water become "
        "their flat base colours, so a frame can be classified by pixel value "
        "instead of eyeballed",
    )
    look.add_argument(
        "--terrain-only",
        action="store_true",
        help="terrain and sky only, no symbology",
    )
    look.add_argument(
        "--msaa",
        type=int,
        default=1,
        help="samples. Must be 1 for readback; >1 is accepted but will fail",
    )

    data = p.add_argument_group("data")
    data.add_argument("--tiles", default=r"D:\EarthData\srtm3")
    data.add_argument("--water", default=None)
    data.add_argument("--nasr", default=None)
    data.add_argument("--cifp", default=None)
    data.add_argument("--dof", default=None)
    data.add_argument("--highways", default="")
    data.add_argument(
        "--water-max-vertices",
        type=int,
        default=1024,
        help="per-polygon vertex cap at load. MUST be >= the pack's largest ring. "
        "WaterDB.DEFAULT_MAX_VERTICES is 32, and at that cap _decode_vertices "
        "stride-decimates the ring while _decode_triangles keeps the ORIGINAL "
        "indices -- which are then clamped, collapsing most triangles to "
        "degenerate slivers. Omitting this silently renders corrupt water",
    )

    p.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="seconds to wait for the scene to settle before failing",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def _default(path, *parts):
    if path is not None:
        return path
    candidate = _REPO.joinpath(*parts)
    return str(candidate) if candidate.exists() else ""


def _default_water():
    found = sorted((_REPO / "water").glob("water_rtree*.sqlite"))
    return str(found[0]) if found else ""


class CapturingAI(AI):
    """AI that can read its own composited framebuffer back at end of paint."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture_to = None
        self.capture_ok = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.capture_to is None:
            return
        path, self.capture_to = self.capture_to, None
        self.capture_ok = _readback(self.viewport(), path)


def _readback(viewport, path):
    """Read the widget's FBO. Must run with the GL context current, i.e. in paint."""
    from OpenGL import GL as gl

    dpr = viewport.devicePixelRatioF()
    w = int(round(viewport.width() * dpr))
    h = int(round(viewport.height() * dpr))

    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    buf = gl.glReadPixels(0, 0, w, h, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)

    # GL's origin is bottom-left; QImage's is top-left. copy() detaches from buf.
    img = QImage(bytes(buf), w, h, QImage.Format.Format_RGBA8888)
    return bool(img.mirrored(False, True).copy().save(path, "PNG"))


def settled(svs, expect_layers):
    """True once every asynchronous collector has finished and been promoted.

    Each layer parks its result in ``_async_state[name]["res"]`` and nothing wakes
    the UI, so a result only becomes visible on the *next* paint. A layer is done
    when no worker is alive, no result is pending promotion, and a key has actually
    been recorded -- ``val`` may legitimately be empty (nothing in range), so the
    test is on ``key``, never on ``val``.

    ``expect_layers`` is the set of layers whose data source was configured. Without
    it a cold first frame looks settled purely because no collector has run yet.
    """
    if svs is None or svs.gl_failed or not svs.drew_terrain:
        return False

    for name in expect_layers:
        state = svs._async_state.get(name)
        if state is None:  # not even requested yet
            return False
        if state.get("res") is not None:
            return False
        worker = state.get("worker")
        if worker is not None and worker.is_alive():
            return False
        if state.get("key") is None:
            return False

    for db_attr, result, worker, key in (
        ("water_db", "_water_result", "_water_worker", "_water_tris_cache_key"),
        ("highway_db", "_hwy_result", "_hwy_worker", "_hwy_cache_key"),
    ):
        db = getattr(svs, db_attr, None)
        if db is None or not getattr(db, "ready", False):
            continue
        if getattr(svs, result) is not None:
            return False
        w = getattr(svs, worker)
        if w is not None and w.is_alive():
            return False
        if getattr(svs, key) is None:
            return False

    return True


def main(argv=None):
    args = parse_args(argv)

    water = args.water if args.water is not None else _default_water()
    nasr = _default(args.nasr, "nasr", "airports.sqlite")
    cifp = _default(args.cifp, "cifp", "FAACIFP18")
    dof = _default(args.dof, "dof", "obstacles.sqlite")

    expect_layers = set()
    if nasr or cifp:
        expect_layers.add("airports")
    if dof:
        expect_layers.add("obstacles")

    fix.initialize({"main": {"FixServer": "localhost", "FixPort": "3490"}})
    for key, desc, lo, hi, units in (
        ("PITCH", "Pitch", -90.0, 90.0, "deg"),
        ("ROLL", "Roll", -180.0, 180.0, "deg"),
        ("ALAT", "LatAccel", -30.0, 30.0, "g"),
        ("TAS", "TAS", 0.0, 2000.0, "knots"),
        ("HEAD", "Heading", 0.0, 359.9, "deg"),
        ("VS", "VS", -30000, 30000, "ft/min"),
        ("GS", "GS", 0.0, 2000.0, "knots"),
        ("TRACK", "Track", 0.0, 359.9, "deg"),
        ("LAT", "Lat", -90.0, 90.0, "deg"),
        ("LONG", "Lon", -180.0, 180.0, "deg"),
        ("ALT", "Alt", -2000, 60000, "ft"),
    ):
        fix.db.define_item(key, desc, "float", lo, hi, units, 50000, "")
        item = fix.db.get_item(key)
        item.bad = False
        item.fail = False

    heading = args.heading % 360.0  # HEAD's range is 0..359.9; 360 would clamp
    for key, value in (
        ("PITCH", args.pitch),
        ("ROLL", args.roll),
        ("ALAT", 0.0),
        ("TAS", 120.0),
        ("HEAD", heading),
        ("VS", 0.0),
        ("GS", 120.0),
        ("TRACK", heading),
        ("LAT", args.lat),
        ("LONG", args.lon),
        ("ALT", args.alt),
    ):
        fix.db.set_value(key, value)

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication([])

    win = QMainWindow()
    win.resize(args.width, args.height)

    widget = CapturingAI(win, show_fpm=not args.terrain_only)
    widget.terrain_only = args.terrain_only
    widget.set_svs_config(
        {
            "enabled": True,
            "tile_path": args.tiles,
            "renderer": "opengl",
            "range_nm": args.range_nm,
            "auto_range": args.auto_range,
            "clearance_green_ft": 1000,
            "clearance_yellow_ft": 500,
            "cifp_path": cifp,
            "nasr_db_path": nasr,
            "dof_db_path": dof,
            "water_db_path": water,
            "water_max_vertices": args.water_max_vertices,
            "highway_db_path": args.highways,
            "paved_only": True,
            "svs_perf_log": False,
            "haze": not args.flat,
            "haze_distance_nm": 40.0,
            "msaa_samples": args.msaa,
            "safe_gradient": not args.flat,
            "terrain_texture": 0.0 if args.flat else 0.35,
            "terrain_grid": 0.0 if args.flat else 0.35,
        }
    )

    # Pin the pose. PoseSource dead-reckons from the seeded GS/TRACK, so without
    # this the frame renders ~124 m downtrack of the commanded position -- and then
    # stops repainting when the 2 s extrapolation cap saturates, which is what
    # freezes the existing goldens half-loaded.
    widget._pose.extrap_cap_s = 0.0

    win.setCentralWidget(widget)
    win.show()

    state = {"confirmed": 0, "elapsed_ms": 0, "requested": False}
    timeout_ms = args.timeout * 1000.0

    def pump():
        svs = getattr(widget, "_svs_renderer", None)

        if svs is not None and svs.gl_failed:
            print("SVS: OpenGL renderer unavailable", file=sys.stderr)
            app.exit(EXIT_GL_FAILED)
            return

        if widget.capture_ok is not None:
            if widget.capture_ok:
                print(f"captured {args.out}")
                app.exit(EXIT_OK)
            else:
                print(f"failed to write {args.out}", file=sys.stderr)
                app.exit(EXIT_SAVE_FAILED)
            return

        if state["elapsed_ms"] > timeout_ms:
            print(
                f"scene never settled within {args.timeout:.0f}s -- refusing to "
                f"capture a half-loaded frame",
                file=sys.stderr,
            )
            app.exit(EXIT_NOT_SETTLED)
            return

        if not state["requested"]:
            if settled(svs, expect_layers):
                state["confirmed"] += 1
                if state["confirmed"] >= CONFIRM_FRAMES:
                    widget.capture_to = args.out
                    state["requested"] = True
            else:
                state["confirmed"] = 0

        # Nothing else will repaint us: _frame_tick short-circuits on an unchanged
        # pose, and the pose is now pinned. Collectors only promote on a paint, so
        # without this the scene can never finish loading.
        widget._frame_dirty = True
        widget.update()
        state["elapsed_ms"] += PUMP_INTERVAL_MS

    timer = QTimer()
    timer.timeout.connect(pump)
    timer.start(PUMP_INTERVAL_MS)

    if args.verbose:
        print(f"pose   : {args.lat}, {args.lon} @ {args.alt} ft, hdg {heading}")
        print(f"range  : {args.range_nm} NM (auto_range={args.auto_range})")
        print(f"layers : {sorted(expect_layers) or 'none'}  water={bool(water)}")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
