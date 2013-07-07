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

class HSI(QGraphicsView):
    def __init__(self, parent=None):
        super(HSI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._heading = 1
        self._headingSelect = 1
        self._courseSelect = 1
        self._courseDevation = 1

    def paintEvent(self, event):
        super(HSI, self).paintEvent(event)
        w = self.width()
        h = self.height()
        c = QPainter(self.viewport())
        c.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        c.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        compassPen = QPen(QColor(Qt.white))
        compassBrush = QBrush(QColor(Qt.white))
        compassPen.setWidth(2)

        headingPen = QPen(QColor(Qt.red))
        headingBrush = QBrush(QColor(Qt.red))
        headingPen.setWidth(2)

        planePen = QPen(QColor(Qt.yellow))
        planePen.setWidth(3)

        # Compass Setup
        c.setPen(compassPen)
        c.drawPoint(w/2, h/2)
        c.drawText(self.rect(), 
                   Qt.AlignHCenter|Qt.AlignTop,
                    str(self._heading))
        c.drawRect(w/2-16, 0+4, 31, 14)

        # Compass Setup
        c.drawEllipse(
                      25,
                      25,
                      w-50,
                      h-50)

        c.save()
        c.translate(w/2 , h/2)
        c.rotate(-(self._heading))
        count = 0
        cardnal = ["N", "E", "S", "W"]
        while count < 360:
            if count % 10 == 0: 
                c.drawLine(0 , -(h/2-25), 0, -(h/2-40))
                if count % 90 == 0:
                    c.drawText(-5,
                               -(h/2-52),
                               cardnal[int(count/90)])
                elif count % 30 == 0:
                    subCardnal = str(int(count/10))
                    if int(count/10) < 10:
                        c.drawText(-5,
                                   -(h/2-52),
                                   subCardnal)
                    else:
                       c.drawText(-9,
                                  -(h/2-52),
                                  subCardnal)
            else:
                c.drawLine(0 , -(h/2-25), 0, -(h/2-35))

            #Draw Heading Bug
            if (count+0 <= self._headingSelect + 10 and 
                count+5 > self._headingSelect + 10):
                c.setPen(headingPen)
                c.setBrush(headingBrush)
                delta = self._headingSelect- count
                c.rotate(delta)
                triangle = QPolygon([QPoint(0+5, -(h/2-25)),
                                     QPoint(0-5, -(h/2-25)),
                                     QPoint(0, -(h/2-35))])
                c.drawPolygon(triangle)
                c.setPen(compassPen)
                c.rotate(-delta)

            c.rotate(5)
            count += 5
        c.restore()

        #Non-moving items
        c.drawLine(w/2 , 0+20, w/2, 0+50)
        c.setPen(planePen)
        c.drawLine(w/2 , h/2+30, w/2, h/2-30)
        c.drawLine(w/2-40 , h/2-15, w/2+40, h/2-15) 
        c.drawLine(w/2-20 , h/2+20, w/2+20, h/2+20)

    def getHeading(self):
        return self._heading 

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = heading
            self.update()

    heading = property(getHeading, setHeading)

    def getHeadingBug(self):
        return self._headingSelect

    def setHeadingBug(self, headingBug):
        if headingBug != self._headingSelect:
            self._headingSelect = headingBug
            self.update()
	

    headingBug = property(getHeadingBug, setHeadingBug)
