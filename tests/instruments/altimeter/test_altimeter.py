import pytest
from unittest import mock
from PyQt6.QtWidgets import QApplication, QGraphicsLineItem
from PyQt6.QtCore import Qt, qRound
from PyQt6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPaintEvent, QFontMetrics
from PyQt6 import QtGui
from pyefis.instruments import altimeter
import pyefis.hmi as hmi
from tests.utils import track_calls

funcAltitudeMeters = lambda x: x / 3.28084 
funcAltitudeFeet = lambda x: x             


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_altimeter(fix,qtbot):
    widget = altimeter.Altimeter()
    assert widget.getRatio() == 1
    qtbot.addWidget(widget)
    assert widget.item.value == 0
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    with track_calls(QPen, "setColor") as tracker:
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.GlobalColor.white))
        fix.db.get_item("ALT").bad = True
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.GlobalColor.gray))
        fix.db.get_item("ALT").bad = False
        fix.db.get_item("ALT").old = True
        widget.paintEvent(None)
        assert tracker.was_called_with("setColor",QColor(Qt.GlobalColor.gray))
        fix.db.get_item("ALT").old = False
        fix.db.get_item("ALT").fail = True
        with track_calls(QPainter, "setBrush") as tracker2:
            widget.paintEvent(None)
            assert tracker2.was_called_with("setBrush",QBrush(QColor(Qt.GlobalColor.red)))

def test_altimeter_unit_switching(fix,qtbot):
    hmi.initialize({})
    widget = altimeter.Altimeter()
    qtbot.addWidget(widget)
    assert widget.conversionFunction1(100) == 100
    assert widget.conversionFunction2(100) == 100
    assert widget.conversionFunction(100) == 100

    widget.conversionFunction1 = funcAltitudeFeet
    widget.unitsOverride1 = 'Ft'
    widget.conversionFunction2 = funcAltitudeMeters
    widget.unitsOverride2 = 'M'
    widget.unitGroup = 'Altitude'
    widget.setUnitSwitching()
    fix.db.get_item("ALT").value = 1100
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.paintEvent(None)
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    widget.paintEvent(None)
    assert widget._altimeter != 1100
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    assert widget._altimeter == 1100
    # Test branches that should do nothing:
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggl")
    hmi.actions.trigger("Set Instrument Units","IAS:Toggle")

    assert widget.getAltimeter() == 1100


def test_altimeter_tape(fix,qtbot):
    widget = altimeter.Altimeter_Tape()
    widget.redraw()
    qtbot.addWidget(widget)
    assert widget.item.value == 0
    assert widget.pph == 0.3
    widget = altimeter.Altimeter_Tape(font_percent=0.5)
    qtbot.addWidget(widget)
    assert widget.pph != 0.3
    widget.resize(100,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.font_mask = None
    widget.resize(90,200)
    #widget.paintEvent(None)


def test_altimeter_tape_honors_div_options(fix, qtbot):
    """The tape's tick spacing / decimals / mask are configurable; they used to
    be hardcoded, so YAML options like minorDiv were silently ignored."""
    widget = altimeter.Altimeter_Tape(
        majorDiv=500, minorDiv=200, total_decimals=3, font_mask="000",
        round_to=100, font_scale=1.2)
    qtbot.addWidget(widget)
    widget.resize(80, 200)
    widget.show()
    qtbot.waitExposed(widget)                  # exercise resizeEvent font path
    assert widget.majorDiv == 500
    assert widget.minorDiv == 200
    assert widget.total_decimals == 3
    assert widget.font_mask == "000"
    assert widget.round_to == 100
    assert widget.font_scale == 1.2
    # defaults preserved when not supplied
    d = altimeter.Altimeter_Tape()
    qtbot.addWidget(d)
    assert (d.majorDiv, d.minorDiv, d.total_decimals, d.round_to) == (200, 100, 5, 0)


def test_altimeter_tape_rounds_numeric_box(fix, qtbot):
    """round_to snaps the numeric box value (so a jittery VS reads in steps and
    the odometer stops scrolling); the tape itself stays on the raw value."""
    widget = altimeter.Altimeter_Tape(dbkey="VS", round_to=100)
    qtbot.addWidget(widget)
    widget.resize(60, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget._altimeter = 137
    widget.redraw()
    assert widget.numerical_display.value == 100      # snapped to nearest 100
    widget._altimeter = -260
    widget.redraw()
    assert widget.numerical_display.value == -300
    # round_to=0 leaves the value untouched
    raw = altimeter.Altimeter_Tape(dbkey="VS")
    qtbot.addWidget(raw)
    raw.resize(60, 200)
    raw.show()
    qtbot.waitExposed(raw)
    raw._altimeter = 137
    raw.redraw()
    assert raw.numerical_display.value == 137


def test_altimeter_tape_numeric_box_can_be_hidden(fix, qtbot):
    """numeric_box=False omits the embedded readout and renders just the tape;
    the old/bad/fail setters and redraw must not choke on the missing box."""
    widget = altimeter.Altimeter_Tape(dbkey="VS", numeric_box=False)
    qtbot.addWidget(widget)
    widget.resize(60, 200)
    widget.show()
    qtbot.waitExposed(widget)
    assert widget.numerical_display is None
    # these all run on data events / construction and must be no-ops, not crashes
    widget.setAltOld(True)
    widget.setAltBad(True)
    widget.setAltFail(True)
    widget._altimeter = 250
    widget.redraw()
    widget.paintEvent(QtGui.QPaintEvent(widget.rect()))   # tape + pointer still paint
    # default keeps the box
    shown = altimeter.Altimeter_Tape(dbkey="VS")
    qtbot.addWidget(shown)
    shown.resize(60, 200)
    shown.show()
    qtbot.waitExposed(shown)
    assert shown.numerical_display is not None


def test_build_altimeter_tape_forwards_options(monkeypatch):
    """build_altimeter_tape must forward the supported tape options (and only
    those present) to the widget — the bug was that only dbkey was passed."""
    from pyefis.screens import screenbuilder_factory as sf
    captured = {}

    def fake_tape(screen, **kwargs):
        captured.update(kwargs)
        return mock.Mock()

    monkeypatch.setattr(sf.altimeter, "Altimeter_Tape", fake_tape)
    sf.build_altimeter_tape(None, {"options": {
        "dbkey": "VS", "minorDiv": 50, "majorDiv": 100, "round_to": 100,
        "total_decimals": 5, "font_mask": "00000", "numeric_box": False,
        "font_scale": 1.2}}, font_family="DejaVu")
    assert captured["dbkey"] == "VS"
    assert captured["minorDiv"] == 50 and captured["majorDiv"] == 100
    assert captured["total_decimals"] == 5 and captured["font_mask"] == "00000"
    assert captured["round_to"] == 100
    assert captured["numeric_box"] is False and captured["font_scale"] == 1.2

    # a config that omits the div keys forwards none of them (defaults apply)
    captured.clear()
    sf.build_altimeter_tape(None, {"options": {"dbkey": "ALT"}}, font_family="x")
    assert captured.get("dbkey") == "ALT"
    assert "minorDiv" not in captured and "majorDiv" not in captured


def test_altimeter_tape_unit_switching(fix,qtbot):
    hmi.initialize({})
    widget = altimeter.Altimeter_Tape()
    qtbot.addWidget(widget)
    assert widget.conversionFunction1(100) == 100
    assert widget.conversionFunction2(100) == 100
    assert widget.conversionFunction(100) == 100

    widget.conversionFunction1 = funcAltitudeFeet
    widget.unitsOverride1 = 'Ft'
    widget.conversionFunction2 = funcAltitudeMeters
    widget.unitsOverride2 = 'M'
    widget.unitGroup = 'Altitude'
    fix.db.get_item("ALT").value = 1100
    widget.resize(200,200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.setUnitSwitching()
    event = QPaintEvent(widget.rect())
    widget.paintEvent(event)
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    widget.paintEvent(event)
    assert widget._altimeter != 1100
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggle")
    assert widget._altimeter == 1100
    # Test branches that should do nothing:
    hmi.actions.trigger("Set Instrument Units","Altitude:Toggl")
    hmi.actions.trigger("Set Instrument Units","IAS:Toggle")

    assert widget.getAltimeter() == 1100
    widget.paintEvent(event)
    widget.setUnitSwitching()
    widget.keyPressEvent(None)
    widget.wheelEvent(None)
    widget.hide()
    widget.setUnitSwitching()


# =============================================================================
# Altimeter-tape requirements test catalog -- keyed to altimeter_widget_spec.md
# sec 4 (Markings, Awareness Cues & Annunciation) and avionics_reference.md
# sec 6.5.
#
# Docstrings: AL-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) tests are the
# executable gap tracker for the unimplemented AC 23.1311-1C sec 17.8 cues: the
# 500/1000-ft tick tiers (AL-MARK-001), the 6-second altitude trend
# (AL-TREND-001), and the altitude reference bug (AL-BUG-001, data-blocked -- no
# selected-altitude FIX key yet). Spec sec 5 carries the case<->requirement map.
# =============================================================================


def _show_alt_tape(qtbot, **kwargs):
    """Build an altimeter tape and drive resizeEvent so the scene (ticks, labels)
    is constructed at a real size."""
    widget = altimeter.Altimeter_Tape(**kwargs)
    qtbot.addWidget(widget)
    widget.resize(120, 400)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _horizontal_tick_x0(widget):
    """Distinct left-edge x of the horizontal tick lines -> one value per tick
    length tier. sec 17.8.a wants three tiers (1000 / 500 / minor)."""
    xs = set()
    for it in widget.scene.items():
        if isinstance(it, QGraphicsLineItem):
            ln = it.line()
            if ln.y1() == ln.y2():                 # horizontal = a scale tick
                xs.add(round(ln.x1(), 1))
    return xs


def test_al_cat_linear_tape_format(fix, qtbot):
    """AL-TC-001 | AL-DISP-001 | Linear moving-scale tape: a scrolling scale under a fixed
    pointer with a digital read-out; the scale scrolls with ALT. AC 23.1311-1C sec 17.8.a."""
    widget = _show_alt_tape(qtbot)
    assert widget.scene is not None                      # a scale was built
    assert widget.numerical_display is not None          # digital read-out (numeric_box)
    widget.setAltimeter(2500)
    assert widget.getAltimeter() == 2500
    assert widget.numerical_display.value == 2500        # read-out tracks present altitude


def test_al_cat_altitude_invalid_annunciation(fix, qtbot):
    """AL-TC-002 | AL-ANN-001 | Invalid altitude is annunciated on the read-out: fail ->
    XXX, old/bad -> not a stale number. AC 23.1311-1C sec 18; ref sec 2 governing rule."""
    widget = _show_alt_tape(qtbot)
    widget.setAltFail(True)
    assert widget.numerical_display.fail is True
    widget.setAltFail(False)
    widget.setAltOld(True)
    assert widget.numerical_display.old is True
    widget.setAltBad(True)
    assert widget.numerical_display.bad is True


def test_al_cat_standard_500_1000_ticks(fix, qtbot):
    """AL-TC-003 | AL-MARK-001 | The tape must denote standard 500- and 1,000-ft increments
    distinctly (1000 = longest + label, 500 = intermediate, minor = short). AC 23.1311-1C
    sec 17.8.a (p.43). Contract: three distinct tick-length tiers on the scale."""
    widget = _show_alt_tape(qtbot, majorDiv=1000, minorDiv=100)
    assert len(_horizontal_tick_x0(widget)) >= 3         # 1000 / 500 / minor tiers


def test_al_cat_six_second_trend_indicator(fix, qtbot):
    """AL-TC-004 | AL-TREND-001 | A 6-second altitude-trend indicator predicts altitude
    ahead for level-off look-ahead. AC 23.1311-1C sec 17.8.b (p.43). Contract: show_trend +
    trend_lookahead=6.0 + _push_trend maintaining a signed _trend_px (climb up / descend down)."""
    widget = _show_alt_tape(qtbot)
    assert widget.show_trend is True
    assert widget.trend_lookahead == 6.0

    widget._trend_history = []
    widget._push_trend(100.0, 1000.0)
    assert widget._trend_px == 0.0                       # one sample -> no trend
    widget._push_trend(102.0, 1200.0)                    # +200 ft in 2 s -> climbing
    assert widget._trend_px > 0

    widget._trend_history = []
    widget._push_trend(200.0, 1200.0)
    widget._push_trend(202.0, 1000.0)                    # -200 ft in 2 s -> descending
    assert widget._trend_px < 0


def test_al_cat_trend_defaults_off_for_vs_tape(fix, qtbot):
    """AL-TC-004b | AL-TREND-001 | The trend is an ALTITUDE cue (sec 17.8.b); the shared
    Altimeter_Tape class must not sprout a trend on a VS tape by default, though an explicit
    show_trend still wins."""
    vs = altimeter.Altimeter_Tape(dbkey="VS")
    assert vs.show_trend is False                        # VS tape: no default trend
    alt = altimeter.Altimeter_Tape(dbkey="ALT")
    assert alt.show_trend is True                        # ALT tape: trend on
    forced = altimeter.Altimeter_Tape(dbkey="VS", show_trend=True)
    assert forced.show_trend is True                     # explicit config wins


@pytest.mark.xfail(strict=True, reason="AL-BUG-001 data-blocked: no selected-altitude FIX key")
def test_al_cat_altitude_reference_bug(fix, qtbot):
    """AL-TC-005 | AL-BUG-001 | An altitude reference bug marks the selected altitude on the
    tape (level-off cue). AC 23.1311-1C sec 17.8.a (p.43). Data-blocked: fix-gateway
    publishes no selected-altitude key yet. Contract: w.selected_altitude + w.alt_bug."""
    widget = _show_alt_tape(qtbot)
    assert getattr(widget, "selected_altitude", None) is not None
    assert getattr(widget, "alt_bug", None) is not None
