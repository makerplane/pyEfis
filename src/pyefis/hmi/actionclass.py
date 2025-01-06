#  Copyright (c) 2018 Phil Birkelbach
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
import logging

from PyQt6.QtCore import pyqtSignal, pyqtBoundSignal
from PyQt6.QtWidgets import QWidget

from pyefis.hmi import functions
from .menu import activateMenu


class ActionClass(QWidget):
    setAirspeedMode = pyqtSignal(object)
    setEgtMode = pyqtSignal(object)
    showScreen = pyqtSignal(object)
    # arg = screen name
    showNextScreen = pyqtSignal(object)
    showPrevScreen = pyqtSignal(object)
    activateMenuItem = pyqtSignal(object)
    menuEncoder = pyqtSignal(object)
    setMenuFocus = pyqtSignal(object)
    setInstUnits = pyqtSignal(object)
    doExit = pyqtSignal(object)
    # arg = <inst name>,<inst name>,<inst name>,..:<Command>

    def __init__(self):
        super(ActionClass, self).__init__()
        self.signalMap = {
            "set airspeed mode": self.setAirspeedMode,
            "set egt mode": self.setEgtMode,
            "show screen": self.showScreen,
            "show next screen": self.showNextScreen,
            "show previous screen": self.showPrevScreen,
            "set value": functions.setValue,
            "change value": functions.changeValue,
            "toggle bit": functions.toggleBool,
            "activate menu item": self.activateMenuItem,
            "activate menu": activateMenu,
            "menu encoder": self.menuEncoder,
            "set menu focus": self.setMenuFocus,
            "set instrument units": self.setInstUnits,
            "exit": self.doExit,
            "evaluate": eval,
        }

    def trigger(self, action, argument=""):
        a = self.signalMap[action.lower()]
        if isinstance(a, pyqtBoundSignal):
            a.emit(argument)
        else:  # It's not a signal so assume it's a function
            a(argument)

    def findAction(self, action):
        a = action.lower()
        if a in self.signalMap:
            return self.signalMap[a]
        else:
            return None
