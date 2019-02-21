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

from instruments import ai
# from instruments import gauges
from instruments import hsi
from instruments import airspeed
from instruments import altimeter
from instruments import vsi
from instruments import tc


class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()

        self.screenColor = (0, 0, 0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        self.airspeed = airspeed.Airspeed(self)

        self.ai = ai.AI(self)
        self.ai.fontSize = 20
        self.ai.pitchDegreesShown = 60

        self.altimeter = altimeter.Altimeter(self)

        self.tc = tc.TurnCoordinator(self)

        self.hsi = hsi.HSI(self, font_size=25, fgcolor=Qt.white)

        self.vsi = vsi.VSI(self)

    def resizeEvent(self, event):
        instWidth = self.width() / 3
        instHeight = instWidth
        menu_offset = 100

        self.airspeed.move(0, menu_offset)
        self.airspeed.resize(instWidth, instHeight)

        self.ai.move(instWidth, 0 + menu_offset)
        self.ai.resize(instWidth, instHeight)

        self.altimeter.move(instWidth * 2, 0 + menu_offset)
        self.altimeter.resize(instWidth, instHeight)

        self.tc.move(0, instHeight + menu_offset)
        self.tc.resize(instWidth, instHeight)

        self.hsi.move(instWidth, instHeight + menu_offset)
        self.hsi.resize(instWidth, instHeight)

        self.vsi.move(instWidth * 2, instHeight + menu_offset)
        self.vsi.resize(instWidth, instHeight)
