from unittest import mock

import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPaintEvent
from PyQt6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView

from pyefis.instruments import ai


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def _reset_ai_items(fix, old=False, bad=False, fail=False):
    for key in ["PITCH", "ROLL", "ALAT", "TAS"]:
        item = fix.db.get_item(key)
        item.old = old
        item.bad = bad
        item.fail = fail


def _show_ai(qtbot, widget, width=240, height=220):
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.show()
    qtbot.waitExposed(widget)
    return QPaintEvent(widget.viewport().rect())


def test_ai_horizon_position(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    _show_ai(qtbot, widget, width=300, height=300)

    # Default: centred -> zero offset, so the plain AI is unchanged.
    assert widget.horizon_position == 50
    assert widget._horizon_offset_px() == 0.0
    assert widget._horizon_offset_deg() == 0.0

    # Raised to two-thirds up: a positive screen offset (fraction of height)
    # and a height-independent look-down angle (fraction of the pitch FOV).
    widget.horizon_position = 67
    assert round(widget._horizon_offset_px(), 3) == round(0.17 * widget.height(), 3)
    assert round(widget._horizon_offset_deg(), 3) == round(0.17 * widget.pitchDegreesShown, 3)
    # redraw applies it without error at a banked, raised attitude.
    widget._rollAngle = 25
    widget._pitchAngle = 5
    widget.redraw()


def test_ai_resize_paint_and_input_events(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI(font_percent=0.2)
    event = _show_ai(qtbot, widget)

    assert widget.fontSize == 48
    assert widget.bankAngleRadius == pytest.approx(220 / 3)
    assert widget.getPitchAngle() == 0
    assert widget.getRollAngle() == 0
    assert widget.getAIOld() is False
    assert widget.getAIBad() is False
    assert widget.getAIFail() is False

    widget.paintEvent(event)

    widget.drawBankMarkers = False
    widget.paintEvent(event)

    widget.keyPressEvent(None)
    widget.wheelEvent(None)
    widget.showEvent(None)


def test_ai_symbology_can_be_fully_hidden(fix, qtbot):
    """SVS-as-background mode: aircraft_symbol 'none' draws nothing, and
    bankOpacity / horizonOpacity 0 hide the bank cluster and the
    zero-pitch reference line. Defaults leave everything solid."""
    _reset_ai_items(fix)
    widget = ai.AI()
    # Defaults keep today's look (and match the schema-gate Props).
    assert widget.bankOpacity == 1.0
    assert widget.horizonOpacity == 1.0

    widget.aircraft_symbol = "none"
    widget.bankOpacity = 0.0
    widget.horizonOpacity = 0.0
    event = _show_ai(qtbot, widget)

    # "none" short-circuits before touching the painter at all.
    painter = mock.Mock()
    widget._draw_aircraft_symbol(painter, 240, 220)
    assert painter.method_calls == []

    # The zero-pitch line is invisible, paint runs clean, and the
    # caution states are still computed with the cluster hidden.
    assert widget._horizon_line.opacity() == 0.0
    widget._rollAngle = 70.0
    widget.paintEvent(event)
    assert widget._excessive_bank is True

    # Partial transparency paints clean too.
    widget.bankOpacity = 0.5
    widget._rollAngle = 0.0
    widget.paintEvent(event)


def test_ai_symbol_scale_and_bank_placement(fix, qtbot):
    """symbol_scale multiplies the reference symbol; bank_position /
    bank_radius move and size the bank cluster. Defaults reproduce the
    classic geometry exactly."""
    _reset_ai_items(fix)
    widget = ai.AI()
    assert widget.symbol_scale == 1.0
    assert widget.bank_position == 50
    assert widget.bank_radius == pytest.approx(100.0 / 3.0)

    widget.bank_radius = 20.0
    widget.bank_position = 25
    widget.symbol_scale = 2.0
    event = _show_ai(qtbot, widget, width=300, height=300)

    # bank_radius drives the default arc radius (explicit
    # bankAngleRadius px would win instead).
    assert widget.bankAngleRadius == pytest.approx(300 * 0.20)
    # anchor: 25% up from the bottom of a 300px widget
    assert widget._bank_anchor_y(300) == pytest.approx(225.0)
    widget.paintEvent(event)

    # An explicit pixel radius still wins over the percent.
    widget2 = ai.AI()
    widget2.bankAngleRadius = 77
    widget2.bank_radius = 20.0
    _show_ai(qtbot, widget2, width=300, height=300)
    assert widget2.bankAngleRadius == 77


def test_ai_resize_with_gray_quality_and_custom_bank_radius(fix, qtbot):
    _reset_ai_items(fix, old=True, bad=True)
    widget = ai.AI()
    widget.bankAngleRadius = 42
    _show_ai(qtbot, widget)

    assert widget.bankAngleRadius == 42
    assert widget.getAIOld() is True
    assert widget.getAIBad() is True


def test_ai_resize_can_skip_unmatched_minor_ticks(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    widget.minorDiv = 7
    _show_ai(qtbot, widget)

    assert widget.pitchItems


def test_ai_setters_bound_values_and_skip_unchanged_or_failed(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    _show_ai(qtbot, widget)
    widget.redraw = mock.Mock()
    widget.update = mock.Mock()

    # P4 frame clock: setters STORE state and mark the frame dirty;
    # the repaint happens on the next frame tick, not in the slot.
    widget._frame_dirty = False
    widget.rollAngle = 999
    assert widget.rollAngle == 180
    assert widget._frame_dirty is True
    widget.redraw.assert_not_called()

    widget._frame_dirty = False
    widget.rollAngle = 180          # unchanged -> not dirtied
    assert widget._frame_dirty is False

    widget.setLateralAcceleration(9)
    assert widget._latAccel == 0.3
    assert widget._frame_dirty is True

    widget._frame_dirty = False
    widget.setLateralAcceleration(0.3)
    assert widget._frame_dirty is False

    widget.setTrueAirspeed(400)
    assert widget._tas == 400
    assert widget._frame_dirty is True

    widget._frame_dirty = False
    widget.setTrueAirspeed(400)
    assert widget._frame_dirty is False

    widget.pitchAngle = -999
    assert widget.pitchAngle == -90
    assert widget._frame_dirty is True

    widget._frame_dirty = False
    widget.pitchAngle = -90
    assert widget._frame_dirty is False

    # The frame tick applies pending changes exactly once...
    widget._frame_dirty = True
    widget._frame_tick()
    widget.redraw.assert_called_once_with()
    widget.update.assert_called_once_with()
    # ...and a clean tick with nothing changed repaints nothing.
    widget._frame_tick()
    assert widget.redraw.call_count == 1

    widget.setAIFailRoll(True)
    widget.setRollAngle(0)
    widget.setPitchAngle(0)
    assert widget.rollAngle == 180
    assert widget.pitchAngle == -90


def test_ai_hidden_setters_update_without_redraw_or_repaint(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    qtbot.addWidget(widget)
    widget.resize(240, 220)
    widget.redraw = mock.Mock()
    widget.update = mock.Mock()

    widget.setRollAngle(15)
    widget.setPitchAngle(12)
    widget.setLateralAcceleration(-9)
    widget.setTrueAirspeed(120)

    assert widget.rollAngle == 15
    assert widget.pitchAngle == 12
    assert widget._latAccel == -0.3
    assert widget._tas == 120
    widget.redraw.assert_not_called()
    widget.update.assert_not_called()


def test_ai_quality_flag_helpers_before_and_after_resize(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()

    widget.setFail(True, "ROLL")
    widget.setFail(True, "ROLL")
    assert widget.getAIFail() is True

    widget.setOld(True, "PITCH")
    widget.setOld(True, "PITCH")
    assert widget.getAIOld() is True

    widget.setBad(True, "ALAT")
    widget.setBad(True, "ALAT")
    assert widget.getAIBad() is True

    _show_ai(qtbot, widget)
    widget.redraw = mock.Mock()

    widget.setAIFailRoll(False)
    assert QGraphicsView.scene(widget) == widget.scene

    widget.setAIFailPitch(True)
    assert QGraphicsView.scene(widget) == widget.fail_scene
    widget.setAIFailLAcc(True)
    widget.setAIFailTAS(True)
    assert widget.getAIFail() is True

    widget.setAIFailPitch(False)
    widget.setAIFailLAcc(False)
    widget.setAIFailTAS(False)
    assert widget.getAIFail() is False
    assert QGraphicsView.scene(widget) == widget.scene
    assert widget.redraw.called

    widget.setAIOldRoll(True)
    widget.setAIOldPitch(False)
    widget.setAIOldLAcc(False)
    widget.setAIOldTAS(False)
    assert widget.getAIOld() is True

    widget.setAIOldRoll(False)
    assert widget.getAIOld() is False

    widget.setAIBadRoll(True)
    widget.setAIBadPitch(False)
    widget.setAIBadLAcc(False)
    widget.setAIBadTAS(False)
    assert widget.getAIBad() is True

    widget.setAIBadRoll(False)
    assert widget.getAIBad() is False


def test_ai_failure_recovery_keeps_gray_when_old_or_bad_remain(fix, qtbot):
    _reset_ai_items(fix, old=True)
    widget = ai.AI()
    _show_ai(qtbot, widget)

    widget.setAIFailRoll(True)
    widget.setAIFailRoll(False)
    assert QGraphicsView.scene(widget) == widget.scene


def test_ai_failure_recovery_restores_color_when_quality_is_good(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    _show_ai(qtbot, widget)

    widget.setAIFailRoll(True)
    widget.setAIFailRoll(False)

    assert QGraphicsView.scene(widget) == widget.scene


def test_ai_failure_recovery_before_sky_rect_exists(fix):
    _reset_ai_items(fix)
    widget = ai.AI()
    widget.fail_scene = QGraphicsScene()
    widget.scene = QGraphicsScene()
    widget.redraw = mock.Mock()

    widget.setAIFailRoll(True)
    widget.setAIFailRoll(False)

    assert QGraphicsView.scene(widget) == widget.scene
    widget.redraw.assert_called_once_with()


def test_ai_paint_caps_standard_rate_bank_marker_angle(fix, qtbot):
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)

    widget.setTrueAirspeed(10000)
    widget.paintEvent(event)

    assert widget._tas == 10000


def test_fd_target_resize_and_update(qtbot):
    center = QPointF(100, 120)
    widget = ai.FDTarget(center, pixelsPerDeg=5)
    qtbot.addWidget(widget)
    widget.resize(80, 40)
    widget.show()
    qtbot.waitExposed(widget)

    assert widget.w == 80
    assert widget.h == 40
    assert center.x() == 60
    assert center.y() == 100

    widget.update(3, 30)

    assert widget.x() == 60
    assert widget.y() == 85
    assert widget.poly.polygon().count() == 4


# --- Flight Path Marker low-speed gating (issue #70) -------------------------

def _fpm_inputs_ok(widget):
    for k in ('VS', 'GS', 'TRACK', 'HEAD'):
        widget._fpm_fail[k] = False


def test_fpm_hidden_below_min_groundspeed(fix, qtbot):
    """Stationary/taxiing, the GPS track is noise so the FPM darts around --
    hide it until groundspeed gives a real solution."""
    widget = ai.AI()
    _fpm_inputs_ok(widget)
    widget._fpm_gs = 0.0
    assert widget._fpm_solution_valid() is False          # idle on the runway
    widget._fpm_gs = widget._FPM_MIN_GS_KT - 0.5
    assert widget._fpm_solution_valid() is False          # slow taxi
    widget._fpm_gs = widget._FPM_MIN_GS_KT + 5.0
    assert widget._fpm_solution_valid() is True           # moving -> solution


def test_fpm_hidden_when_required_input_failed(fix, qtbot):
    """A failed GPS input (e.g. no TRACK) also has no solution, regardless of
    speed."""
    widget = ai.AI()
    _fpm_inputs_ok(widget)
    widget._fpm_gs = 120.0
    assert widget._fpm_solution_valid() is True
    widget._fpm_fail['TRACK'] = True
    assert widget._fpm_solution_valid() is False


def test_fpm_solution_independent_of_optional_vpath(fix, qtbot):
    """VPATH is optional (real GPS won't publish it) -- it must not gate the
    FPM."""
    widget = ai.AI()
    _fpm_inputs_ok(widget)
    widget._fpm_gs = 120.0
    widget._fpm_fail['VPATH'] = True
    assert widget._fpm_solution_valid() is True


# =============================================================================
# AI requirements test catalog -- keyed to ai_widget_spec.md sec 4 (Flags,
# Alerts & Recovery Annunciation) and avionics_reference.md.
#
# Docstrings: AI-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) tests are the
# executable gap tracker for the unimplemented recovery/envelope alerts: they
# fail today and flip the run red when the alert is implemented, forcing removal
# of the marker. AI-LIM-001 stays xfail until fix-gateway publishes AOA / stall
# margin. Spec sec 5 carries the case<->requirement map.
# =============================================================================


def test_ai_cat_attitude_fail_shows_fail_scene(fix, qtbot):
    """AI-TC-001 | AI-ANN-001 | On PITCH/ROLL fail the AI removes the attitude and shows
    the fail display (XXX / fail_scene). Table 4-1 p.27 -- loss of attitude is
    Catastrophic."""
    _reset_ai_items(fix)
    widget = ai.AI()
    _show_ai(qtbot, widget)
    assert QGraphicsView.scene(widget) == widget.scene        # valid -> attitude shown
    widget.setAIFailPitch(True)
    assert widget.getAIFail() is True
    assert QGraphicsView.scene(widget) == widget.fail_scene   # failed -> XXX


def test_ai_cat_degraded_attitude_stays_greyed(fix, qtbot):
    """AI-TC-002 | AI-FAIL-001 | Stale/invalid (old/bad) attitude greys the display but
    keeps showing it -- degraded, not removed (that is the fail case)."""
    _reset_ai_items(fix, old=True, bad=True)
    widget = ai.AI()
    _show_ai(qtbot, widget)
    assert widget.getAIOld() is True and widget.getAIBad() is True
    assert widget.getAIFail() is False
    assert QGraphicsView.scene(widget) == widget.scene        # greyed, still shown


def test_ai_cat_slip_ball_tracks_lateral_accel(fix, qtbot):
    """AI-TC-003 | AI-SLIP-001 | The slip/skid ball deflects with lateral acceleration
    (ALAT). AC 25-11B App A A.2.6."""
    _reset_ai_items(fix)
    widget = ai.AI()
    _show_ai(qtbot, widget)
    widget.setLateralAcceleration(9)
    assert widget._latAccel == pytest.approx(0.3)             # slip right
    widget.setLateralAcceleration(-9)
    assert widget._latAccel == pytest.approx(-0.3)            # slip left
    widget.setLateralAcceleration(0)
    assert widget._latAccel == pytest.approx(0.0)             # coordinated


def test_ai_cat_recovery_chevrons_at_extreme_pitch(fix, qtbot):
    """AI-TC-101 | AI-CHEV-001 | Beyond the unusual-attitude pitch threshold the AI must
    show recovery chevrons pointing to the nearest horizon (recognize + recover < 1 s).
    AC 25-11B App A A.2.2 (p.70). Contract: paintEvent sets w._show_recovery_chevrons."""
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)

    widget.pitchAngle = 10           # normal climb -> no chevrons
    widget.paintEvent(event)
    assert widget._show_recovery_chevrons is False

    widget.pitchAngle = 45           # nose-high unusual attitude
    widget.paintEvent(event)
    assert widget._show_recovery_chevrons is True

    widget.pitchAngle = -30          # nose-low unusual attitude (lower threshold)
    widget.paintEvent(event)
    assert widget._show_recovery_chevrons is True


def test_ai_cat_excessive_bank_annunciation(fix, qtbot):
    """AI-TC-102 | AI-BANK-001 | Beyond the excessive-bank threshold (before stall buffet)
    the AI annunciates excessive bank (amber bank scale). AC 25-11B App A A.2.5 (p.70)."""
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)
    widget.rollAngle = 20            # normal bank -> no caution
    widget.paintEvent(event)
    assert widget._excessive_bank is False
    widget.rollAngle = 60            # steep bank -> caution
    widget.paintEvent(event)
    assert widget._excessive_bank is True


def test_ai_cat_declutter_at_unusual_attitude(fix, qtbot):
    """AI-TC-103 | AI-DCL-001 | At an unusual attitude the AI must de-clutter -- remove
    non-essential overlays, keep recovery info. AC 25-11B p.47, App A. Contract:
    paintEvent sets w._decluttered."""
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)

    widget.pitchAngle = 5            # normal attitude, gentle bank -> no de-clutter
    widget.rollAngle = 20
    widget.paintEvent(event)
    assert widget._decluttered is False

    widget.pitchAngle = 45           # unusual pitch -> de-clutter
    widget.rollAngle = 0
    widget.paintEvent(event)
    assert widget._decluttered is True

    widget.pitchAngle = 0            # steep bank alone (past unusualBankDeg) -> de-clutter
    widget.rollAngle = 70
    widget.paintEvent(event)
    assert widget._decluttered is True

    # A normal steep turn (excessive-bank caution) is NOT yet the unusual-attitude
    # regime -- the display stays fully cluttered so the pilot keeps all cues.
    widget.rollAngle = 50
    widget.paintEvent(event)
    assert widget._excessive_bank is True
    assert widget._decluttered is False


def test_ai_cat_excessive_sideslip_annunciation(fix, qtbot):
    """AI-TC-104 | AI-SLIP-002 | Beyond the excessive-sideslip threshold the AI gives a
    salient (amber) slip alert. AC 25-11B App A A.2.6 (p.70)."""
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)
    widget.setLateralAcceleration(0.1)   # small slip (in scale) -> no caution
    widget.paintEvent(event)
    assert widget._excessive_slip is False
    widget.setLateralAcceleration(0.3)   # ball pegged -> caution
    widget.paintEvent(event)
    assert widget._excessive_slip is True


@pytest.mark.xfail(strict=True, reason="AI-LIM-001 data-blocked: no AOA / stall-margin key yet")
def test_ai_cat_pitch_limit_indication(fix, qtbot):
    """AI-TC-105 | AI-LIM-001 | Approaching stall AOA the AI must show a pitch-limit
    indication. AC 25-11B App A A.2.4 (p.70). Data-blocked: fix-gateway publishes no AOA /
    stall-margin key yet (OnSpeed/AOA path). Contract: w._show_pitch_limit."""
    _reset_ai_items(fix)
    widget = ai.AI()
    event = _show_ai(qtbot, widget)
    widget.paintEvent(event)
    assert widget._show_pitch_limit is True
