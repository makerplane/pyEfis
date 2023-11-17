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

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


from .abstract import AbstractGauge

class HorizontalBar(AbstractGauge):
    def __init__(self, parent=None, min_size=True):
        super(HorizontalBar, self).__init__(parent)
        if min_size:
            self.setMinimumSize(100, 50)

    def resizeEvent(self, event):
        self.bigFont = QFont()
        self.bigFont.setPixelSize(qRound(self.height() / 2))
        self.smallFont = QFont()
        self.smallFont.setPixelSize(qRound(self.height() / 5))
        self.barHeight = self.height() / 6
        self.barTop = self.height() / 5 + 4
        self.nameTextRect = QRectF(1, 1, self.width(), self.height() / 5 + 10)
        self.valueTextRect = QRectF(1, self.barTop + self.barHeight + 4,
                                    self.width()-5, self.height() / 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(self.textColor)
        p.setPen(pen)
        p.setFont(self.smallFont)
        p.drawText(self.nameTextRect, self.name)

        # Units
        p.setFont(self.smallFont)
        opt = QTextOption(Qt.AlignRight)
        p.drawText(self.valueTextRect, self.units, opt)

        # Main Value
        p.setFont(self.bigFont)
        pen.setColor(self.valueColor)
        p.setPen(pen)
        opt = QTextOption(Qt.AlignLeft | Qt.AlignBottom)
        p.drawText(self.valueTextRect, self.valueText, opt)

        # Draws the bar
        p.setRenderHint(QPainter.Antialiasing, False)
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(QRectF(0, self.barTop, self.width(), self.barHeight))
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn):
            p.drawRect(QRectF(0, self.barTop,
                              self.interpolate(self.lowWarn, self.width()),
                              self.barHeight))
        if(self.highWarn):
            x = self.interpolate(self.highWarn, self.width())
            p.drawRect(QRectF(x, self.barTop,
                              self.width() - x, self.barHeight))
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm):
            p.drawRect(QRectF(0, self.barTop,
                              self.interpolate(self.lowAlarm, self.width()),
                              self.barHeight))
        if(self.highAlarm):
            x = self.interpolate(self.highAlarm, self.width())
            p.drawRect(QRectF(x, self.barTop,
                              self.width() - x, self.barHeight))
        # Indicator Line
        pen.setColor(QColor(Qt.darkGray))
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        x = self.interpolate(self._value, self.width())
        if x < 0: x = 0
        if x > self.width(): x = self.width()
        p.drawRect(QRectF(x-2, self.barTop-4, 4, self.barHeight+8))
