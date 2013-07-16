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
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.Qt
import math

class Airspeed(QWidget):
    def __init__(self, parent=None):
        super(Airspeed, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._airspeed = 0

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        f = QFont()
        f.setPixelSize(20)
        fontMetrics = QFontMetricsF(f)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        needleBrush = QBrush(QColor(Qt.white))

        vnePen = QPen(QColor(Qt.red))
        vneBrush = QBrush(QColor(Qt.red))
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
        Va = 120
        Vfe = 70

        # VSpeed to angle for drawArc
        Vs0_angle = (-(((Vs0-30)*2.5)+26)+90)*16
        Vs_angle = (-(((Vs-30)*2.5)+26)+90)*16
        Vfe_angle = (-(((Vfe-30)*2.5)+25)+90)*16
        Vno_angle = (-(((Vno-30)*2.5)+25)+90)*16
        Vne_angle = (-(((Vne-30)*2.5)+25)+90)*16

        # Vspeeds Arcs
        dial.setPen(vnoPen)
        dial.drawArc(QRectF(25,25,w-50,h-50), Vs_angle,
                  -(Vs_angle-Vno_angle))
        dial.setPen(vsoPen)
        dial.drawArc(QRectF(28,28,w-56,h-56), Vs0_angle, 
                  -(Vs0_angle-Vfe_angle))
        dial.setPen(yellowPen)
        dial.drawArc(QRectF(25,25,w-50,h-50), Vno_angle,
                  -(Vno_angle-Vne_angle))
        dial.save()
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.translate(w/2 , h/2)
        count = 0
        a_s = 0
        while count < 360:
            if count % 25 == 0 and a_s <= 140:
                dial.drawLine(0 , -(h/2-25), 0, -(h/2-40))
                x = fontMetrics.width(str(a_s))/2
                y = f.pixelSize()
                dial.drawText(-x, -(h/2-40-y),
                           str(a_s))
                a_s += 10
                if count == 0:
                    a_s = 30
                    count = count + 19
                    dial.rotate(19)
            elif count % 12.5 == 0 and a_s <= 140:
                dial.drawLine(0 , -(h/2-25), 0, -(h/2-35))
            if count == (-Vne_angle/16)+90:
                dial.setPen(vnePen)
                dial.drawLine(0 , -(h/2-25), 0, -(h/2-40))
                dial.setPen(dialPen)
            dial.rotate(0.5)
            count += 0.5

        dial.setBrush(needleBrush)
        #Needle Movement
        needle = QPolygon([QPoint(5, 0), QPoint(0,+5), QPoint(-5, 0),
                            QPoint(0, -(h/2-40))])
        
        if self.airspeed <= 30: #Airspeeds Below 30 Knots
            needle_angle = self._airspeed *0.83
        else: #Airspeeds above 30 Knots
            needle_angle = (self._airspeed-30) * 2.5 +25

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
