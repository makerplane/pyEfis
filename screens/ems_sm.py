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
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

from instruments import gauges
from instruments import misc

class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()

        self.screenColor = (0,0,0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        self.rpm = gauges.ArcGauge(self)
        self.rpm.name = "RPM"
        self.rpm.decimalPlaces = 0
        self.rpm.dbkey = "TACH1"

        self.map_g = gauges.ArcGauge(self)
        self.map_g.name = "MAP"
        self.map_g.decimalPlaces = 1
        self.map_g.dbkey = "MAP1"

        self.op = gauges.HorizontalBar(self)
        self.op.name = "Oil Press"
        self.op.decimalPlaces = 1
        self.op.dbkey = "OILP1"

        self.ot = gauges.HorizontalBar(self)
        self.ot.name = "Oil Temp"
        # Use a lambda to convert the values internally
        self.ot.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        # This causes the units sent from the server to be overridden
        self.ot.unitsOverride = u'\N{DEGREE SIGN}F'
        self.ot.decimalPlaces = 1
        self.ot.dbkey = "OILT1"

        self.fuel = misc.StaticText("Fuel", parent=self)

        self.fuell = gauges.VerticalBar(self)
        self.fuell.name = "Left"
        self.fuell.decimalPlaces = 1
        self.fuell.dbkey = "FUELQ1"
        self.fuell.showUnits = False

        self.fuelr = gauges.VerticalBar(self)
        self.fuelr.name = "Right"
        self.fuelr.decimalPlaces = 1
        self.fuelr.dbkey = "FUELQ2"
        self.fuelr.showUnits = False

        self.ff = gauges.VerticalBar(self)
        self.ff.name = "Flow"
        self.ff.decimalPlaces = 1
        self.ff.dbkey = "FUELF1"
        self.ff.showUnits = False

        self.fuelp = gauges.VerticalBar(self)
        self.fuelp.name = "Press"
        self.fuelp.decimalPlaces = 0
        self.fuelp.dbkey = "FUELP1"
        self.fuelp.showUnits = False

        self.fuelt = gauges.NumericDisplay(self)
        self.fuelt.name = "Total"
        self.fuelt.decimalPlaces = 1
        self.fuelt.dbkey = "FUELQT"


        # self.cht = gauges.HorizontalBar(self)
        # self.cht.name = "Max CHT"
        # # Use a lambda to convert the values internally
        # self.cht.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        # # This causes the units sent from the server to be overridden
        # self.cht.unitsOverride = u'\N{DEGREE SIGN}F'
        # self.cht.dbkey = "CHTMAX"
        #
        # self.egt = gauges.HorizontalBar(self)
        # self.egt.name = "Avg EGT"
        # # Use a lambda to convert the values internally
        # self.egt.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        # # This causes the units sent from the server to be overridden
        # self.egt.unitsOverride = u'\N{DEGREE SIGN}F'
        # self.egt.decimalPlaces = 0
        # self.egt.dbkey = "EGTAVG"



    def resizeEvent(self, event):
        instWidth = self.width() - 150
        instHeight = self.height() - 60

        self.rpm.resize(240, 120)
        self.rpm.move(0, 0)

        self.map_g.resize(240, 120)
        self.map_g.move(240,0)

        self.op.resize(200, 75)
        self.op.move(self.width() - 202, 0)

        self.ot.resize(200, 75)
        self.ot.move(self.width() - 202, 75)


        self.fuel.resize(200, 30)
        self.fuel.move(self.width() - 200, 170)

        self.fuell.resize(50,150)
        self.fuell.move(self.width() - 200, 200)

        self.fuelr.resize(50, 150)
        self.fuelr.move(self.width() - 150, 200)

        self.ff.resize(50, 150)
        self.ff.move(self.width() - 100, 200)

        self.fuelp.resize(50, 150)
        self.fuelp.move(self.width() - 50, 200)

        self.fuelt.resize(100, 30)
        self.fuelt.move(self.width() - 200, 355)
        self.fuelt.showUnits = False
        self.fuelt.showName = False


        # self.cht.resize(150, 50)
        # self.cht.move(self.width() - 150, 380)
        #
        # self.egt.resize(150, 50)
        # self.egt.move(self.width() - 150, 430)
