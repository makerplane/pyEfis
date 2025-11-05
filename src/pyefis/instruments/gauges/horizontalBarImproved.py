#  Copyright (c) 2013 Phil Birkelbach
#  Copyright (c) 2025 Improved alignment version
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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

from .horizontalBar import HorizontalBar


class HorizontalBarImproved(HorizontalBar):
    """Improved horizontal bar with better alignment for color bands."""
    
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super().__init__(parent, min_size, font_family)
    
    def _calculateThresholdPixel(self, value):
        """Calculate pixel position for a threshold value with consistent rounding."""
        if value is None or self.highRange == self.lowRange:
            return None
        
        barWidth = int(self.width())
        if barWidth <= 0:
            return None
        
        normalized = (value - self.lowRange) / (self.highRange - self.lowRange)
        normalized = max(0.0, min(1.0, normalized))
        
        scaledPosition = int(normalized * 1000)
        pixelFromLeft = (scaledPosition * barWidth) // 1000
        
        return pixelFromLeft
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        
        p.setFont(self.smallFont)
        if self.show_name: 
            if self.name_font_ghost_mask:
                opt = QTextOption(Qt.AlignmentFlag.AlignLeft)
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(self.nameTextRect, self.name_font_ghost_mask, opt)
                self.textColor.setAlpha(alpha)
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.drawText(self.nameTextRect, self.name)

        p.setFont(self.unitsFont)
        opt = QTextOption(Qt.AlignmentFlag.AlignRight)
        if self.show_units: 
            if self.units_font_ghost_mask:
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(self.valueTextRect, self.units_font_ghost_mask, opt)
                self.textColor.setAlpha(alpha)
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.drawText(self.valueTextRect, self.units, opt)

        p.setFont(self.bigFont)
        opt = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        if self.show_value: 
            if self.font_ghost_mask:
                alpha = self.valueColor.alpha()
                self.valueColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.valueColor)
                p.setPen(pen)
                p.drawText(self.valueTextRect, self.font_ghost_mask, opt)
                self.valueColor.setAlpha(alpha)
            pen.setColor(self.valueColor)
            p.setPen(pen)
            p.drawText(self.valueTextRect, self.valueText, opt)

        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        barTop = int(self.barTop)
        barHeight = int(self.barHeight)
        barWidth = int(self.width())
        
        lowAlarmPixel = self._calculateThresholdPixel(self.lowAlarm) if self.lowAlarm else None
        lowWarnPixel = self._calculateThresholdPixel(self.lowWarn) if self.lowWarn else None
        highWarnPixel = self._calculateThresholdPixel(self.highWarn) if self.highWarn else None
        highAlarmPixel = self._calculateThresholdPixel(self.highAlarm) if self.highAlarm else None
        
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(0, barTop, barWidth, barHeight)
        
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if lowWarnPixel is not None:
            p.drawRect(0, barTop, lowWarnPixel, barHeight)
        if highWarnPixel is not None:
            warnWidth = barWidth - highWarnPixel
            p.drawRect(highWarnPixel, barTop, warnWidth, barHeight)
        
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if lowAlarmPixel is not None:
            p.drawRect(0, barTop, lowAlarmPixel, barHeight)
        if highAlarmPixel is not None:
            alarmWidth = barWidth - highAlarmPixel
            p.drawRect(highAlarmPixel, barTop, alarmWidth, barHeight)

        if self.segments > 0:
            segment_gap = barWidth * self.segment_gap_percent
            segment_size = (barWidth - (segment_gap * (self.segments - 1))) / self.segments
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)
            for segment in range(self.segments - 1):
                seg_left = int(((segment + 1) * segment_size) + (segment * segment_gap))
                p.drawRect(seg_left, barTop, int(segment_gap), barHeight)

        pen.setColor(QColor(Qt.GlobalColor.darkGray))
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        
        if self._value is not None:
            x = self._calculateThresholdPixel(self._value)
            if x is None:
                x = 0
            x = max(0, min(barWidth, x))
            
            if not self.segments > 0:
                p.drawRect(x-2, barTop-4, 4, barHeight+8)
            else:
                pen.setColor(QColor(0, 0, 0, self.segment_alpha))
                p.setPen(pen)
                p.setBrush(QColor(0, 0, 0, self.segment_alpha))
                p.drawRect(x, barTop, barWidth - x, barHeight)
