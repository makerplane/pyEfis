from unittest import mock

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal

from pyefis import hmi
from pyefis.hmi import keys


class FakeKeyEvent:
    def __init__(self, key, auto_repeat=False):
        self._key = key
        self._auto_repeat = auto_repeat

    def key(self):
        return self._key

    def isAutoRepeat(self):
        return self._auto_repeat


class FakeWindow(QObject):
    keyPress = pyqtSignal(object)
    keyRelease = pyqtSignal(object)


@pytest.fixture(autouse=True)
def reset_key_bindings(monkeypatch):
    keys.__dict__["__keypress"].clear()
    keys.__dict__["__keyrelease"].clear()

    actions = mock.Mock()
    actions.findAction.side_effect = lambda action: action != "missing action"
    monkeypatch.setattr(hmi, "actions", actions)

    yield actions

    keys.__dict__["__keypress"].clear()
    keys.__dict__["__keyrelease"].clear()


def test_keybinding_defaults_to_press_with_blank_args(reset_key_bindings):
    binding = keys.KeyBinding({"key": "A", "action": "show screen"})

    assert binding.key.toString() == "A"
    assert binding.action == "show screen"
    assert binding.args == ""
    assert binding.direction == "DN"
    assert str(binding) == "Key Binding: A - show screen()"
    reset_key_bindings.findAction.assert_called_once_with("show screen")


def test_keybinding_uses_args_and_up_direction(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "B", "action": "show screen", "args": "engine", "direction": "up"}
    )

    assert binding.args == "engine"
    assert binding.direction == "UP"


def test_keybinding_keeps_press_direction_for_non_up_direction(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "B", "action": "show screen", "direction": "down"}
    )

    assert binding.direction == "DN"


def test_keybinding_converts_none_args_to_blank(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "C", "action": "show screen", "args": None}
    )

    assert binding.args == ""


def test_keybinding_logs_invalid_key(reset_key_bindings):
    with mock.patch.object(keys.log, "error") as error:
        binding = keys.KeyBinding({"key": "", "action": "show screen"})

    error.assert_called_once_with("Invalid Key ")
    assert not hasattr(binding, "action")
    reset_key_bindings.findAction.assert_not_called()


def test_keybinding_logs_missing_action(reset_key_bindings):
    with mock.patch.object(keys.log, "error") as error:
        binding = keys.KeyBinding({"key": "D", "action": "missing action"})

    error.assert_called_once_with("Action Not Found - missing action")
    assert not hasattr(binding, "action")


def test_key_press_triggers_matching_non_repeat_binding(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "A", "action": "show screen", "args": "primary"}
    )
    keys.__dict__["__keypress"].append(binding)

    keys.keyPress(FakeKeyEvent(Qt.Key.Key_A))

    reset_key_bindings.trigger.assert_called_once_with("show screen", "primary")


def test_key_press_ignores_non_matching_and_auto_repeat_events(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "A", "action": "show screen", "args": "primary"}
    )
    keys.__dict__["__keypress"].append(binding)

    keys.keyPress(FakeKeyEvent(Qt.Key.Key_B))
    keys.keyPress(FakeKeyEvent(Qt.Key.Key_A, auto_repeat=True))

    reset_key_bindings.trigger.assert_not_called()


def test_key_release_triggers_matching_non_repeat_binding(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "A", "action": "show previous screen", "args": "secondary"}
    )
    keys.__dict__["__keyrelease"].append(binding)

    keys.keyRelease(FakeKeyEvent(Qt.Key.Key_A))

    reset_key_bindings.trigger.assert_called_once_with(
        "show previous screen", "secondary"
    )


def test_key_release_ignores_non_matching_and_auto_repeat_events(reset_key_bindings):
    binding = keys.KeyBinding(
        {"key": "A", "action": "show previous screen", "args": "secondary"}
    )
    keys.__dict__["__keyrelease"].append(binding)

    keys.keyRelease(FakeKeyEvent(Qt.Key.Key_B))
    keys.keyRelease(FakeKeyEvent(Qt.Key.Key_A, auto_repeat=True))

    reset_key_bindings.trigger.assert_not_called()


def test_initialize_splits_press_and_release_bindings_and_connects_window(
    reset_key_bindings,
):
    window = FakeWindow()

    keys.initialize(
        window,
        [
            {"key": "A", "action": "show screen", "args": "primary"},
            {
                "key": "B",
                "action": "show previous screen",
                "args": "secondary",
                "direction": "up",
            },
        ],
    )

    assert len(keys.__dict__["__keypress"]) == 1
    assert len(keys.__dict__["__keyrelease"]) == 1

    window.keyPress.emit(FakeKeyEvent(Qt.Key.Key_A))
    window.keyRelease.emit(FakeKeyEvent(Qt.Key.Key_B))

    assert reset_key_bindings.trigger.call_args_list == [
        mock.call("show screen", "primary"),
        mock.call("show previous screen", "secondary"),
    ]


def test_initialize_logs_config_errors_and_continues(reset_key_bindings):
    window = FakeWindow()

    with mock.patch.object(keys.log, "error") as error:
        keys.initialize(
            window,
            [
                {"action": "show screen"},
                {"key": "C", "action": "show next screen"},
            ],
        )

    error.assert_called_once_with("Unable to load Key Binding {'action': 'show screen'}")
    assert len(keys.__dict__["__keypress"]) == 1
