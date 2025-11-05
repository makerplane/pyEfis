#  Copyright (c) 2013 Phil Birkelbach
#  Copyright (c) 2025 Simplified single-color version
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

from .verticalBar import VerticalBar as VerticalBarBase


class VerticalBarSimple(VerticalBarBase):
    """
    Simplified vertical bar that changes color based on value.
    
    No color bands, no segments - just a clean filled bar that changes
    color (green/yellow/red) based on the current value and thresholds.
    
    This eliminates ALL alignment issues and gives a clean, modern look.
    """
    
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super().__init__(parent, min_size, font_family)
    
    def _getBarColor(self):
        """
        Determine the bar color based on current value and thresholds.
        Returns the appropriate color (safe, warn, or alarm).
        """
        value = self._value
        
        # Check high alarm
        if self.highAlarm is not None and value >= self.highAlarm:
            return self.alarmColor
        
        # Check high warning
        if self.highWarn is not None and value >= self.highWarn:
            return self.warnColor
        
        # Check low alarm
        if self.lowAlarm is not None and value <= self.lowAlarm:
            return self.alarmColor
        
        # Check low warning
        if self.lowWarn is not None and value <= self.lowWarn:
            return self.warnColor
        
        # Default to safe color
        return self.safeColor
    
    def paintEvent(self, event):
        # Check highlight status
        if self.highlight_key:
            if self._highlightValue == self._rawValue:
                self.highlight = True
            else:
                self.highlight = False

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        
        # Draw name
        opt = QTextOption(Qt.AlignmentFlag.AlignCenter)
        if self.show_name:
            if self.name_font_ghost_mask:
                opt = QTextOption(Qt.AlignmentFlag.AlignLeft)
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.setFont(self.smallFont)
                p.drawText(self.nameTextRect, self.name_font_ghost_mask, opt)
                self.textColor.setAlpha(alpha)
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.setFont(self.smallFont)
            p.drawText(self.nameTextRect, self.name, opt)
        
        # Draw value
        if self.show_value:
            if self.peakMode:
                dv = self.value - self.peakValue
                if dv <= -10:
                    pen.setColor(self.peakColor)
                    p.setFont(self.bigFont)
                    p.setPen(pen)
                    p.drawText(self.valueTextRect, str(round(dv)), opt)
                else:
                    self.drawValue(p, pen)
            else:
                self.drawValue(p, pen)

        # Draw units
        opt = QTextOption(Qt.AlignmentFlag.AlignCenter)
        pen.setColor(self.textColor)
        p.setPen(pen)
        if self.show_units:
            if self.units_font_mask:
                opt = QTextOption(Qt.AlignmentFlag.AlignRight)
                p.setFont(self.unitsFont)
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(self.unitsTextRect, self.units_font_ghost_mask, opt)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(self.unitsTextRect, self.units, opt)
            else:
                p.setFont(self.smallFont)
                p.drawText(self.unitsTextRect, self.units, opt)

        # ===== SIMPLIFIED BAR DRAWING - SINGLE COLOR, NO BANDS =====
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Get the color for the entire bar based on current value
        barColor = self._getBarColor()
        
        # Draw background (empty portion) - dark gray
        pen.setColor(QColor(40, 40, 40))
        p.setPen(pen)
        p.setBrush(QColor(40, 40, 40))
        p.drawRect(QRectF(self.barLeft, self.barTop, self.barWidth, self.barHeight))
        
        # Calculate value position
        if self.normalizeMode and self.normalize_range > 0:
            nval = self._value - self.normalizeReference
            start = self.barTop + self.barHeight / 2
            valuePixel = start - (nval * self.barHeight / self.normalize_range)
        else:
            valuePixel = self.barTop + (self.barHeight - self.interpolate(self._value, self.barHeight))
        
        valuePixel = max(self.barTop, min(self.barBottom, valuePixel))
        
        # Draw filled portion in the appropriate color
        filledHeight = self.barBottom - valuePixel
        if filledHeight > 0:
            pen.setColor(barColor)
            p.setPen(pen)
            p.setBrush(barColor)
            p.drawRect(QRectF(self.barLeft, valuePixel, self.barWidth, filledHeight))
        
        # Highlight ball
        if self.highlight:
            pen.setColor(Qt.GlobalColor.black)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(self.highlightColor)
            p.drawEllipse(self.ballCenter, self.ballRadius, self.ballRadius)

        # Peak value line
        if self.peakMode:
            pen.setColor(QColor(Qt.GlobalColor.white))
            brush = QBrush(self.peakColor)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(brush)
            if self.normalizeMode and self.normalize_range > 0:
                nval = self.peakValue - self.normalizeReference
                start = self.barTop + self.barHeight / 2
                y = start - (nval * self.barHeight / self.normalize_range)
            else:
                y = self.barTop + (self.barHeight - self.interpolate(self.peakValue, self.barHeight))
            y = max(self.barTop, min(self.barBottom, y))
            p.drawRect(qRound(self.lineLeft), qRound(y - 2), qRound(self.lineWidth), qRound(4))
