from types import SimpleNamespace

import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication, QWidget

from pyefis.instruments import weston


@pytest.fixture
def app(qtbot):
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class FakeProcess:
    instances = []

    def __init__(self, parent=None):
        self.parent = parent
        self.environment = None
        self.started = None
        self.terminated = False
        self.killed = False
        self.wait_results = [True]
        FakeProcess.instances.append(self)

    def setProcessEnvironment(self, environment):
        self.environment = environment

    def start(self, command, args):
        self.started = (command, args)

    def terminate(self):
        self.terminated = True

    def waitForFinished(self, _timeout):
        return self.wait_results.pop(0)

    def kill(self):
        self.killed = True


class RaisingProcess(FakeProcess):
    def terminate(self):
        raise RuntimeError("shutdown failed")


class FakeWindow:
    def __init__(self, win_id):
        self._win_id = win_id
        self.flags = []

    def setFlag(self, flag, enabled):
        self.flags.append((flag, enabled))

    def winId(self):
        return self._win_id


class FakeXWindow:
    def __init__(self):
        self.reparented = None
        self.mapped = False

    def reparent(self, container, x, y):
        self.reparented = (container, x, y)

    def map(self):
        self.mapped = True


class FakeDisplay:
    instances = []

    def __init__(self):
        self.resources = []
        self.flushed = False
        FakeDisplay.instances.append(self)

    def create_resource_object(self, kind, win_id):
        resource = FakeXWindow()
        self.resources.append((kind, win_id, resource))
        return resource

    def flush(self):
        self.flushed = True


@pytest.fixture
def fake_weston_runtime(monkeypatch):
    FakeProcess.instances = []
    FakeDisplay.instances = []
    windows = []
    containers = []

    monkeypatch.setattr(weston, "QProcess", FakeProcess)
    monkeypatch.setattr(
        weston.QProcessEnvironment,
        "systemEnvironment",
        staticmethod(lambda: "fake environment"),
    )
    monkeypatch.setattr(weston.time, "sleep", lambda _seconds: None)

    def from_win_id(win_id):
        window = FakeWindow(win_id)
        windows.append(window)
        return window

    def create_container(window, parent, flags):
        container = QWidget(parent)
        containers.append((window, parent, flags, container))
        return container

    monkeypatch.setattr(weston.QWindow, "fromWinId", staticmethod(from_win_id))
    monkeypatch.setattr(
        weston.QWidget,
        "createWindowContainer",
        staticmethod(create_container),
    )
    monkeypatch.setattr(weston.display, "Display", FakeDisplay)

    return SimpleNamespace(
        processes=FakeProcess.instances,
        displays=FakeDisplay.instances,
        windows=windows,
        containers=containers,
    )


def _completed_process(returncode=0, stdout=b""):
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_weston_starts_without_size_and_retries_when_xwininfo_fails(
    app, qtbot, monkeypatch, fake_weston_runtime
):
    calls = []

    def fake_run(args, stdout):
        calls.append((args, stdout))
        return _completed_process(returncode=1)

    monkeypatch.setattr(weston.subprocess, "run", fake_run)

    widget = weston.Weston(socket="pyefis", ini="weston.ini")
    qtbot.addWidget(widget)

    process = fake_weston_runtime.processes[0]
    assert process.environment == "fake environment"
    assert process.started == (
        "weston",
        ["-cweston.ini", "-i0", "-Bx11-backend.so", "-Spyefis"],
    )
    assert len(calls) == 15
    assert fake_weston_runtime.windows == []


def test_weston_starts_with_size_and_embeds_matching_x11_window(
    app, qtbot, monkeypatch, fake_weston_runtime
):
    seen = []
    xwininfo = b'     0x2a "Weston Compositor - pyEfis"\n'

    def fake_run(args, stdout):
        seen.append((args, stdout))
        return _completed_process(stdout=xwininfo)

    monkeypatch.setattr(weston.subprocess, "run", fake_run)

    widget = weston.Weston(
        socket="sized",
        ini="custom.ini",
        wide=1024,
        high=600,
    )
    qtbot.addWidget(widget)

    process = fake_weston_runtime.processes[0]
    assert process.started == (
        "weston",
        [
            "-ccustom.ini",
            "-i0",
            "-Bx11-backend.so",
            "--width=1024",
            "--height=600",
            "--fullscreen",
            "-Ssized",
        ],
    )
    assert len(seen) == 1
    assert fake_weston_runtime.windows[0].winId() == 0x2A

    display = fake_weston_runtime.displays[0]
    x11_window = display.resources[0][2]
    container_window = display.resources[1][2]
    assert display.resources[0][:2] == ("window", 0x2A)
    assert display.resources[1][0] == "window"
    assert x11_window.reparented == (container_window, 0, 0)
    assert x11_window.mapped is True
    assert display.flushed is True


def test_weston_ignores_non_matching_xwininfo_lines_before_retrying(
    app, qtbot, monkeypatch, fake_weston_runtime
):
    results = [
        _completed_process(stdout=b'     0x10 "Other Window"\n'),
        _completed_process(stdout=b'     0x11 "Weston Compositor - pyEfis"\n'),
    ]

    def fake_run(_args, stdout):
        return results.pop(0)

    monkeypatch.setattr(weston.subprocess, "run", fake_run)

    widget = weston.Weston(socket="retry", ini="weston.ini")
    qtbot.addWidget(widget)

    assert fake_weston_runtime.windows[0].winId() == 0x11


def test_close_event_terminates_or_kills_weston_process(
    app, qtbot, monkeypatch, fake_weston_runtime
):
    monkeypatch.setattr(
        weston.subprocess,
        "run",
        lambda _args, stdout: _completed_process(returncode=1),
    )

    widget = weston.Weston(socket="close", ini="weston.ini")
    qtbot.addWidget(widget)
    process = fake_weston_runtime.processes[0]
    process.wait_results = [False, True]

    widget.closeEvent(QCloseEvent())

    assert process.terminated is True
    assert process.killed is True


def test_close_event_allows_missing_or_failing_process(
    app, qtbot, monkeypatch, fake_weston_runtime
):
    monkeypatch.setattr(
        weston.subprocess,
        "run",
        lambda _args, stdout: _completed_process(returncode=1),
    )

    widget = weston.Weston(socket="none", ini="weston.ini")
    qtbot.addWidget(widget)
    widget.weston = None
    widget.closeEvent(QCloseEvent())

    monkeypatch.setattr(weston, "QProcess", RaisingProcess)
    failing_widget = weston.Weston(socket="failing", ini="weston.ini")
    qtbot.addWidget(failing_widget)
    failing_widget.closeEvent(QCloseEvent())
