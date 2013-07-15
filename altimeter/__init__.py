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
        self._altimeter = 0

    def paintEvent(self, event):
        #super(Altimeter, self).paintEvent(event)
        w = self.width()
        h = self.height()
        dial = QPainter(self.viewport())
        dial.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        f = QFont()
        f.setPixelSize(30)
        fontMetrics = QFontMetricsF(f)

        dialPen = QPen(QColor(Qt.white))
        dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)
        

        # Dial Setup
        #dial.save()
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.drawEllipse(
                      25,
                      25,
                      w-50,
                      h-50)

        dial.translate(w/2 , h/2)
        count = 0
        altimeter_numbers = 0
        while count < 360:
            if count % 36 == 0: 
                dial.drawLine(0 , -(h/2-25), 0, -(h/2-40))
                
                dial.drawText(-9.5, -(h/2-67),
                           str(altimeter_numbers))
		altimeter_numbers += 1
            else:
                dial.drawLine(0 , -(h/2-25), 0, -(h/2-35))

            dial.rotate(36)
            count += 36
        count = 0
        while count < 360:
            dial.drawLine(0 , -(h/2-25), 0, -(h/2-35))

            dial.rotate(3.6)
            count += 3.6

        dial.setBrush(dialBrush)
        #Needle Movement
        sm_dial = QPolygon([QPoint(5, 0), QPoint(0,+5), QPoint(-5, 0),
                            QPoint(0, -(h/2-40))])
        lg_dial = QPolygon([QPoint(10, -(h/2-120)), QPoint(5, 0),
                            QPoint(0,+5), QPoint(-5, 0),
                            QPoint(-10, -(h/2-120)),
                            QPoint(0, -(h/2-100))])

        sm_dial_angle = self._altimeter * .36
        lg_dial_angle = self._altimeter/10 * .36

        dial.rotate(sm_dial_angle)
        dial.drawPolygon(sm_dial)
        dial.rotate(-sm_dial_angle)
        dial.rotate(lg_dial_angle)
        dial.drawPolygon(lg_dial)

    def getAltimeter(self):
        return self._altimeter 

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            print altimeter
            self.update()

    altimeter = property(getAltimeter, setAltimeter)
