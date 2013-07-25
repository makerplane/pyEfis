#!/usr/bin/env python

#  Copyright (c) 2013 Phil Birkelbach
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

import sys
import argparse
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.Qt

import config
import fix
import gauges
import ai
import hsi
import airspeed
import altimeter
import vsi
import tc

# This is a container object to hold the callback for the FIX thread
# which when called emits the signals for each parameter
class FlightData(QObject):
    rollChanged = pyqtSignal(float, name = "rollChanged")
    pitchChanged = pyqtSignal(float, name = "pitchChanged")
    headingChanged = pyqtSignal(float, name = "headingChanged")
    turnRateChanged = pyqtSignal(float, name = "turnRateChanged")
    rpmChanged = pyqtSignal(float, name = "rpmChanged")
    mapChanged = pyqtSignal(float, name = "mapChanged")
    oilPressChanged = pyqtSignal(float, name = "oilPressChanged")
    oilTempChanged = pyqtSignal(float, name = "oilTempChanged")
    fuelFlowChanged = pyqtSignal(float, name = "fuelFlowChanged")
    fuelQtyChanged = pyqtSignal(float, name = "fuelQtyChanged")
    
    def getParameter(self, param):
        if param.name == "Roll Angle":
            self.rollChanged.emit(param.value)
        elif param.name == "Pitch Angle":
            self.pitchChanged.emit(param.value)
        elif param.name == "Heading":
            self.headingChanged.emit(param.value)
        elif param.name == "Turn Rate":
            self.turnRateChanged.emit(param.value)
        elif param.name == "N1 or Engine RPM #1":
            self.rpmChanged.emit(param.value)
        elif param.name == "Manifold Pressure #1":
            self.mapChanged.emit(param.value)
        elif param.name == "Oil Pressure #1":
            self.oilPressChanged.emit(param.value)
        elif param.name == "Oil Temperature #1":
            self.oilTempChanged.emit(param.value)
        elif param.name == "Fuel Flow #1":
            self.fuelFlowChanged.emit(param.value)
        elif param.name == "Fuel Quantity #1":
            self.fuelQtyChanged.emit(param.value)
        else:
            print param.name, "=", param.value

class MainWindow(QWidget):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.a = ai.AI(self)
        self.h = hsi.HSI(self)
        self.air = airspeed.Airspeed(self)
        self.alt = altimeter.Altimeter(self)
        self.vs = vsi.VSI(self)
        self.turn = tc.TurnCoordinator(self)
        self.map = gauges.RoundGauge(self)
        self.rpm = gauges.RoundGauge(self)
        self.op = gauges.HorizontalBar(self)
        self.ot = gauges.HorizontalBar(self)
        self.fuel = gauges.HorizontalBar(self)
        self.ff = gauges.HorizontalBar(self)
        self.cht = gauges.HorizontalBar(self)
        self.egt = gauges.HorizontalBar(self)
        
    def resizeEvent(self, e):
        instWidth = self.height()/2
        print self.width(), self.height()
        
        self.a.resize(instWidth,instWidth)
        self.a.move((self.width()-200)/3*1,0)
        
        self.h.resize(instWidth,instWidth)
        self.h.move((self.width()-200)/3,instWidth)
        
        self.air.resize(instWidth,instWidth)
        self.air.move((self.width()-200)/3*0,0)
        
        self.alt.resize(instWidth,instWidth)
        self.alt.move((self.width()-200)/3*2,0)
        
        self.vs.resize(instWidth, instWidth)
        self.vs.move((self.width()-200)/3*2, instWidth)
        
        self.turn.resize(instWidth, instWidth)
        self.turn.move(0, instWidth)
        self.turn.latAcc = 0.0
        
        self.map.name = "MAP"
        self.map.decimalPlaces = 1
        self.map.lowRange = 0.0
        self.map.highRange = 30.0
        self.map.highWarn = 28.0
        self.map.highAlarm = 29.0
        self.map.resize(200, 100)
        self.map.move(self.width()-200,100)
        
        self.rpm.name = "RPM"
        self.rpm.decimalPlaces = 0
        self.rpm.lowRange = 0.0
        self.rpm.highRange = 2800.0
        self.rpm.highWarn = 2600.0
        self.rpm.highAlarm = 2760.0
        self.rpm.resize(200, 100)
        self.rpm.move(self.width()-200,0)
        
        self.op.name = "Oil Press"
        self.op.units = "psi"
        self.op.decimalPlaces = 1
        self.op.lowRange = 0.0
        self.op.highRange = 100.0
        self.op.highWarn = 90.0
        self.op.highAlarm = 95.0
        self.op.lowWarn = 45.0
        self.op.lowAlarm = 10.0
        self.op.resize(190, 75)
        self.op.move(self.width()-200,220)
        self.op.value = 45.2
        
        self.ot.name = "Oil Temp"
        self.ot.units = "degF"
        self.ot.decimalPlaces = 1
        self.ot.lowRange = 160.0
        self.ot.highRange = 250.0
        self.ot.highWarn = 210.0
        self.ot.highAlarm = 230.0
        self.ot.lowWarn = None
        self.ot.lowAlarm = None
        self.ot.resize(190, 75)
        self.ot.move(self.width()-200,300)
        self.ot.value = 215.2
        
        self.fuel.name = "Fuel Qty"
        self.fuel.units = "gal"
        self.fuel.decimalPlaces = 1
        self.fuel.lowRange = 0.0
        self.fuel.highRange = 20.0
        self.fuel.lowWarn = 2.0
        self.fuel.resize(190, 75)
        self.fuel.move(self.width()-200,380)
        self.fuel.value = 15.2
        
        self.ff.name = "Fuel Flow"
        self.ff.units = "gph"
        self.ff.decimalPlaces = 1
        self.ff.lowRange = 0.0
        self.ff.highRange = 20.0
        self.ff.highWarn = None
        self.ff.highAlarm = None
        self.ff.lowWarn = None
        self.ff.lowAlarm = None
        self.ff.resize(190, 75)
        self.ff.move(self.width()-200,460)
        self.ff.value = 5.2
        
        self.cht.name = "Max CHT"
        self.cht.units = "degF"
        self.cht.decimalPlaces = 0
        self.cht.lowRange = 0.0
        self.cht.highRange = 500.0
        self.cht.highWarn = 380
        self.cht.highAlarm = 400
        self.cht.resize(190, 75)
        self.cht.move(self.width()-200,540)
        self.cht.value = 350
        
        self.egt.name = "Avg EGT"
        self.egt.units = "degF"
        self.egt.decimalPlaces = 0
        self.egt.lowRange = 800.0
        self.egt.highRange = 1500.0
        self.egt.resize(190, 75)
        self.egt.move(self.width()-200,620)
        self.egt.value = 1350
        
    def nextScreen(b):
        print "Button Pushed"

def main(test):
    if not test:
        flightData = FlightData()
        cfix = fix.Fix(config.canAdapter, config.canDevice)
        cfix.setParameterCallback(flightData.getParameter)
    
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(config.screenSize[0],config.screenSize[1])
    w.move(0,0)
    w.setWindowTitle('PFD')
    p = w.palette()
    if config.screenColor:
        p.setColor(w.backgroundRole(), QColor(config.screenColor))
        w.setPalette(p)
        w.setAutoFillBackground(True)
    
    if not test:
        flightData.pitchChanged.connect(w.a.setPitchAngle)
        flightData.rollChanged.connect(w.a.setRollAngle)
        flightData.headingChanged.connect(w.h.setHeading)
        flightData.turnRateChanged.connect(w.turn.setTurnRate)
        flightData.rpmChanged.connect(w.rpm.setValue)
        flightData.mapChanged.connect(w.map.setValue)
        flightData.oilPressChanged.connect(w.op.setValue)
        flightData.oilTempChanged.connect(w.ot.setValue)
        flightData.fuelFlowChanged.connect(w.ff.setValue)
        flightData.fuelQtyChanged.connect(w.fuel.setValue)

    else:
        toggle = QPushButton(w)
        toggle.setText("Screen")
        toggle.move(0,0)
        toggle.clicked.connect(w.nextScreen)
        
        roll = QSlider(Qt.Horizontal,w)
        roll.setMinimum(-180)
        roll.setMaximum(180)
        roll.setValue(0)
        roll.resize(200,20)
        roll.move(440,0)
        
        pitch = QSlider(Qt.Vertical,w)
        pitch.setMinimum(-90)
        pitch.setMaximum(90)
        pitch.setValue(0)
        pitch.resize(20,200)
        pitch.move(360,80)
        
        smap = QSlider(Qt.Horizontal,w)
        smap.setMinimum(0)
        smap.setMaximum(30)
        smap.setValue(0)
        smap.resize(200,20)
        smap.move(w.width()-200,200)
        
        srpm = QSlider(Qt.Horizontal,w)
        srpm.setMinimum(0)
        srpm.setMaximum(3000)
        srpm.setValue(0)
        srpm.resize(200,20)
        srpm.move(w.width()-200,100)
        
        heading = QSpinBox(w)
        heading.move(370, 680)
        heading.setRange(1, 360)
        heading.setValue(1)
        heading.valueChanged.connect(w.h.setHeading)

        headingBug = QSpinBox(w)
        headingBug.move(650, 680)
        headingBug.setRange(0, 360)
        headingBug.setValue(1)
        headingBug.valueChanged.connect(w.h.setHeadingBug)

        alt_gauge = QSpinBox(w)
        alt_gauge.setMinimum(0)
        alt_gauge.setMaximum(10000)
        alt_gauge.setSingleStep(10)
        alt_gauge.setValue(0)
        alt_gauge.move(720,10)
        alt_gauge.valueChanged.connect(w.alt.setAltimeter)

        as_gauge = QSpinBox(w)
        as_gauge.setMinimum(0)
        as_gauge.setMaximum(140)
        as_gauge.setValue(0)
        as_gauge.move(10,360)
        as_gauge.valueChanged.connect(w.air.setAirspeed)
        
        svsi = QSlider(Qt.Vertical, w)
        svsi.setMinimum(-4000)
        svsi.setMaximum(4000)
        svsi.setValue(0)
        svsi.resize(20,200)
        svsi.move(740,360)
        
        stc = QSlider(Qt.Horizontal, w)
        stc.setMinimum(-6) # deg / sec
        stc.setMaximum(6)
        stc.setValue(0)
        stc.resize(200,20)
        stc.move(80,360 + 30)

        pitch.valueChanged.connect(w.a.setPitchAngle)
        roll.valueChanged.connect(w.a.setRollAngle)
        smap.valueChanged.connect(w.map.setValue)
        srpm.valueChanged.connect(w.rpm.setValue)
        svsi.valueChanged.connect(w.vs.setROC)
        stc.valueChanged.connect(w.turn.setTurnRate)

    if(config.screenFullSize):
        w.showFullScreen()
    w.show()
    if not test:
        cfix.start()
    result = app.exec_()
    if not test:
        cfix.quit()
    sys.exit(result)

parser = argparse.ArgumentParser(description='pyEfis')
parser.add_argument('--test', '-t', action='store_true', help='Run in test mode')

args = parser.parse_args()

main(args.test)
