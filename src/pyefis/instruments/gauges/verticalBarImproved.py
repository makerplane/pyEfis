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
import sys
import logging

from .verticalBar import VerticalBar as VerticalBarBase

log = logging.getLogger(__name__)


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
        self._bar_left = -1

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
        
        # CRITICAL: Set pen to no outline for color bands
        # A 1-pixel pen draws on the rectangle border and can cause misalignment
        pen.setWidth(0)  # No outline
        pen.setStyle(Qt.PenStyle.NoPen)  # Disable pen completely
        
        # Convert bar boundaries to integers for pixel-perfect alignment
        barTop = int(self.barTop)
        barBottom = int(self.barBottom)

        widgetWidth = int(self.width())

        # Start with local geometry based on this widget alone.
        barWidth = max(1, int(round(widgetWidth * self.bar_width_percent)))
        barWidth = min(barWidth, widgetWidth)
        barLeft = (widgetWidth - barWidth) // 2
        lineWidth = max(1, int(round(widgetWidth * self.line_width_percent)))
        lineWidth = min(lineWidth, widgetWidth)
        lineLeft = (widgetWidth - lineWidth) // 2

        # When part of a ganged layout, align using the parent container width so
        # every bar paints using the exact same geometry regardless of its own widget width.
        parent_obj = self.parent()
        if parent_obj is not None and hasattr(parent_obj, 'bars'):
            try:
                bars = parent_obj.bars
                barCount = len(bars)
                if barCount > 0:
                    index = bars.index(self)
                    parentWidth = max(1, parent_obj.width())
                    slotWidth = parentWidth / barCount

                    barWidth = max(1, int(round(slotWidth * self.bar_width_percent)))
                    barWidth = min(barWidth, widgetWidth)
                    lineWidth = max(1, int(round(slotWidth * self.line_width_percent)))
                    lineWidth = min(lineWidth, widgetWidth)

                    slotLeft = slotWidth * index
                    desiredBarLeft = slotLeft + (slotWidth - barWidth) / 2.0
                    desiredLineLeft = slotLeft + (slotWidth - lineWidth) / 2.0

                    # Translate global coordinates back into the widget's local space.
                    barLeft = int(round(desiredBarLeft - self.x()))
                    lineLeft = int(round(desiredLineLeft - self.x()))
            except ValueError:
                # Bar not found in parent list; keep local geometry.
                pass

        # Clamp to ensure drawing stays inside this widget.
        barLeft = max(0, min(widgetWidth - barWidth, barLeft))
        lineLeft = max(0, min(widgetWidth - lineWidth, lineLeft))

        # Calculate ball geometry from the aligned bar values.
        ballRadius = max(1, int(round(barWidth * 0.40)))
        ballCenter = QPointF(barLeft + (barWidth / 2.0), self.barBottom - (barWidth / 2.0))
        
        # Calculate all threshold positions once with consistent rounding
        lowAlarmPixel = self._calculateThresholdPixel(self.lowAlarm) if self.lowAlarm and self.lowAlarm >= self.lowRange else None
        lowWarnPixel = self._calculateThresholdPixel(self.lowWarn) if self.lowWarn and self.lowWarn >= self.lowRange else None
        highWarnPixel = self._calculateThresholdPixel(self.highWarn) if self.highWarn and self.highWarn <= self.highRange else None
        highAlarmPixel = self._calculateThresholdPixel(self.highAlarm) if self.highAlarm and self.highAlarm <= self.highRange else None
        
        # DEBUG: Print pixel positions for specific bars (limited to avoid spam)
        # Looking for CHT11 or OILP1, but checking actual bar names
        if hasattr(self, 'name'):
            # Check if this is a bar we're interested in
            debug_this = False
            if 'ted' in str(self.name):
                debug_this = True
            
            if debug_this:
                log.warning(f"=== {self.name} Bar Debug ===")
                log.warning(f"  Widget width: {widgetWidth}, self.width(): {self.width()}")
                log.warning(f"  Original self.barLeft: {self.barLeft}, self.barWidth: {self.barWidth}")
                log.warning(f"  Calculated barLeft: {barLeft}, barWidth: {barWidth} (using bar_width_percent={self.bar_width_percent})")
                log.warning(f"  Bar dimensions: top={barTop}, bottom={barBottom}, left={barLeft}, width={barWidth}, height={barBottom-barTop}")
                log.warning(f"  Range: {self.lowRange} to {self.highRange}")
                log.warning(f"  Thresholds: lowAlarm={self.lowAlarm}, lowWarn={self.lowWarn}, highWarn={self.highWarn}, highAlarm={self.highAlarm}")
                log.warning(f"  Threshold pixels: lowAlarm={lowAlarmPixel}, lowWarn={lowWarnPixel}, highWarn={highWarnPixel}, highAlarm={highAlarmPixel}")
        
        # Draw the bar in sections from top to bottom using integer coordinates
        currentTop = barTop

        # 1) Snap to device pixels (Python/PyQt)
        try:
            dpr = p.device().devicePixelRatioF()
        except Exception:
            try:
                dpr = self.devicePixelRatioF()
            except Exception:
                dpr = 1.0

        def snap(v: float) -> float:
            return round(v * dpr) / dpr

        # 2) Paint stacked bars with fillRect (no borders), AA off
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(Qt.PenStyle.NoPen)

        def draw_bar(x: float, y: float, w: float, h: float, color):
            snx = snap(x)
            sny = snap(y)
            snw = snap(w)
            snh = snap(h)
            # log.warning(f"  Snapped {self.name}: x={snx:.4f}, y={sny:.4f}, w={snw:.4f}, h={snh:.4f}")
            r = QRectF(snx, sny, snw, snh)
            p.fillRect(r, color)

        # Top alarm zone (high alarm)
        if highAlarmPixel is not None:
            alarmHeight = highAlarmPixel - currentTop
            if alarmHeight > 0:
                # DEBUG: Print alarm zone rect
                if hasattr(self, 'name'):
                    if 'ted' in str(self.name):
                        log.warning(f"  High Alarm rect: x={barLeft}, y={currentTop}, w={barWidth}, h={alarmHeight}")
                #p.setPen(Qt.PenStyle.NoPen)
                #p.setBrush(self.alarmColor)
                #p.drawRect(barLeft, currentTop, barWidth, alarmHeight)
                draw_bar(barLeft, currentTop, barWidth, alarmHeight, self.alarmColor)
                currentTop = highAlarmPixel
        
        # High warning zone
        if highWarnPixel is not None:
            warnHeight = highWarnPixel - currentTop
            if warnHeight > 0:
                # DEBUG: Print warning zone rect
                if hasattr(self, 'name'):
                    if 'ted' in str(self.name):
                        log.warning(f"  High Warn rect: x={barLeft}, y={currentTop}, w={barWidth}, h={warnHeight}")
                #p.setPen(Qt.PenStyle.NoPen)
                #p.setBrush(self.warnColor)
                #p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                draw_bar(barLeft, currentTop, barWidth, warnHeight, self.warnColor)
                currentTop = highWarnPixel
        
        # Safe zone (middle)
        safeBottom = lowWarnPixel if lowWarnPixel is not None else barBottom
        safeHeight = safeBottom - currentTop
        if safeHeight > 0:
            # DEBUG: Print safe zone rect
            if hasattr(self, 'name'):
                if 'ted' in str(self.name):
                    log.warning(f"  Safe Zone rect: x={barLeft}, y={currentTop}, w={barWidth}, h={safeHeight}")
            #p.setPen(Qt.PenStyle.NoPen)
            #p.setBrush(self.safeColor)
            #p.drawRect(barLeft, currentTop, barWidth, safeHeight)
            draw_bar(barLeft, currentTop, barWidth, safeHeight, self.safeColor)
            currentTop = safeBottom
        
        # Low warning zone
        if lowWarnPixel is not None:
            lowWarnBottom = lowAlarmPixel if lowAlarmPixel is not None else barBottom
            warnHeight = lowWarnBottom - currentTop
            if warnHeight > 0:
                if hasattr(self, 'name'):
                    if 'ted' in str(self.name):
                        log.warning(f"  Low Warn rect: x={barLeft}, y={currentTop}, w={barWidth}, h={warnHeight}")
                #p.setPen(Qt.PenStyle.NoPen)
                #p.setBrush(self.warnColor)
                #p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                draw_bar(barLeft, currentTop, barWidth, warnHeight, self.warnColor)
                currentTop = lowWarnBottom
        
        # Bottom alarm zone (low alarm)
        if lowAlarmPixel is not None:
            alarmHeight = barBottom - currentTop
            if alarmHeight > 0:
                if hasattr(self, 'name'):
                    if 'ted' in str(self.name):
                        log.warning(f"  Low Alarm rect: x={barLeft}, y={currentTop}, w={barWidth}, h={alarmHeight}")
                #p.setPen(Qt.PenStyle.NoPen)
                #p.setBrush(self.alarmColor)
                #p.drawRect(barLeft, currentTop, barWidth, alarmHeight)
                draw_bar(barLeft, currentTop, barWidth, alarmHeight, self.alarmColor)

        # Draw segments if needed (simplified)
        if self.segments > 1:  # Only draw if > 1
            segment_gap = self.barHeight * self.segment_gap_percent
            segment_size = (self.barHeight - (segment_gap * (self.segments - 1))) / self.segments
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)

            gap_height = max(1, int(round(segment_gap)))  # At least 1 pixel
            for segment in range(self.segments - 1):
                seg_top = int(self.barTop + round((segment + 1) * segment_size + segment * segment_gap))
                #p.drawRect(barLeft, seg_top, barWidth, gap_height)
                draw_bar(barLeft, seg_top, barWidth, gap_height, Qt.GlobalColor.black)
        
        # Highlight ball
        if self.highlight:
            pen.setColor(Qt.GlobalColor.black)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(self.highlightColor)
            p.drawEllipse(ballCenter, ballRadius, ballRadius)

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
            #p.drawRect(qRound(lineLeft), qRound(y - 2), qRound(lineWidth), qRound(4))

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
        
        valuePixelInt = int(valuePixel)
        
        if self.segments > 0:
            # Filled bar effect - darken above the value
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            darkenHeight = valuePixelInt - barTop
            if darkenHeight > 0:
                p.drawRect(barLeft, barTop, barWidth, darkenHeight)
        else:
            # Traditional line indicator
            p.drawRect(lineLeft, valuePixelInt - 2, lineWidth, 4)

        # Draw 1-pixel grey guide lines on the sides of the bar.
        # Left: full bar height; Right: tracks the top of the colored bar (current value).
        # p.save()
        # p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # p.setPen(Qt.PenStyle.NoPen)
        # p.setBrush(QColor(160, 160, 160))  # grey
        # # Left edge (full height)
        # p.drawRect(barLeft, barTop, 1, barBottom - barTop)
        # # Right edge (from current value to bottom)
        # right_x = barLeft + barWidth - 1
        # start_y = valuePixelInt if isinstance(valuePixelInt, int) else int(valuePixel)
        # # Clamp to bar bounds
        # if start_y < barTop:
        #     start_y = barTop
        # if start_y > barBottom:
        #     start_y = barBottom
        # p.drawRect(right_x, start_y, 1, barBottom - start_y)
        # p.restore()
