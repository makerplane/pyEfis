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
