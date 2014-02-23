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

class Altimeter(QWidget):
    def __init__(self, parent=None):
        super(Altimeter, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._altimeter = 0

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
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
            self.update()

    altimeter = property(getAltimeter, setAltimeter)

class Altimeter_Tape(QGraphicsView):
    def __init__(self, parent=None):
        super(Altimeter_Tape, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._altimeter = 0

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        self.pph = 0.5
        f = QFont()
        f.setPixelSize(20)
        fontMetrics = QFontMetricsF(f)
        height_pixel = 5000 + h

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        self.scene = QGraphicsScene(0,0,w, height_pixel)
        self.scene.addRect(0, 0, w, height_pixel, 
                           QPen(QColor(Qt.black)),QBrush(QColor(Qt.black)))

        for i in range(100, -1, -1):
            if i % 2 == 0:
                self.scene.addLine(w/2 + 15, (-i*50)+ 5000+h/2, w, (-i*50)+ 5000+h/2,
                                   dialPen)
                t = self.scene.addText(str(i*100))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(0)
                t.setY(((-i*50)+5000+h/2) - t.boundingRect().height()/2)
            else:
                self.scene.addLine(w/2+ 30, (-i*50)+5000+h/2, w, (-i*50)+5000+h/2, dialPen)
        self.setScene(self.scene)

    def redraw(self):
        self.resetTransform()
        self.centerOn(self.scene.width()/2,
                      -self._altimeter * self.pph + 5000+self.height()/2)


    def getAltimeter(self):
        return self._altimeter 

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            self.redraw()

    altimeter = property(getAltimeter, setAltimeter)
