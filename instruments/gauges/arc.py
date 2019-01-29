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
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import efis
import fix
from .abstract import AbstractGauge, drawCircle

class ArcGauge(AbstractGauge):
    def __init__(self, parent=None):
        super(ArcGauge, self).__init__(parent)
        self.setMinimumSize(100, 50)
        self.startAngle = 45
        self.sweepAngle = 180 - 45

    def resizeEvent(self, event):
        self.arcCenter = QPoint(self.width() / 2, self.height())
        self.arcRadius = self.height() - 10

    def paintEvent(self, e):
        start = self.startAngle
        sweep = self.sweepAngle
        r = self.arcRadius
        if self.highWarn:
            warnAngle = sweep - self.interpolate(self.highWarn, sweep)
        else:
            warnAngle = 0
        if self.highAlarm:
            alarmAngle = sweep - self.interpolate(self.highAlarm, sweep)
        else:
            alarmAngle = 0
        centerX = self.arcCenter.x()
        centerY = self.arcCenter.y()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(10)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(self.alarmColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start, alarmAngle)
        pen.setColor(self.warnColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start + alarmAngle, warnAngle - alarmAngle)
        pen.setColor(self.safeColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start + warnAngle, sweep - warnAngle)
        # Now we draw the line pointer
        pen.setColor(self.penColor)
        pen.setWidth(2)
        p.setPen(pen)
        valAngle = sweep - int(self.interpolate(self._value, sweep))
        theta = math.radians(start + valAngle)
        x = (r + 10) * math.sin(theta)
        y = (r + 10) * math.cos(theta)
        endPoint = QPoint(self.arcCenter.y() + y, self.arcCenter.x() - x)
        p.drawLine(self.arcCenter, endPoint)
        # Draw Text
        pen.setColor(self.textColor)
        pen.setWidth(1)
        p.setPen(pen)
        f = QFont()
        f.setPixelSize(self.height() / 6)
        p.setFont(f)
        opt = QTextOption(Qt.AlignLeft | Qt.AlignBottom)
        #p.drawText(QPoint(centerX - (r - 40), centerY - (r - 40)), self.name)
        p.drawText(QPoint(self.width() / 20,f.pixelSize()), self.name)

        # Main value text
        f.setPixelSize(self.height() / 2)
        pen.setColor(self.valueColor)
        p.setPen(pen)
        p.setFont(f)
        opt = QTextOption(Qt.AlignRight | Qt.AlignBottom)
        rect = QRectF(0, 0, self.width(), self.height())
        p.drawText(rect, self.valueText, opt)
