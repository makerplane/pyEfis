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
from pyefis.instruments.ai.VirtualVfr import VirtualVfr
from pyefis.instruments import gauges
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

        self.screenColor = (0,0,0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        # attitude indicator
        self.ai = VirtualVfr(self)
        self.ai.fontSize = 20
        self.ai.pitchDegreesShown = 90

	# altimeter tape
        self.alt_tape = altimeter.Altimeter_Tape(self)
        self.alt_Trend = vsi.Alt_Trend_Tape(self)

        # airspeed tape
        self.as_tape = airspeed.Airspeed_Tape(self)
        #self.as_Trend = vsi.AS_Trend_Tape(self)

        # airspeed tape numeral display box
        self.asd_Box = airspeed.Airspeed_Box(self)
        #self.parent.change_asd_mode.connect(self.change_asd_mode)

        # HSI
        self.hsi = hsi.HSI(self, font_size=12, fg_color="#00C911")
        self.heading_disp = hsi.HeadingDisplay(self, font_size=10, fg_color="#00C911")

        # barometric pressure numeric display
        self.alt_setting = gauges.NumericDisplay(self)
        self.alt_setting.dbkey = "BARO"
        self.alt_setting.decimal_places = 2

        # turn coordinator dial on/off
        self.tc = tc.TurnCoordinator(self, dial=False)

        # manifold pressure gauge
        self.map_g = gauges.ArcGauge(self)
        self.map_g.name = "MAP"
        self.map_g.decimal_places = 1
        self.map_g.dbkey = "MAP1"

        # RPM gauge
        self.rpm = gauges.ArcGauge(self)
        self.rpm.name = "RPM"
        self.rpm.decimal_places = 0
        self.rpm.dbkey = "TACH1"

        # oil pressure gauge
        self.op = gauges.HorizontalBar(self)
        self.op.name = "Oil Press"
        self.op.decimal_places = 1
        self.op.dbkey = "OILP1"

        # oil temperature gauge
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

        # fuel quantity gauge
        self.fuel = gauges.HorizontalBar(self)
        self.fuel.name = "Fuel Qty"
        self.fuel.decimal_places = 1
        self.fuel.dbkey = "FUELQT"

        # fuel flow gauge
        self.ff = gauges.HorizontalBar(self)
        self.ff.name = "Fuel Flow"
        self.ff.decimal_places = 1
        self.ff.dbkey = "FUELF1"

        # cht gauge
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

        # egt gauge
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
        instWidth = self.width() - 200
        instHeight = self.height() - 150

        # AI position and size
        self.ai.move(0, 5)
        self.ai.resize(instWidth, instHeight)

        # altitude tape position and size
        self.alt_tape.resize(90, instHeight)
        self.alt_tape.move(instWidth -90, 5)

        # altitude trend tape position and size
        self.alt_Trend.resize(40, instHeight)
        self.alt_Trend.move(instWidth , 5)

        # airspeed tape position and size
        self.as_tape.resize(90, instHeight)
        self.as_tape.move(0, 5)

        # airspeed trend position and size
        #self.as_Trend.resize(10, instHeight)
        #self.as_Trend.move(90, 5)

        #airspeed numeric display size and position
        self.asd_Box.resize(100, 100)
        self.asd_Box.move(5, instHeight + 50)

        #HSI size and position
        hsi_diameter=instWidth/1.85
        self.hsi.resize(qRound(hsi_diameter), qRound(hsi_diameter))
        self.hsi.move(qRound((instWidth-hsi_diameter)/2), qRound(instHeight - hsi_diameter+5))

        #HSI text box
        self.heading_disp.move(qRound((instWidth-self.heading_disp.width())/2),
                    qRound(instHeight - hsi_diameter - self.heading_disp.height()+250))

        # baro pressure font size and placement
        self.alt_setting.resize(110, 20)
        self.alt_setting.move(instWidth -40, instHeight + 70)

        #turn coordinator size and position
        tc_width = instWidth * .3
        self.tc.resize (qRound(tc_width), qRound(tc_width))
        self.tc.move (qRound((instWidth-tc_width)/2), qRound(instHeight+20-tc_width/3))

        # RPM gauge position and size
        self.rpm.resize(150, 70)
        self.rpm.move(self.width() - 150, 0)

        # manifold pressure gauge position and size
        self.map_g.resize(150, 70)
        self.map_g.move(self.width() - 150, 1100)

        # oil pressure gauge position and size
        self.op.resize(100, 70)
        self.op.move(self.width() - 125, 75)

        # oil temperature gauge position and size
        self.ot.resize(100, 70)
        self.ot.move(self.width() - 125, 140)

        # fuel flow gauge position and size
        self.ff.resize(100, 70)
        self.ff.move(self.width() - 125, 1340)

        # cht gauge position and size
        self.cht.resize(100, 70)
        self.cht.move(self.width() - 125, 220)

        # egt gauge position and size
        self.egt.resize(100, 70)
        self.egt.move(self.width() - 125, 285)

        # fuel quantity gauge position and size
        self.fuel.resize(100, 70)
        self.fuel.move(self.width() - 125, 350)


    def change_asd_mode(self, event):
        self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
