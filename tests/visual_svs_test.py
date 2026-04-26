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
    SVS_RENDERER    cpu_sparse | cpu_dense (default: cpu_sparse)
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
RANGE_NM  = float(os.environ.get("SVS_RANGE", "30"))
RENDERER  = os.environ.get("SVS_RENDERER", "cpu_sparse")

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
app = QApplication(sys.argv)

win = QMainWindow()
win.setWindowTitle(
    f"SVS Visual Test — {RENDERER}  lat={LAT} lon={LON} alt={ALT} ft  "
    f"hdg={HEAD}° range={RANGE_NM} nm"
)
win.resize(800, 600)

widget = AI(win, show_fpm=True)
widget.set_svs_config({
    "enabled":           True,
    "tile_path":         TILE_PATH,
    "renderer":          RENDERER,
    "range_nm":          RANGE_NM,
    "clearance_green_ft": 1000,
    "clearance_yellow_ft": 500,
})
win.setCentralWidget(widget)
win.show()

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
