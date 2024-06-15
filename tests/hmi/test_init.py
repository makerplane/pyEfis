import pytest
from unittest.mock import patch, MagicMock
import logging
from pyefis.hmi import initialize, actionclass, data


# Fixture to patch and reset global actions variable
@pytest.fixture(autouse=True)
def patch_globals():
    with patch("pyefis.hmi.actions", None):
        yield


# Fixture to patch the logging module
@pytest.fixture
def log_mock():
    with patch("pyefis.hmi.logging.getLogger") as logger_mock:
        yield logger_mock


def test_initialize_with_databindings(log_mock):
    # Mock the actionclass.ActionClass
    with patch(
        "pyefis.hmi.actionclass.ActionClass", autospec=True
    ) as mock_action_class:
        # Mock the data.initialize function
        with patch("pyefis.hmi.data.initialize") as mock_data_initialize:
            # Sample config with databindings
            config = {"databindings": {"key": "value"}}
            # Call the initialize function with config
            initialize(config)
            # Check that logging was called correctly
            log_mock.return_value.info.assert_called_once_with("Initializing Actions")
            # Check that ActionClass was instantiated
            mock_action_class.assert_called_once()
            # Check that data.initialize was called with correct config
            mock_data_initialize.assert_called_once_with(config["databindings"])


def test_initialize_without_databindings(log_mock):
    # Mock the actionclass.ActionClass
    with patch(
        "pyefis.hmi.actionclass.ActionClass", autospec=True
    ) as mock_action_class:
        # Mock the data.initialize function
        with patch("pyefis.hmi.data.initialize") as mock_data_initialize:
            # Sample config without databindings
            config = {}
            # Call the initialize function with config
            initialize(config)
            # Check that logging was called correctly
            log_mock.return_value.info.assert_called_once_with("Initializing Actions")
            # Check that ActionClass was instantiated
            mock_action_class.assert_called_once()
            # Check that data.initialize was not called
            mock_data_initialize.assert_not_called()
