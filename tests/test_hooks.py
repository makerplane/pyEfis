from unittest import mock

import pytest

import pyefis.hooks as hooks


def test_initialize_returns_when_config_is_none():
    with mock.patch.object(hooks.importlib, "import_module") as import_module:
        hooks.initialize(None)

    import_module.assert_not_called()


def test_initialize_accepts_empty_config():
    with mock.patch.object(hooks.importlib, "import_module") as import_module:
        hooks.initialize({})

    import_module.assert_not_called()


def test_initialize_imports_configured_hook_modules():
    config = {
        "first": {"module": "custom_hooks.first"},
        "second": {"module": "custom_hooks.second"},
    }

    with mock.patch.object(hooks.importlib, "import_module") as import_module:
        hooks.initialize(config)

    assert import_module.call_args_list == [
        mock.call("custom_hooks.first"),
        mock.call("custom_hooks.second"),
    ]


def test_initialize_logs_and_reraises_import_errors():
    config = {"bad": {"module": "custom_hooks.missing"}}
    error = RuntimeError("boom")

    with mock.patch.object(hooks.importlib, "import_module", side_effect=error):
        with mock.patch.object(hooks.logging, "critical") as critical:
            with pytest.raises(RuntimeError, match="boom"):
                hooks.initialize(config)

    critical.assert_called_once_with(
        "Unable to load module - custom_hooks.missing: boom"
    )
