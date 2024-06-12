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

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import time
import importlib
import logging
import sys
import os
from pyefis import hooks
from pyefis import hmi
import pyavtools.fix as fix
import pyavtools.scheduler as scheduler


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
    def __init__(self, config, config_path, preferences, scr, parent=None):
        super(Main, self).__init__(parent)
        self.preferences = preferences
        self.config_path = config_path
        self.scr = scr
        self.screenWidth = int(config["main"].get("screenWidth", False))
        self.screenHeight = int(config["main"].get("screenHeight", False))
        if not ( self.screenWidth and self.screenHeight ):
            # screenWidth and screenHeight are not defined in the config file
            # go full screen
            pscreen = QApplication.primaryScreen()
            screensize = pscreen.size()
            self.screenWidth = screensize.width()
            self.screenHeight = screensize.height()

        self.screenColor = config["main"]["screenColor"]
        self.nodeID = config["main"].get('nodeID', 1)

        self.setObjectName("EFIS")
        self.resize(self.screenWidth, self.screenHeight)
        w = QWidget(self)
        w.setGeometry(0, 0, self.screenWidth, self.screenHeight)

        p = w.palette()
        if self.screenColor:
             p.setColor(w.backgroundRole(), QColor(self.screenColor))
             w.setPalette(p)
             w.setAutoFillBackground(True)

        print(self.scr)
        print(dir(self.scr))
        scr.object = self.scr.module.Screen(self)
        setattr(scr.object,'screenName',scr.name)
        scr.object.resize(self.width(), self.height())
        scr.object.move(0,0)
        scr.show()


    #def doExit(self, s=""):
        # Ensure external processes are terminated before exiting
        # For example waydroid/weston if they are in use
        #for s in screens:
        #    s.object.close()
        # Close down fix connections
        # This needs done before the main event loop is stopped below

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
        print(f"child:{child,} key:{key}")
        if self.scr.object == child:
            print("match")
            print(self.scr.config)
            return self.scr.config.get(key)
        else:
            return None


def initialize(config,config_path,preferences):
    global mainWindow
    global log
    log = logging.getLogger(__name__)
    log.info("Initializing Graphics")
    module = "pyefis.screens.screenbuilder"

    scr = Screen("TEST", module, config['screens']["TEST"])
    print(scr)
    mainWindow = Main(config,config_path,preferences,scr)

    mainWindow.showFullScreen()

    def button_timeout():
        # set MENUTIMEOUT True
        button_key.value = True

    def button_timeout_reset():
        if not button_key.value:
            #When set to False reset timer    
            button_timer.start()

    if config['main'].get('button_timeout', False):
        scheduler.initialize()
        button_timer = scheduler.scheduler.getTimer(config['main']['button_timeout'])
        if not button_timer:
            scheduler.scheduler.timers.append(scheduler.IntervalTimer(config['main']['button_timeout']))
            scheduler.scheduler.timers[-1].start()
            button_timer = scheduler.scheduler.getTimer(config['main']['button_timeout'])
        button_key = fix.db.get_item('HIDEBUTTON')
        button_timer.add_callback(button_timeout)
        button_key.valueWrite[bool].connect(button_timeout_reset)


