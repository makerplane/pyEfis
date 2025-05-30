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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

from pyefis.instruments import ai
from pyefis.instruments import gauges
from pyefis.instruments import hsi
from pyefis.instruments import airspeed
from pyefis.instruments import altimeter
from pyefis.instruments import vsi

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

        self.ai = ai.AI(self)
        self.ai.fontSize = 19
        self.ai.bankMarkSize = 10
        self.ai.pitchDegreesShown = 60
        self.ai.bankAngleRadius = 150

        self.alt_tape = altimeter.Altimeter_Tape(self)
        #self.alt_Trend = vsi.Alt_Trend_Tape(self)
        self.as_tape = airspeed.Airspeed_Tape(self)
        #self.as_Trend = vsi.AS_Trend_Tape(self)
        #self.asd_Box = airspeed.Airspeed_Mode(self)
        self.head_tape = hsi.DG_Tape(self)
        #self.alt_setting = altimeter.Altimeter_Setting(self)

        self.map_g = gauges.ArcGauge(self)
        self.map_g.name = "MAP"
        self.map_g.decimal_places = 1
        self.map_g.dbkey = "MAP1"

        self.rpm = gauges.ArcGauge(self)
        self.rpm.name = "RPM"
        self.rpm.decimal_places = 0
        self.rpm.dbkey = "TACH1"

        self.op = gauges.HorizontalBar(self)
        self.op.name = "Oil Press"
        self.op.decimal_places = 1
        self.op.dbkey = "OILP1"


        self.ot = gauges.HorizontalBar(self)
        self.ot.name = "Oil Temp"
        # Use a lambda to convert the values internally
        self.ot.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
        self.ot.conversionFunction2 = lambda x: x
        # This causes the units sent from the server to be overridden
        self.ot.unitsOverride1 = u'\N{DEGREE SIGN}F'
        self.ot.unitsOverride2 = u'\N{DEGREE SIGN}C'
        self.ot.setUnitSwitching()
        self.ot.dbkey = "OILT1"


        self.fuel = gauges.HorizontalBar(self)
        self.fuel.name = "Fuel Qty"
        self.fuel.decimal_places = 1
        self.fuel.dbkey = "FUELQT"

        self.ff = gauges.HorizontalBar(self)
        self.ff.name = "Fuel Flow"
        self.ff.decimal_places = 1
        self.ff.dbkey = "FUELF1"

        self.cht = gauges.HorizontalBar(self)
        self.cht.name = "Max CHT"
        # Use a lambda to convert the values internally
        self.cht.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
        self.cht.conversionFunction2 = lambda x: x
        # This causes the units sent from the server to be overridden
        self.cht.unitsOverride1 = u'\N{DEGREE SIGN}F'
        self.cht.unitsOverride2 = u'\N{DEGREE SIGN}C'
        self.cht.unitGroup = "Temperature"
        self.cht.setUnitSwitching()
        self.cht.dbkey = "CHTMAX1"

        self.egt = gauges.HorizontalBar(self)
        self.egt.name = "Avg EGT"
        # Use a lambda to convert the values internally
        self.egt.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
        self.egt.conversionFunction2 = lambda x: x
        # This causes the units sent from the server to be overridden
        self.egt.unitsOverride1 = u'\N{DEGREE SIGN}F'
        self.egt.unitsOverride2 = u'\N{DEGREE SIGN}C'
        self.egt.unitGroup = "Temperature"
        self.egt.setUnitSwitching()
        self.egt.decimal_places = 0
        self.egt.dbkey = "EGTAVG1"



    def resizeEvent(self, event):
        instWidth = self.width() - 150
        instHeight = self.height() - 60
        self.ai.move(0, 0)
        self.ai.resize(instWidth, instHeight)

        self.alt_tape.fontsize = 15
        self.alt_tape.resize(60, instHeight)
        self.alt_tape.move(instWidth - 60, 0)

        self.as_tape.fontsize = 15
        self.as_tape.resize(60, instHeight)
        self.as_tape.move(0, 0)

        self.head_tape.fontsize = 15
        self.head_tape.resize(instWidth, 60)
        self.head_tape.move(0, self.height() - 60)

        #self.alt_setting.resize(90, 100)
        #self.alt_setting.move(instWidth -100, instHeight + 100)

        self.rpm.resize(150, 75)
        self.rpm.move(self.width() - 150, 0)

        self.map_g.resize(150, 75)
        self.map_g.move(self.width() - 150, 75)


        self.op.resize(150, 50)
        self.op.move(self.width() - 150, 180)

        self.ot.resize(150, 50)
        self.ot.move(self.width() - 150, 230)

        self.fuel.resize(150, 50)
        self.fuel.move(self.width() - 150, 280)

        self.ff.resize(150, 50)
        self.ff.move(self.width() - 150, 330)

        self.cht.resize(150, 50)
        self.cht.move(self.width() - 150, 380)

        self.egt.resize(150, 50)
        self.egt.move(self.width() - 150, 430)

    def change_asd_mode(self, event):
        self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
