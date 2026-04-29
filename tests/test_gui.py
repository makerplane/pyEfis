import sys
import types
import logging
from unittest import mock

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QWidget

import pyefis.gui as gui
import pyefis.hmi as hmi


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


@pytest.fixture(autouse=True)
def reset_gui_state():
    gui.screens.clear()
    gui.log = logging.getLogger("tests.pyefis.gui")
    hmi.initialize({})
    yield
    for screen in gui.screens:
        if screen.object is not None:
            try:
                screen.object.close()
            except RuntimeError:
                pass
    gui.screens.clear()
    sys.modules.pop("qtui", None)


def _screen_module(name):
    module = types.ModuleType(name)

    class FakeScreen(QWidget):
        instances = []

        def __init__(self, parent=None):
            super().__init__(parent)
            self.init_count = 0
            self.closed = False
            self.shown = False
            self.hidden = False
            FakeScreen.instances.append(self)

        def show(self):
            self.shown = True
            self.hidden = False
            super().show()

        def hide(self):
            self.hidden = True
            self.shown = False
            super().hide()

        def initScreen(self):
            self.init_count += 1

        def close(self):
            self.closed = True
            try:
                return super().close()
            except RuntimeError:
                return False

    module.Screen = FakeScreen
    sys.modules[name] = module
    return module


def _screen_module_without_init(name):
    module = types.ModuleType(name)

    class FakeScreen(QWidget):
        instances = []

        def __init__(self, parent=None):
            super().__init__(parent)
            self.shown = False
            self.hidden = False
            FakeScreen.instances.append(self)

        def show(self):
            self.shown = True
            self.hidden = False
            super().show()

        def hide(self):
            self.hidden = True
            self.shown = False
            super().hide()

    module.Screen = FakeScreen
    sys.modules[name] = module
    return module


def _config(width=320, height=240, default=0, full=False, **extra_main):
    main = {
        "screenWidth": width,
        "screenHeight": height,
        "screenColor": "#102030",
        "nodeID": 7,
        "defaultScreen": default,
        "screenFullSize": full,
    }
    main.update(extra_main)
    return {"main": main}


def _add_screen(name, module_name, config=None, default=False):
    screen = gui.Screen(name, module_name, config or {})
    screen.default = default
    gui.screens.append(screen)
    return screen


def test_screen_wraps_module_object_and_emits_visibility_signals(app):
    _screen_module("tests.fake_gui_screen_signal")
    screen = gui.Screen(
        "PFD",
        "tests.fake_gui_screen_signal",
        {"setting": "value"},
    )
    screen.object = mock.Mock()
    shown = mock.Mock()
    hidden = mock.Mock()
    screen.screenShow.connect(shown)
    screen.screenHide.connect(hidden)

    screen.show()
    screen.hide()

    assert screen.name == "PFD"
    assert screen.config == {"setting": "value"}
    screen.object.show.assert_called_once_with()
    screen.object.hide.assert_called_once_with()
    shown.assert_called_once_with()
    hidden.assert_called_once_with()


def test_set_default_screen_by_index_name_and_missing(app):
    _screen_module("tests.fake_gui_screen_default")
    first = _add_screen("FIRST", "tests.fake_gui_screen_default")
    second = _add_screen("SECOND", "tests.fake_gui_screen_default")

    assert gui.setDefaultScreen(1) is True
    assert first.default is False
    assert second.default is True

    assert gui.setDefaultScreen("FIRST") is True
    assert first.default is True
    assert second.default is False

    assert gui.setDefaultScreen("MISSING") is False
    assert first.default is False
    assert second.default is False


def test_main_loads_screens_switches_and_exposes_config(app, qtbot):
    first_mod = _screen_module("tests.fake_gui_screen_main_first")
    second_mod = _screen_module("tests.fake_gui_screen_main_second")
    _add_screen("FIRST", "tests.fake_gui_screen_main_first", {"mode": "first"}, True)
    _add_screen("SECOND", "tests.fake_gui_screen_main_second", {"mode": "second"})

    window = gui.Main(_config(default=0), "/config/path", {"pref": True})
    qtbot.addWidget(window)

    assert window.preferences == {"pref": True}
    assert window.config_path == "/config/path"
    assert window.screenWidth == 320
    assert window.screenHeight == 240
    assert window.nodeID == 7
    assert window.running_screen == 0
    assert first_mod.Screen.instances[0].screenName == "FIRST"
    assert second_mod.Screen.instances[0].screenName == "SECOND"
    assert first_mod.Screen.instances[0].shown is True
    assert second_mod.Screen.instances[0].hidden is True
    assert second_mod.Screen.instances[0].init_count == 1
    assert window.get_config_item(second_mod.Screen.instances[0], "mode") == "second"
    assert window.get_config_item(QWidget(), "mode") is None

    window.showScreen("SECOND")
    assert window.running_screen == 1
    assert first_mod.Screen.instances[0].hidden is True
    assert second_mod.Screen.instances[0].shown is True

    window.showScreen(1)
    assert window.running_screen == 1

    window.showNextScreen()
    assert window.running_screen == 0

    window.showNextScreen()
    assert window.running_screen == 1

    window.showPrevScreen()
    assert window.running_screen == 0

    window.showScreen(0)
    assert window.running_screen == 0

    window.showPrevScreen()
    assert window.running_screen == 1

    with pytest.raises(KeyError):
        window.showScreen("NOPE")

    with pytest.raises(KeyError):
        window.showScreen(-1)


def test_main_skips_init_screen_when_hidden_screen_has_no_hook(app, qtbot):
    _screen_module("tests.fake_gui_screen_with_init")
    no_init_mod = _screen_module_without_init("tests.fake_gui_screen_without_init")
    _add_screen("FIRST", "tests.fake_gui_screen_with_init", {}, True)
    _add_screen("SECOND", "tests.fake_gui_screen_without_init")

    window = gui.Main(_config(default=0), ".", {})
    qtbot.addWidget(window)

    assert no_init_mod.Screen.instances[0].hidden is True


def test_main_uses_primary_screen_when_size_not_configured(app, qtbot, monkeypatch):
    _screen_module("tests.fake_gui_screen_primary_size")
    _add_screen("FIRST", "tests.fake_gui_screen_primary_size", {}, True)
    fake_size = mock.Mock()
    fake_size.width.return_value = 111
    fake_size.height.return_value = 222
    fake_screen = mock.Mock()
    fake_screen.size.return_value = fake_size
    monkeypatch.setattr(gui.QApplication, "primaryScreen", mock.Mock(return_value=fake_screen))

    config = _config(width=0, height=0, default=0, screenColor=None, nodeID=99)
    window = gui.Main(config, ".", {})
    qtbot.addWidget(window)

    assert window.screenWidth == 111
    assert window.screenHeight == 222
    assert window.nodeID == 99


def test_main_events_running_screen_and_exit(app, qtbot, monkeypatch):
    _screen_module("tests.fake_gui_screen_events")
    _add_screen("FIRST", "tests.fake_gui_screen_events", {}, True)
    window = gui.Main(_config(default=0), ".", {})
    qtbot.addWidget(window)

    seen = {
        "show": mock.Mock(),
        "close": mock.Mock(),
        "press": mock.Mock(),
        "release": mock.Mock(),
    }
    window.windowShow.connect(seen["show"])
    window.windowClose.connect(seen["close"])
    window.keyPress.connect(seen["press"])
    window.keyRelease.connect(seen["release"])
    event = QEvent(QEvent.Type.None_)

    window.showEvent(event)
    window.closeEvent(event)
    window.keyPressEvent(event)
    window.keyReleaseEvent(event)

    seen["show"].assert_called_once_with(event)
    seen["close"].assert_called_once_with(event)
    seen["press"].assert_called_once_with(event)
    seen["release"].assert_called_once_with(event)
    assert window.getRunningScreen() == "Unknown"

    class NamedIndex(int):
        pass

    window.running_screen = NamedIndex(0)
    window.running_screen.name = "RUNNING"
    assert window.getRunningScreen() == gui.screens[window.running_screen].name

    monkeypatch.setattr(gui.fix, "stop", mock.Mock())
    monkeypatch.setattr(gui.time, "sleep", mock.Mock())
    monkeypatch.setattr(gui.QCoreApplication, "quit", mock.Mock())

    window.doExit()

    assert gui.screens[0].object.closed is True
    gui.fix.stop.assert_called_once_with()
    gui.time.sleep.assert_called_once_with(5)
    gui.QCoreApplication.quit.assert_called_once_with()


def test_initialize_loads_screens_menu_fms_window_and_button_timeout(
    app,
    fix,
    monkeypatch,
):
    _screen_module("tests.fake_gui_screen_initialize_one")
    _screen_module("tests.fake_gui_screen_initialize_two")
    menu_instance = mock.Mock()
    menu_class = mock.Mock(return_value=menu_instance)
    monkeypatch.setattr(gui.hmi.menu, "Menu", menu_class)
    monkeypatch.setattr(gui.scheduler, "initialize", mock.Mock())

    class FakeTimer:
        def __init__(self):
            self.callbacks = []
            self.started = False

        def add_callback(self, callback):
            self.callbacks.append(callback)

        def start(self):
            self.started = True

    timer = FakeTimer()
    fake_scheduler = mock.Mock()
    fake_scheduler.timers = []
    fake_scheduler.getTimer.side_effect = [None, timer]
    monkeypatch.setattr(gui.scheduler, "scheduler", fake_scheduler, raising=False)
    monkeypatch.setattr(gui.scheduler, "IntervalTimer", mock.Mock(return_value=timer))

    qtui = types.ModuleType("qtui")
    qtui_widget = mock.Mock()
    qtui.FMSUI = mock.Mock(return_value=qtui_widget)
    sys.modules["qtui"] = qtui

    config = {
        "main": {
            "screenWidth": 320,
            "screenHeight": 240,
            "screenColor": "#000000",
            "defaultScreen": "SECOND",
            "screenFullSize": False,
            "button_timeout": 12,
        },
        "screens": {
            "FIRST": {"module": "tests.fake_gui_screen_initialize_one"},
            "SECOND": {"module": "tests.fake_gui_screen_initialize_two"},
        },
        "menu": {"items": []},
        "FMS": {
            "module_dir": "/tmp/fms",
            "flight_plan_dir": "/tmp/plans",
            "ui_width": 640,
        },
    }

    gui.initialize(config, "/config", {"includes": {}})

    assert [screen.name for screen in gui.screens] == ["FIRST", "SECOND"]
    assert gui.screens[0].default is False
    assert gui.screens[1].default is True
    assert gui.mainWindow.running_screen == 1
    menu_class.assert_called_once_with(gui.mainWindow, {"items": []})
    menu_instance.start.assert_called_once_with()
    qtui.FMSUI.assert_called_once_with("/tmp/plans", gui.mainWindow)
    qtui_widget.resize.assert_called_once_with(640, 65)
    qtui_widget.move.assert_called_once_with(30, 32)
    menu_instance.register_target.assert_called_once_with("FMS", qtui_widget)
    gui.scheduler.initialize.assert_called_once_with()
    gui.scheduler.IntervalTimer.assert_called_once_with(12)
    assert len(timer.callbacks) == 1

    timer.callbacks[0]()
    assert fix.db.get_item("HIDEBUTTON").value is True
    fix.db.get_item("HIDEBUTTON").value = False
    assert timer.started is True


def test_initialize_defaults_to_first_screen_and_fullscreen(app, monkeypatch):
    _screen_module("tests.fake_gui_screen_initialize_full")
    config = {
        "main": {
            "screenWidth": 320,
            "screenHeight": 240,
            "screenColor": "#000000",
            "screenFullSize": True,
        },
        "screens": {
            "FIRST": {"module": "tests.fake_gui_screen_initialize_full"},
        },
    }
    show_full_screen = mock.Mock()
    monkeypatch.setattr(gui.Main, "showFullScreen", show_full_screen)

    gui.initialize(config, ".", {})

    assert gui.screens[0].default is True
    show_full_screen.assert_called_once_with()


def test_initialize_uses_default_fms_width_and_existing_button_timer(
    app,
    fix,
    monkeypatch,
):
    _screen_module("tests.fake_gui_screen_initialize_defaults")
    menu_instance = mock.Mock()
    monkeypatch.setattr(gui.hmi.menu, "Menu", mock.Mock(return_value=menu_instance))
    monkeypatch.setattr(gui.scheduler, "initialize", mock.Mock())

    timer = mock.Mock()
    fake_scheduler = mock.Mock()
    fake_scheduler.getTimer.return_value = timer
    monkeypatch.setattr(gui.scheduler, "scheduler", fake_scheduler, raising=False)
    interval_timer = mock.Mock()
    monkeypatch.setattr(gui.scheduler, "IntervalTimer", interval_timer)

    qtui = types.ModuleType("qtui")
    qtui_widget = mock.Mock()
    qtui.FMSUI = mock.Mock(return_value=qtui_widget)
    sys.modules["qtui"] = qtui

    config = {
        "main": {
            "screenWidth": 320,
            "screenHeight": 240,
            "screenColor": "#000000",
            "screenFullSize": False,
            "button_timeout": 99,
        },
        "screens": {
            "FIRST": {"module": "tests.fake_gui_screen_initialize_defaults"},
        },
        "menu": {"items": []},
        "FMS": {
            "module_dir": "/tmp/fms",
            "flight_plan_dir": "/tmp/plans",
        },
    }

    gui.initialize(config, ".", {})

    qtui_widget.resize.assert_called_once_with(1000, 65)
    timer.add_callback.assert_called_once()
    interval_timer.assert_not_called()


def test_initialize_raises_when_screen_module_fails(app):
    config = {
        "main": {
            "screenWidth": 320,
            "screenHeight": 240,
            "screenColor": "#000000",
            "screenFullSize": False,
        },
        "screens": {
            "BROKEN": {"module": "tests.fake_gui_missing_module"},
        },
    }

    with pytest.raises(ModuleNotFoundError):
        gui.initialize(config, ".", {})
