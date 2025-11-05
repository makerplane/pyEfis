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

from .verticalBar import VerticalBar as VerticalBarBase


class VerticalBarImproved(VerticalBarBase):
    """
    Improved vertical bar with better alignment for color bands.
    
    Key improvements:
    - Consistent pixel rounding for all thresholds
    - Color bands calculated from absolute positions
    - Cleaner segment rendering
    """
    
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super().__init__(parent, min_size, font_family)
    
    def _calculateThresholdPixel(self, value):
        """
        Calculate pixel position for a threshold value with consistent rounding.
        Returns position from barTop (0 = top of bar, barHeight = bottom).
        
        Uses integer arithmetic throughout to ensure consistent positioning
        across bars with identical thresholds.
        """
        if value is None or self.highRange == self.lowRange:
            return None
        
        # Use integer barHeight to ensure consistent calculations
        barHeight = int(self.barHeight)
        if barHeight <= 0:
            return None
        
        # Calculate normalized position (0.0 to 1.0)
        normalized = (value - self.lowRange) / (self.highRange - self.lowRange)
        normalized = max(0.0, min(1.0, normalized))  # Clamp to valid range
        
        # Convert to pixel position using integer math for consistency
        # Scale by 1000 to maintain precision, then divide back
        scaledPosition = int(normalized * 1000)
        pixelFromBottom = (scaledPosition * barHeight) // 1000
        pixelFromTop = barHeight - pixelFromBottom
        
        # Add barTop offset as integer
        return int(self.barTop) + pixelFromTop
    
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

        # ===== IMPROVED BAR DRAWING WITH CONSISTENT ALIGNMENT =====
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Convert bar boundaries to integers for pixel-perfect alignment
        barTop = int(self.barTop)
        barBottom = int(self.barBottom)
        barLeft = int(self.barLeft)
        barWidth = int(self.barWidth)
        
        # Calculate all threshold positions once with consistent rounding
        lowAlarmPixel = self._calculateThresholdPixel(self.lowAlarm) if self.lowAlarm and self.lowAlarm >= self.lowRange else None
        lowWarnPixel = self._calculateThresholdPixel(self.lowWarn) if self.lowWarn and self.lowWarn >= self.lowRange else None
        highWarnPixel = self._calculateThresholdPixel(self.highWarn) if self.highWarn and self.highWarn <= self.highRange else None
        highAlarmPixel = self._calculateThresholdPixel(self.highAlarm) if self.highAlarm and self.highAlarm <= self.highRange else None
        
        # Draw the bar in sections from top to bottom using integer coordinates
        currentTop = barTop
        
        # Top alarm zone (high alarm)
        if highAlarmPixel is not None:
            alarmHeight = highAlarmPixel - currentTop
            if alarmHeight > 0:
                pen.setColor(self.alarmColor)
                p.setPen(pen)
                p.setBrush(self.alarmColor)
                p.drawRect(barLeft, currentTop, barWidth, alarmHeight)
                currentTop = highAlarmPixel
        
        # High warning zone
        if highWarnPixel is not None:
            warnHeight = highWarnPixel - currentTop
            if warnHeight > 0:
                pen.setColor(self.warnColor)
                p.setPen(pen)
                p.setBrush(self.warnColor)
                p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                currentTop = highWarnPixel
        
        # Safe zone (middle)
        safeBottom = lowWarnPixel if lowWarnPixel is not None else barBottom
        safeHeight = safeBottom - currentTop
        if safeHeight > 0:
            pen.setColor(self.safeColor)
            p.setPen(pen)
            p.setBrush(self.safeColor)
            p.drawRect(barLeft, currentTop, barWidth, safeHeight)
            currentTop = safeBottom
        
        # Low warning zone
        if lowWarnPixel is not None:
            lowWarnBottom = lowAlarmPixel if lowAlarmPixel is not None else barBottom
            warnHeight = lowWarnBottom - currentTop
            if warnHeight > 0:
                pen.setColor(self.warnColor)
                p.setPen(pen)
                p.setBrush(self.warnColor)
                p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                currentTop = lowWarnBottom
        
        # Bottom alarm zone (low alarm)
        if lowAlarmPixel is not None:
            alarmHeight = barBottom - currentTop
            if alarmHeight > 0:
                pen.setColor(self.alarmColor)
                p.setPen(pen)
                p.setBrush(self.alarmColor)
                p.drawRect(barLeft, currentTop, barWidth, alarmHeight)

        # Draw segments if needed (simplified)
        if self.segments > 1:  # Only draw if > 1
            segment_gap = self.barHeight * self.segment_gap_percent
            segment_size = (self.barHeight - (segment_gap * (self.segments - 1))) / self.segments
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)
            
            for segment in range(self.segments - 1):
                seg_top = self.barTop + round((segment + 1) * segment_size + segment * segment_gap)
                gap_height = max(1, round(segment_gap))  # At least 1 pixel
                p.drawRect(QRectF(self.barLeft, seg_top, self.barWidth, gap_height))
        
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

        # Indicator (filled bar effect or line)
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setBrush(brush)
        
        if self.normalizeMode and self.normalize_range > 0:
            pen.setColor(QColor(Qt.GlobalColor.gray))
            p.setPen(pen)
            nval = self._value - self.normalizeReference
            start = self.barTop + self.barHeight / 2
            valuePixel = start - (nval * self.barHeight / self.normalize_range)
        else:
            pen.setColor(QColor(Qt.GlobalColor.darkGray))
            p.setPen(pen)
            valuePixel = self.barTop + (self.barHeight - self.interpolate(self._value, self.barHeight))
        
        valuePixel = max(self.barTop, min(self.barBottom, valuePixel))
        
        if self.segments > 0:
            # Filled bar effect - darken above the value
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            darkenHeight = valuePixel - self.barTop
            if darkenHeight > 0:
                p.drawRect(QRectF(self.barLeft, self.barTop, self.barWidth, darkenHeight))
        else:
            # Traditional line indicator
            p.drawRect(QRectF(self.lineLeft, valuePixel - 2, self.lineWidth, 4))
