#  Screenshot generator for the pyEFIS manual.
#
#  Renders each widget/screen config in tests/screenshots/configs/ offscreen and
#  saves a PNG to docs/images/generated/. OPT-IN: it is skipped during normal
#  test runs and only executes when GENERATE_SCREENSHOTS is set, so it never
#  affects CI:
#
#      GENERATE_SCREENSHOTS=1 PYTHONPATH="C:/pylib;src" \
#          python -m pytest tests/screenshots/generate_screenshots.py --no-cov -q
#
#  pytest is configured (pyproject.toml) to run with QT_QPA_PLATFORM=offscreen at
#  1000x1000, so no display is required. Non-GL widgets render fully offscreen;
#  GL terrain (SVS / virtual_vfr) does not render offscreen and is captured by
#  the SVS visual harness / on real hardware instead.
#
#  A config may carry two optional top-level keys understood only by this
#  generator (the screen builder ignores unknown top-level keys):
#    screenshot: <name>        # output file stem (default: the config filename)
#    seed: {KEY: value, ...}   # FIX values to set before capture

import glob
import os

import pytest
import yaml

from tests.screenshots import gui

GENERATE = bool(os.environ.get("GENERATE_SCREENSHOTS"))

# The offscreen platform on Windows does not resolve the widgets' default font
# ("DejaVu Sans Condensed") by name, so text renders as tofu boxes. Register the
# TTFs explicitly and substitute the family names the code asks for onto whatever
# actually loaded. Fonts not present anywhere (DSEG segmented, Open Sans) fall
# back to the loaded sans so text stays legible.
_FONT_FILES = {
    "DejaVu Sans Condensed": ["C:/Windows/Fonts/DejaVuSansCondensed.ttf",
                              "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"],
    "DejaVu Sans": ["C:/Windows/Fonts/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "DejaVu Sans Mono": ["C:/Windows/Fonts/DejaVuSansMono.ttf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
}
_FONTS_LOADED = False


def _load_fonts():
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return
    from PyQt6.QtGui import QFont, QFontDatabase
    loaded = {}
    for requested, paths in _FONT_FILES.items():
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
    _FONTS_LOADED = True
HERE = os.path.dirname(__file__)
CONFIG_DIR = os.path.join(HERE, "configs")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "images", "generated"))

CONFIG_FILES = sorted(glob.glob(os.path.join(CONFIG_DIR, "*.yaml")))

# Real shipped config tree, for capturing assembled preset screens.
REAL_CONFIG = os.path.normpath(
    os.path.join(HERE, "..", "..", "src", "pyefis", "config"))
PRESET_SCREENS = ["SIXPACK", "EMS", "EMS2", "RADIO", "PFD", "PFD_AI_ONLY",
                  "DataStatus"]


def _auto_define_missing(fix):
    """Preset screens bind to many keys (radio, fuel, buttons) the test fixture
    doesn't define; the real FIX db raises KeyError on an undefined key, which
    aborts screen init. Wrap get_item so an unknown key is defined on demand
    (bool for button/flag keys, float otherwise) and the screen renders fully."""
    db = fix.db
    if getattr(db, "_auto_define_installed", False):
        return
    orig = db.get_item

    def get_item(key):
        try:
            return orig(key)
        except Exception:
            up = str(key).upper()
            is_bool = up.startswith(("TSBTN", "BTN", "EGTBTN")) or "BUTTON" in up
            dtype = "bool" if is_bool else "float"
            aux = "" if is_bool else "Min,Max,lowWarn,lowAlarm,highWarn,highAlarm"
            fix.db.define_item(key, key, dtype, None if is_bool else 0,
                               None if is_bool else 100, "", 50000, aux)
            it = orig(key)
            it.bad = False
            it.fail = False
            it.old = False
            return it

    db.get_item = get_item
    db._auto_define_installed = True


def _has_gl_ahrs(screen_cfg):
    """True if the screen includes the SVS-capable virtual_vfr / AHRS widget,
    whose QOpenGLWidget does not initialise under the offscreen platform (it
    hangs rather than failing gracefully). Those screens are captured on real
    hardware (the Pi) instead."""
    for ins in screen_cfg.get("instruments", []):
        if not isinstance(ins, dict):
            continue
        t = str(ins.get("type", "")).lower()
        if "virtual_vfr" in t or "ahrs" in t:
            return True
    return False


def _is_button_chrome(ins):
    """True for button widgets / button-bar includes that we strip from preset
    captures to avoid condition-loop hangs."""
    if not isinstance(ins, dict):
        return False
    t = str(ins.get("type", ""))
    if t in ("button", "ganged_button"):
        return True
    if t.startswith("include,"):
        target = t.split(",", 1)[1].upper()
        if "BUTTON" in target:
            return True
    return False


def _assemble_real_config():
    """Load + merge the shipped preferences and assemble the full config exactly
    as pyefis.main does, so the preset screens resolve their includes/preferences."""
    import pyefis.cfg as cfg
    from pyefis.main import merge_dict
    with open(os.path.join(REAL_CONFIG, "preferences.yaml")) as cf:
        prefs = yaml.safe_load(cf)
    custom = os.path.join(REAL_CONFIG, "preferences.yaml.custom")
    if os.path.exists(custom):
        with open(custom) as cf:
            merge_dict(prefs, yaml.safe_load(cf))
    config = cfg.from_yaml(os.path.join(REAL_CONFIG, "default.yaml"),
                           preferences=prefs)
    return config, prefs


def _seed_extra(fix):
    """Define engine/EMS and misc keys the `fix` conftest fixture does not, so
    EMS gauge configs have data + warning/alarm bands to render."""
    AUX = "Min,Max,lowWarn,lowAlarm,highWarn,highAlarm"

    def gauge(key, value, mn, mx, units, low_w=None, low_a=None, high_w=None,
              high_a=None):
        fix.db.define_item(key, key, "float", mn, mx, units, 50000, AUX)
        fix.db.set_value(key, value)
        it = fix.db.get_item(key)
        it.bad = False
        it.fail = False
        it.set_aux_value("Min", mn)
        it.set_aux_value("Max", mx)
        if low_w is not None:
            it.set_aux_value("lowWarn", low_w)
        if low_a is not None:
            it.set_aux_value("lowAlarm", low_a)
        if high_w is not None:
            it.set_aux_value("highWarn", high_w)
        if high_a is not None:
            it.set_aux_value("highAlarm", high_a)

    gauge("TACH1", 2400, 0, 3000, "RPM", high_w=2700, high_a=2800)
    gauge("MAP1", 24.5, 0, 35, "inHg", high_w=30, high_a=33)
    gauge("OILP1", 62, 0, 120, "psi", low_w=25, low_a=15, high_w=90, high_a=100)
    gauge("OILT1", 180, 0, 300, "degF", low_w=120, high_w=230, high_a=250)
    gauge("VOLT", 13.8, 0, 16, "V", low_w=12.5, low_a=11.5, high_w=15, high_a=15.5)
    gauge("CURRNT", 18, -60, 60, "A", high_w=45, high_a=55)
    gauge("FUELP1", 24, 0, 40, "psi", low_w=14, low_a=10, high_w=35)
    gauge("FUELF1", 11.5, 0, 30, "gph", high_w=24)
    gauge("FUELQT", 38, 0, 60, "gal", low_w=10, low_a=5)
    for n in (1, 2, 3, 4):
        gauge(f"EGT1{n}", 1320 + n * 12, 0, 1800, "degF", high_w=1600, high_a=1700)
        gauge(f"CHT1{n}", 330 + n * 8, 0, 500, "degF", high_w=420, high_a=450)
    gauge("EGTMAX1", 1356, 0, 1800, "degF", high_w=1600, high_a=1700)
    gauge("CHTMAX1", 362, 0, 500, "degF", high_w=420, high_a=450)

    # Heal the core flight keys and give demonstrative values. The conftest
    # fixture has a copy-paste bug that leaves VS flagged bad/fail (it clears
    # ROT's flags twice instead of VS's), so the VSI shows XXX; fix that here
    # and set nav needles so HSI/VSI/altimeter render live in the captures.
    demo = {
        "ALT": 3500.0, "VS": -350.0, "HEAD": 75.0, "TRACK": 78.0,
        "COURSE": 80.0, "CDI": 0.3, "GSI": -0.2, "ROT": 3.0, "ALAT": 0.05,
        "BARO": 29.92, "OAT": 12.0,
    }
    for k, v in demo.items():
        try:
            it = fix.db.get_item(k)
            fix.db.set_value(k, v)
            it.bad = False
            it.fail = False
            it.old = False
        except Exception:
            pass


@pytest.mark.skipif(not GENERATE, reason="set GENERATE_SCREENSHOTS=1 to render")
@pytest.mark.parametrize("config_path", CONFIG_FILES,
                         ids=[os.path.basename(p) for p in CONFIG_FILES])
def test_generate_screenshot(config_path, fix, qtbot, request):
    with open(config_path) as cf:
        config = yaml.safe_load(cf)

    _load_fonts()
    _seed_extra(fix)

    # Some widgets (e.g. airspeed_box) connect to hmi.actions in __init__, which
    # the app creates at startup via hmi.initialize(); do the same here.
    import pyefis.hmi as hmi
    if hmi.actions is None:
        hmi.initialize({})

    name = config.get("screenshot") or os.path.splitext(
        os.path.basename(config_path))[0]
    for key, value in (config.get("seed") or {}).items():
        fix.db.set_value(key, value)
        it = fix.db.get_item(key)
        it.bad = False
        it.fail = False
        it.old = False

    gui.initialize(config, "tests", {}, fullscreen=False)
    screen = gui.mainWindow.scr.object

    main = config.get("main", {})
    w = int(main.get("screenWidth") or 1000)
    h = int(main.get("screenHeight") or 1000)
    screen.resize(w, h)
    qtbot.wait(250)  # let layout + first paint settle

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{name}.png")
    assert screen.grab().save(out), f"failed to save {out}"
    assert os.path.getsize(out) > 0
    print(f"wrote {out} ({w}x{h})")

    gui.mainWindow.close()


@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not GENERATE, reason="set GENERATE_SCREENSHOTS=1 to render")
@pytest.mark.parametrize("screen_name", PRESET_SCREENS)
def test_generate_preset_screen(screen_name, fix, qtbot, request):
    _load_fonts()
    _seed_extra(fix)
    _auto_define_missing(fix)
    import pyefis.hmi as hmi
    if hmi.actions is None:
        hmi.initialize({})

    config, prefs = _assemble_real_config()
    if screen_name not in config.get("screens", {}):
        pytest.skip(f"{screen_name} not in assembled config")

    if _has_gl_ahrs(config["screens"][screen_name]):
        pytest.skip(f"{screen_name} uses GL virtual_vfr/SVS — capture on the Pi")

    # The interactive button bars evaluate pycond conditions that can form
    # feedback loops in the offscreen harness (which lacks the full app's input
    # wiring), hanging the build. Strip the button chrome for a clean
    # instruments-only capture; disable the BUTTONS feature flag too.
    prefs.setdefault("enabled", {})["BUTTONS"] = False
    screen_cfg = dict(config["screens"][screen_name])
    instruments = screen_cfg.get("instruments", [])
    screen_cfg["instruments"] = [
        ins for ins in instruments
        if not _is_button_chrome(ins)
    ]

    W, H = 1280, 720
    test_config = {
        "main": dict(config["main"], screenWidth=W, screenHeight=H),
        "screens": {"TEST": screen_cfg},
    }

    gui.initialize(test_config, REAL_CONFIG, prefs, fullscreen=False)
    screen = gui.mainWindow.scr.object
    screen.resize(W, H)
    qtbot.wait(400)  # let includes build, layout, and first paint settle

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"screen_{screen_name.lower()}.png")
    assert screen.grab().save(out), f"failed to save {out}"
    print(f"wrote {out} ({W}x{H})")

    gui.mainWindow.close()
