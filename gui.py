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
from menu import Menu

screens = []

# This class is just a structure to hold information about a single
# screen that will be loaded.
class Screen(QObject):
    screenShow = pyqtSignal()
    screenHide = pyqtSignal()

    def __init__(self, name, module, config):
        super(Screen, self).__init__()
        self.name = name
        # strings here remove the options from the list before it is
        # sent to the plugin.
        exclude_options = ["module"]
        self.module = importlib.import_module(module)
        # Here items winds up being a list of tuples [('key', 'value'),...]
        items = [item for item in config.items("Screen." + name)
                 if item[0] not in exclude_options]
        # Append the command line arguments to the items list as a tuple
        items.append(('argv', sys.argv))
        # Convert this to a dictionary before passing to the plugin
        self.config = {}
        for each in items:
            self.config[each[0]] = each[1]

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
    change_asd_mode = pyqtSignal(QEvent)

    def __init__(self, config, parent=None):
        super(Main, self).__init__(parent)

        self.screenWidth = int(config.get("mainscreen", "screenSize.Width"))
        self.screenHeight = int(config.get("mainscreen", "screenSize.Height"))
        self.screenColor = config.get("mainscreen", "screenColor")

        self.setObjectName("PFD")
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

    def change_asd_mode_event (self, event):
        self.change_asd_mode.emit(event)

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

    # Load the Screens
    for each in config.sections():
        if each.startswith ("Screen."):
            module = config.get(each, "module")
            try:
                name = each[7:]
                screens.append(Screen(name, module, config))
                log.debug("Creating Screen {0}".format(name))
                #load_screen(each[7:], module, config)
            except Exception as e:
                log.critical("Unable to load module - " + module + ": " + str(e))
                raise


    try:
        d = config.get("mainscreen", "defaultScreen")
    except ConfigParser.NoOptionError:
        d = 0

    setDefaultScreen(d)

    mainWindow = Main(config)
    menu = Menu(mainWindow, config.get("menu", "config_file"))
    menu.start()

    screen = config.getboolean("mainscreen", "screenFullSize")
    if screen:
        mainWindow.showFullScreen()
    else:
        mainWindow.width = int(config.get("mainscreen", "screenSize.Width"))
        mainWindow.height = int(config.get("mainscreen", "screenSize.Height"))
        mainWindow.show()
