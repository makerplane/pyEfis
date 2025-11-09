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
        # Use the drawable bar width (excludes left label area when enabled)
        _, _, barWidth, _ = self.get_bar_geometry()
        if barWidth <= 0:
            return None
        
        normalized = (value - self.lowRange) / (self.highRange - self.lowRange)
        normalized = max(0.0, min(1.0, normalized))
        
        scaledPosition = int(normalized * 1000)
        pixelFromLeft = (scaledPosition * barWidth) // 1000
        
        return pixelFromLeft
    
    def paintEvent(self, event):
        # Ensure geometry reflects any preference attributes set after construction
        from time import perf_counter_ns
        from pyefis.diagnostics.overlay import GaugeDiagnostics
        _t0 = perf_counter_ns()
        self._recompute_geometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        # Top row: name/dbkey followed immediately by units (use base cache helper)
        top_rect = QRectF(self.nameTextRect)
        fitted_font, (name_text, units_text, spacer, name_w) = self._get_top_layout()
        p.setFont(fitted_font)
        pen.setColor(self.textColor)
        p.setPen(pen)
        if name_text:
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if self.name_font_ghost_mask:
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(top_rect, self.name_font_ghost_mask, opt_left)
                self.textColor.setAlpha(alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
            p.drawText(top_rect, name_text, opt_left)
            if units_text:
                units_rect = QRectF(top_rect.left() + name_w, top_rect.top(), max(0, top_rect.width() - name_w), top_rect.height())
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(units_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(units_rect, units_text, opt_left)
        else:
            if units_text:
                opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(top_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(top_rect, units_text, opt_left)
        # Draw value either in standard position or inside left label area
        if not self.value_on_bar_left:
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
        else:
            # Always show numeric value on left (dbkey already used as name when requested)
            label_text = self.valueText
            left_font = self._font_fit(self.bigFont, label_text or "", self.barValueRect)
            p.setFont(left_font)
            pen.setColor(self.valueColor)
            p.setPen(pen)
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.drawText(self.barValueRect, label_text, opt_left)

        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bar_left, barTop, barWidth, barHeight = self.get_bar_geometry()
        p.save()
        p.setClipRect(QRectF(bar_left, barTop, barWidth, barHeight))

        lowAlarmPixel = self._calculateThresholdPixel(self.lowAlarm) if self.lowAlarm else None
        lowWarnPixel = self._calculateThresholdPixel(self.lowWarn) if self.lowWarn else None
        highWarnPixel = self._calculateThresholdPixel(self.highWarn) if self.highWarn else None
        highAlarmPixel = self._calculateThresholdPixel(self.highAlarm) if self.highAlarm else None
        
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(bar_left, barTop, barWidth, barHeight)
        
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if lowWarnPixel is not None:
            p.drawRect(bar_left, barTop, lowWarnPixel, barHeight)
        if highWarnPixel is not None:
            warnWidth = barWidth - highWarnPixel
            p.drawRect(bar_left + highWarnPixel, barTop, warnWidth, barHeight)
        
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if lowAlarmPixel is not None:
            p.drawRect(bar_left, barTop, lowAlarmPixel, barHeight)
        if highAlarmPixel is not None:
            alarmWidth = barWidth - highAlarmPixel
            p.drawRect(bar_left + highAlarmPixel, barTop, alarmWidth, barHeight)

        if self.segments > 0:
            segment_gap = barWidth * self.segment_gap_percent
            segment_size = (barWidth - (segment_gap * (self.segments - 1))) / self.segments
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)
            for segment in range(self.segments - 1):
                seg_left = int(((segment + 1) * segment_size) + (segment * segment_gap))
                p.drawRect(bar_left + seg_left, barTop, int(segment_gap), barHeight)

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
            x = bar_left + x
            
            if not self.segments > 0:
                p.drawRect(x-2, barTop-4, 4, barHeight+8)
            else:
                pen.setColor(QColor(0, 0, 0, self.segment_alpha))
                p.setPen(pen)
                p.setBrush(QColor(0, 0, 0, self.segment_alpha))
                # Darken from the indicator to the end of the bar area
                p.drawRect(x, barTop, (bar_left + barWidth) - x, barHeight)
        p.restore()
        _t1 = perf_counter_ns()
        try:
            GaugeDiagnostics.get().record(self.__class__.__name__, _t1 - _t0)
            GaugeDiagnostics.get().record_painted_value(self.__class__.__name__, float(self._value))
        except Exception:
            pass
        self._last_painted_value = self._value
