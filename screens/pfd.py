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
from instruments.ai.VirtualVfr import VirtualVfr
from instruments import gauges
from instruments import hsi
from instruments import airspeed
from instruments import altimeter
from instruments import vsi

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

        self.ai = VirtualVfr(self)
        self.ai.fontSize = 20
        self.ai.pitchDegreesShown = 90

        self.alt_tape = altimeter.Altimeter_Tape(self)
        self.alt_Trend = vsi.Alt_Trend_Tape(self)
        self.as_tape = airspeed.Airspeed_Tape(self)
        #self.as_Trend = vsi.AS_Trend_Tape(self)
        self.asd_Box = airspeed.Airspeed_Mode(self)
        self.parent.change_asd_mode.connect(self.change_asd_mode)
        self.head_tape = hsi.DG_Tape(self)
        self.alt_setting = altimeter.Altimeter_Setting(self)

        self.map_g = gauges.ArcGauge(self)
        self.map_g.name = "MAP"
        self.map_g.decimalPlaces = 1
        self.map_g.dbkey = "MAP1"

        self.rpm = gauges.ArcGauge(self)
        self.rpm.name = "RPM"
        self.rpm.decimalPlaces = 0
        self.rpm.dbkey = "TACH1"

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


        self.fuel = gauges.HorizontalBar(self)
        self.fuel.name = "Fuel Qty"
        self.fuel.decimalPlaces = 1
        self.fuel.dbkey = "FUELQ1"

        self.ff = gauges.HorizontalBar(self)
        self.ff.name = "Fuel Flow"
        self.ff.decimalPlaces = 1
        self.ff.dbkey = "FUELF1"

        self.cht = gauges.HorizontalBar(self)
        self.cht.name = "Max CHT"
        # Use a lambda to convert the values internally
        self.cht.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        # This causes the units sent from the server to be overridden
        self.cht.unitsOverride = u'\N{DEGREE SIGN}F'
        self.cht.dbkey = "CHTMAX"

        self.egt = gauges.HorizontalBar(self)
        self.egt.name = "Avg EGT"
        # Use a lambda to convert the values internally
        self.egt.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        # This causes the units sent from the server to be overridden
        self.egt.unitsOverride = u'\N{DEGREE SIGN}F'
        self.egt.decimalPlaces = 0
        self.egt.dbkey = "EGTAVG"



    def resizeEvent(self, event):
        instWidth = self.width() - 210
        instHeight = self.height() - 200
        self.ai.move(0, 100)
        self.ai.resize(instWidth, instHeight)

        self.alt_tape.resize(90, instHeight)
        self.alt_tape.move(instWidth -90, 100)

        self.alt_Trend.resize(10, instHeight)
        self.alt_Trend.move(instWidth , 100)

        self.as_tape.resize(90, instHeight)
        self.as_tape.move(0, 100)

        #self.as_Trend.resize(10, instHeight)
        #self.as_Trend.move(90, 100)

        self.asd_Box.resize(90, 100)
        self.asd_Box.move(0, instHeight + 100)

        self.head_tape.resize(instWidth-200, 100)
        self.head_tape.move(100, instHeight + 100)

        self.alt_setting.resize(90, 100)
        self.alt_setting.move(instWidth -100, instHeight + 100)

        self.map_g.resize(200, 100)
        self.map_g.move(self.width() - 200, 100)

        self.rpm.resize(200, 100)
        self.rpm.move(self.width() - 200, 0)

        self.op.resize(190, 75)
        self.op.move(self.width() - 200, 220)

        self.ot.resize(190, 75)
        self.ot.move(self.width() - 200, 300)

        self.fuel.resize(190, 75)
        self.fuel.move(self.width() - 200, 380)

        self.ff.resize(190, 75)
        self.ff.move(self.width() - 200, 460)

        self.cht.resize(190, 75)
        self.cht.move(self.width() - 200, 540)

        self.egt.resize(190, 75)
        self.egt.move(self.width() - 200, 620)

    def change_asd_mode(self, event):
        self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
