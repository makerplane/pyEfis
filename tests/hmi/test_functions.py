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
