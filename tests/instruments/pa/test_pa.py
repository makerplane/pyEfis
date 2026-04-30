import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QGraphicsRectItem, QGraphicsTextItem

from pyefis.instruments import pa


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def _resize(widget, width=300, height=200):
    widget.resize(width, height)
    widget.resizeEvent(None)


def _outer_rect(widget):
    rects = [
        item
        for item in widget.scene.items()
        if isinstance(item, QGraphicsRectItem) and item.rect().x() == 0
    ]
    return rects[0]


def _text_item(widget):
    texts = [item for item in widget.scene.items() if isinstance(item, QGraphicsTextItem)]
    return texts[0]


def test_pa_initializes_and_renders_default_label(qtbot):
    widget = pa.Panel_Annunciator(font_family="Courier")
    qtbot.addWidget(widget)

    assert widget.getState() == 0
    assert widget.getWARNING_Name() == 0
    assert widget.Warning_State_Label == "null"
    assert widget.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert widget.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert widget.focusPolicy() == Qt.FocusPolicy.NoFocus

    _resize(widget)

    assert widget.scene.sceneRect().width() == 300
    assert widget.scene.sceneRect().height() == 200
    assert _outer_rect(widget).brush().color() == QColor(Qt.GlobalColor.black)
    assert _text_item(widget).toPlainText() == "null"
    assert _text_item(widget).font().family() == "Courier"
    assert _text_item(widget).font().bold() is True
    assert _text_item(widget).font().pixelSize() == 16


@pytest.mark.parametrize(
    "mode,color",
    [
        (1, Qt.GlobalColor.yellow),
        (2, Qt.GlobalColor.red),
        (3, Qt.GlobalColor.green),
        (0, Qt.GlobalColor.black),
    ],
)
def test_pa_modes_redraw_with_expected_background(qtbot, mode, color):
    widget = pa.Panel_Annunciator()
    qtbot.addWidget(widget)
    widget.setWARNING_Name("Pull UP!")
    _resize(widget)

    if mode == 0:
        widget.setState(1)
    widget.setState(mode)

    assert widget.getState() == mode
    assert _outer_rect(widget).brush().color() == QColor(color)
    assert _outer_rect(widget).pen().color() == QColor(Qt.GlobalColor.gray)
    assert _text_item(widget).toPlainText() == "Pull UP!"
    assert _text_item(widget).defaultTextColor() == QColor(Qt.GlobalColor.white)


def test_pa_unchanged_state_does_not_redraw(qtbot, monkeypatch):
    widget = pa.Panel_Annunciator()
    qtbot.addWidget(widget)
    _resize(widget)
    redraw_calls = []
    monkeypatch.setattr(widget, "redraw", lambda: redraw_calls.append(True))

    widget.setState(0)

    assert redraw_calls == []


def test_pa_state_can_be_set_before_resize_and_unknown_state_is_ignored(qtbot):
    widget = pa.Panel_Annunciator()
    qtbot.addWidget(widget)

    widget.setState(2)
    widget.setState(99)
    _resize(widget)

    assert widget.getState() == 2
    assert _outer_rect(widget).brush().color() == QColor(Qt.GlobalColor.red)


def test_pa_panel_annunciator_property_controls_state(qtbot):
    widget = pa.Panel_Annunciator()
    qtbot.addWidget(widget)
    _resize(widget)

    widget.panel_annunciator = 3

    assert widget.panel_annunciator == 3
    assert _outer_rect(widget).brush().color() == QColor(Qt.GlobalColor.green)
