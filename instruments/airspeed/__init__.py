#  Copyright (c) 2013 Neil Domalik
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
sys.path.insert(0, './lib/AeroCalc-0.11/')
from aerocalc import airspeed

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import fix

class Airspeed(QWidget):
    def __init__(self, parent=None):
        super(Airspeed, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontsize = 20
        self._airspeed = 0
        fix.db.get_item("IAS", True).valueChanged[float].connect(self.setAirspeed)


    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        f = QFont()
        f.setPixelSize(self.fontsize)
        fontMetrics = QFontMetricsF(f)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        needleBrush = QBrush(QColor(Qt.white))

        vnePen = QPen(QColor(Qt.red))
        vnePen.setWidth(6)

        vsoPen = QPen(QColor(Qt.white))
        vsoPen.setWidth(4)

        vnoPen = QPen(QColor(Qt.green))
        vnoPen.setWidth(4)

        yellowPen = QPen(QColor(Qt.yellow))
        yellowPen.setWidth(4)

        # Dial Setup
        # V Speeds
        Vs = 45
        Vs0 = 40
        Vno = 125
        Vne = 140
        #Va = 120
        Vfe = 70

        # VSpeed to angle for drawArc
        Vs0_angle = (-(((Vs0 - 30) * 2.5) + 26) + 90) * 16
        Vs_angle = (-(((Vs - 30) * 2.5) + 26) + 90) * 16
        Vfe_angle = (-(((Vfe - 30) * 2.5) + 25) + 90) * 16
        Vno_angle = (-(((Vno - 30) * 2.5) + 25) + 90) * 16
        Vne_angle = (-(((Vne - 30) * 2.5) + 25) + 90) * 16

        # Vspeeds Arcs
        dial.setPen(vnoPen)
        dial.drawArc(QRectF(25, 25, w - 50, h - 50), Vs_angle,
                  -(Vs_angle - Vno_angle))
        dial.setPen(vsoPen)
        dial.drawArc(QRectF(28, 28, w - 56, h - 56), Vs0_angle,
                  -(Vs0_angle - Vfe_angle))
        dial.setPen(yellowPen)
        dial.drawArc(QRectF(25, 25, w - 50, h - 50), Vno_angle,
                  -(Vno_angle - Vne_angle))
        dial.save()
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.translate(w / 2, h / 2)
        count = 0
        a_s = 0
        while count < 360:
            if count % 25 == 0 and a_s <= 140:
                dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 40))
                x = fontMetrics.width(str(a_s)) / 2
                y = f.pixelSize()
                dial.drawText(-x, -(h / 2 - 40 - y),
                           str(a_s))
                a_s += 10
                if count == 0:
                    a_s = 30
                    count = count + 19
                    dial.rotate(19)
            elif count % 12.5 == 0 and a_s <= 140:
                dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 35))
            if count == (-Vne_angle / 16) + 90:
                dial.setPen(vnePen)
                dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 40))
                dial.setPen(dialPen)
            dial.rotate(0.5)
            count += 0.5

        dial.setBrush(needleBrush)
        #Needle Movement
        needle = QPolygon([QPoint(5, 0), QPoint(0, +5), QPoint(-5, 0),
                            QPoint(0, -(h / 2 - 40))])

        if self.airspeed <= 30:  # Airspeeds Below 30 Knots
            needle_angle = self._airspeed * 0.83
        else:  # Airspeeds above 30 Knots
            needle_angle = (self._airspeed - 30) * 2.5 + 25

        dial.rotate(needle_angle)
        dial.drawPolygon(needle)

        dial.restore()

    def getAirspeed(self):
        return self._airspeed

    def setAirspeed(self, airspeed):
        if airspeed != self._airspeed:
            self._airspeed = airspeed
            self.update()

    airspeed = property(getAirspeed, setAirspeed)


class Airspeed_Tape(QGraphicsView):
    def __init__(self, parent=None):
        super(Airspeed_Tape, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(32, 32, 32, 75%)")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._airspeed = 0
        fix.db.get_item("IAS", True).valueChanged[float].connect(self.setAirspeed)

        # V Speeds
        #Vs = 45
        self.Vs0 = 40
        self.Vno = 125
        self.Vne = 140
        #Va = 120
        self.Vfe = 70
        self.max = 180

        self.pph = 10 # Pixels per unit
        self.fontsize = 20


    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        self.markWidth = w / 5
        f = QFont()
        f.setPixelSize(self.fontsize)
        tape_height = self.max * self.pph + h
        tape_start = self.max * self.pph + h/2

        dialPen = QPen(QColor(Qt.white))

        self.scene = QGraphicsScene(0, 0, w, tape_height)
        self.scene.addRect(0, 0, w, tape_height,
                           QPen(QColor(32, 32, 32, 10)), QBrush(QColor(32, 32, 32, 10)))

        # Add Markings
        # Green Bar
        r = QRectF(QPoint(0,              -self.Vno * self.pph + tape_start),
                   QPoint(self.markWidth, -self.Vs0 * self.pph + tape_start))
        self.scene.addRect(r, QPen(QColor(0,155,0)), QBrush(QColor(0,155,0)))

        # White Bar
        r = QRectF(QPoint(self.markWidth / 2,              -self.Vs0 * self.pph + tape_start),
                   QPoint(self.markWidth, -self.Vfe * self.pph + tape_start))
        self.scene.addRect(r, QPen(Qt.white), QBrush(Qt.white))

        # Yellow Bar
        r = QRectF(QPoint(0,              -self.Vno * self.pph + tape_start),
                   QPoint(self.markWidth, -self.Vne * self.pph + tape_start))
        self.scene.addRect(r, QPen(Qt.yellow), QBrush(Qt.yellow))

        # Draw the little white lines and the text
        for i in range(self.max, -1, -5):
            if i % 10 == 0:
                self.scene.addLine(0, (- i * self.pph) + tape_start, w / 2,
                                   (- i * self.pph) + tape_start, dialPen)
                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(w - t.boundingRect().width())
                t.setY(((- i * self.pph) + tape_start)
                       - t.boundingRect().height() / 2)
            else:
                self.scene.addLine(0, (- i * self.pph) + tape_start,
                                   w / 2 - 20, (- i * self.pph) + tape_start,
                                   dialPen)

        # Red Line
        vnePen = QPen(QColor(Qt.red))
        vnePen.setWidth(4)
        self.scene.addLine(0, -self.Vne * self.pph + tape_start,
                           30, -self.Vne * self.pph + tape_start,
                           vnePen)

        self.setScene(self.scene)

    def redraw(self):
        tape_start = self.max * self.pph + self.height()/2

        self.resetTransform()
        self.centerOn(self.scene.width() / 2,
                      -self._airspeed * self.pph + tape_start)

    #  Index Line that doesn't move to make it easy to read the airspeed.
    def paintEvent(self, event):
        super(Airspeed_Tape, self).paintEvent(event)
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)

        marks = QPen(Qt.white)
        marks.setWidth(3)
        p.translate(0, h / 2-2)
        p.setPen(marks)
        p.drawLine(QLine(w / 3, 0, 0, 0))

    def getAirspeed(self):
        return self._airspeed

    def setAirspeed(self, airspeed):
        if airspeed != self._airspeed:
            self._airspeed = airspeed
            self.redraw()

    airspeed = property(getAirspeed, setAirspeed)


class Airspeed_Mode(QGraphicsView):
    def __init__(self, parent=None):
        super(Airspeed_Mode, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._Mode_Indicator = 0
        self._AS_Data_Box = 0
        self._airspeed_mode = "IAS"

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()
        self.f = QFont()
        self.f.setPixelSize(20)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        self.scene.addRect(0, 0, self.w, self.h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))

        t = self.scene.addText(self._airspeed_mode)
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY((self.h - t.boundingRect().height()) / 2 - (
                                    t.boundingRect().height() / 2))
        t = self.scene.addText(str(self._AS_Data_Box))
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY(((self.h - t.boundingRect().height()) / 2) + (
                                    t.boundingRect().height() / 2))
        self.setScene(self.scene)

    def redraw(self):
        self.scene.clear()
        self.scene.addRect(0, 0, self.w, self.h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        t = self.scene.addText(self._airspeed_mode)
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY((self.h - t.boundingRect().height()) / 2 - (
                                    t.boundingRect().height() / 2))
        t = self.scene.addText(str(self._AS_Data_Box))
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY(((self.h - t.boundingRect().height()) / 2) + (
                                    t.boundingRect().height() / 2))
        self.setScene(self.scene)

    def getMode(self):
        return self._Mode_Indicator

    def setMode(self, Mode):
        if Mode != self._Mode_Indicator:
            if Mode == 0:
                self._Mode_Indicator = 0
                self._airspeed_mode = "IAS"
            elif Mode == 1:
                self._Mode_Indicator = 1
                self._airspeed_mode = "TAS"
            elif Mode == 2:
                self._Mode_Indicator = 2
                self._airspeed_mode = "GS"
            elif Mode == 3:
                self._Mode_Indicator = 0
                self._airspeed_mode = "IAS"
            self.redraw()

    def getAS_Data(self):
        return self._Mode_Indicator

    def setAS_Data(self, AS_Data, PA_Data, OAT):
        if self._Mode_Indicator == 1:
            self._AS_Data_Box = int(airspeed.cas2tas(AS_Data, PA_Data, OAT))
        elif AS_Data != self._AS_Data_Box and self._Mode_Indicator != 1:
            if self._Mode_Indicator == 0:
                self._AS_Data_Box = int(AS_Data)
            elif self._Mode_Indicator == 2:
                self._AS_Data_Box = int(AS_Data)
        self.redraw()

    def setIAS(self, IAS):
        self.setAS_Data(IAS, 0, 0)

    airspeed_mode = property(getMode, setMode, getAS_Data, setAS_Data)
