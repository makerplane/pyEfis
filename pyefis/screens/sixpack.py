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

from pyefis.instruments import ai
# from pyefis.instruments import gauges
from pyefis.instruments import hsi
from pyefis.instruments import airspeed
from pyefis.instruments import altimeter
from pyefis.instruments import vsi
from pyefis.instruments import tc


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
        self.ai.fontSize = 12
        self.ai.bankMarkSize = 7
        self.ai.pitchDegreesShown = 60

        self.altimeter = altimeter.Altimeter(self)

        self.tc = tc.TurnCoordinator(self)

        self.hsi = hsi.HSI(self, font_size=12, fgcolor=Qt.white)
        self.heading_disp = hsi.HeadingDisplay(self, font_size=17, fgcolor=Qt.white)

        self.vsi = vsi.VSI_Dial(self)

    def resizeEvent(self, event):
        menu_offset = 30
        instWidth = qRound(self.width()/3)
        instHeight = qRound((self.height()-menu_offset)/2)
        diameter=min(instWidth,instHeight)

        self.airspeed.move(0,menu_offset)
        self.airspeed.resize(instWidth,instHeight)

        self.ai.move(instWidth, 0 + menu_offset)
        self.ai.resize(instWidth, instHeight)

        self.altimeter.move(instWidth*2, 0 + menu_offset)
        self.altimeter.resize(instWidth,instHeight)

        self.tc.move(0, instHeight + menu_offset)
        self.tc.resize(instWidth, instHeight)

        hdh = self.heading_disp.height()
        hdw = self.heading_disp.width()
        hsi_diameter = diameter - (hdh+30)
        offset = instHeight-hsi_diameter
        self.hsi.move(qRound(instWidth+(instWidth-hsi_diameter)/2), qRound(instHeight + menu_offset + offset-20))
        self.hsi.resize(hsi_diameter,hsi_diameter)
        self.heading_disp.move(qRound(instWidth*1.5-hdw/2), qRound(instHeight + menu_offset+10))

        self.vsi.move(instWidth * 2, instHeight + menu_offset)
        self.vsi.resize(instWidth, instHeight)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
