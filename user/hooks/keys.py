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

import gui
import fix
import hooks

def keyPress(event):
    if event.key() == Qt.Key_BracketRight:
        x = fix.db.get_item("BARO")
        x.value = x.value + 0.01

    #  Decrease Altimeter Setting
    elif event.key() == Qt.Key_BracketLeft:
        x = fix.db.get_item("BARO")
        x.value = x.value - 0.01

    elif event.key() == Qt.Key_Q:
        fix.db.set_value("BTN16", True)

    #  Decrease Altimeter Setting
    elif event.key() == Qt.Key_M:
        hooks.log.debug("Change Airspeed Mode")
        #self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    elif event.key() == Qt.Key_S:
        hooks.log.debug("Screen Change")
        gui.mainWindow.showScreen(0)
        #self.asd_Box.setMode(self.asd_Box.getMode() + 1)


def keyRelease(event):
    if event.key() == Qt.Key_Q:
        fix.db.set_value("BTN16", False)


gui.mainWindow.keyPress.connect(keyPress)
gui.mainWindow.keyRelease.connect(keyRelease)
