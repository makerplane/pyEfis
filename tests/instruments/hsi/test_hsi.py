from unittest import mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPen
from PyQt6.QtWidgets import QApplication

from pyefis.instruments import hsi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def _set_quality(item, *, old=False, bad=False, fail=False):
    item.old = old
    item.bad = bad
    item.fail = fail


def test_hsi_default_flags_heading_and_bug(fix, qtbot):
    widget = hsi.HSI(font_percent=0.1)
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()
    qtbot.waitExposed(widget)

    assert widget.getRatio() == 1
    assert widget.cdi_enabled is False
    assert widget.gsi_enabled is False
    assert widget._CdiOld is False
    assert widget._GsiFail is False
    assert widget.fontSize == 30
    assert widget.getHeading() == 0
    assert widget.getCoursePointer() == 0
    assert len(widget.labels) > 0

    widget.rotate = mock.Mock()
    widget.heading = 350
    widget.heading = 10
    widget.heading = 200
    widget.heading = 350
    widget.heading = 100
    widget.heading = 200
    widget.heading = 200

    assert widget.heading == 200
    assert widget.rotate.call_args_list[0].args == (10,)
    assert widget.rotate.call_args_list[1].args == (-20,)
    assert widget.rotate.call_args_list[2].args == (170,)
    assert widget.rotate.call_args_list[3].args == (-150,)
    assert widget.rotate.call_args_list[4].args == (-110,)

    widget.coursePointer = 370
    assert widget.coursePointer == 360
    assert widget.course_pointer is not None
    assert widget.course_pointer.polygon().count() == 3
    widget.coursePointer = 360

    widget.keyPressEvent(None)
    widget.wheelEvent(None)
    widget.showEvent(None)


def test_hsi_resize_does_not_accumulate_rotation(fix, qtbot):
    """resizeEvent must re-apply the absolute -heading rotation from a clean
    transform. It fires repeatedly (layout settling / geometry changes); without
    resetting first, each call stacked another -heading rotation and the card
    showed heading+offset (e.g. 290 when actually 052)."""
    import math
    widget = hsi.HSI()
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.setHeading(52)

    widget.resizeEvent(None)
    t1 = widget.transform()
    widget.resizeEvent(None)
    widget.resizeEvent(None)
    t2 = widget.transform()

    assert t1 == t2                                      # idempotent, no stacking
    # transform is exactly a -52 rotation, not a multiple of it
    assert abs(t2.m11() - math.cos(math.radians(52))) < 1e-6


def test_hsi_course_pointer_before_resize_and_no_deviation_paint(fix, qtbot):
    widget = hsi.HSI()
    qtbot.addWidget(widget)
    widget.setCoursePointer(45)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)

    assert widget.coursePointer == 45
    widget.paintEvent(QPaintEvent(widget.rect()))


def test_hsi_source_auto_color(fix, qtbot):
    """source_auto_color tints the course pointer + CDI by NAVSRC: magenta
    (course_color) for a GPS source (2), green (vloc_color) for a NAV source
    (0/1). Off, or with no NAVSRC, falls back to the static colours."""
    widget = hsi.HSI(cdi_enabled=True)
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)

    widget.setNavsrc(2)                                   # GPS
    assert widget._source_color() == QColor(widget.course_color)
    assert widget.course_pointer.brush().color() == QColor(widget.course_color)

    widget.setNavsrc(0)                                   # NAV1
    assert widget._source_color() == QColor(widget.vloc_color)
    assert widget.course_pointer.brush().color() == QColor(widget.vloc_color)

    widget.source_auto_color = False                      # static fallback
    assert widget._source_color() is None


def test_hsi_source_label(fix, qtbot):
    """The source annunciation reads GPS for a GPS source, VLOCn from NAVSRC
    alone, and refines to VOR/LOC when NAVTYPE is set."""
    widget = hsi.HSI()
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)

    widget.setNavsrc(2)
    assert widget._source_label() == "GPS"
    widget.setNavsrc(0)
    assert widget._source_label() == "VLOC1"     # no NAVTYPE -> VLOC fallback
    widget.setNavtype(1)                         # VOR
    assert widget._source_label() == "VOR1"
    widget.setNavtype(2)                         # LOC
    assert widget._source_label() == "LOC1"
    widget.setNavsrc(1)                          # NAV2
    widget.setNavtype(0)                         # type unknown -> VLOC fallback
    assert widget._source_label() == "VLOC2"


def test_hsi_cdi_gsi_old_tracks_oldchanged_not_failchanged(fix, qtbot):
    """Regression: CDI/GSI 'old' and 'bad' must follow the oldChanged/badChanged
    signals. They were wired to failChanged, so once the items were old at
    construction (no data yet) the flags latched True and the deviation needles
    never reappeared even with valid data."""
    widget = hsi.HSI(cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(widget)
    widget._CdiOld = widget._GsiOld = True
    widget._CdiBad = widget._GsiBad = True

    widget.cdidb.oldChanged.emit(False)
    widget.cdidb.badChanged.emit(False)
    widget.gsidb.oldChanged.emit(False)
    widget.gsidb.badChanged.emit(False)
    widget._GsiFail = False

    assert widget._CdiOld is False and widget._CdiBad is False
    assert widget._GsiOld is False and widget._GsiBad is False

    # with the flags clear, the needles are shown independently per channel
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.paintEvent(QPaintEvent(widget.rect()))
    assert widget._showCDI is True
    assert widget._showGSI is True


def test_hsi_gsi_hidden_when_no_glideslope(fix, qtbot):
    """GSV=0 (a VOR has no glideslope) hides the GS needle while the lateral CDI
    stays. GSV absent or >=0.5 -> GS shown on its own quality."""
    widget = hsi.HSI(cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget._CdiOld = widget._CdiBad = widget._GsiOld = widget._GsiBad = widget._GsiFail = False

    widget.setGsv(1)
    widget.paintEvent(QPaintEvent(widget.rect()))
    assert widget._showGSI is True

    widget.setGsv(0)                       # no glideslope (VOR)
    widget.paintEvent(QPaintEvent(widget.rect()))
    assert widget._showGSI is False        # GS needle hidden
    assert widget._showCDI is True         # lateral guidance unaffected

    widget.setTofrom(1)                    # TO -> triangle renders without error
    widget.paintEvent(QPaintEvent(widget.rect()))


def test_hsi_source_label_tap_cycles_navsrc(fix, qtbot, monkeypatch):
    """Tapping the nav-source annunciation writes the next NAVSRC (GPS 2 -> NAV1
    0); taps outside the label do nothing."""
    widget = hsi.HSI(cdi_enabled=True)
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.navsrcdb = object()             # simulate a panel with a nav source
    widget._navsrc = 2                      # GPS
    widget.paintEvent(QPaintEvent(widget.rect()))   # sets the tap rect
    assert widget._source_label_rect is not None

    written = []
    monkeypatch.setattr(hsi.fix.db, "set_value", lambda k, v: written.append((k, v)))

    class _P:
        def __init__(s, x, y): s._x, s._y = x, y
        def x(s): return s._x
        def y(s): return s._y

    class _Ev:
        def __init__(s, x, y): s._p = _P(x, y)
        def pos(s): return s._p
        def accept(s): pass

    r = widget._source_label_rect
    widget.mousePressEvent(_Ev(r[0] + r[2] // 2, r[1] + r[3] // 2))   # inside label
    assert written == [("NAVSRC", 0.0)]    # GPS(2) -> NAV1(0)


def test_hsi_enabled_cdi_gsi_state_and_paint_paths(fix, qtbot):
    _set_quality(fix.db.get_item("HEAD"))
    _set_quality(fix.db.get_item("COURSE"))
    _set_quality(fix.db.get_item("CDI"))
    _set_quality(fix.db.get_item("GSI"))
    fix.db.set_value("CDI", 0.5)
    fix.db.set_value("GSI", -0.5)

    widget = hsi.HSI(cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(widget)
    widget.visiblePointers = [False, False, False, False]
    widget.resize(300, 300)
    widget.show()
    qtbot.waitExposed(widget)
    event = QPaintEvent(widget.rect())

    with track_calls(QPen, "setWidth") as tracker:
        widget.paintEvent(event)

    assert tracker.was_called_with("setWidth", 3)
    assert widget.cdi == 0.5
    assert widget.gsi == -0.5
    assert widget.isOld() is False
    assert widget.isFail() is False

    widget.update = mock.Mock()
    widget.cdi = -0.25
    widget.gsi = 0.25
    widget.setCdiOld(True)
    widget.setCdiBad(True)
    widget.setGsiOld(True)
    widget.setGsiBad(True)

    assert widget.cdi == -0.25
    assert widget.gsi == 0.25
    assert widget._CdiOld is True
    assert widget._CdiBad is True
    assert widget._GsiOld is True
    assert widget._GsiBad is True
    assert widget.update.call_count >= 4

    widget.paintEvent(event)
    assert widget._showCDI is False
    assert widget._showGSI is False


def test_hsi_quality_flags_hide_and_restore_labels(fix, qtbot):
    _set_quality(fix.db.get_item("HEAD"))
    _set_quality(fix.db.get_item("COURSE"))
    _set_quality(fix.db.get_item("CDI"))
    _set_quality(fix.db.get_item("GSI"))
    widget = hsi.HSI(cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(widget)
    widget.resize(300, 300)
    widget.show()
    qtbot.waitExposed(widget)

    widget.setHeadOld(True)
    widget.setHeadBad(True)
    widget.setCourseOld(True)
    widget.setCourseBad(True)
    assert widget.isOld() is True

    widget.setHeadFail(True)
    assert widget._HeadFail is True
    assert widget.isFail() is True
    assert all(label.opacity() == 0 for label in widget.labels)
    widget.setHeadFail(True)

    widget.setHeadBad(False)
    widget.setHeadFail(False)
    widget.setCourseBad(False)
    widget.setCourseFail(True)
    assert widget._CourseFail is True
    widget.setCourseFail(False)
    widget.setCourseFail(False)

    widget.setCdiFail(True)
    assert widget._CdiFail is True
    widget.setCdiFail(True)
    widget.setCdiFail(False)
    widget.setGsiFail(True)
    assert widget._GsiFail is True
    widget.setGsiFail(True)
    widget.setGsiFail(False)

    widget.setHeadOld(False)
    widget.setCourseOld(False)
    widget.setCdiOld(False)
    widget.setCdiBad(False)
    widget.setGsiOld(False)
    widget.setGsiBad(False)

    assert widget.isFail() is False
    assert widget.isOld() is False
    assert all(label.opacity() == 1 for label in widget.labels)


def test_hsi_setters_skip_noop_and_hidden_updates(fix, qtbot):
    _set_quality(fix.db.get_item("HEAD"))
    _set_quality(fix.db.get_item("COURSE"))
    _set_quality(fix.db.get_item("CDI"))
    _set_quality(fix.db.get_item("GSI"))
    widget = hsi.HSI(cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(widget)

    widget.update = mock.Mock()
    widget.setCdi(0.25)
    widget.setCdi(0.25)
    widget.setGsi(0)
    widget.setCdiOld(False)
    widget.setCdiBad(False)
    widget.setGsiOld(False)
    widget.setGsiBad(False)

    widget.update.assert_not_called()


def test_hsi_disabled_cdi_gsi_setters_do_not_update(fix, qtbot):
    widget = hsi.HSI(cdi_enabled=False, gsi_enabled=False)
    qtbot.addWidget(widget)
    widget.resize(200, 200)
    widget.show()
    qtbot.waitExposed(widget)
    widget.update = mock.Mock()

    widget.setCdiOld(True)
    widget.setCdiBad(True)
    widget.setCdiFail(True)
    widget.setGsiOld(True)
    widget.setGsiBad(True)
    widget.setGsiFail(True)

    assert widget._CdiOld is False
    assert widget._CdiBad is False
    assert widget._CdiFail is False
    assert widget._GsiOld is False
    assert widget._GsiBad is False
    assert widget._GsiFail is False
    widget.update.assert_not_called()


def test_heading_display_format():
    """The boxed heading readout is always three zero-padded digits with a
    trailing degree sign; 360 and 0 both read 000."""
    f = hsi.HeadingDisplay._fmt_heading
    assert f(3) == "003°"
    assert f(30) == "030°"
    assert f(0) == "000°"
    assert f(360) == "000°"
    assert f(90) == "090°"
    assert f(359.7) == "359°"      # truncates, like the old display


def test_heading_display_quality_and_heading_paths(fix, qtbot):
    _set_quality(fix.db.get_item("HEAD"))
    widget = hsi.HeadingDisplay(fg_color=Qt.GlobalColor.white)
    qtbot.addWidget(widget)
    widget.resize(300, 100)
    widget.show()
    qtbot.waitExposed(widget)
    widget.resizeEvent(None)
    event = QPaintEvent(widget.rect())

    assert widget.getHeading() == 0
    widget.update = mock.Mock()
    widget.heading = 361
    widget.heading = 360

    assert widget.heading == 360
    widget.update.assert_called_once_with()

    with track_calls(QPen, "__init__") as tracker:
        widget.setFail(True)
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))

    widget.setFail(False)
    with track_calls(QPen, "__init__") as tracker:
        widget.setBad(True)
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(255, 150, 0))

    with track_calls(QPen, "__init__") as tracker:
        widget.setBad(False)
        widget.setOld(True)
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(255, 150, 0))

    widget.setOld(False)
    widget.paintEvent(event)
    widget.showEvent(None)


def test_dg_tape_heading_and_events(fix, qtbot):
    widget = hsi.DG_Tape()
    qtbot.addWidget(widget)
    widget.resize(300, 100)
    widget.show()
    qtbot.waitExposed(widget)

    assert widget.getHeading() == 0
    assert widget.scene is not None
    widget.centerOn = mock.Mock()

    widget.heading = 45
    widget.heading = 45
    widget.showEvent(None)
    widget.keyPressEvent(None)
    widget.wheelEvent(None)

    assert widget.heading == 45
    assert widget.centerOn.call_count == 2


# =============================================================================
# HSI requirements test catalog -- keyed to hsi_widget_spec.md sec 7 (Flags,
# Alerts & Failure Annunciation) and avionics_reference.md.
#
# Each docstring: HSI-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) tests are the
# executable gap tracker for the not-yet-implemented warning flags: they fail
# today (the flag state does not exist) and will xpass -- which, under strict,
# fails the run -- the moment the flag is implemented, prompting removal of the
# marker. Spec sec 10 carries the full case<->requirement map.
# =============================================================================


def _mk_hsi(qtbot, **kw):
    w = hsi.HSI(**kw)
    qtbot.addWidget(w)
    w.resize(300, 300)
    w.show()
    qtbot.waitExposed(w)
    return w


def test_hsi_cat_all_valid_shows_both_needles(fix, qtbot):
    """HSI-TC-001 | HSI-FAIL-001 (happy path) | Every deviation signal valid and a
    glideslope present -> both the CDI and GS needles are shown."""
    w = _mk_hsi(qtbot, cdi_enabled=True, gsi_enabled=True)
    w._CdiOld = w._CdiBad = w._GsiOld = w._GsiBad = w._GsiFail = False
    w.setGsv(1)
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showCDI is True
    assert w._showGSI is True


def test_hsi_cat_cdi_hidden_when_old_or_bad(fix, qtbot):
    """HSI-TC-021 | HSI-FAIL-001 (CDI) | Stale (old) or invalid (bad) lateral deviation
    removes the CDI bar."""
    w = _mk_hsi(qtbot, cdi_enabled=True)
    w._CdiOld, w._CdiBad = True, False
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showCDI is False
    w._CdiOld, w._CdiBad = False, True
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showCDI is False


def test_hsi_cat_gsi_hidden_when_old_or_bad(fix, qtbot):
    """HSI-TC-031 | HSI-FAIL-001 (GSI) | Stale/invalid GS deviation removes the GS
    diamond even with a glideslope present."""
    w = _mk_hsi(qtbot, cdi_enabled=True, gsi_enabled=True)
    w.setGsv(1)
    w._GsiOld, w._GsiBad = True, False
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showGSI is False


def test_hsi_cat_gs_absent_when_gsv_zero(fix, qtbot):
    """HSI-TC-032 | HSI-ANN-003 (no-GS case) | GSV=0 (a VOR / no glideslope) -> GS scale
    absent, lateral CDI unaffected. The 'no GS present' branch, distinct from GS-lost
    (HSI-TC-103)."""
    w = _mk_hsi(qtbot, cdi_enabled=True, gsi_enabled=True)
    w._CdiOld = w._CdiBad = w._GsiOld = w._GsiBad = w._GsiFail = False
    w.setGsv(0)
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showGSI is False
    assert w._showCDI is True


def test_hsi_cat_cdi_full_scale_boundary(fix, qtbot):
    """HSI-TC-060 | HSI-DEV-001 (edge) | The normalized CDI at +/-1.0 full-scale (and 0)
    paints without error and stays shown; the source owns full-scale (spec sec 4.2)."""
    w = _mk_hsi(qtbot, cdi_enabled=True)
    w._CdiOld = w._CdiBad = False
    for dev in (1.0, -1.0, 0.0):
        w.setCdi(dev)
        w.paintEvent(QPaintEvent(w.rect()))
        assert w._showCDI is True


def test_hsi_cat_gsi_full_scale_boundary(fix, qtbot):
    """HSI-TC-062 | HSI-DEV-001 (edge) | The normalized GS at +/-1.0 full-scale (and 0)
    paints without error and stays shown."""
    w = _mk_hsi(qtbot, cdi_enabled=True, gsi_enabled=True)
    w.setGsv(1)
    w._GsiOld = w._GsiBad = w._GsiFail = False
    for dev in (1.0, -1.0, 0.0):
        w.setGsi(dev)
        w.paintEvent(QPaintEvent(w.rect()))
        assert w._showGSI is True


def test_hsi_cat_source_switch_tracks_colour_and_label(fix, qtbot):
    """HSI-TC-041 | HSI-COLOR-001 + HSI-SRC-001 (edge) | Switching NAVSRC GPS->NAV1->NAV2
    moves the source colour (magenta<->green) and the annunciation together."""
    w = _mk_hsi(qtbot, cdi_enabled=True)
    w.setNavsrc(2)
    assert w._source_color() == QColor(w.course_color) and w._source_label() == "GPS"
    w.setNavsrc(0)
    assert w._source_color() == QColor(w.vloc_color) and w._source_label() == "VLOC1"
    w.setNavsrc(1)
    assert w._source_color() == QColor(w.vloc_color) and w._source_label() == "VLOC2"


def test_hsi_cat_hdg_flag_on_head_fail(fix, qtbot):
    """HSI-TC-101 | HSI-ANN-001 | On HEAD fail the HSI annunciates a heading (compass)
    warning flag (IFH p.118; AC 25-11B 4.2): paintEvent sets w._showHdgFlag and draws a
    red HDG flag."""
    w = _mk_hsi(qtbot, cdi_enabled=True)
    w.setHeadFail(True)
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showHdgFlag is True


def test_hsi_cat_nav_flag_on_cdi_invalid(fix, qtbot):
    """HSI-TC-102 | HSI-ANN-002 | On selected-lateral-source fail/invalid the HSI shows a
    NAV warning flag and removes the CDI (IFH p.118/p.283): paintEvent sets w._showNavFlag
    and _showCDI is False."""
    w = _mk_hsi(qtbot, cdi_enabled=True)
    w.setCdiBad(True)
    w.setCdiFail(True)
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showNavFlag is True
    assert w._showCDI is False        # flag + remove the deviation bar


def test_hsi_cat_gs_flag_on_gs_lost(fix, qtbot):
    """HSI-TC-103 | HSI-ANN-003 | When a glideslope is expected (present) but its signal
    is lost/failed, the HSI shows a GS warning flag and no diamond -- distinct from 'no GS
    present' (GSV=0, HSI-TC-032) where the scale is simply absent (IFH p.283): paintEvent
    sets w._showGsFlag and _showGSI stays False (mutually exclusive)."""
    w = _mk_hsi(qtbot, cdi_enabled=True, gsi_enabled=True)
    w.setGsv(1)            # glideslope present / expected
    w.setGsiFail(True)     # ...but the GS signal has failed
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._showGsFlag is True
    assert w._showGSI is False       # flag replaces the diamond


# =============================================================================
# Heading / compass requirements test catalog -- keyed to heading_widget_spec.md
# sec 4 (Heading Presentation & Annunciation) and avionics_reference.md sec 4.4.
#
# Docstrings: HDG-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) test is the gap
# tracker for DG_Tape heading-invalid annunciation (AC 23.1311-1C sec 8.6.a):
# today the heading tape ignores HEAD fail/old/bad (an in-code TODO). Spec sec 5
# carries the case<->requirement map.
# =============================================================================


def test_hdg_cat_heading_presentation(fix, qtbot):
    """HDG-TC-001 | HDG-DISP-001 | Clear heading presentation: a boxed numeric readout plus
    a heading scale/tape with cardinal points. AC 23.1311-1C sec 8.6.b (p.23)."""
    _set_quality(fix.db.get_item("HEAD"))
    disp = hsi.HeadingDisplay(fg_color=Qt.GlobalColor.white)
    qtbot.addWidget(disp)
    disp.resize(200, 80)
    disp.show()
    qtbot.waitExposed(disp)
    disp.setHeading(90)
    assert disp.getHeading() == 90

    tape = hsi.DG_Tape()
    qtbot.addWidget(tape)
    tape.resize(300, 100)
    tape.show()
    qtbot.waitExposed(tape)
    assert tape.scene is not None
    assert tape.cardinal[:4] == ["N", "E", "S", "W"]      # cardinal points
    tape.setHeading(180)
    assert tape.getHeading() == 180


def test_hdg_cat_heading_format_wraps(fix, qtbot):
    """HDG-TC-002 | HDG-FMT-001 | Magnetic heading is three zero-padded digits, wrapping at
    360 (000-359). AC 23.1311-1C sec 8.6.b (p.23)."""
    f = hsi.HeadingDisplay._fmt_heading
    assert f(30) == "030°"
    assert f(0) == "000°"
    assert f(360) == "000°"        # wraps
    assert f(359.7) == "359°"


def test_hdg_cat_numeric_invalid_annunciation(fix, qtbot):
    """HDG-TC-003 | HDG-ANN-001 | The numeric heading readout annunciates invalid HEAD:
    fail -> red XXX, old/bad -> amber blank. AC 23.1311-1C sec 8.6.a; ref sec 2."""
    _set_quality(fix.db.get_item("HEAD"))
    widget = hsi.HeadingDisplay(fg_color=Qt.GlobalColor.white)
    qtbot.addWidget(widget)
    widget.resize(200, 80)
    widget.show()
    qtbot.waitExposed(widget)
    event = QPaintEvent(widget.rect())

    with track_calls(QPen, "__init__") as tracker:
        widget.setFail(True)
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))

    widget.setFail(False)
    with track_calls(QPen, "__init__") as tracker:
        widget.setBad(True)
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(255, 150, 0))


def test_hdg_cat_tape_invalid_annunciation(fix, qtbot):
    """HDG-TC-004 | HDG-ANN-001 | The heading tape must annunciate invalid HEAD (fail -> red
    flag, old/bad -> grey/amber) rather than keep scrolling a frozen tape. AC 23.1311-1C
    sec 8.6.a; ref sec 2. Contract: DG_Tape wires HEAD old/bad/fail (w._fail etc.) and
    paintEvent flags it."""
    _set_quality(fix.db.get_item("HEAD"))
    widget = hsi.DG_Tape()
    qtbot.addWidget(widget)
    widget.resize(300, 100)
    widget.show()
    qtbot.waitExposed(widget)
    event = QPaintEvent(widget.rect())

    fix.db.get_item("HEAD").fail = True
    assert widget._fail is True                           # quality wired
    with track_calls(QPen, "__init__") as tracker:
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))   # red flag
