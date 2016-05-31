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
    from PyQt5.QtCore import *
except:
    from PyQt4.QtCore import *

import logging
import importlib


# Instead of creating callbacks and putting hook calls all over the code
# we just create a bunch of signals and emit them for different events
# To create hooks just have the module loaded via the main configuration file
# import this module and connect to signals on the signals object.
class Signals(QObject):
    keyPress = pyqtSignal(QEvent)
    mainWindowShow = pyqtSignal(QEvent)
    mainWindowClose = pyqtSignal(QEvent)

    def __init__(self):
        super(Signals, self).__init__()

    def keyPressEmit(self, event):
        self.keyPress.emit(event)

    def mainWindowShowEmit(self, event):
        self.mainWindowShow.emit(event)

    def mainWindowCloseEmit(self, event):
        self.mainWindowClose.emit(event)


signals = Signals()

# Read through the configuration and load the hook modules
def initialize(config):
    global log
    log = logging.getLogger(__name__)

    # Load the Hook Modules
    for each in config.sections():
        if each[:5] == "Hook.":
            module = config.get(each, "module")
            try:
                name = each[5:]
                importlib.import_module(module)
                #load_screen(each[7:], module, config)
            except Exception as e:
                logging.critical("Unable to load module - " + module + ": " + str(e))
                raise
