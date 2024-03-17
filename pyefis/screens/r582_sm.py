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

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from pyefis.instruments import gauges
from pyefis.instruments import misc
import pyavtools.fix as fix

funcTempF = lambda x: x * (9.0/5.0) + 32.0
funcTempC = lambda x: x

ENGINE_NUMBER = "1"

CYLINDER_COUNT = 2

def gauge_list(width, height):
    il = [
        {
            "name":"RPM",
            "type":gauges.ArcGauge,
            "key":"TACH" + ENGINE_NUMBER,
            "decPlaces":0,
            "width":240,
            "height":120,
            "x":100,
            "y":40,
        },
        {
            "name":"H2O",
            "type":gauges.ArcGauge,
            "key":"H2OT1",
            "decPlaces":0,
            "width":240,
            "height":120,
            "x":460,
            "y":40,
        },
        {
            "name":"Volt",
            "type":gauges.VerticalBar,
            "key":"VOLT",
            "decPlaces":1,
            "show_units":False,
            "width":50,
            "height":150,
            "x":100,
            "y":240,
        },
        {
            "name":"Amp",
            "type":gauges.VerticalBar,
            "key":"CURRNT",
            "decPlaces":1,
            "show_units":False,
            "width":50,
            "height":150,
            "x":150,
            "y":240,
        },
        {
            "name":"EGTs",
            "type":gauges.EGTGroup,
            "engine": ENGINE_NUMBER,
            "cylinderCount": CYLINDER_COUNT,
            "decPlaces":0,
            "show_units":False,
            "width":200,
            "height":150,
            "x":300,
            "y":240,
        },
        {
            "name":"EGT",
            "type":misc.StaticText,
            "width":200,
            "height":30,
            "x":300,
            "y":210,
        },

    ]
    return il

class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()
        self.cylCount = 2

        self.screenColor = (0,0,0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        # First we setup a list of the widgets on this screen.  We intantiate
        # objects for the screen based on the dictionary returned from
        # gauge_list().  We don't send the width and height yet because we
        # don't know it at this point.  We'll do this again on a resize to get
        # the positions and sizes
        self.widget_list = []
        ilist = gauge_list(0,0)
        for item in ilist:
            if item["type"] == gauges.EGTGroup:
                keys = []
                for cyl in range(item["cylinderCount"]):
                    keys.append("EGT{}{}".format(item["engine"], cyl+1))
                i = gauges.EGTGroup(self, item["cylinderCount"], keys)
            elif item["type"] == misc.StaticText:
                i = misc.StaticText(item["name"], parent = self)
            else:
                i = item["type"](self)
            i.name = item["name"]
            if "key" in item: i.dbkey = item["key"]
            if "decPlaces" in item: i.decimal_places = item["decPlaces"]
            if "show_units" in item: i.show_units = item["show_units"]
            if "show_name" in item: i.show_name = item["show_name"]
            if "units1" in item: i.unitsOverride1 = item["units1"]
            if "units2" in item: i.unitsOverride2 = item["units2"]
            if "unitFunction1" in item: i.conversionFunction1 = item["unitFunction1"]
            if "unitFunction2" in item: i.conversionFunction2 = item["unitFunction2"]

            self.widget_list.append(i)

        # Leaving this alone for now until I can fix the CHT grouping
        self.cht = misc.StaticText("CHT", parent=self)
        self.chts = []
        for x in range(self.cylCount):
            cht = gauges.VerticalBar(self)

            cht.name = str(x+1)
            cht.decimal_places = 0
            cht.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
            cht.conversionFunction2 = lambda x: x
            #cht.unitsOverride1 = u'\N{DEGREE SIGN}F'
            #cht.unitsOverride2 = u'\N{DEGREE SIGN}C'
            cht.unitGroup = "Temperature"
            cht.setUnitSwitching()
            cht.show_units = False
            cht.dbkey = "CHT1{}".format(x+1)
            self.chts.append(cht)
            item = fix.db.get_item(cht.dbkey)
            item.valueChanged.connect(self.chtMax)

        self.chtmaxlabel = misc.StaticText("MAX", parent=self)

        self.chtmax = gauges.NumericDisplay(self)
        self.chtmax.name = "CHT Max"
        self.chtmax.decimal_places = 0
        self.chtmax.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
        self.chtmax.conversionFunction2 = lambda x: x
        self.chtmax.unitsOverride1 = u'\N{DEGREE SIGN}F'
        self.chtmax.unitsOverride2 = u'\N{DEGREE SIGN}C'
        self.chtmax.setUnitSwitching()
        self.chtmax.unitGroup = "Temperature"
        self.chtmax.dbkey = "CHTMAX1"

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

        inst_list = gauge_list(self.width(), self.height())

        for x, item in enumerate(inst_list):
            self.widget_list[x].resize(item["width"], item["height"])
            self.widget_list[x].move(item["x"], item["y"])

        chtstartx = 600
        self.cht.resize(200, 30)
        self.cht.move(550, 210)

        for x in range(len(self.chts)):
            self.chts[x].resize(50, 150)
            self.chts[x].move(chtstartx + (50*x), 240)

        self.chtmaxlabel.resize(30,12)
        self.chtmaxlabel.move(chtstartx + 10, 400)
        self.chtmax.resize(75, 30)
        self.chtmax.move(chtstartx + 45, 395)
