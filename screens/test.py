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


class Screen(QWidget):
    def __init__(self, parent=None):
        super(main, self).__init__(parent)
        
        w = QWidget(MainWindow)
        w.setGeometry(0, 0, self.width, self.height)

        p = w.palette()
        if self.screenColor:
            p.setColor(w.backgroundRole(), QColor(self.screenColor))
            w.setPalette(p)
            w.setAutoFillBackground(True)
        instWidth = self.width - 210
        instHeight = self.height - 200
        self.a = ai.AI(w)
        self.a.resize(instWidth, instHeight)
        self.a.move(0, 100)

        self.alt_tape = altimeter.Altimeter_Tape(w)
        self.alt_tape.resize(90, instHeight)
        self.alt_tape.move(instWidth -90, 100)

        #self.alt_Trend = vsi.Alt_Trend_Tape(w)
        #self.alt_Trend.resize(10, instHeight)
        #self.alt_Trend.move(instWidth , 100)

        self.as_tape = airspeed.Airspeed_Tape(w)
        self.as_tape.resize(90, instHeight)
        self.as_tape.move(0, 100)

        #self.as_Trend = vsi.AS_Trend_Tape(w)
        #self.as_Trend.resize(10, instHeight)
        #self.as_Trend.move(90, 100)

        self.asd_Box = airspeed.Airspeed_Mode(w)
        self.asd_Box.resize(90, 100)
        self.asd_Box.move(0, instHeight + 100)

        self.head_tape = hsi.DG_Tape(w)
        self.head_tape.resize(instWidth-200, 100)
        self.head_tape.move(100, instHeight + 100)

        self.alt_setting = altimeter.Altimeter_Setting(w)
        self.alt_setting.resize(90, 100)
        self.alt_setting.move(instWidth -100, instHeight + 100)


        self.map_g = gauges.RoundGauge(w)
        self.map_g.name = "MAP"
        self.map_g.decimalPlaces = 1
        self.map_g.lowRange = 0.0
        self.map_g.highRange = 30.0
        self.map_g.highWarn = 28.0
        self.map_g.highAlarm = 29.0
        self.map_g.resize(200, 100)
        self.map_g.move(w.width() - 200, 100)

        self.rpm = gauges.RoundGauge(w)
        self.rpm.name = "RPM"
        self.rpm.decimalPlaces = 0
        self.rpm.lowRange = 0.0
        self.rpm.highRange = 2800.0
        self.rpm.highWarn = 2600.0
        self.rpm.highAlarm = 2760.0
        self.rpm.resize(200, 100)
        self.rpm.move(w.width() - 200, 0)

        self.op = gauges.HorizontalBar(w)
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
        self.op.move(w.width() - 200, 220)
        self.op.value = 45.2

        self.ot = gauges.HorizontalBar(w)
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
        self.ot.move(w.width() - 200, 300)
        self.ot.value = 215.2

        self.fuel = gauges.HorizontalBar(w)
        self.fuel.name = "Fuel Qty"
        self.fuel.units = "gal"
        self.fuel.decimalPlaces = 1
        self.fuel.lowRange = 0.0
        self.fuel.highRange = 50.0
        self.fuel.lowWarn = 2.0
        self.fuel.resize(190, 75)
        self.fuel.move(w.width() - 200, 380)
        self.fuel.value = 15.2

        self.ff = gauges.HorizontalBar(w)
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
        self.ff.move(w.width() - 200, 460)
        self.ff.value = 5.2

        cht = gauges.HorizontalBar(w)
        cht.name = "Max CHT"
        cht.units = "degF"
        cht.decimalPlaces = 0
        cht.lowRange = 0.0
        cht.highRange = 500.0
        cht.highWarn = 380
        cht.highAlarm = 400
        cht.resize(190, 75)
        cht.move(w.width() - 200, 540)
        cht.value = 350

        self.egt = gauges.HorizontalBar(w)
        self.egt.name = "Avg EGT"
        self.egt.units = "degF"
        self.egt.decimalPlaces = 0
        self.egt.lowRange = 0.0
        self.egt.highRange = 1500.0
        self.egt.resize(190, 75)
        self.egt.move(w.width() - 200, 620)
        self.egt.value = 1350

        if test == 'normal':
            self.flightData.pitchChanged.connect(self.a.setPitchAngle)
            self.flightData.rollChanged.connect(self.a.setRollAngle)
            self.flightData.headingChanged.connect(self.head_tape.setHeading)
            self.flightData.altitudeChanged.connect(self.alt_tape.setAltimeter)
            self.flightData.altitudeChanged.connect(self.alt_Trend.setAlt_Trend)
            #self.flightData.vsiChanged.connect(self.alt_Trend.setAlt_Trend)
            self.flightData.airspeedChanged.connect(self.as_tape.setAirspeed)
            self.flightData.airspeedChanged.connect(self.as_Trend.setAS_Trend)
            self.flightData.airspeedChanged.connect(self.asd_Box.setIAS)
            self.flightData.RPMChanged.connect(self.rpm.setValue)
            self.flightData.MAPChanged.connect(self.map_g.setValue)
            self.flightData.OilPressChanged.connect(self.op.setValue)
            self.flightData.OilTempChanged.connect(self.ot.setValue)
            self.flightData.FuelFlowChanged.connect(self.ff.setValue)
            self.flightData.FuelQtyChanged.connect(self.fuel.setValue)

        elif test == 'test':
            roll = QSlider(Qt.Horizontal, w)
            roll.setMinimum(-180)
            roll.setMaximum(180)
            roll.setValue(0)
            roll.resize(200, 20)
            roll.move(440, 100)

            pitch = QSlider(Qt.Vertical, w)
            pitch.setMinimum(-90)
            pitch.setMaximum(90)
            pitch.setValue(0)
            pitch.resize(20, 200)
            pitch.move(360, 180)

            smap = QSlider(Qt.Horizontal, w)
            smap.setMinimum(0)
            smap.setMaximum(30)
            smap.setValue(0)
            smap.resize(200, 20)
            smap.move(w.width() - 200, 200)

            srpm = QSlider(Qt.Horizontal, w)
            srpm.setMinimum(0)
            srpm.setMaximum(3000)
            srpm.setValue(0)
            srpm.resize(200, 20)
            srpm.move(w.width() - 200, 100)

            heading = QSpinBox(w)
            heading.move(0, instHeight + 100)
            heading.setRange(0, 360)
            heading.setValue(1)
            heading.hide
            heading.valueChanged.connect(self.head_tape.setHeading)

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
            alt_gauge.move(instWidth - 100, 100)
            alt_gauge.valueChanged.connect(self.alt_tape.setAltimeter)

            as_gauge = QSpinBox(w)
            as_gauge.setMinimum(0)
            as_gauge.setMaximum(140)
            as_gauge.setValue(0)
            as_gauge.move(10, 100)
            as_gauge.valueChanged.connect(self.as_tape.setAirspeed)

            pitch.valueChanged.connect(self.a.setPitchAngle)
            roll.valueChanged.connect(self.a.setRollAngle)
            smap.valueChanged.connect(self.map_g.setValue)
            srpm.valueChanged.connect(self.rpm.setValue)

        def MSL_Altitude(self, pressure_alt):
        MSL_atl = pressure_alt - std_atm.press2alt(
                                    self.alt_setting.getAltimeter_Setting())
        return MSL_atl

        def guiUpdate(self):
        """
        Pull messages from the Queue and updates the Respected gauges.
        """
        try:
            msg = self.queue.get(0)
            msg = msg.split(',')

            try:
                self.as_tape.setAirspeed(float(msg[0]))
                if self.asd_Box.getMode() == 2:
                    self.asd_Box.setAS_Data(float(msg[15]), float(msg[4]),
                                             float(msg[18]))
                else:
                    self.asd_Box.setAS_Data(float(msg[0]), float(msg[4]),
                                            float(msg[18]))
                self.a.setPitchAngle(float(msg[1]))
                self.a.setRollAngle(float(msg[2]))
                self.head_tape.setHeading(float(msg[3]))
                self.alt_tape.setAltimeter(self.MSL_Altitude(float(msg[4])))
                self.as_Trend.setAS_Trend(float(msg[0]))
                self.alt_Trend.setAlt_Trend(float(msg[4]))
                self.op.setValue(float(msg[10]))
                self.ot.setValue(float(msg[9]))
                self.egt.setValue(float(msg[11]))
                self.ff.setValue(float(msg[12]))
                self.rpm.setValue(int(float(msg[7])))
                self.map_g.setValue(float(msg[8]))
                self.fuel.setValue(float(msg[13]) + float(msg[14]))
                print('Lat: ', msg[16], 'Long: ', msg[17])
            except:
                pass