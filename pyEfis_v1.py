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


class main (QMainWindow):
    def __init__(self, test, parent = None):
        super(main,  self).__init__(parent)
        if not test:
            self.flightData = FlightData()
            self.cfix = fix.Fix(config.canAdapter, config.canDevice)
            self.cfix.setParameterCallback(self.flightData.getParameter)
        self.setupUi(self, test)
        
    def setupUi(self, MainWindow, test):
        MainWindow.setObjectName("PFD")
        MainWindow.resize(config.screenSize[0],config.screenSize[1])

    
        w = QWidget(MainWindow)
        w.setGeometry(0,0, config.screenSize[0],config.screenSize[1])

        p = w.palette()
        if config.screenColor:
            p.setColor(w.backgroundRole(), QColor(config.screenColor))
            w.setPalette(p)
            w.setAutoFillBackground(True)
        instWidth = config.screenSize[0]-410
        instHeight = config.screenSize[1]-200
        a = ai.AI(w)
        a.resize(instWidth,instHeight)
        a.move(100,100)

        alt_tape = altimeter.Altimeter_Tape(w)
        alt_tape.resize(100,instHeight)
        alt_tape.move(instWidth+100, 100)

        as_tape = airspeed.Airspeed_Tape(w)
        as_tape.resize(100,instHeight)
        as_tape.move(0, 100)

        head_tape = hsi.DG_Tape(w)
        head_tape.resize(instWidth,100)
        head_tape.move(100, instHeight+100)
    
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
        op = gauges.HorizontalBar(w)
        op.name = "Oil Press"
        op.units = "psi"
        op.decimalPlaces = 1
        op.lowRange = 0.0
        op.highRange = 100.0
        op.highWarn = 90.0
        op.highAlarm = 95.0
        op.lowWarn = 45.0
        op.lowAlarm = 10.0
        op.resize(190, 75)
        op.move(w.width()-200,220)
        op.value = 45.2
    
        ot = gauges.HorizontalBar(w)
        ot.name = "Oil Temp"
        ot.units = "degF"
        ot.decimalPlaces = 1
        ot.lowRange = 160.0
        ot.highRange = 250.0
        ot.highWarn = 210.0
        ot.highAlarm = 230.0
        ot.lowWarn = None
        ot.lowAlarm = None
        ot.resize(190, 75)
        ot.move(w.width()-200,300)
        ot.value = 215.2
    
        fuel = gauges.HorizontalBar(w)
        fuel.name = "Fuel Qty"
        fuel.units = "gal"
        fuel.decimalPlaces = 1
        fuel.lowRange = 0.0
        fuel.highRange = 20.0
        fuel.lowWarn = 2.0
        fuel.resize(190, 75)
        fuel.move(w.width()-200,380)
        fuel.value = 15.2
        
        ff = gauges.HorizontalBar(w)
        ff.name = "Fuel Flow"
        ff.units = "gph"
        ff.decimalPlaces = 1
        ff.lowRange = 0.0
        ff.highRange = 20.0
        ff.highWarn = None
        ff.highAlarm = None
        ff.lowWarn = None
        ff.lowAlarm = None
        ff.resize(190, 75)
        ff.move(w.width()-200,460)
        ff.value = 5.2
        
        cht = gauges.HorizontalBar(w)
        cht.name = "Max CHT"
        cht.units = "degF"
        cht.decimalPlaces = 0
        cht.lowRange = 0.0
        cht.highRange = 500.0
        cht.highWarn = 380
        cht.highAlarm = 400
        cht.resize(190, 75)
        cht.move(w.width()-200,540)
        cht.value = 350
        
        egt = gauges.HorizontalBar(w)
        egt.name = "Avg EGT"
        egt.units = "degF"
        egt.decimalPlaces = 0
        egt.lowRange = 800.0
        egt.highRange = 1500.0
        egt.resize(190, 75)
        egt.move(w.width()-200,620)
        egt.value = 1350
    
        if not test:
            self.flightData.pitchChanged.connect(a.setPitchAngle)
            self.flightData.rollChanged.connect(a.setRollAngle)
            self.flightData.headingChanged.connect(head_tape.setHeading)
        else:
            roll = QSlider(Qt.Horizontal,w)
            roll.setMinimum(-180)
            roll.setMaximum(180)
            roll.setValue(0)
            roll.resize(200,20)
            roll.move(440,100)
        
            pitch = QSlider(Qt.Vertical,w)
            pitch.setMinimum(-90)
            pitch.setMaximum(90)
            pitch.setValue(0)
            pitch.resize(20,200)
            pitch.move(360,180)

        
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
            heading.move(0, instHeight+100)
            heading.setRange(0, 360)
            heading.setValue(1)
            heading.valueChanged.connect(head_tape.setHeading)

            #headingBug = QSpinBox(w)
            #headingBug.move(650, 680)
            #headingBug.setRange(0, 360)
            #headingBug.setValue(1)
            #headingBug.valueChanged.connect(h.setHeadingBug)

            alt_gauge = QSpinBox(w)
            alt_gauge.setMinimum(0)
            alt_gauge.setMaximum(10000)
            alt_gauge.setValue(0)
            alt_gauge.setSingleStep(10)
            alt_gauge.move(1100,100)
            alt_gauge.valueChanged.connect(alt_tape.setAltimeter)

            as_gauge = QSpinBox(w)
            as_gauge.setMinimum(0)
            as_gauge.setMaximum(140)
            as_gauge.setValue(0)
            as_gauge.move(10,100)
            as_gauge.valueChanged.connect(as_tape.setAirspeed)
        
            pitch.valueChanged.connect(a.setPitchAngle)
            roll.valueChanged.connect(a.setRollAngle)
            smap.valueChanged.connect(map.setValue)
            srpm.valueChanged.connect(rpm.setValue)



#parser = argparse.ArgumentParser(description='pyEfis')
#parser.add_argument('--test', '-t', action='store_true', help='Run in test mode')

#args = parser.parse_args()

#main(args.test)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    parser = argparse.ArgumentParser(description='pyEfis')
    parser.add_argument('--test', '-t', action='store_true', help='Run in test mode')

    args = parser.parse_args()
    form = main(args.test)
    form.show()
    
    if not args.test:
        form.cfix.start()
    result = app.exec_()
    if not args.test:
        form.cfix.quit()
    sys.exit(result)
