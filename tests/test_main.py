import os
import importlib
import types
from unittest import mock

import pytest
import yaml

import pyefis.main as main_module


class FakeApp:
    instances = []

    def __init__(self, argv):
        self.argv = argv
        self.exec = mock.Mock(return_value=7)
        FakeApp.instances.append(self)


class FakeFixItem:
    def __init__(self):
        self.value = None


class FakeResource:
    def __init__(self, name, path=None, children=None):
        self.name = name
        self._path = path
        self._children = children or []

    def iterdir(self):
        return iter(self._children)

    def is_dir(self):
        return bool(self._children)

    def as_posix(self):
        return str(self._path)


@pytest.fixture
def config_files(tmp_path):
    config_file = tmp_path / "default.yaml"
    config_file.write_text("main: {}\n")
    preferences_file = tmp_path / "preferences.yaml"
    preferences_file.write_text(yaml.safe_dump({"enabled": {"AUTO_START": True}}))
    return config_file, preferences_file


@pytest.fixture
def patched_runtime(monkeypatch):
    FakeApp.instances = []
    version_item = FakeFixItem()
    fake_fms = mock.Mock()

    monkeypatch.delenv("INVOCATION_ID", raising=False)
    monkeypatch.setattr(main_module, "QApplication", FakeApp)
    monkeypatch.setattr(main_module.fix, "initialize", mock.Mock())
    monkeypatch.setattr(main_module.fix, "stop", mock.Mock())
    fake_db = types.SimpleNamespace(get_item=mock.Mock(return_value=version_item))
    monkeypatch.setattr(
        main_module.fix, "db", fake_db, raising=False
    )
    monkeypatch.setattr(main_module.hmi, "initialize", mock.Mock())
    monkeypatch.setattr(main_module.hmi.keys, "initialize", mock.Mock())
    monkeypatch.setattr(main_module.gui, "initialize", mock.Mock())
    monkeypatch.setattr(main_module.gui, "mainWindow", object(), raising=False)
    monkeypatch.setattr(main_module.hooks, "initialize", mock.Mock())
    monkeypatch.setattr(main_module.logging, "basicConfig", mock.Mock())
    monkeypatch.setattr(main_module.logging.config, "dictConfig", mock.Mock())
    monkeypatch.setattr(main_module.logging.config, "fileConfig", mock.Mock())
    monkeypatch.setattr(
        main_module.importlib,
        "import_module",
        mock.Mock(return_value=fake_fms),
    )
    monkeypatch.setattr(main_module, "create_config_dir", mock.Mock())

    return types.SimpleNamespace(version_item=version_item, fms=fake_fms)


def test_merge_dict_recursively_updates_nested_values():
    dest = {"main": {"width": 800, "height": 480}, "keep": True}
    override = {"main": {"height": 600}, "new": "value"}

    main_module.merge_dict(dest, override)

    assert dest == {
        "main": {"width": 800, "height": 600},
        "keep": True,
        "new": "value",
    }


def test_main_with_config_file_runs_startup_and_shutdown(
    monkeypatch, config_files, patched_runtime
):
    config_file, _preferences_file = config_files
    config = {
        "hooks": {"sample": {"module": "custom.hook"}},
        "keybindings": [{"key": "A"}],
        "FMS": {"module_dir": "/fms/path", "aircraft_config": "aircraft.yaml"},
    }
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value=config))

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 7
    main_module.create_config_dir.assert_not_called()
    main_module.cfg.from_yaml.assert_called_once_with(
        str(config_file), preferences={"enabled": {"AUTO_START": True}}
    )
    main_module.fix.initialize.assert_called_once_with(config)
    main_module.hmi.initialize.assert_called_once_with(config)
    main_module.importlib.import_module.assert_called_once_with("FixIntf")
    patched_runtime.fms.start.assert_called_once_with("aircraft.yaml")
    main_module.gui.initialize.assert_called_once_with(
        config, str(config_file.parent), {"enabled": {"AUTO_START": True}}
    )
    assert patched_runtime.version_item.value == main_module.__version__
    main_module.hmi.keys.initialize.assert_called_once_with(
        main_module.gui.mainWindow, config["keybindings"]
    )
    main_module.hooks.initialize.assert_called_once_with(config["hooks"])
    main_module.fix.stop.assert_called_once_with()
    patched_runtime.fms.stop.assert_called_once_with()


def test_main_config_search_checks_multiple_paths_before_match(
    monkeypatch, config_files, patched_runtime, tmp_path
):
    config_file, _preferences_file = config_files
    missing_path = tmp_path / "missing"
    matching_path = config_file.parent
    monkeypatch.setattr(main_module, "path_options", [str(missing_path), str(matching_path)])
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"hooks": {}}))

    with pytest.raises(SystemExit):
        main_module.main()

    assert main_module.config_path == str(config_file.parent)


def test_main_config_search_handles_empty_path_options_with_config_file(
    monkeypatch, config_files, patched_runtime
):
    config_file, _preferences_file = config_files
    monkeypatch.setattr(main_module, "path_options", [])
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"hooks": {}}))

    with pytest.raises(SystemExit):
        main_module.main()

    main_module.cfg.from_yaml.assert_called_once_with(
        str(config_file), preferences={"enabled": {"AUTO_START": True}}
    )


def test_main_without_config_file_creates_user_config_and_uses_basic_logging(
    monkeypatch, tmp_path, patched_runtime
):
    config_dir = tmp_path / "makerplane" / "pyefis" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "default.yaml").write_text("main: {}\n")
    (config_dir / "preferences.yaml").write_text("{}\n")
    monkeypatch.setattr(main_module, "user_home", str(tmp_path))
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis"])
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"hooks": {}}))

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 7
    main_module.create_config_dir.assert_called_once_with(
        f"{tmp_path}/makerplane/pyefis"
    )
    main_module.logging.basicConfig.assert_called_once_with()
    main_module.hmi.keys.initialize.assert_not_called()
    main_module.importlib.import_module.assert_not_called()


def test_main_merges_custom_preferences_and_configures_logging_dict(
    monkeypatch, config_files, patched_runtime
):
    config_file, preferences_file = config_files
    preferences_file.write_text(
        yaml.safe_dump({"display": {"brightness": 20}, "enabled": {}})
    )
    preferences_file.with_suffix(".yaml.custom").write_text(
        yaml.safe_dump({"display": {"brightness": 80}})
    )
    logging_config = {"version": 1}
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setattr(
        main_module.cfg,
        "from_yaml",
        mock.Mock(return_value={"hooks": {}, "logging": logging_config}),
    )

    with pytest.raises(SystemExit):
        main_module.main()

    main_module.cfg.from_yaml.assert_called_once_with(
        str(config_file), preferences={"display": {"brightness": 80}, "enabled": {}}
    )
    main_module.logging.config.dictConfig.assert_called_once_with(logging_config)


def test_main_uses_log_config_file_when_provided(
    monkeypatch, config_files, patched_runtime, tmp_path
):
    config_file, _preferences_file = config_files
    log_config = tmp_path / "logging.ini"
    log_config.write_text("[loggers]\nkeys=root\n")
    monkeypatch.setattr(
        main_module.sys,
        "argv",
        ["pyefis", "--config-file", str(config_file), "--log-config", str(log_config)],
    )
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"hooks": {}}))

    with pytest.raises(SystemExit):
        main_module.main()

    passed_file = main_module.logging.config.fileConfig.call_args.args[0]
    assert passed_file.name == str(log_config)
    main_module.logging.config.dictConfig.assert_not_called()
    main_module.logging.basicConfig.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "expected_level"),
    [
        (["pyefis", "--verbose"], main_module.logging.INFO),
        (["pyefis", "--debug"], main_module.logging.DEBUG),
    ],
)
def test_main_sets_requested_log_level(
    monkeypatch, config_files, patched_runtime, argv, expected_level
):
    config_file, _preferences_file = config_files
    logger = mock.Mock()
    monkeypatch.setattr(
        main_module.sys, "argv", argv + ["--config-file", str(config_file)]
    )
    monkeypatch.setattr(main_module.logging, "getLogger", mock.Mock(return_value=logger))
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"hooks": {}}))

    with pytest.raises(SystemExit):
        main_module.main()

    logger.setLevel.assert_called_once_with(expected_level)


def test_main_systemd_exits_when_auto_start_is_false(
    monkeypatch, config_files, patched_runtime
):
    config_file, _preferences_file = config_files
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setitem(main_module.environ, "INVOCATION_ID", "systemd")
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value={"auto start": False}))
    monkeypatch.setattr(main_module.os, "_exit", mock.Mock(side_effect=SystemExit(0)))

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 0
    main_module.os._exit.assert_called_once_with(0)
    main_module.fix.initialize.assert_not_called()


def test_main_systemd_string_auto_start_checks_preferences_enabled(
    monkeypatch, config_files, patched_runtime
):
    config_file, preferences_file = config_files
    preferences_file.write_text(yaml.safe_dump({"enabled": {"AUTO_START": False}}))
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setitem(main_module.environ, "INVOCATION_ID", "systemd")
    monkeypatch.setattr(
        main_module.cfg, "from_yaml", mock.Mock(return_value={"auto start": "AUTO_START"})
    )
    monkeypatch.setattr(main_module.os, "_exit", mock.Mock(side_effect=SystemExit(0)))

    with pytest.raises(SystemExit):
        main_module.main()

    main_module.os._exit.assert_called_once_with(0)


def test_main_systemd_string_auto_start_exits_when_enabled_section_missing(
    monkeypatch, config_files, patched_runtime
):
    config_file, preferences_file = config_files
    preferences_file.write_text(yaml.safe_dump({"display": {}}))
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setitem(main_module.environ, "INVOCATION_ID", "systemd")
    monkeypatch.setattr(
        main_module.cfg, "from_yaml", mock.Mock(return_value={"auto start": "AUTO_START"})
    )
    monkeypatch.setattr(main_module.os, "_exit", mock.Mock(side_effect=SystemExit(0)))

    with pytest.raises(SystemExit):
        main_module.main()

    main_module.os._exit.assert_called_once_with(0)


@pytest.mark.parametrize("config", [{"auto start": "AUTO_START"}, {"auto start": True}])
def test_main_systemd_continues_when_auto_start_is_enabled(
    monkeypatch, config_files, patched_runtime, config
):
    config_file, _preferences_file = config_files
    config["hooks"] = {}
    monkeypatch.setattr(main_module.sys, "argv", ["pyefis", "--config-file", str(config_file)])
    monkeypatch.setitem(main_module.environ, "INVOCATION_ID", "systemd")
    monkeypatch.setattr(main_module.os, "_exit", mock.Mock())
    monkeypatch.setattr(main_module.cfg, "from_yaml", mock.Mock(return_value=config))

    with pytest.raises(SystemExit) as exc:
        main_module.main()

    assert exc.value.code == 7
    main_module.os._exit.assert_not_called()
    main_module.fix.initialize.assert_called_once_with(config)


def test_create_config_dir_copies_new_changed_and_user_modified_files(
    monkeypatch, tmp_path
):
    source_new = tmp_path / "source-new.yaml"
    source_new.write_text("new")
    source_changed = tmp_path / "source-changed.yaml"
    source_changed.write_text("changed")
    source_custom = tmp_path / "source-custom.yaml"
    source_custom.write_text("custom source")
    source_same = tmp_path / "source-same.yaml"
    source_same.write_text("same")
    existing_changed = tmp_path / "out" / "config" / "changed.yaml"
    existing_custom = tmp_path / "out" / "config" / "custom.yaml"
    existing_same = tmp_path / "out" / "config" / "same.yaml"
    existing_changed.parent.mkdir(parents=True)
    existing_changed.write_text("old")
    existing_custom.write_text("user edited")
    existing_same.write_text("same")
    os.utime(existing_changed, (350039106.789, 350039106.789))
    os.utime(existing_same, (350039106.789, 350039106.789))

    nested = FakeResource("nested", children=[FakeResource("child.yaml", source_new)])
    root = FakeResource(
        "config",
        children=[
            FakeResource("new.yaml", source_new),
            FakeResource("changed.yaml", source_changed),
            FakeResource("custom.yaml", source_custom),
            FakeResource("same.yaml", source_same),
            nested,
        ],
    )

    def files(package):
        if package == "pyefis.config":
            return root
        if package == "pyefis.config.nested":
            return nested
        pytest.fail(f"unexpected package {package}")

    resources = types.SimpleNamespace(files=files)
    monkeypatch.setitem(main_module.sys.modules, "importlib.resources", resources)

    main_module.create_config_dir(str(tmp_path / "out"))

    assert (tmp_path / "out" / "config" / "new.yaml").read_text() == "new"
    assert existing_changed.read_text() == "changed"
    assert existing_same.read_text() == "same"
    assert (tmp_path / "out" / "config" / "custom.yaml.dist").read_text() == "custom source"
    assert (tmp_path / "out" / "config" / "nested" / "child.yaml").read_text() == "new"


def import_main_with_path_state(monkeypatch, path, env=None, isdir=None):
    monkeypatch.delitem(main_module.sys.modules, "pyefis.main", raising=False)
    monkeypatch.setattr(main_module.sys, "path", path[:])
    monkeypatch.setattr(main_module.os, "environ", env or {})
    if isdir is not None:
        monkeypatch.setattr(main_module.os.path, "isdir", isdir)
    imported = importlib.import_module("pyefis.main")
    monkeypatch.setitem(main_module.sys.modules, "pyefis.main", main_module)
    return imported


def test_import_path_setup_skips_when_paths_are_already_present(monkeypatch):
    imported = import_main_with_path_state(
        monkeypatch,
        ["/already/pyAvTools", "/already/pyAvMap"],
    )

    assert imported.sys.path == ["/already/pyAvTools", "/already/pyAvMap"]


def test_import_path_setup_uses_tools_env_and_neighbor_map(monkeypatch):
    imported = import_main_with_path_state(
        monkeypatch,
        ["/app"],
        env={"TOOLS_PATH": "/tools-env"},
        isdir=lambda path: path == os.path.join("..", "pyAvMap"),
    )

    assert "/tools-env" in imported.sys.path
    assert os.path.join("..", "pyAvMap") in imported.sys.path


def test_import_path_setup_uses_map_env_and_skips_missing_tools_env(monkeypatch):
    imported = import_main_with_path_state(
        monkeypatch,
        ["/app"],
        env={"MAP_PATH": "/map-env"},
        isdir=lambda _path: False,
    )

    assert "/map-env" in imported.sys.path
    assert "/app" in imported.sys.path
