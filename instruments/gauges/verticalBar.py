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

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import fix
from .abstract import AbstractGauge

class VerticalBar(AbstractGauge):
    def __init__(self, parent=None):
        super(VerticalBar, self).__init__(parent)
        self.setMinimumSize(50, 100)
        self.showValue = True
        self.showUnits = True
        self.showName = True
        self.barWidthPercent = 0.3
        self.lineWidthPercent = 0.5
        self.textGap = 3
        self.smallFontPercent = 0.08
        self.bigFontPercent = 0.10

    def resizeEvent(self, event):
        self.barWidth = self.width() * self.barWidthPercent
        self.lineWidth = self.width() * self.lineWidthPercent
        self.bigFont = QFont()
        self.bigFont.setPixelSize(self.height() * self.bigFontPercent)
        self.smallFont = QFont()
        self.smallFont.setPixelSize(self.height() * self.smallFontPercent)
        #self.barHeight = self.height() / 6
        if self.showName:
            self.barTop = self.smallFont.pixelSize() + self.textGap
        else:
            self.barTop = 1
        self.barBottom = self.height()
        if self.showValue:
            self.barBottom -= (self.bigFont.pixelSize() + self.textGap)
        if self.showUnits:
            self.barBottom -= (self.smallFont.pixelSize() + self.textGap)

        self.nameTextRect = QRectF(0, 0, self.width(), self.smallFont.pixelSize())
        self.valueTextRect = QRectF(0, self.barBottom + self.textGap, self.width(), self.bigFont.pixelSize())
        self.unitsTextRect = QRectF(0, self.height() - self.smallFont.pixelSize() - self.textGap, self.width(), self.smallFont.pixelSize())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        opt = QTextOption(Qt.AlignCenter)
        if self.showName:
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.setFont(self.smallFont)
            p.drawText(self.nameTextRect, self.name, opt)
        if self.showValue:
            # Draw Value
            pen.setColor(self.valueColor)
            p.setPen(pen)
            p.setFont(self.bigFont)
            p.drawText(self.valueTextRect, self.valueText, opt)
        if self.showUnits:
            # Units
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.setFont(self.smallFont)
            p.drawText(self.unitsTextRect, self.units, opt)

        barLeft = (self.width() - self.barWidth) / 2
        barRight = barLeft + self.barWidth
        lineLeft = (self.width() - self.lineWidth) / 2
        lineRight = lineLeft + self.lineWidth
        barHeight = self.barBottom - self.barTop

        # Draws the bar
        p.setRenderHint(QPainter.Antialiasing, False)
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(barLeft, self.barTop, self.barWidth, barHeight)

        # Draw Warning Bands
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn):
            x = self.interpolate(self.lowWarn, barHeight)
            p.drawRect(barLeft, self.barBottom - x,
                       self.barWidth,
                       x + 1)
        if(self.highWarn):
            p.drawRect(barLeft, self.barTop,
                       self.barWidth,
                       barHeight - self.interpolate(self.highWarn, barHeight))

        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm):
            x = self.interpolate(self.lowAlarm, barHeight)
            p.drawRect(barLeft, self.barBottom - x,
                       self.barWidth,
                       x + 1)
        if(self.highAlarm):
            p.drawRect(barLeft, self.barTop,
                       self.barWidth,
                       barHeight - self.interpolate(self.highAlarm, barHeight))

        # Indicator Line
        pen.setColor(self.penColor)
        brush = QBrush()
        pen.setWidth(4)
        p.setPen(pen)
        p.setBrush(brush)
        x = self.barTop + (barHeight - self.interpolate(self._value, barHeight))
        p.drawLine(lineLeft, x,
                   lineRight, x)
