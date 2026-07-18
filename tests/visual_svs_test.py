"""
Standalone visual test for the SVS terrain renderer.

Displays the AI widget with SVS enabled in a resizable window.
No fix-gateway server needed — uses the same mock DB as unit tests.

Usage (run from pyEfis repo root):
    python tests/visual_svs_test.py

Optional env vars:
    SVS_TILE_PATH   path to srtm3/ directory  (default: D:/EarthData/srtm3)
    SVS_LAT         latitude  (default: 32.8  — Fort Worth, TX)
    SVS_LON         longitude (default: -97.3 — Fort Worth, TX)
    SVS_ALT         altitude in feet (default: 3000)
    SVS_PITCH       pitch angle deg  (default: 0)
    SVS_ROLL        roll angle deg   (default: 0)
    SVS_HEAD        heading deg      (default: 360)
    SVS_RANGE       range_nm         (default: 30)
    SVS_RENDERER    cpu_sparse | cpu_dense | cpu_ultra | polar | opengl
                    (default: cpu_sparse). polar uses a forward (range,
                    azimuth) fan with finer cells near the aircraft —
                    see docs/svs_rendering.md.
    SVS_WATER_PATH  path to a water polygons sqlite (default: first
                    water/water_rtree*.sqlite in the repo, if present)
    SVS_PERF_LOG    1 to enable the per-segment SVS perf log (implies
                    INFO logging to stderr)
    SVS_ANIMATE     heading change rate in deg/s (default 0 = static).
                    Drives continuous repaints via HEAD updates at
                    ~30 Hz so perf numbers reflect sustained rendering.
    SVS_SCREENSHOT  path to save a PNG of the AI widget, then exit.
                    Captured after SVS_SCREENSHOT_DELAY_MS (default
                    2000) so tile/db loads settle first.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure dependencies are findable (C:\pylib short-path install on Windows)
# ---------------------------------------------------------------------------
if r"C:\pylib" not in sys.path:
    sys.path.insert(0, r"C:\pylib")

# ---------------------------------------------------------------------------
# Patch pyavtools so we run without a live fix-gateway server
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import mock_db.client
import mock_db.scheduler
sys.modules["pyavtools.fix.client"] = mock_db.client
sys.modules["pyavtools.scheduler"] = mock_db.scheduler

# ---------------------------------------------------------------------------
# Imports (after patching)
# ---------------------------------------------------------------------------
import pyavtools.fix as fix
from PyQt6.QtWidgets import QApplication, QMainWindow
from pyefis.instruments.ai import AI

# ---------------------------------------------------------------------------
# Configuration from env
# ---------------------------------------------------------------------------
TILE_PATH = os.environ.get("SVS_TILE_PATH", r"D:\EarthData\srtm3")
LAT       = float(os.environ.get("SVS_LAT",  "32.8"))
LON       = float(os.environ.get("SVS_LON",  "-97.3"))
ALT       = float(os.environ.get("SVS_ALT",  "3000"))
PITCH     = float(os.environ.get("SVS_PITCH", "0"))
ROLL      = float(os.environ.get("SVS_ROLL",  "0"))
HEAD      = float(os.environ.get("SVS_HEAD",  "360"))
RANGE_NM   = float(os.environ.get("SVS_RANGE", "30"))
RENDERER   = os.environ.get("SVS_RENDERER", "cpu_sparse")
AUTO_RANGE = os.environ.get("SVS_AUTO_RANGE", "true").lower() != "false"
# FAA CIFP path: defaults to the in-repo cifp/ directory if present.
_DEFAULT_CIFP = str(Path(__file__).parent.parent / "cifp" / "FAACIFP18")
CIFP_PATH  = os.environ.get("SVS_CIFP_PATH",  _DEFAULT_CIFP if Path(_DEFAULT_CIFP).is_file() else "")
# FAA NASR SQLite (richer data, preferred): defaults to in-repo nasr/airports.sqlite.
_DEFAULT_NASR = str(Path(__file__).parent.parent / "nasr" / "airports.sqlite")
NASR_PATH  = os.environ.get("SVS_NASR_PATH",  _DEFAULT_NASR if Path(_DEFAULT_NASR).is_file() else "")
# FAA DOF (obstacles): defaults to in-repo dof/obstacles.sqlite.
_DEFAULT_DOF = str(Path(__file__).parent.parent / "dof" / "obstacles.sqlite")
DOF_PATH   = os.environ.get("SVS_DOF_PATH",   _DEFAULT_DOF if Path(_DEFAULT_DOF).is_file() else "")
# Water polygons sqlite: defaults to the first water/water_rtree*.sqlite
# in the repo (name varies by region extract — water_rtree.sqlite on the
# Pi, water_rtree_texas.sqlite on the dev machine).
_water_candidates = sorted(
    (Path(__file__).parent.parent / "water").glob("water_rtree*.sqlite"))
WATER_PATH = os.environ.get(
    "SVS_WATER_PATH",
    str(_water_candidates[0]) if _water_candidates else "")
PERF_LOG   = os.environ.get("SVS_PERF_LOG", "").lower() in ("1", "true", "yes")
ANIMATE_DEG_S = float(os.environ.get("SVS_ANIMATE", "0"))
SCREENSHOT = os.environ.get("SVS_SCREENSHOT", "")
SCREENSHOT_DELAY_MS = int(os.environ.get("SVS_SCREENSHOT_DELAY_MS", "2000"))

if PERF_LOG:
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

# ---------------------------------------------------------------------------
# Bootstrap fix DB
# ---------------------------------------------------------------------------
fix.initialize({"main": {"FixServer": "localhost", "FixPort": "3490"}})


def _def(key, desc, dtype, lo, hi, units, aux=""):
    fix.db.define_item(key, desc, dtype, lo, hi, units, 50000, aux)
    fix.db.get_item(key).bad  = False
    fix.db.get_item(key).fail = False


_def("PITCH",  "Pitch",    "float", -90.0,  90.0,   "deg")
_def("ROLL",   "Roll",     "float", -180.0, 180.0,  "deg")
_def("ALAT",   "LatAccel", "float", -30.0,  30.0,   "g")
_def("TAS",    "TAS",      "float",  0.0,   2000.0, "knots")
_def("HEAD",   "Heading",  "float",  0.0,   359.9,  "deg")
_def("VS",     "VS",       "float", -30000, 30000,  "ft/min",  "Min,Max")
_def("GS",     "GS",       "float",  0.0,   2000.0, "knots")
_def("TRACK",  "Track",    "float",  0.0,   359.9,  "deg")
_def("LAT",    "Lat",      "float", -90.0,  90.0,   "deg")
_def("LONG",   "Lon",      "float", -180.0, 180.0,  "deg")
_def("ALT",    "Alt",      "float", -2000,  60000,  "ft")

fix.db.set_value("PITCH", PITCH)
fix.db.set_value("ROLL",  ROLL)
fix.db.set_value("ALAT",  0.0)
fix.db.set_value("TAS",   120.0)
fix.db.set_value("HEAD",  HEAD)
fix.db.set_value("VS",    0.0)
fix.db.set_value("GS",    120.0)
fix.db.set_value("TRACK", HEAD)
fix.db.set_value("LAT",   LAT)
fix.db.set_value("LONG",  LON)
fix.db.set_value("ALT",   ALT)

# ---------------------------------------------------------------------------
# Build and show window
# ---------------------------------------------------------------------------
from PyQt6.QtCore import Qt
QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)

win = QMainWindow()
win.setWindowTitle(
    f"SVS Visual Test — {RENDERER}  lat={LAT} lon={LON} alt={ALT} ft  "
    f"hdg={HEAD}° range={RANGE_NM} nm"
)
win.resize(int(os.environ.get("SVS_W", "800")), int(os.environ.get("SVS_H", "600")))

widget = AI(win, show_fpm=True)
widget.aircraft_symbol = os.environ.get("SVS_SYMBOL", "classic")
widget.symbol_color = os.environ.get("SVS_SYMBOL_COLOR", "yellow")
# Overlay opacity knobs (SVS-as-background A/B: SVS_SYMBOL=none plus all
# three at 0 and SVS_FPM=0 leaves the bare environment).
widget.pitchOpacity = float(os.environ.get("SVS_PITCH_OPACITY", "0.6"))
widget.bankOpacity = float(os.environ.get("SVS_BANK_OPACITY", "1.0"))
widget.horizonOpacity = float(os.environ.get("SVS_HORIZON_OPACITY", "1.0"))
widget.show_fpm = os.environ.get("SVS_FPM", "1").lower() \
    not in ("0", "false", "no")
widget.symbol_scale = float(os.environ.get("SVS_SYMBOL_SCALE", "1.0"))
widget.bank_position = float(os.environ.get("SVS_BANK_POSITION", "50"))
widget.bank_radius = float(os.environ.get("SVS_BANK_RADIUS",
                                          str(100.0 / 3.0)))
widget.pitch_ladder_avoid_bank = os.environ.get(
    "SVS_LADDER_AVOID_BANK", "").lower() in ("1", "true", "yes")
# Clean-terrain capture for the configurator's static SVS preview: render only
# the terrain + sky, no symbology, so the configurator twin can draw live
# symbology over it (SVS_TERRAIN_ONLY=1).
widget.terrain_only = os.environ.get("SVS_TERRAIN_ONLY", "").lower() \
    in ("1", "true", "yes")
widget.set_svs_config({
    "enabled":            True,
    "tile_path":          TILE_PATH,
    "renderer":           RENDERER,
    "range_nm":           RANGE_NM,
    "auto_range":         AUTO_RANGE,
    "clearance_green_ft": 1000,
    "clearance_yellow_ft": 500,
    "cifp_path":          CIFP_PATH,    # used only if NASR isn't configured
    "nasr_db_path":       NASR_PATH,    # preferred — Tier C surface markings
    "dof_db_path":        DOF_PATH,     # FAA DOF obstacles (towers, antennas)
    "water_db_path":      WATER_PATH,   # OSM/NE water polygons
    "svs_perf_log":       PERF_LOG,
    "haze":               os.environ.get("SVS_HAZE", "1").lower()
                          not in ("0", "false", "no"),
    "haze_distance_nm":   float(os.environ.get("SVS_HAZE_NM", "40")),
    "msaa_samples":       int(os.environ.get("SVS_MSAA", "2")),
    "safe_gradient":      os.environ.get("SVS_SAFE_GRAD", "1").lower()
                          not in ("0", "false", "no"),
    "terrain_texture":    float(os.environ.get("SVS_TEX_AMP", "0.35")),
    "terrain_grid":       float(os.environ.get("SVS_GRID_AMP", "0.35")),
    "highway_db_path":    os.environ.get("SVS_HIGHWAY_PATH", ""),
    "paved_only":         os.environ.get("SVS_PAVED_ONLY", "1").lower()
                          not in ("0", "false", "no"),
})
win.setCentralWidget(widget)
win.show()

# ---------------------------------------------------------------------------
# Optional animation — drives continuous repaints through the normal FIX
# update path so perf numbers reflect sustained rendering (a static pose
# only repaints on expose events).
# ---------------------------------------------------------------------------
if ANIMATE_DEG_S != 0.0:
    from PyQt6.QtCore import QTimer
    _ANIM_INTERVAL_MS = 33
    _anim_state = {"head": HEAD}

    def _anim_tick():
        _anim_state["head"] = (
            _anim_state["head"] + ANIMATE_DEG_S * _ANIM_INTERVAL_MS / 1000.0
        ) % 360.0
        fix.db.set_value("HEAD", _anim_state["head"])
        fix.db.set_value("TRACK", _anim_state["head"])
        # Force a repaint — production repaints are driven by the FIX
        # keys the AI subscribes to with update() (LAT/LONG/ALT etc.);
        # HEAD alone doesn't repaint, and a perf run needs every tick
        # to render.
        widget.update()

    _anim_timer = QTimer()
    _anim_timer.timeout.connect(_anim_tick)
    _anim_timer.start(_ANIM_INTERVAL_MS)

# ---------------------------------------------------------------------------
# Optional GPS motion simulation — 1 Hz position fixes dead-reckoned
# from GS/TRACK, exercising the P4 frame clock + pose interpolation
# (the display should glide at the frame rate between the 1 Hz steps).
# ---------------------------------------------------------------------------
if os.environ.get("SVS_SIM_MOTION", "").lower() in ("1", "true", "yes"):
    import math as _math
    from PyQt6.QtCore import QTimer
    _sim = {"lat": LAT, "lon": LON}

    def _sim_tick():
        gs, trk = 120.0, HEAD
        d_deg = (gs * 1.0 / 3600.0) / 60.0
        _sim["lat"] += d_deg * _math.cos(_math.radians(trk))
        _sim["lon"] += (d_deg * _math.sin(_math.radians(trk))
                        / _math.cos(_math.radians(_sim["lat"])))
        fix.db.set_value("LAT", _sim["lat"])
        fix.db.set_value("LONG", _sim["lon"])

    _sim_timer = QTimer()
    _sim_timer.timeout.connect(_sim_tick)
    _sim_timer.start(1000)

# ---------------------------------------------------------------------------
# Optional screenshot-and-exit — used for golden-image captures.
# ---------------------------------------------------------------------------
if SCREENSHOT:
    from PyQt6.QtCore import QTimer

    def _capture():
        # With the P5 QOpenGLWidget viewport, QWidget.grab() cannot see
        # GL content — grab the composited framebuffer instead (Qt
        # renders the scene AND the QPainter overlay into it).
        vp = widget.viewport()
        is_gl = hasattr(vp, "grabFramebuffer")
        if os.environ.get("SVS_SCREENGRAB") or (
                is_gl and sys.platform == "win32"):
            # True screen capture. On Windows, grabFramebuffer of the
            # QOpenGLWidget viewport returns blank (composition
            # happens outside the widget FBO on this driver path) —
            # the screen is the ground truth.
            scr = app.primaryScreen()
            ok = scr.grabWindow(win.winId()).save(SCREENSHOT, "PNG")
        elif is_gl:
            ok = vp.grabFramebuffer().save(SCREENSHOT, "PNG")
        else:
            ok = widget.grab().save(SCREENSHOT, "PNG")
        print(f"Screenshot {'saved to' if ok else 'FAILED:'} {SCREENSHOT}")
        app.exit(0 if ok else 1)

    QTimer.singleShot(SCREENSHOT_DELAY_MS, _capture)

print(f"SVS visual test window open.")
print(f"  Tile path : {TILE_PATH}")
print(f"  Position  : lat={LAT}  lon={LON}  alt={ALT} ft")
print(f"  Heading   : {HEAD}°   range: {RANGE_NM} nm   renderer: {RENDERER}")
print()
print("Suggested altitude tests for Fort Worth (terrain ~600-900 ft MSL):")
print("  SVS_ALT=3000  -> green  (>1000 ft clearance)")
print("  SVS_ALT=1500  -> amber  (500-999 ft clearance)")
print("  SVS_ALT=1000  -> red    (0-499 ft clearance)")
print("  SVS_ALT=500   -> magenta (below terrain — underground)")
print()
print("Override with env vars (SVS_LAT, SVS_LON, SVS_ALT, SVS_PITCH, SVS_ROLL,")
print("  SVS_HEAD, SVS_RANGE, SVS_RENDERER, SVS_TILE_PATH)")
print()
print("Close window to exit.")

sys.exit(app.exec())
