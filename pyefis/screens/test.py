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

#from instruments import ai
#from instruments import gauges
#from instruments import hsi
from instruments import airspeed
#from instruments import altimeter
#from instruments import vsi

class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()

        self.screenColor = (0, 0, 0)
        if self.screenColor:
            self.setPalette(p)
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setAutoFillBackground(True)

        self.airspeed = airspeed.Airspeed(self)

    def resizeEvent(self, event):

        instWidth = self.width() - 210
        instHeight = self.height() - 200

        self.airspeed.move(0,0)
        self.airspeed.resize(200,200)
