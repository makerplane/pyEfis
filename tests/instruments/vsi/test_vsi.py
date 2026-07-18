from unittest import mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPen
from PyQt6.QtWidgets import QApplication

from pyefis.instruments import vsi
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def _show_widget(qtbot, widget, width=300, height=200):
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.resizeEvent(None)
    widget.show()
    qtbot.waitExposed(widget)
    return QPaintEvent(widget.rect())


def _parent(qtbot, update_period=None):
    parent = mock.Mock()
    parent.get_config_item = mock.Mock(return_value=update_period)
    return parent


def _reset_vs_item(fix):
    item = fix.db.get_item("VS")
    item.bad = False
    item.old = False
    item.fail = False
    return item


def test_vsi_dial_defaults_setters_and_quality(fix, qtbot):
    item = _reset_vs_item(fix)
    widget = vsi.VSI_Dial()
    event = _show_widget(qtbot, widget)

    assert widget.getRatio() == 1
    assert widget.getROC() == 0

    widget.update = mock.Mock()
    widget.roc = 500
    widget.roc = 500

    assert widget.roc == 500
    widget.update.assert_called_once_with()

    widget.paintEvent(event)

    with track_calls(QPen, "__init__") as tracker:
        item.bad = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    item.bad = False
    with track_calls(QPen, "__init__") as tracker:
        item.old = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "__init__") as tracker:
        item.old = False
        item.fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))


def test_vsi_pfd_value_branches_and_events(fix, qtbot):
    widget = vsi.VSI_PFD()
    event = _show_widget(qtbot, widget)

    assert widget.getValue() == 0

    widget.update = mock.Mock()
    widget.value = 250

    assert widget.value == 250
    widget.update.assert_called_once_with()

    widget.paintEvent(event)

    widget.value = -99999
    widget.paintEvent(event)

    widget.value = 99999
    widget.paintEvent(event)

    widget.max = 0
    widget.paintEvent(event)

    widget.keyPressEvent(None)
    widget.wheelEvent(None)


def test_vsi_pfd_resize_without_font_mask(fix, qtbot):
    widget = vsi.VSI_PFD()
    widget.font_mask = None
    _show_widget(qtbot, widget)

    assert widget.fontSize >= 0


def test_as_trend_tape_tracks_changed_and_unchanged_values(fix, qtbot):
    widget = vsi.AS_Trend_Tape()
    _show_widget(qtbot, widget)

    widget.setAS_Trend(10)

    assert widget._airspeed == 10
    assert widget._airspeed_trend == [10]
    assert widget._airspeed_diff == 600

    widget.setAS_Trend(10)

    assert widget._airspeed == 10
    assert widget._airspeed_trend == [10, 0]

    widget._airspeed_trend = list(range(widget.freq))
    widget.setAS_Trend(20)

    assert len(widget._airspeed_trend) == widget.freq
    assert widget._airspeed_trend[-1] == 10

    widget._airspeed_trend = list(range(widget.freq))
    widget.setAS_Trend(20)

    assert len(widget._airspeed_trend) == widget.freq
    assert widget._airspeed_trend[-1] == 0

    class NeitherEqualNorDifferent:
        def __eq__(self, other):
            return False

        def __ne__(self, other):
            return False

    widget.setAS_Trend(NeitherEqualNorDifferent())


def test_alt_trend_tape_resize_config_and_redraw_states(fix, qtbot):
    _reset_vs_item(fix)
    parent = _parent(qtbot, update_period=0)

    hidden_widget = vsi.Alt_Trend_Tape()
    hidden_widget.myparent = parent
    hidden_widget.resize(300, 200)
    hidden_widget.resizeEvent(None)
    hidden_widget.redraw()

    assert hidden_widget.indicator_line is None

    widget = vsi.Alt_Trend_Tape()
    widget.myparent = parent
    _show_widget(qtbot, widget)
    widget.redraw()

    assert widget.update_period == 0
    assert widget.y_offset(0) == widget.zero_y
    assert widget.indicator_line is not None
    parent.get_config_item.assert_any_call("update_period")

    widget.setVs(500)
    positive_rect = widget.indicator_line.rect()
    assert positive_rect.y() < widget.zero_y

    widget.setVs(-500)
    negative_rect = widget.indicator_line.rect()
    assert negative_rect.y() == widget.zero_y

    widget.fail = True
    assert widget.indicator_line is None
    assert widget.vstext.toPlainText() == "XXX"
    widget.redraw()
    assert widget.indicator_line is None

    widget.fail = False
    assert widget.indicator_line is not None

    widget.bad = True
    assert widget.getBad() is True
    assert widget.vstext.toPlainText() == ""

    widget.bad = False
    widget.old = True
    assert widget.getOld() is True
    assert widget.vstext.toPlainText() == ""

    widget.old = False
    widget.setVs(123.4)
    assert widget.vstext.toPlainText() == "123"


def test_alt_trend_tape_default_update_period_and_throttle(fix, qtbot):
    _reset_vs_item(fix)
    parent = _parent(qtbot)
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = parent
    _show_widget(qtbot, widget)

    assert widget.update_period == 0.1

    widget.last_update_time = vsi.time.time()
    widget.indicator_line = mock.Mock()
    widget.redraw()

    widget.indicator_line.setRect.assert_not_called()


def test_alt_trend_tape_unchanged_setters_skip_redraw(fix, qtbot):
    _reset_vs_item(fix)
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = _parent(qtbot, update_period=0)
    _show_widget(qtbot, widget)

    widget.redraw = mock.Mock()
    widget.setVs(widget._vs)
    widget.bad = widget._bad
    widget.old = widget._old
    widget.fail = widget._fail

    assert widget.getFail() is False
    widget.redraw.assert_not_called()


# =============================================================================
# VSI requirements test catalog -- keyed to vsi_widget_spec.md sec 4 (Scale,
# Sign & Annunciation) and avionics_reference.md sec 7.
#
# Docstrings: VSI-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) test is the gap
# tracker for VSI_PFD invalid-VS annunciation (AC 25-11B Table 4-6: display of
# misleading vertical speed = Major): today its magenta dot always draws. Spec
# sec 5 carries the case<->requirement map.
# =============================================================================


def test_vsi_cat_scale_zero_and_sign(fix, qtbot):
    """VSI-TC-001 | VSI-DISP-001 | The VSI shows a performance-appropriate scale with a
    clear zero and up=climb / down=descend. AC 23.1311-1C sec 8.11 (p.24); AC 25-11B sec A.6."""
    _reset_vs_item(fix)
    tape = vsi.Alt_Trend_Tape()
    tape.myparent = _parent(qtbot, update_period=0)
    _show_widget(qtbot, tape)
    assert tape.y_offset(0) == tape.zero_y                 # clear zero reference
    assert tape.y_offset(1000) < tape.zero_y               # climb -> up
    assert tape.y_offset(-1000) > tape.zero_y              # descend -> down

    pfd = vsi.VSI_PFD()
    _show_widget(qtbot, pfd)
    assert pfd.max == 2000                                 # performance range (fpm)
    assert (2000, "2000") in pfd.marks                     # marks span the range


def test_vsi_cat_dial_invalid_annunciation(fix, qtbot):
    """VSI-TC-002 | VSI-ANN-001 | The round dial annunciates invalid VS: fail -> red XXX,
    old/bad -> grey. AC 25-11B Table 4-6 (p.32, Major); ref sec 2."""
    item = _reset_vs_item(fix)
    widget = vsi.VSI_Dial()
    event = _show_widget(qtbot, widget)

    with track_calls(QPen, "__init__") as tracker:
        item.bad = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    item.bad = False
    with track_calls(QPen, "__init__") as tracker:
        item.fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))


def test_vsi_cat_tape_invalid_annunciation(fix, qtbot):
    """VSI-TC-003 | VSI-ANN-001 | The VS tape annunciates invalid VS: fail -> XXX + bar
    removed, old/bad -> blank value. AC 25-11B Table 4-6 (p.32, Major); ref sec 2."""
    _reset_vs_item(fix)
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = _parent(qtbot, update_period=0)
    _show_widget(qtbot, widget)
    widget.redraw()
    assert widget.indicator_line is not None

    widget.fail = True
    assert widget.vstext.toPlainText() == "XXX"            # fail -> flag
    assert widget.indicator_line is None                   # ...and bar removed
    widget.fail = False
    widget.bad = True
    assert widget.vstext.toPlainText() == ""               # bad -> no live value
    widget.bad = False
    widget.old = True
    assert widget.vstext.toPlainText() == ""               # old -> no live value


def test_vsi_cat_pfd_invalid_annunciation(fix, qtbot):
    """VSI-TC-004 | VSI-ANN-001 | The PFD moving-dot VSI must annunciate invalid VS rather
    than keep drawing the magenta dot (misleading VS = Major, AC 25-11B Table 4-6 p.32).
    Contract: on fail paintEvent draws a red flag (no magenta dot); on old/bad the dot greys."""
    item = _reset_vs_item(fix)
    widget = vsi.VSI_PFD()
    event = _show_widget(qtbot, widget)
    widget.value = 500

    item.fail = True
    with track_calls(QPen, "__init__") as tracker:
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))   # red fail flag

    item.fail = False
    item.old = True
    with track_calls(QColor, "__init__") as tracker:
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))  # degraded -> grey


def test_vsi_cat_trend_tape_configurable_scale(fix, qtbot):
    """VSI-TC-005 | VSI-DISP-001 | The trend tape's range and graduations are
    configurable so the scale suits the airplane's climb/descent performance
    (AC 23.1311-1C sec 8.11 p.24; AC 25-11B sec A.6 p.74). Closes the
    vsi_widget_spec sec 7 'configurable range' open item."""
    _reset_vs_item(fix)
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = _parent(qtbot, update_period=0)
    widget.maxvs = 1000
    widget.minorDiv = 100
    widget.numberedDiv = 500
    _show_widget(qtbot, widget)
    # full scale honoured: +/-1000 maps to the tape extents around zero
    assert widget.y_offset(1000) < widget.y_offset(0) < widget.y_offset(-1000)
    span = widget.y_offset(-1000) - widget.y_offset(1000)
    assert abs(span - (widget.height() - widget.top_margin)) < 2.0
    # numbered graduations follow numberedDiv (labels in hundreds)
    labels = {t.toPlainText() for t in widget.scene.items()
              if hasattr(t, "toPlainText")}
    assert {"10", "5", "0", "-5", "-10"} <= labels          # every 500 fpm
    assert "2" not in labels                                # not the old 200 grid


def test_vsi_cat_trend_tape_bg_opacity(fix, qtbot):
    """VSI-TC-006 | display convention | The tape face honours bg_color +
    bg_opacity (percent) like the other boxed instruments; 0 = transparent."""
    _reset_vs_item(fix)
    widget = vsi.Alt_Trend_Tape()
    widget.myparent = _parent(qtbot, update_period=0)
    widget.bg_color = "#102040"
    widget.bg_opacity = 40
    _show_widget(qtbot, widget)
    rects = [i for i in widget.scene.items()
             if i.__class__.__name__ == "QGraphicsRectItem"]
    face = max(rects, key=lambda r: r.rect().width() * r.rect().height())
    c = face.brush().color()
    assert (c.red(), c.green(), c.blue()) == (0x10, 0x20, 0x40)
    assert abs(c.alphaF() - 0.4) < 0.02
