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

try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *

except:
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *


class ActionClass(QWidget):
    def __init__(self):
        super(ActionClass, self).__init__()
        self.signalMap = {"change asd mode":self.setAirspeedMode,
                          "set egt mode":self.setEgtMode,
                          "show screen":self.showScreen,
                          "show next screen":self.showNextScreen,
                          "show previous screen":self.showPrevScreen
                    }

    setAirspeedMode = pyqtSignal(str)
    setEgtMode = pyqtSignal(str)
    showScreen = pyqtSignal(str)
    showNextScreen = pyqtSignal(str)
    showPrevScreen = pyqtSignal(str)

    def trigger(self, action, argument=""):
        self.signalMap[action.lower()].emit(argument)
