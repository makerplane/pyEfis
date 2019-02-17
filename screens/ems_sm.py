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
import fix

class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()
        self.cylCount = 4

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
        self.fuell.showUnits = False
        self.fuell.dbkey = "FUELQ1"

        self.fuelr = gauges.VerticalBar(self)
        self.fuelr.name = "Right"
        self.fuelr.decimalPlaces = 1
        self.fuelr.showUnits = False
        self.fuelr.dbkey = "FUELQ2"

        self.ff = gauges.VerticalBar(self)
        self.ff.name = "Flow"
        self.ff.decimalPlaces = 1
        self.ff.showUnits = False
        self.ff.dbkey = "FUELF1"

        self.fuelp = gauges.VerticalBar(self)
        self.fuelp.name = "Press"
        self.fuelp.decimalPlaces = 0
        self.fuelp.showUnits = False
        self.fuelp.dbkey = "FUELP1"

        self.fuelt = gauges.NumericDisplay(self)
        self.fuelt.name = "Total"
        self.fuelt.decimalPlaces = 1
        self.fuelt.dbkey = "FUELQT"

        self.cht = misc.StaticText("CHT", parent=self)
        self.chts = []
        for x in range(self.cylCount):
            cht = gauges.VerticalBar(self)

            cht.name = str(x+1)
            cht.decimalPlaces = 0
            cht.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
            cht.showUnits = False
            cht.dbkey = "CHT1{}".format(x+1)
            self.chts.append(cht)
            item = fix.db.get_item(cht.dbkey)
            item.valueChanged.connect(self.chtMax)

        self.chtmaxlabel = misc.StaticText("MAX", parent=self)

        self.chtmax = gauges.NumericDisplay(self)
        self.chtmax.name = "CHT Max"
        self.chtmax.decimalPlaces = 0
        self.chtmax.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        self.chtmax.unitsOverride = u'\N{DEGREE SIGN}F'
        self.chtmax.dbkey = "CHTMAX1"

        self.egt = misc.StaticText("EGT", parent=self)
        self.egtgroup = gauges.EGTGroup(self, self.cylCount, ["EGT11", "EGT12", "EGT13", "EGT14"])

        self.hobbslabel = misc.StaticText("Engine Time", parent=self)

        self.hobbs = gauges.NumericDisplay(self)
        self.hobbs.name = "Hobbs"
        self.hobbs.decimalPlaces = 1
        self.hobbs.dbkey = "HOBBS1"
        self.hobbs.alignment = Qt.AlignRight | Qt.AlignVCenter
        self.hobbs.showUnits = True
        self.hobbs.smallFontPercent = 0.6

    # Find the hightest CHT and highlight it
    # TODO: This could probably be optimized a little better
    def chtMax(self):
        max = self.chts[0].value
        sel = 0
        for x in range(self.cylCount - 1):
            if self.chts[x+1].value > max:
                sel = x+1
                max = self.chts[x+1].value
        for each in self.chts:
            each.highlight = False
        self.chts[sel].highlight = True
        for each in self.chts:
            each.update()


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

        self.fuelt.resize(90, 30)
        self.fuelt.move(self.width() - 195, 355)
        self.fuelt.showUnits = False
        self.fuelt.showName = False

        chtstartx = 380
        self.cht.resize(200, 30)
        self.cht.move(chtstartx, 170)

        for x in range(len(self.chts)):
            self.chts[x].resize(50, 150)
            self.chts[x].move(chtstartx + (50*x), 200)

        self.chtmaxlabel.resize(30,12)
        self.chtmaxlabel.move(chtstartx + 10, 360)
        self.chtmax.resize(75, 30)
        self.chtmax.move(chtstartx + 45, 355)

        self.egt.resize(200, 30)
        self.egt.move(130, 170)
        self.egtgroup.resize(200, 150)
        self.egtgroup.move(130, 200)

        self.hobbslabel.resize(100,15)
        self.hobbslabel.move(self.width()-115, self.height()-85)
        self.hobbs.resize(110,20)
        self.hobbs.move(self.width()-115, self.height()-70)
