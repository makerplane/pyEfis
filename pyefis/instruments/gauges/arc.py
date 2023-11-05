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

import math
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from .abstract import AbstractGauge, drawCircle

class ArcGauge(AbstractGauge):
    def __init__(self, parent=None):
        super(ArcGauge, self).__init__(parent)
        self.setMinimumSize(100, 50)
        self.startAngle = 45
        self.sweepAngle = 180 - 45

    def get_height(self, width):
        return width/ 2

    def get_width(self, height):
        return height * 2

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 2

    def resizeEvent(self, event):
        #Properly pick a center and arc that will fit the area defined
        if self.width() < self.height():
            self.r_height = self.get_height(self.width())
            self.r_width = self.width()
            if self.height() < self.r_height:
                self.r_height = self.height()
                self.r_width = self.get_width(self.height())
        else:
            self.r_width = self.get_width(self.height())
            self.r_height = self.height()
            if self.width() < self.r_width:
                self.r_height = self.get_height(self.width())
                self.r_width = self.width()

        c_height = ((self.height() - self.r_height)  / 2) + self.r_height
        self.lrcx = self.width() - ((self.width()  - self.r_width)  / 2)
        self.lrcy =  self.height() - ((self.height() - self.r_height)  / 2)
        self.tlcx = 0 +  ((self.width() - self.r_width)   / 2)
        self.tlcy = 0 + ((self.height() - self.r_height)  / 2)


        self.arcCenter = QPointF(self.width() / 2, c_height -  5)

        self.arcRadius = self.r_height - 10

        # A polygon for the pointer
        self.arrow = QPolygonF()
        self.arrow.append(QPointF(0,self.arcRadius * .5))
        self.arrow.append(QPointF(5,5+self.arcRadius * .5))
        self.arrow.append(QPointF(1, self.arcRadius))
        self.arrow.append(QPointF(-1, self.arcRadius))
        self.arrow.append(QPointF(-5,5+self.arcRadius * .5))
        self.arrow.append(QPointF(0,self.arcRadius * .5))

    def paintEvent(self, e):
        start = self.startAngle
        sweep = self.sweepAngle
        r = self.arcRadius
        if self.lowWarn:
            lowWarnAngle = self.interpolate(self.lowWarn, sweep)
            if lowWarnAngle < 0: lowWarnAngle = 0
        else:
            lowWarnAngle = 0
        if self.lowAlarm:
            lowAlarmAngle = self.interpolate(self.lowAlarm, sweep)
            if lowAlarmAngle < 0: lowAlarmAngle = 0
        else:
            lowAlarmAngle = 0

        if self.highWarn:
            highWarnAngle = self.interpolate(self.highWarn, sweep)
            if highWarnAngle > sweep: highWarnAngle = sweep
        else:
            highWarnAngle = sweep
        if self.highAlarm:
            highAlarmAngle = self.interpolate(self.highAlarm, sweep)
            if highAlarmAngle > sweep: highAlarmAngle = sweep
        else:
            highAlarmAngle = sweep
        centerX = self.arcCenter.x()
        centerY = self.arcCenter.y()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(10)
        pen.setCapStyle(Qt.FlatCap)

        # Red Arcs
        pen.setColor(self.alarmColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start, sweep - highAlarmAngle)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start+sweep, -lowAlarmAngle)

        # Yellow Arcs
        pen.setColor(self.warnColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start + (sweep-highAlarmAngle), -(highWarnAngle - highAlarmAngle))
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start+sweep-lowAlarmAngle, -(lowWarnAngle-lowAlarmAngle))

        # Green Arc
        pen.setColor(self.safeColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start + (sweep - highWarnAngle), highWarnAngle-lowWarnAngle)

        # Now we draw the line pointer
        brush = QBrush(self.penColor)
        pen.setColor(QColor(Qt.black))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        valAngle = 90 + self.interpolate(self._value, sweep)
        t = QTransform()
        t.translate(self.arcCenter.x(), self.arcCenter.y())
        t.rotate(valAngle)
        arrow = t.map(self.arrow)
        p.drawPolygon(arrow)

        # Draw Text
        pen.setColor(self.textColor)
        pen.setWidth(1)
        p.setPen(pen)
        f = QFont()
        f.setPixelSize(qRound(self.r_height / 6))
        p.setFont(f)
        #p.drawText(QPoint(centerX - (r - 40), centerY - (r - 40)), self.name)
        p.drawText(QPointF(self.tlcx + (self.r_width / 20),self.tlcy + f.pixelSize()), self.name)

        # Main value text
        path = QPainterPath()
        brush = QBrush(self.valueColor)
        p.setBrush(brush)
        pen.setColor(QColor(Qt.black))
        p.setPen(pen)
        f.setPixelSize(qRound(self.r_height / 2))
        fm = QFontMetrics(f)
        x = fm.width(self.valueText)
        path.addText(QPointF( self.lrcx - x, self.lrcy - 1),f, self.valueText)
        p.drawPath(path)
