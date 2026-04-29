from unittest import mock

import pytest
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableWidgetItem, QWidget

from pyefis.instruments import listbox


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


@pytest.fixture
def mock_parent_widget():
    real_parent = QWidget()
    real_parent.parent = mock.Mock()
    real_parent.parent.config_path = "tests/data/listbox/"
    return real_parent


@pytest.fixture
def listbox_widget(mock_parent_widget, fix, qtbot):
    lists = [
        {"name": "List 1", "file": "list1.yaml"},
        {"name": "List 2", "file": "list2.yaml"},
    ]
    widget = listbox.ListBox(
        mock_parent_widget,
        lists=lists,
        replace={"{radio_id}": "1"},
    )
    qtbot.addWidget(mock_parent_widget)
    qtbot.addWidget(widget)
    mock_parent_widget.resize(1000, 1000)
    mock_parent_widget.show()
    widget.resize(500, 300)
    widget.resizeEvent(None)
    widget.show()
    return widget


def _cell_text(widget, row, column=0):
    item = widget.table.item(row, column)
    return item.text() if item is not None else None


def _make_widget(parent, qtbot, lists, replace=None):
    widget = listbox.ListBox(parent, lists=lists, replace=replace)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    parent.resize(1000, 1000)
    parent.show()
    widget.resize(500, 300)
    widget.resizeEvent(None)
    widget.show()
    return widget


def _define_radio_outputs(fix):
    fix.db.define_item(
        "COMACTFREQSET1",
        "Active com frequency",
        "float",
        0,
        200000,
        "",
        50000,
        "",
    )
    fix.db.define_item(
        "COMACTNAMESET1",
        "Active com name",
        "str",
        "",
        "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
        "",
        50000,
        "",
    )
    fix.db.get_item("COMACTFREQSET1").bad = False
    fix.db.get_item("COMACTFREQSET1").fail = False
    fix.db.get_item("COMACTNAMESET1").bad = False
    fix.db.get_item("COMACTNAMESET1").fail = False


def test_listbox_loads_actions_and_initial_rows(listbox_widget):
    widget = listbox_widget

    assert widget.isVisible() is True
    assert widget.active_list == "List 1"
    assert widget.header.text == "List 1"
    assert widget.column_names == ["Name", "Identifier", "Frequency"]
    assert widget.table.rowCount() == 11

    assert _cell_text(widget, 0) == "Load List"
    assert widget.actions[0] == {"select_list": True}
    assert _cell_text(widget, 1) == "Sort by:"
    assert _cell_text(widget, 1, 1) == "Nearest"
    assert widget.actions[1] == {"select_nearest": True}
    assert _cell_text(widget, 2, 1) == "Name"
    assert widget.actions[2] == {"sort": True, "option": 0}
    assert _cell_text(widget, 3, 1) == "Identifier"
    assert widget.actions[3] == {"sort": True, "option": 1}

    assert _cell_text(widget, 4) == "Akron-Canton Reg Tower"
    assert widget.actions[4]["select"] is True
    assert widget.actions[4]["option"]["Identifier"] == "KCAK"


def test_listbox_hides_nearest_sort_when_location_quality_is_bad(listbox_widget):
    widget = listbox_widget

    widget.setLatBad(True)

    assert widget.table.rowCount() == 10
    assert {"select_nearest": True} not in widget.actions
    assert _cell_text(widget, 1, 1) == "Name"
    assert widget.badLocation() is True


def test_clicking_sort_option_sorts_data_rows_by_column(listbox_widget):
    widget = listbox_widget

    assert _cell_text(widget, 4) == "Akron-Canton Reg Tower"

    widget.clicked(widget.table.item(2, 0))

    assert widget.sort == "Name"
    assert _cell_text(widget, 4) == "Akron-Canton Reg ATIS"
    assert _cell_text(widget, 5) == "Akron-Canton Reg Tower"


def test_clicking_nearest_option_sorts_by_distance(listbox_widget, fix):
    widget = listbox_widget
    fix.db.set_value("LAT", 39.99)
    fix.db.set_value("LONG", -82.89)

    widget.clicked(widget.table.item(1, 0))

    assert widget.nearest is True
    assert _cell_text(widget, 4) == "John Glenn Int. Tower"
    assert _cell_text(widget, 5) == "John Glenn Int. Ground"


def test_list_selector_switches_active_list_and_preserves_return_sort(listbox_widget):
    widget = listbox_widget
    widget.clicked(widget.table.item(2, 0))
    assert widget.sort == "Name"

    widget.clicked(widget.table.item(0, 0))

    assert widget.column_names == ["Select a list"]
    assert widget.table.rowCount() == 3
    assert _cell_text(widget, 0) == "Return"
    assert widget.actions[0] == {
        "load_list": True,
        "option": "List 1",
        "sort": "Name",
    }
    assert _cell_text(widget, 2) == "List 2"

    widget.clicked(widget.table.item(2, 0))

    assert widget.active_list == "List 2"
    assert widget.sort is False
    assert widget.table.rowCount() == 8
    assert _cell_text(widget, 4) == "Rickenbacker Int Tower"


def test_encoder_change_wraps_selection(listbox_widget):
    widget = listbox_widget

    widget.table.selectRow(0)
    assert widget.enc_changed(-1) is True
    assert widget.table.currentRow() == widget.table.rowCount() - 1

    assert widget.enc_changed(1) is True
    assert widget.table.currentRow() == 0

    assert widget.enc_changed(1) is True
    assert widget.table.currentRow() == 1

    assert widget.enc_changed(widget.table.rowCount() * 2 + 1) is True
    assert widget.table.currentRow() == 2

    assert widget.enc_changed(-(widget.table.rowCount() * 2 + 2)) is True
    assert widget.table.currentRow() == 0


def test_encoder_helpers_highlight_and_select_current_row(listbox_widget):
    widget = listbox_widget

    assert widget.enc_selectable() is True
    assert widget.enc_select() is True

    widget.enc_highlight(True)
    assert widget.header.color == QColor("orange")
    widget.enc_highlight(False)
    assert widget.header.color == QColor(Qt.GlobalColor.white)

    widget.table.selectRow(2)
    assert widget.enc_clicked() is True
    assert widget.sort == "Name"


def test_location_signal_setters_update_state_and_reload(listbox_widget):
    widget = listbox_widget
    widget.loadList = mock.Mock()

    widget.setLongitude(-81.1)
    widget.setLatitude(41.2)
    widget.setLngBad(True)
    widget.setLngFail(True)
    widget.setLatFail(True)
    widget.setLngOld(True)
    widget.setLatOld(True)

    assert widget.lng == -81.1
    assert widget.lat == 41.2
    assert widget.badLocation() is True
    assert widget.loadList.call_count == 5


def test_clicking_select_row_writes_fix_values_with_column_placeholders(
    listbox_widget,
    fix,
):
    widget = listbox_widget
    _define_radio_outputs(fix)
    freq = fix.db.get_item("COMACTFREQSET1")
    name = fix.db.get_item("COMACTNAMESET1")
    freq.output_value = mock.Mock()
    name.output_value = mock.Mock()

    widget.table.selectRow(4)
    result = widget.clicked(widget.table.item(4, 0))

    assert result is False
    assert freq.value == 134750
    assert name.value == "Akron-Canton Reg Tower"
    freq.output_value.assert_called_once_with()
    name.output_value.assert_called_once_with()


def test_single_list_without_replacements_skips_list_selector(
    mock_parent_widget,
    fix,
    qtbot,
):
    widget = _make_widget(
        mock_parent_widget,
        qtbot,
        [{"name": "Only List", "file": "list1.yaml"}],
    )

    assert widget.active_list == "Only List"
    assert widget.table.rowCount() == 10
    assert _cell_text(widget, 0) == "Sort by:"
    assert {"select_list": True} not in widget.actions


def test_single_column_list_uses_compact_action_labels(
    mock_parent_widget,
    fix,
    qtbot,
    tmp_path,
):
    list_file = tmp_path / "single_column.yaml"
    list_file.write_text(
        """
display:
  location: true
  columns:
    - name: Name
      sort: true
list:
  - Name: Bravo
    lat: 40.0
    long: -82.0
    set: {}
  - Name: Alpha
    set: {}
""",
        encoding="utf-8",
    )
    mock_parent_widget.parent.config_path = str(tmp_path)
    widget = _make_widget(
        mock_parent_widget,
        qtbot,
        [{"name": "Single", "file": "single_column.yaml"}],
    )

    assert widget.table.columnCount() == 1
    assert _cell_text(widget, 0) == "Sort by: Nearest"
    assert _cell_text(widget, 1) == "Sort by: Name"
    assert _cell_text(widget, 2) == "Bravo"

    widget.clicked(widget.table.item(1, 0))

    assert widget.sort == "Name"
    assert _cell_text(widget, 2) == "Alpha"


def test_load_list_selects_row_count_when_current_row_is_beyond_new_rows(
    listbox_widget,
):
    widget = listbox_widget
    widget.table.currentRow = mock.Mock(return_value=99)
    widget.table.selectRow = mock.Mock()

    widget.loadList()

    widget.table.selectRow.assert_called_once_with(widget.table.rowCount())


def test_clicked_returns_true_for_unknown_action(listbox_widget):
    widget = listbox_widget
    widget.table.setRowCount(1)
    widget.table.setItem(0, 0, QTableWidgetItem("No action"))
    widget.actions = [{}]

    assert widget.clicked(widget.table.item(0, 0)) is True
