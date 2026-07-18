import pytest
from unittest.mock import MagicMock, patch
import pyefis.hmi.functions


# Mock the fix module
@pytest.fixture
def fix_mock():
    with patch("pyefis.hmi.functions.fix") as fix_mock:
        yield fix_mock


# Test for setValue function
def test_setValue(fix_mock):
    # Mocking the arg for setValue
    arg = "key,value"
    # Setting up the mock for the item
    item_mock = MagicMock()
    item_mock.value = None
    fix_mock.db.get_item.return_value = item_mock

    # Calling the function
    pyefis.hmi.functions.setValue(arg)

    # Assertions
    fix_mock.db.get_item.assert_called_once_with("key")
    assert item_mock.value == "value"
    assert item_mock.output_value.called


# Test for changeValue function
def test_changeValue(fix_mock):
    # Mocking the arg for changeValue
    arg = "key,1"
    # Setting up the mock for the item
    item_mock = MagicMock()
    item_mock.value = 1
    item_mock.dtype.return_value = 1
    fix_mock.db.get_item.return_value = item_mock

    # Calling the function
    pyefis.hmi.functions.changeValue(arg)

    # Assertions
    fix_mock.db.get_item.assert_called_once_with("key")
    assert item_mock.value == 2
    assert item_mock.dtype.called
    assert item_mock.output_value.called


class _Item:
    """A minimal numeric FIX item for the wrap/sync math (MagicMock can't do
    real arithmetic on .min / .max / .value)."""
    def __init__(self, value=0.0, mn=0.0, mx=359.9):
        self.value = value
        self.min = mn
        self.max = mx
        self.dtype = float
        self.output_called = False

    def output_value(self):
        self.output_called = True


# changeValueWrap wraps within [min, max] instead of clamping.
def test_changeValueWrap_down_across_zero(fix_mock):
    item = _Item(0.0, 0.0, 359.9)
    fix_mock.db.get_item.return_value = item
    pyefis.hmi.functions.changeValueWrap("HEADBUG, -1")
    assert round(item.value, 1) == 358.9
    assert item.output_called


def test_changeValueWrap_up_across_max(fix_mock):
    item = _Item(357.0, 0.0, 359.9)
    fix_mock.db.get_item.return_value = item
    pyefis.hmi.functions.changeValueWrap("HEADBUG, 5")
    assert round(item.value, 1) == 2.1


def test_changeValueWrap_within_range_is_plain_add(fix_mock):
    item = _Item(100.0, 0.0, 359.9)
    fix_mock.db.get_item.return_value = item
    pyefis.hmi.functions.changeValueWrap("HEADBUG, 20")
    assert round(item.value, 1) == 120.0


# syncValue copies the source key's value into the destination key.
def test_syncValue(fix_mock):
    dest = _Item(0.0)
    src = _Item(287.0)
    fix_mock.db.get_item.side_effect = lambda k: {"HEADBUG": dest, "HEAD": src}[k.strip()]
    pyefis.hmi.functions.syncValue("HEADBUG, HEAD")
    assert dest.value == 287.0
    assert dest.output_called


# Test for toggleBool function
def test_toggleBool(fix_mock):
    # Mocking the arg for toggleBool
    arg = "key"
    # Setting up the mock for the item
    item_mock = MagicMock()
    item_mock.value = False
    fix_mock.db.get_item.return_value = item_mock

    # Calling the function
    pyefis.hmi.functions.toggleBool(arg)

    # Assertions
    fix_mock.db.get_item.assert_called_once_with("key")
    assert item_mock.value == True
    assert item_mock.output_value.called
