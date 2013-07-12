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

class Altimeter(QGraphicsView):
    def __init__(self, parent=None):
        super(Altimeter, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._airspeed = 0

    def paintEvent(self, event):
        super(Altimeter, self).paintEvent(event)
        w = self.width()
        h = self.height()
        c = QPainter(self.viewport())
        c.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        c.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        dialPen = QPen(QColor(Qt.white))
        dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)

        vnePen = QPen(QColor(Qt.red))
        vneBrush = QBrush(QColor(Qt.red))
        vnePen.setWidth(2)

        vsoPen = QPen(QColor(Qt.yellow))
        vsoPen.setWidth(3)

        # Compass Setup
        c.setPen(dialPen)
        c.drawPoint(w/2, h/2)

        # Dial Setup
        c.drawEllipse(
                      25,
                      25,
                      w-50,
                      h-50)

        c.save()

        c.translate(w/2 , h/2)
        count = 0
        altimeter_numbers = 0
        while count < 360:
            if count % 36 == 0: 
                c.drawLine(0 , -(h/2-25), 0, -(h/2-40))
                
                c.drawText(-5, -(h/2-52),
                           str(altimeter_numbers))
		altimeter_numbers += 1
            else:
                c.drawLine(0 , -(h/2-25), 0, -(h/2-35))

            c.rotate(36)
            count += 36
        #c.restore()
        count = 0
        while count < 360:
            c.drawLine(0 , -(h/2-25), 0, -(h/2-35))

            c.rotate(3.6)
            count += 3.6
        c.restore()

    def getAirspeed(self):
        return self._airspeed 

    def setAirspeed(self, airspeed):
        if heading != self._airspeed:
            self._airspeed = airspeed
            self.update()

    airspeed = property(getAirspeed, setAirspeed)
