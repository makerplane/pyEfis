import pytest
from PyQt6.QtCore import pyqtSignal, pyqtBoundSignal
from PyQt6.QtWidgets import QApplication
from unittest import mock  # MagicMock, mock.patch
from pyefis.hmi import actionclass  # ActionClass


# Ensure QApplication instance
@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_initialization(qtbot):
    action_class = actionclass.ActionClass()
    assert action_class.signalMap is not None
    assert "set airspeed mode" in action_class.signalMap


@mock.patch("pyefis.hmi.functions.setValue")
def test_trigger_function(mock_setValue, qtbot):
    action_class = actionclass.ActionClass()
    # Mocking the entire functions module
    mock_setValue.return_value = None
    # mock_db.get_item.return_value = None  # Mocking pyavtools.fix.db as well

    action_class.trigger("set value", "test")

    # Asserting that setValue is called
    mock_setValue.assert_called_once_with("test")


def test_trigger_signal(qtbot):
    action_class = actionclass.ActionClass()
    mock_signal = mock.MagicMock(spec=pyqtBoundSignal)
    action_class.signalMap["set airspeed mode"] = (
        mock_signal  # mock.patching emit directly
    )
    action_class.trigger("set airspeed mode", "test")
    mock_signal.emit.assert_called_once_with(
        "test"
    )  # Use assert_called_once_with on mock_signal directly


def test_find_action_exists(qtbot):
    action_class = actionclass.ActionClass()
    action = action_class.findAction("set airspeed mode")
    assert action == action_class.setAirspeedMode


def test_find_action_not_exists(qtbot):
    action_class = actionclass.ActionClass()
    action = action_class.findAction("nonexistent action")
    assert action is None


def test_trigger_eval(qtbot):
    action_class = actionclass.ActionClass()
    mock_eval = mock.MagicMock()
    action_class.signalMap["evaluate"] = mock_eval
    action_class.trigger("evaluate", "print('test')")
    mock_eval.assert_called_once_with("print('test')")


if __name__ == "__main__":
    pytest.main()
