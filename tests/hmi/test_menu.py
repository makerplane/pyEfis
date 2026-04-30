from unittest import mock

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

import pyefis.hmi as hmi
from pyefis.hmi import menu


class FakeActions(QObject):
    activateMenuItem = pyqtSignal(object)
    setMenuFocus = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.trigger = mock.Mock()


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


@pytest.fixture
def actions(monkeypatch):
    fake_actions = FakeActions()
    monkeypatch.setattr(hmi, "actions", fake_actions)
    return fake_actions


@pytest.fixture
def menu_fix(fix):
    fix.db.define_item("ENC1", "Encoder", "int", -100, 100, "", 50000, "")
    fix.db.set_value("ENC1", 0)
    fix.db.get_item("ENC1").bad = False
    fix.db.get_item("ENC1").fail = False

    fix.db.define_item("MENUBOOL", "Menu Boolean", "bool", None, None, "", 50000, "")
    fix.db.set_value("MENUBOOL", False)
    fix.db.get_item("MENUBOOL").bad = False
    fix.db.get_item("MENUBOOL").fail = False
    return fix


@pytest.fixture(autouse=True)
def reset_global_menu():
    menu.TheMenuObject = None
    yield
    menu.TheMenuObject = None


def menu_config(**overrides):
    config = {
        "buttons_spacing": 100,
        "left_margin": 10,
        "top_margin": 20,
        "number_of_buttons": 3,
        "start_menu": "main",
        "menus": {
            "main": [
                ("One", "first action", "alpha"),
                ("Two", "second action", "bravo", False),
                ("Three", "third action", "charlie", True, True),
            ],
            "short": [
                ("Short", "short action", "delta"),
            ],
            "four_show": [
                ("Show", "show action", "echo", True),
            ],
            "bad": [
                ("Broken", "missing"),
            ],
        },
    }
    config.update(overrides)
    return config


def make_menu(qtbot, actions, menu_fix, config=None):
    parent = QWidget()
    qtbot.addWidget(parent)
    widget = menu.Menu(parent, config or menu_config())
    qtbot.addWidget(widget)
    return widget


class FakeThread:
    def __init__(self, target):
        self.target = target

    def start(self):
        pass


def test_menu_initializes_buttons_targets_and_global(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)

    assert menu.TheMenuObject is widget
    assert len(widget.buttons) == 3
    assert "BARO" in widget.registered_targets
    assert widget.pos().x() == 10
    assert widget.pos().y() == 20


def test_menu_negative_button_spacing_offsets_widget(qtbot, actions, menu_fix):
    widget = make_menu(
        qtbot,
        actions,
        menu_fix,
        menu_config(buttons_spacing=-100, left_margin=300, number_of_buttons=3),
    )

    assert widget.pos().x() == 100
    assert [button.pos().x() for button in widget.buttons] == [200, 100, 0]


def test_start_activates_start_menu_and_activate_menu_hides_unused_buttons(
    qtbot, actions, menu_fix
):
    widget = make_menu(qtbot, actions, menu_fix)

    widget.start()
    assert widget.buttons[0].text() == "One"
    assert widget.buttons[1].text() == "Two"
    assert widget.buttons[2].text() == "Three"
    assert all(not button.isHidden() for button in widget.buttons)
    assert widget.button_show_menu == [True, False, True]
    assert widget.button_blind_performance == [False, True, True]

    widget.activate_menu("short")

    assert widget.buttons[0].text() == "Short"
    assert not widget.buttons[0].isHidden()
    assert widget.buttons[1].isHidden()
    assert widget.buttons[2].isHidden()


def test_activate_menu_rejects_unknown_button_configuration(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)

    with pytest.raises(RuntimeError, match="unknown button configuration"):
        widget.activate_menu("bad")


def test_activate_menu_keeps_default_blind_performance_for_four_item_show_button(
    qtbot, actions, menu_fix
):
    widget = make_menu(qtbot, actions, menu_fix)

    widget.activate_menu("four_show")

    assert widget.button_show_menu[0] is True
    assert widget.button_blind_performance[0] is False


def test_hide_and_show_menu_toggle_visible_buttons(qtbot, actions, menu_fix, monkeypatch):
    monkeypatch.setattr(menu.threading, "Thread", FakeThread)
    widget = make_menu(qtbot, actions, menu_fix, menu_config(show_time=1))
    widget.activate_menu("main")
    widget.show_begin_time = 10
    monkeypatch.setattr(menu.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(menu.time, "time", lambda: 12)

    widget.hide_menu()

    assert widget.hiding_menu is True
    assert all(button.isHidden() for button in widget.buttons)

    widget.show_menu()

    assert widget.hiding_menu is False
    assert all(not button.isHidden() for button in widget.buttons)


def test_hide_menu_leaves_buttons_visible_before_timeout(
    qtbot, actions, menu_fix, monkeypatch
):
    monkeypatch.setattr(menu.threading, "Thread", FakeThread)
    widget = make_menu(qtbot, actions, menu_fix, menu_config(show_time=5))
    widget.activate_menu("main")
    widget.show_begin_time = 10
    monkeypatch.setattr(menu.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(menu.time, "time", lambda: 12)

    widget.hide_menu()

    assert widget.hiding_menu is False
    assert all(not button.isHidden() for button in widget.buttons)


def test_focus_moves_between_registered_targets_and_toggles_done_text(
    qtbot, actions, menu_fix
):
    widget = make_menu(qtbot, actions, menu_fix)
    target = mock.Mock()
    widget.register_target("TARGET", target)
    widget.activate_menu("main")
    widget.last_button_clicked = 1

    widget.focus("TARGET")

    target.focus.assert_called_once_with()
    assert widget.focused_object is target
    assert widget.buttons[1].text() == "Two Done"

    widget.focus("TARGET")

    target.defocus.assert_called_once_with()
    assert widget.focused_object is None
    assert widget.buttons[1].text() == "Two"


def test_focus_replaces_existing_target(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)
    first = mock.Mock()
    second = mock.Mock()
    widget.register_target("FIRST", first)
    widget.register_target("SECOND", second)
    widget.activate_menu("main")
    widget.last_button_clicked = 0
    widget.focus("FIRST")

    widget.last_button_clicked = 2
    widget.focus("SECOND")

    first.defocus.assert_called_once_with()
    second.focus.assert_called_once_with()
    assert widget.buttons[0].text() == "One"
    assert widget.buttons[2].text() == "Three Done"


def test_perform_action_handles_none_index_string_callable_and_eval(
    qtbot, actions, menu_fix
):
    widget = make_menu(qtbot, actions, menu_fix)
    callback = mock.Mock()
    widget.button_actions[0] = "nested action"
    widget.button_args[0] = "nested args"

    widget.perform_action(None, None)
    widget.perform_action(0, None)
    widget.perform_action("direct action", "direct args")
    widget.perform_action(callback, None)

    assert actions.trigger.call_args_list == [
        mock.call("nested action", "nested args"),
        mock.call("direct action", "direct args"),
    ]
    callback.assert_called_once_with()

    actions.trigger.side_effect = RuntimeError("unknown action")
    with pytest.raises(RuntimeError, match="unknown action"):
        widget.perform_action("self.button_args.append('blocked')", None)

    widget.allow_evals = True
    widget.perform_action("self.button_args.append('evaluated')", None)
    assert "evaluated" in widget.button_args


def test_toggle_db_bool_updates_value_and_last_button_style(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)
    db_item = menu_fix.db.get_item("MENUBOOL")
    widget.last_button_clicked = 0

    widget.toggle_db_bool("MENUBOOL")

    assert db_item.value is True
    assert "green" in widget.buttons[0].styleSheet()

    widget.toggle_db_bool("MENUBOOL")

    assert db_item.value is False
    assert "black" in widget.buttons[0].styleSheet()


def test_button_clicked_performs_or_reveals_based_on_hidden_state(
    qtbot, actions, menu_fix
):
    widget = make_menu(qtbot, actions, menu_fix)
    widget.activate_menu("main")
    actions.trigger.reset_mock()

    widget.button_clicked(0)

    actions.trigger.assert_called_once_with("first action", "alpha")

    actions.trigger.reset_mock()
    widget.hiding_menu = True
    widget.button_clicked(0)

    actions.trigger.assert_not_called()
    assert widget.hiding_menu is False

    widget.hiding_menu = True
    widget.button_clicked(1)

    actions.trigger.assert_called_once_with("second action", "bravo")

    actions.trigger.reset_mock()
    widget.hiding_menu = True
    widget.button_clicked(2)

    actions.trigger.assert_called_once_with("third action", "charlie")


def test_button_clicked_negative_index_is_noop(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)
    widget.activate_menu("main")

    widget.button_clicked(-1)

    actions.trigger.assert_not_called()


def test_button_clicked_starts_hide_thread_when_show_time_is_configured(
    qtbot, actions, menu_fix, monkeypatch
):
    starts = []

    class RecordingThread:
        def __init__(self, target):
            self.target = target

        def start(self):
            starts.append(self.target)

    monkeypatch.setattr(menu.threading, "Thread", RecordingThread)
    widget = make_menu(qtbot, actions, menu_fix, menu_config(show_time=1))
    widget.activate_menu("main")
    actions.trigger.reset_mock()

    widget.button_clicked(0)

    assert starts[-1] == widget.hide_menu
    actions.trigger.assert_called_once_with("first action", "alpha")


def test_button_clicked_wrappers_and_activate_menu_item_signal(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)
    widget.activate_menu("main")
    widget.button_clicked = mock.Mock()

    widget.button_clicked1(None)
    widget.button_clicked2(None)
    widget.button_clicked3(None)
    widget.button_clicked4(None)
    widget.button_clicked5(None)
    widget.button_clicked6(None)
    widget.activateMenuItem("2")

    assert widget.button_clicked.call_args_list == [
        mock.call(0),
        mock.call(1),
        mock.call(2),
        mock.call(3),
        mock.call(4),
        mock.call(5),
        mock.call(1),
    ]


def test_activate_menu_function_delegates_to_global_menu(qtbot, actions, menu_fix):
    widget = make_menu(qtbot, actions, menu_fix)
    widget.activate_menu = mock.Mock()

    menu.activateMenu("main")

    widget.activate_menu.assert_called_once_with("main")


def test_baro_proxy_adjusts_baro_from_encoder_changes(menu_fix):
    proxy = menu.BaroProxy()
    enc = menu_fix.db.get_item("ENC1")
    baro = menu_fix.db.get_item("BARO")

    proxy.focus()
    enc.value = 3

    assert baro.value == pytest.approx(29.95)

    proxy.defocus()
    enc.value = 8

    assert baro.value == pytest.approx(29.95)
