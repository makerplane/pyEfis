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

# This is a container object to hold the callback for the FIX thread
# which when called emits the signals for each parameter
class FlightData(QObject):
    rollChanged = pyqtSignal(float, name = "rollChanged")
    pitchChanged = pyqtSignal(float, name = "pitchChanged")
    headingChanged = pyqtSignal(float, name = "headingChanged")
    
    def getParameter(self, param):
        if param.name == "Roll Angle":
            self.rollChanged.emit(param.value)
        elif param.name == "Pitch Angle":
            self.pitchChanged.emit(param.value)
        elif param.name == "Heading":
            self.headingChanged.emit(param.value)


def main(test):
    if not test:
        flightData = FlightData()

        cfix = fix.Fix(config.canAdapter, config.canDevice)
        cfix.setParameterCallback(flightData.getParameter)
    
    app = QApplication(sys.argv)
    w = QWidget()
    w.resize(config.screenSize[0],config.screenSize[1])
    w.move(0,0)
    w.setWindowTitle('PFD')
    p = w.palette()
    if config.screenColor:
        p.setColor(w.backgroundRole(), QColor(config.screenColor))
        w.setPalette(p)
        w.setAutoFillBackground(True)
    instWidth = config.screenSize[1]/2
    a = ai.AI(w)
    a.resize(instWidth,instWidth)
    a.move((w.width()-200)/3*1,0)

    h = hsi.HSI(w)
    h.resize(instWidth,instWidth)
    h.move((w.width()-200)/3*1,instWidth)

    air = airspeed.Airspeed(w)
    air.resize(instWidth,instWidth)
    air.move((w.width()-200)/3*0,0)

    alt = altimeter.Altimeter(w)
    alt.resize(instWidth,instWidth)
    alt.move((w.width()-200)/3*2,0)

    vb = gauges.VerticalBar(w)
    vb.resize(10,150)
    vb.move(w.width()-180,350)
    vb.highWarn = 75
    vb.highAlarm = 85
    vb.value = 0
    
    map = gauges.RoundGauge(w)
    map.name = "MAP"
    map.decimalPlaces = 1
    map.lowRange = 0.0
    map.highRange = 30.0
    map.highWarn = 28.0
    map.highAlarm = 29.0
    map.resize(200, 100)
    map.move(w.width()-200,100)
    
    rpm = gauges.RoundGauge(w)
    rpm.name = "RPM"
    rpm.decimalPlaces = 0
    rpm.lowRange = 0.0
    rpm.highRange = 2800.0
    rpm.highWarn = 2600.0
    rpm.highAlarm = 2760.0
    rpm.resize(200, 100)
    rpm.move(w.width()-200,0)
    

    if not test:
        flightData.pitchChanged.connect(a.setPitchAngle)
        flightData.rollChanged.connect(a.setRollAngle)
        flightData.headingChanged.connect(h.setHeading)
    else:
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
        
        v = QSlider(Qt.Vertical,w)
        v.setMinimum(0)
        v.setMaximum(100)
        v.setValue(0)
        v.valueChanged.connect(vb.setValue)
        v.resize(20,150)
        v.move(w.width()-200,350)
        
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
        heading.valueChanged.connect(h.setHeading)

        headingBug = QSpinBox(w)
        headingBug.move(650, 680)
        headingBug.setRange(0, 360)
        headingBug.setValue(1)
        headingBug.valueChanged.connect(h.setHeadingBug)

        alt_gauge = QSpinBox(w)
        alt_gauge.setMinimum(0)
        alt_gauge.setMaximum(10000)
        alt_gauge.setValue(0)
        alt_gauge.move(720,10)
        alt_gauge.valueChanged.connect(alt.setAltimeter)

        as_gauge = QSpinBox(w)
        as_gauge.setMinimum(0)
        as_gauge.setMaximum(140)
        as_gauge.setValue(0)
        as_gauge.move(10,360)
        as_gauge.valueChanged.connect(air.setAirspeed)

        pitch.valueChanged.connect(a.setPitchAngle)
        roll.valueChanged.connect(a.setRollAngle)
        smap.valueChanged.connect(map.setValue)
        srpm.valueChanged.connect(rpm.setValue)

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
