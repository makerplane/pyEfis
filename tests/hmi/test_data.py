import logging

import pytest

from pyefis.hmi import data


class FakeActions:
    def __init__(self, available=True):
        self.available = available
        self.triggers = []

    def findAction(self, _action):
        return self.available

    def trigger(self, action, args):
        self.triggers.append((action, args))


@pytest.fixture
def actions(monkeypatch):
    fake = FakeActions()
    monkeypatch.setattr(data.hmi, "actions", fake)
    return fake


def test_databinding_value_placeholder_sends_initial_and_changed_value(fix, actions):
    fix.db.define_item("ENC1", "Encoder", "int", -100, 100, "", 50000, "")
    fix.db.set_value("ENC1", 0)

    binding = data.DataBinding(
        {
            "key": "ENC1",
            "action": "Menu Encoder",
            "args": "<VALUE>",
        }
    )

    fix.db.set_value("ENC1", 4)

    assert binding.args is None
    assert actions.triggers == [("Menu Encoder", "0"), ("Menu Encoder", "4")]


def test_databinding_bool_condition_triggers_once_until_condition_resets(
    fix, actions
):
    data.DataBinding(
        {
            "key": "HIDEBUTTON",
            "condition": True,
            "action": "Activate Menu Item",
            "args": 1,
        }
    )

    fix.db.set_value("HIDEBUTTON", True)
    fix.db.set_value("HIDEBUTTON", True)
    fix.db.set_value("HIDEBUTTON", False)
    fix.db.set_value("HIDEBUTTON", True)

    assert actions.triggers == [
        ("Activate Menu Item", "1"),
        ("Activate Menu Item", "1"),
    ]


def test_databinding_condition_stays_quiet_while_result_remains_true(fix, actions):
    binding = data.DataBinding(
        {
            "key": "INT",
            "condition": "< 25",
            "action": "Show Screen",
            "args": "EMS",
        }
    )

    fix.db.set_value("INT", 24)
    fix.db.set_value("INT", 23)
    fix.db.set_value("INT", 30)
    fix.db.set_value("INT", 24)

    assert str(binding) == "Data Binding: INT<25 - Show Screen(EMS)"
    assert actions.triggers == [("Show Screen", "EMS"), ("Show Screen", "EMS")]


@pytest.mark.parametrize(
    "condition,below,above",
    [
        ("< 5", 4, 5),
        ("< 25", 24, 25),
        ("< 100", 99, 100),
        (">= 100", 100, 99),
        ("= 42", 42, 41),
    ],
)
def test_databinding_numeric_conditions_parse_all_threshold_lengths(
    fix, actions, condition, below, above
):
    data.DataBinding(
        {
            "key": "INT",
            "condition": condition,
            "action": "Show Screen",
            "args": "EMS",
        }
    )

    fix.db.set_value("INT", below)
    fix.db.set_value("INT", above)

    assert actions.triggers == [("Show Screen", "EMS")]


def test_databinding_defaults_none_args_to_blank_string(fix, actions):
    binding = data.DataBinding(
        {
            "key": "INT",
            "action": "Show Screen",
            "args": None,
        }
    )

    fix.db.set_value("INT", 30)

    assert binding.args == ""
    assert actions.triggers == [("Show Screen", "")]


def test_databinding_without_args_uses_blank_string(fix, actions):
    binding = data.DataBinding(
        {
            "key": "INT",
            "action": "Show Screen",
        }
    )

    fix.db.set_value("INT", 30)

    assert str(binding) == "Data Binding: INT - Show Screen()"
    assert actions.triggers == [("Show Screen", "")]


def test_databinding_unknown_action_logs_and_does_not_connect(
    fix, monkeypatch, caplog
):
    fake = FakeActions(available=False)
    monkeypatch.setattr(data.hmi, "actions", fake)

    with caplog.at_level(logging.ERROR):
        data.DataBinding({"key": "INT", "action": "Bogus"})

    fix.db.set_value("INT", 30)

    assert "Action Not Found - Bogus" in caplog.text
    assert fake.triggers == []


def test_databinding_unknown_condition_operator_logs_and_never_triggers(
    fix, actions, caplog
):
    with caplog.at_level(logging.ERROR):
        binding = data.DataBinding(
            {
                "key": "INT",
                "condition": "! 30",
                "action": "Show Screen",
                "args": "EMS",
            }
        )

    fix.db.set_value("INT", 30)

    assert "Unknown Condition Operator" in caplog.text
    assert binding.compare is None
    assert actions.triggers == [("Show Screen", "EMS")]


def test_initialize_accepts_none_empty_and_reraises_bad_bindings(fix, actions):
    data.initialize(None)
    data.initialize([])
    data.initialize([{"key": "INT", "action": "Show Screen"}])

    with pytest.raises(KeyError):
        data.initialize([{"key": "MISSING", "action": "Show Screen"}])
