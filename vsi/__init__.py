#  Copyright (c) 2013 Neil Domalik, Phil Birkelbach
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

class VSI(QWidget):
    def __init__(self, parent=None):
        super(VSI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontSize = 30
        self._roc = 0
        self.maxRange = 4000
        self.maxAngle = 155.0

    def resizeEvent(self, event):
        self.background = QPixmap(self.width(), self.height())
        f = QFont()
        f.setPixelSize(self.fontSize)
        p = QPainter(self.background)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(f)
        pen = QPen(QColor(Qt.white))
        pen.setWidth(2)
        brush = QBrush(QColor(Qt.white))
        p.setPen(pen)
        self.center = QPointF(p.device().width()/2, p.device().height()/2)
        self.r = min(self.width(), self.height())/2 - 25
        
        p.fillRect(0, 0, self.width(), self.height(), Qt.black)
        p.drawEllipse(self.center, self.r, self.r)
        
        # Draw tick marks and text
        tickCount = self.maxRange / 100
        tickAngle = self.maxAngle / float(tickCount)
        longLine = QLine(0 , -self.r, 0, -(self.r-self.fontSize))
        shortLine = QLine(0 , -self.r, 0, -(self.r-self.fontSize/2))
        textRect = QRect(-40, -self.r+self.fontSize, 80, self.fontSize+10)
        p.save()
        p.translate(self.center)
        p.rotate(-90)
        p.drawLine(longLine)
        p.drawText(textRect,Qt.AlignHCenter|Qt.AlignVCenter, '0')
        for each in range(1, tickCount+1):
            p.rotate(tickAngle)
            if each % 10 == 0:
                p.drawLine(longLine)
                p.drawText(textRect, Qt.AlignHCenter|Qt.AlignVCenter, str(each / 10))
            else:
                p.drawLine(shortLine)
        p.restore()
        p.save()
        p.translate(self.center)
        p.rotate(-90)
        for each in range(1, tickCount+1):
            p.rotate(-tickAngle)
            if each % 10 == 0:
                p.drawLine(longLine)
                p.drawText(textRect, Qt.AlignHCenter|Qt.AlignVCenter, str(each / 10))
            else:
                p.drawLine(shortLine)
        p.restore()
        
        
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Insert Background
        dial.drawPixmap(0,0,self.background)

        # Setup Pens
        f = QFont()
        f.setPixelSize(self.fontSize)
        
        dialPen = QPen(QColor(Qt.white))
        dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)
        
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.setBrush(dialBrush)

        #Needle Movement
        needle = QPolygon([QPoint(5, 0), QPoint(0,+5), QPoint(-5, 0),
                            QPoint(0, -(h/2-60))])
        
        #dial_angle = self._roc * -0.0338 # 135deg / 4000 fpm
        dial_angle = self._roc * (self.maxAngle/self.maxRange)
        dial.translate(self.center)
        dial.rotate(dial_angle-90)
        dial.drawPolygon(needle)
        
    def getROC(self):
        return self._roc 

    def setROC(self, roc):
        if roc != self._roc:
            self._roc = roc
            print roc
            self.update()

    roc = property(getROC, setROC)
