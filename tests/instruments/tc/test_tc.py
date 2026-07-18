from unittest import mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPen
from PyQt6.QtWidgets import QApplication, QWidget

from pyefis.instruments import tc
from tests.utils import track_calls


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


@pytest.fixture
def config_parent(qtbot):
    parent = QWidget()
    parent.get_config_item = mock.Mock(return_value=None)
    qtbot.addWidget(parent)
    return parent


def _show_widget(qtbot, widget, width=300, height=200):
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.resizeEvent(None)
    widget.show()
    qtbot.waitExposed(widget)
    return QPaintEvent(widget.rect())


def test_turn_coordinator_dial_defaults_and_setters(fix, qtbot, config_parent):
    widget = tc.TurnCoordinator(parent=config_parent)
    event = _show_widget(qtbot, widget)

    assert widget.getRatio() == 1
    assert widget.render_as_dial is True
    assert widget.slip_skid_only is False
    assert widget.filter is None
    assert widget.center.x() == 150
    config_parent.get_config_item.assert_any_call("alat_filter_depth")
    config_parent.get_config_item.assert_any_call("alat_multiplier")

    widget.update = mock.Mock()
    widget.rate = 2.5
    widget.rate = 2.5
    widget.latAcc = 0.1
    widget.latAcc = 0.1
    widget.quality_change(True)

    assert widget.getROT() == 2.5
    assert widget.getLatAcc() == 0.1
    assert widget.update.call_count == 3

    widget.paintEvent(event)


def test_turn_coordinator_parent_config_filter_and_multiplier(fix, qtbot):
    parent = QWidget()
    parent.get_config_item = mock.Mock(
        side_effect=lambda key: {
            "alat_filter_depth": 2,
            "alat_multiplier": 2,
        }.get(key)
    )
    qtbot.addWidget(parent)
    widget = tc.TurnCoordinator(parent=parent, filter_depth=1)
    _show_widget(qtbot, widget)

    assert widget.filter is not None
    assert widget.alat_multiplier == 2
    assert widget.max_tc_displacement == 0.5

    widget.update = mock.Mock()
    widget.setLatAcc(0.2)
    widget.setLatAcc(0.4)

    assert widget.getLatAcc() != 0
    assert widget.update.called


def test_turn_coordinator_non_dial_slip_skid_only_and_alat_quality(
    fix,
    qtbot,
    config_parent,
):
    widget = tc.TurnCoordinator(parent=config_parent, dial=False, ss_only=True)
    event = _show_widget(qtbot, widget)

    assert widget.render_as_dial is False
    assert widget.slip_skid_only is True

    widget.latAcc = 99
    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ALAT").bad = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ALAT").bad = False
        fix.db.get_item("ALAT").old = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ALAT").old = False
        fix.db.get_item("ALAT").fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))


def test_turn_coordinator_rate_quality_and_clipping(fix, qtbot, config_parent):
    widget = tc.TurnCoordinator(parent=config_parent)
    event = _show_widget(qtbot, widget)

    widget.rate = 10
    widget.latAcc = -99
    widget.paintEvent(event)
    assert widget.rate == 5

    widget.rate = -10
    widget.paintEvent(event)
    assert widget.rate == -5

    with track_calls(QPen, "setColor") as tracker:
        fix.db.get_item("ROT").bad = True
        widget.paintEvent(event)
    assert tracker.was_called_with("setColor", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "setColor") as tracker:
        fix.db.get_item("ROT").bad = False
        fix.db.get_item("ROT").old = True
        widget.paintEvent(event)
    assert tracker.was_called_with("setColor", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ROT").old = False
        fix.db.get_item("ROT").fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))


def test_turn_coordinator_tape_paint_and_lat_acc(qtbot):
    widget = tc.TurnCoordinator_Tape()
    event = _show_widget(qtbot, widget)

    assert widget.getLatAcc() == 0
    widget.update = mock.Mock()
    widget.latAcc = 0.25
    widget.latAcc = 0.25

    assert widget.latAcc == 0.25
    widget.update.assert_called_once_with()
    widget.paintEvent(event)


# =============================================================================
# Turn-coordinator / slip-skid requirements test catalog -- keyed to
# tc_widget_spec.md sec 4 (Rate-of-turn, Slip-skid & Annunciation) and
# avionics_reference.md sec 8.
#
# Docstrings: TC-TC-NNN | requirement ID | intent.
# Passing tests verify shipped behaviour. The xfail(strict) test is the gap
# tracker for the excessive-slip amber cue (AC 25-11B sec A.2.6) -- the dedicated
# slip-skid instrument should carry the same salience the AI slip/skid already
# does (AI-SLIP-002). Spec sec 5 carries the case<->requirement map.
# =============================================================================


def _reset_tc_items(fix):
    for key in ("ALAT", "ROT"):
        item = fix.db.get_item(key)
        item.bad = False
        item.old = False
        item.fail = False


def test_tc_cat_rate_of_turn_and_standard_rate(fix, qtbot, config_parent):
    """TC-TC-001 | TC-DISP-001 | Rate-of-turn: the airplane symbol banks with ROT against
    fixed standard-rate marks, clamped to scale. AC 23.1311-1C sec 8.9 (p.26); 91.205(d)."""
    _reset_tc_items(fix)
    widget = tc.TurnCoordinator(parent=config_parent)
    event = _show_widget(qtbot, widget)
    assert widget.rot_item.key == "ROT"
    assert widget.slip_skid_only is False                  # full rate-of-turn face
    widget.rate = 99
    widget.paintEvent(event)
    assert widget.rate == 5                                 # clamped to scale
    widget.rate = -99
    widget.paintEvent(event)
    assert widget.rate == -5


def test_tc_cat_slip_skid_ball_tracks_alat(fix, qtbot, config_parent):
    """TC-TC-002 | TC-SLIP-001 | The integral slip-skid ball deflects with ALAT and centers
    in coordinated flight. AC 23.1311-1C sec 8.10 (p.26); 91.205(d)(4)."""
    _reset_tc_items(fix)
    widget = tc.TurnCoordinator(parent=config_parent, dial=False, ss_only=True)
    event = _show_widget(qtbot, widget)
    assert widget.alat_item.key == "ALAT"
    widget.setLatAcc(0.0)
    assert widget.getLatAcc() == 0.0                       # coordinated -> centered
    widget.setLatAcc(0.1)
    assert widget.getLatAcc() == pytest.approx(0.1)        # deflects with lateral accel
    widget.paintEvent(event)


def test_tc_cat_invalid_annunciation(fix, qtbot, config_parent):
    """TC-TC-003 | TC-ANN-001 | Invalid ALAT (ball) and ROT (airplane) are annunciated:
    fail -> red XXX, old/bad -> grey. ref sec 2 governing principle."""
    _reset_tc_items(fix)
    widget = tc.TurnCoordinator(parent=config_parent)
    event = _show_widget(qtbot, widget)

    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ALAT").bad = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.gray))

    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ALAT").bad = False
        fix.db.get_item("ALAT").fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))

    _reset_tc_items(fix)
    with track_calls(QPen, "__init__") as tracker:
        fix.db.get_item("ROT").fail = True
        widget.paintEvent(event)
    assert tracker.was_called_with("__init__", QColor(Qt.GlobalColor.red))


def test_tc_cat_excessive_slip_annunciation(fix, qtbot, config_parent):
    """TC-TC-004 | TC-SLIP-002 | Beyond the excessive-slip threshold the ball gives a
    salient (amber) alert, consistent with the AI slip/skid. AC 25-11B sec A.2.6 (p.70).
    Contract: paintEvent sets w._excessive_slip and draws the ball amber."""
    _reset_tc_items(fix)
    widget = tc.TurnCoordinator(parent=config_parent)
    event = _show_widget(qtbot, widget)

    widget.setLatAcc(0.05)                                 # small slip (in scale) -> no caution
    widget.paintEvent(event)
    assert widget._excessive_slip is False
    with track_calls(QPen, "__init__") as tracker:
        widget.setLatAcc(0.2)                              # ball pegged -> caution
        widget.paintEvent(event)
    assert widget._excessive_slip is True
    assert tracker.was_called_with("__init__", QColor(255, 150, 0))   # amber
