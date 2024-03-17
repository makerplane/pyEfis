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
#ENGINE_NUMBER = "2"

CYLINDER_COUNT = 4
#CYLINDER_COUNT = 6


def gauge_list(width, height):
    il = [
        {
            "name":"RPM",
            "type":gauges.ArcGauge,
            "key":"TACH" + ENGINE_NUMBER,
            "decPlaces":0,
            "width":240,
            "height":120,
            "x":0,
            "y":0,
        },
        {
            "name":"MAP",
            "type":gauges.ArcGauge,
            "key":"MAP" + ENGINE_NUMBER,
            "decPlaces":1,
            "width":240,
            "height":120,
            "x":240,
            "y":0,
        },
        {
            "name":"Oil Press",
            "type":gauges.HorizontalBar,
            "key":"OILP" + ENGINE_NUMBER,
            "decPlaces":1,
            "width":200,
            "height":75,
            "x":width - 202,
            "y":0,
        },
        {
            "name":"Oil Temp",
            "type":gauges.HorizontalBar,
            "key":"OILT" + ENGINE_NUMBER,
            "decPlaces":1,
            "units1":u'\N{DEGREE SIGN}F',
            "unitFunction1":funcTempF,
            "units2":u'\N{DEGREE SIGN}C',
            "unitFunction2":funcTempC,
            "width":200,
            "height":75,
            "x":width - 202,
            "y":75,
        },
        {
            "name":"Fuel",
            "type":misc.StaticText,
            "width":200,
            "height":30,
            "x":width - 200,
            "y":170,
        },
        {
            "name":"Left",
            "type":gauges.VerticalBar,
            "key":"FUELQ1",
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":width - 200,
            "y":200,
        },
        {
            "name":"Right",
            "type":gauges.VerticalBar,
            "key":"FUELQ2",
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":width - 150,
            "y":200,
        },
        {
            "name":"Flow",
            "type":gauges.VerticalBar,
            "key":"FUELF" + ENGINE_NUMBER,
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":width - 100,
            "y":200,
        },
        {
            "name":"Press",
            "type":gauges.VerticalBar,
            "key":"FUELP" + ENGINE_NUMBER,
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":width - 50,
            "y":200,
        },
        {
            "name":"Total",
            "type":gauges.NumericDisplay,
            "key":"FUELQT",
            "decPlaces":1,
            "showUnits":True,
            "show_name":False,
            "width":90,
            "height":30,
            "x":width - 195,
            "y":355,
        },
        {
            "name":"Volt",
            "type":gauges.VerticalBar,
            "key":"VOLT",
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":0,
            "y":200,
        },
        {
            "name":"Amp",
            "type":gauges.VerticalBar,
            "key":"CURRNT",
            "decPlaces":1,
            "showUnits":False,
            "width":50,
            "height":150,
            "x":50,
            "y":200,
        },
        {
            "name":"EGTs",
            "type":gauges.EGTGroup,
            "engine": ENGINE_NUMBER,
            "cylinderCount": CYLINDER_COUNT,
            "decPlaces":0,
            "showUnits":False,
            "width":200,
            "height":150,
            "x":150,
            "y":200,
        },
        {
            "name":"EGT",
            "type":misc.StaticText,
            "width":200,
            "height":30,
            "x":150,
            "y":170,
        },

    ]
    return il

        # self.egt.resize(200, 30)
        # self.egt.move(150, 170)
        # self.egtgroup.resize(200, 150)
        # self.egtgroup.move(150, 200)

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
            if "decPlaces" in item: i.decimal_places = item["decPlaces"]
            if "showUnits" in item: i.showUnits = item["showUnits"]
            if "show_name" in item: i.show_name = item["show_name"]
            if "units1" in item: i.unitsOverride1 = item["units1"]
            if "units2" in item: i.unitsOverride2 = item["units2"]
            if "unitFunction1" in item: i.conversionFunction1 = item["unitFunction1"]
            if "unitFunction2" in item: i.conversionFunction2 = item["unitFunction2"]
            if "units1" in item: i.setUnitSwitching()
            if "key" in item: i.dbkey = item["key"]

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
            cht.showUnits = False
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
        #
        # self.egt = misc.StaticText("EGT", parent=self)
        # self.egtgroup = gauges.EGTGroup(self, self.cylCount, ["EGT11", "EGT12", "EGT13", "EGT14"])
        #
        # self.hobbslabel = misc.StaticText("Engine Time", parent=self)
        #
        # self.hobbs = gauges.NumericDisplay(self)
        # self.hobbs.name = "Hobbs"
        # self.hobbs.decimal_places = 1
        # self.hobbs.dbkey = "HOBBS1"
        # self.hobbs.alignment = Qt.AlignRight | Qt.AlignVCenter
        # self.hobbs.showUnits = True
        # self.hobbs.smallFontPercent = 0.6
        #
        # self.oatlabel = misc.StaticText("OAT", parent=self)
        # self.oatlabel.alignment = Qt.AlignLeft | Qt.AlignVCenter
        #
        # self.oat = gauges.NumericDisplay(self)
        # self.oat.name = "OAT"
        # self.oat.decimal_places = 1
        # self.oat.dbkey = "OAT"
        # self.oat.alignment = Qt.AlignLeft | Qt.AlignVCenter
        # self.oat.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
        # self.oat.conversionFunction2 = lambda x: x
        # self.oat.unitsOverride1 = u'\N{DEGREE SIGN}F'
        # self.oat.unitsOverride2 = u'\N{DEGREE SIGN}C'
        # self.oat.showUnits = True
        # self.oat.setUnitSwitching()
        # self.oat.smallFontPercent = 0.6
        #
        # self.timez = misc.ValueDisplay(self)
        # self.timez.dbkey = "TIMEZ"

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
        # instWidth = self.width() - 150
        # instHeight = self.height() - 60

        inst_list = gauge_list(self.width(), self.height())

        for x, item in enumerate(inst_list):
            self.widget_list[x].resize(item["width"], item["height"])
            self.widget_list[x].move(item["x"], item["y"])

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
        #
        #
        # self.hobbslabel.resize(100,15)
        # self.hobbslabel.move(self.width()-115, self.height()-85)
        # self.hobbs.resize(110,20)
        # self.hobbs.move(self.width()-115, self.height()-70)
        #
        # self.timez.resize(100, 20)
        # self.timez.move(self.width()-115, self.height()-40)
        #
        # self.oatlabel.resize(100,15)
        # self.oatlabel.move(10, self.height()-85)
        # self.oat.resize(80,25)
        # self.oat.move(10, self.height()-70)
