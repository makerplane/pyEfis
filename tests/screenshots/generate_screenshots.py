import pytest
import warnings
import importlib
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QColor
#from pyefis.screens import screenbuilder
from tests.screenshots import gui
import yaml

@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_save_screenshot(qtbot, request):
    with open("tests/screenshots/configs/pyefis.instruments.gauges.NumericDisplay.yaml") as cf:
        config = yaml.safe_load(cf)
    #widget = Screen("TEST", "pyefis.screens.screenbuilder", config)
    gui.initialize(config,"tests",{})
    qtbot.waitExposed(gui.mainWindow.scr.module)
    qtbot.wait(5000)
#show()
#resize(1024,1024)

#screenbuilder.Screen(config=config)
