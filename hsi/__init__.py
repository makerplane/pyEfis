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

class HSI(QWidget):
    def __init__(self, parent=None):
        super(HSI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontSize = 25
        self._heading = 1
        self._headingSelect = 1
        self._courseSelect = 1
        self._courseDevation = 1
        self.cardinal = ["N", "E", "S", "W"]

    def resizeEvent(self, event):
        self.cx = self.width() / 2
        self.cy = self.height() / 2 + self.fontSize / 2 + 7
        self.r = self.height() / 2 - 21
        
    def paintEvent(self, event):
        c = QPainter(self)
        c.setRenderHint(QPainter.Antialiasing)
        f = QFont()
        f.setPixelSize(self.fontSize)
        c.setFont(f)
        
        #Draw the Black Background
        c.fillRect(0, 0, self.width(), self.height(), Qt.black)

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
        c.drawPoint(self.cx, self.cy)
        tr = QRect(self.cx-self.fontSize*1.5, 3, 
                   self.fontSize * 3, self.fontSize + 5)
        c.drawText(tr, Qt.AlignHCenter|Qt.AlignVCenter,
                   str(int(self._heading)))
        c.drawRect(tr)

        # Compass Setup
        center = QPointF(self.cx, self.cy)
        c.drawEllipse(center, self.r,self.r)

        c.save()
        c.translate(self.cx, self.cy)
        c.rotate(-(self._heading))
        
        longLine = QLine(0 , -self.r, 0, -(self.r-self.fontSize))
        shortLine = QLine(0 , -self.r, 0, -(self.r-self.fontSize/2))
        textRect = QRect(-40, -self.r+self.fontSize, 80, self.fontSize+10)
        for count in range(0, 360, 5):
            if count % 10 == 0: 
                c.drawLine(longLine)
                if count % 90 == 0:
                    c.drawText(textRect, Qt.AlignHCenter|Qt.AlignVCenter, 
                               self.cardinal[int(count/90)])
                elif count % 30 == 0:
                    c.drawText(textRect, Qt.AlignHCenter|Qt.AlignVCenter, 
                               str(int(count/10)))
            else:
                c.drawLine(shortLine)
            c.rotate(5)

        #Draw Heading Bug
        c.setPen(headingPen)
        c.setBrush(headingBrush)
        delta = self._headingSelect
        c.rotate(delta)
        inc = int(self.fontSize / 2 *0.8)
        triangle = QPolygon([QPoint(inc, -self.r+1),
                             QPoint(-inc, -self.r+1),
                             QPoint(0, -(self.r-inc*2))])
        c.drawPolygon(triangle)
        c.rotate(-delta)

        c.restore()

        #Non-moving items
        c.setPen(planePen)
        c.drawLine(self.cx , self.cy-self.r-5, self.cx, self.cy-self.r+self.fontSize+5)
        c.drawLine(self.cx , self.cy+40, self.cx, self.cy-20)
        c.drawLine(self.cx-40 , self.cy, self.cx+40, self.cy) 
        c.drawLine(self.cx-20 , self.cy+30, self.cx+20, self.cy+30)


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
