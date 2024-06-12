import pytest
import warnings
import importlib
from unittest import mock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QColor
#from pyefis.screens import screenbuilder
from tests.screen import gui

class Screen(QObject):
    def __init__(self, name, module, config):
        super(Screen, self).__init__()
        self.name = name
        self.module = importlib.import_module(module)
        self.config = config
        self.object = None
        self.default = False
    def show(self):
        self.object.show()
        self.screenShow.emit()
    def hide(self):
        self.object.hide()
        self.screenHide.emit()


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


def test_save_screenshot(qtbot, request):

    config = {
      "main": {
        "nodeID": 1,
        "screenWidth": 1024,
        "screenHeight": 1024,
        "screenColor": "0,0,0"
      },
      "screens": {
        "TEST": {
          "layout": {
            "rows": 100,
            "columns": 100,
          },
          "instruments": [
            { 
            "type": "value_text",
            "row": 0,
            "column": 0,
            "span": {
              "rows": 10,
              "columns": 10
            },
            "options": {
              "dbkey": "TEST"
            }


            }
          ]
        }
      }
    }

    #widget = Screen("TEST", "pyefis.screens.screenbuilder", config)
    gui.initialize(config,"tests",{})
    qtbot.waitExposed(gui.mainWindow.scr.module)
    qtbot.wait(5000)
#show()
#resize(1024,1024)

#screenbuilder.Screen(config=config)
