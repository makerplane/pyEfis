#  Copyright (c) 2016 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import importlib
import logging
import sys
import hooks
import hmi
from hmi import Menu

screens = []

# This class is just a structure to hold information about a single
# screen that will be loaded.
class Screen(QObject):
    screenShow = pyqtSignal()
    screenHide = pyqtSignal()

    def __init__(self, name, module, config):
        super(Screen, self).__init__()
        self.name = name
        self.module = importlib.import_module(module)
        self.config = config

        # This would hold the instantiated Screen object from the module.
        self.object = None
        self.default = False

    def show(self):
        self.object.show()
        self.screenShow.emit()

    def hide(self):
        self.object.hide()
        self.screenHide.emit()


class Main(QMainWindow):
    keyPress = pyqtSignal(QEvent)
    keyRelease = pyqtSignal(QEvent)
    windowShow = pyqtSignal(QEvent)
    windowClose = pyqtSignal(QEvent)
    #change_asd_mode = pyqtSignal(QEvent)

    def __init__(self, config, parent=None):
        super(Main, self).__init__(parent)

        self.screenWidth = int(config["main"]["screenWidth"])
        self.screenHeight = int(config["main"]["screenHeight"])
        self.screenColor = config["main"]["screenColor"]

        self.setObjectName("EFIS")
        self.resize(self.screenWidth, self.screenHeight)
        w = QWidget(self)
        w.setGeometry(0, 0, self.screenWidth, self.screenHeight)

        p = w.palette()
        if self.screenColor:
             p.setColor(w.backgroundRole(), QColor(self.screenColor))
             w.setPalette(p)
             w.setAutoFillBackground(True)

        for idx, scr in enumerate(screens):

            scr.object = scr.module.Screen(self)
            log.debug("Loading Screen {0}".format(scr.name))
            # TODO Figure out how to have different size screens
            scr.object.resize(self.width(), self.height())
            scr.object.move(0,0)
            if scr.default:
                scr.show()
                self.running_screen = idx
            else:
                scr.hide()

    def showScreen(self, scr):
        found = None
        if type(scr) == int:
            if scr >= 0 and scr < len(screens):
                found = scr
        else:
            for i, s in enumerate(screens):
                if s.name == scr:
                    found = i
                    break
        if found is not None:
            if found != self.running_screen:  # Make sure it's different.
                screens[found].show()
                screens[self.running_screen].hide()
                self.running_screen = found
        else:
            raise KeyError("Screen {0} Not Found".format(scr))

    def showNextScreen(self, s=""):
        if self.running_screen == len(screens)-1:
            self.showScreen(0)
        else:
            self.showScreen(self.running_screen + 1)

    def showPrevScreen(self, s=""):
        if self.running_screen == 0:
            self.showScreen(len(screens)-1)
        else:
            self.showScreen(self.running_screen-1)


    # We send signals for these events so everybody can play.
    def showEvent(self, event):
        self.windowShow.emit(event)

    def closeEvent(self, event):
        log.debug("Window Close event received")
        self.windowClose.emit(event)

    def keyPressEvent(self, event):
        self.keyPress.emit(event)

    def keyReleaseEvent(self, event):
        self.keyRelease.emit(event)

    # def change_asd_mode_event (self, event):
    #     self.change_asd_mode.emit(event)

    def get_config_item(self, child, key):
        for s in screens:
            if s.object == child:
                return s.config[key]
        else:
            return None

def setDefaultScreen(s):
    found = False
    if type(s) == int:
        for i, scr in enumerate(screens):
            if i == s:
                found = True
                scr.default = True
                log.debug("setting screen {0} to default".format(s))
            else:
                scr.default = False
    else:
        for scr in screens:
            if scr.name == s:
                found = True
                scr.default = True
                log.debug("setting screen {0} to default".format(s))
            else:
                scr.default = False
    return found


def initialize(config):
    global mainWindow
    global log
    log = logging.getLogger(__name__)
    log.info("Initializing Graphics")
    # Load the Screens
    for each in config['screens']:
        module = config['screens'][each]["module"]
        try:
            name = each
            screens.append(Screen(name, module, config['screens'][each]))
            log.debug("Creating Screen {0}".format(name))
        except Exception as e:
            log.critical("Unable to load module - " + module + ": " + str(e))
            raise

    try:
        d = config["main"]["defaultScreen"]
    except KeyError:
        d = 0

    setDefaultScreen(d)

    mainWindow = Main(config)
    hmi.actions.showNextScreen.connect(mainWindow.showNextScreen)
    hmi.actions.showPrevScreen.connect(mainWindow.showPrevScreen)
    hmi.actions.showScreen.connect(mainWindow.showScreen)

    if 'menu' in config:
        menu = Menu(mainWindow, config["menu"])
        menu.start()


    if 'FMS' in config:
        sys.path.insert(0, config["FMS"]["module_dir"])
        ui = importlib.import_module ("qtui")
        uiwidget = ui.FMSUI(config["FMS"]["flight_plan_dir"], mainWindow)
        uiwidget.resize (700, 65)
        uiwidget.move (30, 32)
        menu.register_target ("FMS", uiwidget)

    screen = bool(config["main"]["screenFullSize"])
    if screen:
        log.debug("Setting Screen to Full Size")
        mainWindow.showFullScreen()
    else:
        mainWindow.width = int(config["main"]["screenWidth"])
        mainWindow.height = int(config["main"]["screenHeight"])
        mainWindow.show()
