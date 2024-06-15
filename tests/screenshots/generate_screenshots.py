import pytest
import warnings
import importlib
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QColor
from tests.screenshots import gui
import yaml
import os

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_save_screenshot_numeric_display(fix, qtbot, request):
    with open("tests/screenshots/configs/pyefis.instruments.gauges.NumericDisplay.yaml") as cf:
        config = yaml.safe_load(cf)
    #widget = Screen("TEST", "pyefis.screens.screenbuilder", config)
    gui.initialize(config,"tests",{})
    qtbot.waitExposed(gui.mainWindow.scr.module)
    path = qtbot.screenshot(gui.mainWindow, "numeric_display")
    qtbot.wait(500)
    os.rename(
        path,
        request.config.rootdir
        + "/extras/extras/test_results/numeric_display.png",
    )
    qtbot.wait(10000)
