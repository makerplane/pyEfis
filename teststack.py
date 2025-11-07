#!/usr/bin/env python3
"""
Test program to visualize vertical bar gauges with color bands.
This replicates the drawing logic from verticalBarImproved.py in a simple standalone test.
"""

import sys
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRectF

# ===== ADJUSTABLE CONSTANTS =====
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

# Bar configuration
BAR_COUNT = 6  # Number of bars to display side by side
BAR_WIDTH = 20
BAR_HEIGHT = 160
BAR_SPACING = 20  # Space between bars
BAR_START_X = 50  # Left margin
BAR_START_Y = 100  # Top margin

# Simulate widget height variations (each bar might be slightly different height in pyEfis)
# This simulates how different widgets might round font sizes differently
WIDGET_HEIGHTS = [160, 160, 160, 160, 160, 160]  # Slight variations
SHOW_NAME = True
SHOW_VALUE = True
SHOW_UNITS = True
TEXT_GAP = 3
SMALL_FONT_PERCENT = 0.08
BIG_FONT_PERCENT = 0.10

# Value range
LOW_RANGE = 0
HIGH_RANGE = 300

# Thresholds (temperatures in °C for CHT example)
LOW_ALARM = 50
LOW_WARN = 85
HIGH_WARN = 204
HIGH_ALARM = 232

# Current value to display
CURRENT_VALUE = 180

# Colors
SAFE_COLOR = QColor("#00FF00") #Qt.GlobalColor.green #QColor(0, 255, 0)      # Green
WARN_COLOR = QColor("#FFFF00") #Qt.GlobalColor.yellow #QColor(255, 255, 0)    # Yellow
ALARM_COLOR = QColor("#FF0000") #Qt.GlobalColor.red #QColor(255, 0, 0)     # Red
BG_COLOR = QColor(40, 40, 40) #Qt.GlobalColor.black #QColor(40, 40, 40)       # Dark gray background

# Font
FONT_FAMILY = "DejaVu Sans Condensed"
FONT_SIZE = 12


class VerticalBarTest(QWidget):
    """Simple widget that draws vertical bars with color bands."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vertical Bar Alignment Test")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(f"background-color: rgb({BG_COLOR.red()}, {BG_COLOR.green()}, {BG_COLOR.blue()});")
        
    def _calculateBarDimensions(self, widgetHeight):
        """
        Calculate bar dimensions the same way pyEfis does in verticalBar.py resizeEvent.
        This is where the variability comes from!
        """
        from PyQt6.QtCore import qRound
        
        # Calculate font sizes based on widget height (like pyEfis does)
        smallFontPixelSize = qRound(widgetHeight * SMALL_FONT_PERCENT)
        bigFontPixelSize = qRound(widgetHeight * BIG_FONT_PERCENT)
        
        # Calculate barTop (depends on font size!)
        if SHOW_NAME:
            barTop = smallFontPixelSize + TEXT_GAP
        else:
            barTop = 1
        
        # Calculate barBottom
        barBottom = widgetHeight
        if SHOW_VALUE:
            barBottom -= (bigFontPixelSize + TEXT_GAP)
        if SHOW_UNITS:
            barBottom -= (smallFontPixelSize + TEXT_GAP)
        
        barHeight = barBottom - barTop
        
        return barTop, barBottom, barHeight, smallFontPixelSize, bigFontPixelSize
    
    def _calculateThresholdPixel(self, value, barTop, barBottom):
        """
        Calculate pixel position for a threshold value with consistent rounding.
        Returns absolute pixel position from top of window.
        
        Uses integer arithmetic throughout to ensure consistent positioning.
        """
        if value is None or HIGH_RANGE == LOW_RANGE:
            return None
        
        # Use integer barHeight to ensure consistent calculations
        barHeight = int(barBottom - barTop)
        if barHeight <= 0:
            return None
        
        # Calculate normalized position (0.0 to 1.0)
        normalized = (value - LOW_RANGE) / (HIGH_RANGE - LOW_RANGE)
        normalized = max(0.0, min(1.0, normalized))  # Clamp to valid range
        
        # Convert to pixel position using integer math for consistency
        # Scale by 1000 to maintain precision, then divide back
        scaledPosition = int(normalized * 1000)
        pixelFromBottom = (scaledPosition * barHeight) // 1000
        pixelFromTop = barHeight - pixelFromBottom
        
        # Add barTop offset as integer
        return int(barTop) + pixelFromTop
    
    def _drawSingleBar(self, p, barLeft, barIndex, barLabel):
        """Draw a single vertical bar with color bands."""
        
        # Get the widget height for this bar (simulating different widget sizes)
        widgetHeight = WIDGET_HEIGHTS[barIndex] if barIndex < len(WIDGET_HEIGHTS) else BAR_HEIGHT
        
        # Calculate bar dimensions the same way pyEfis does
        barTopCalc, barBottomCalc, barHeightCalc, smallFont, bigFont = self._calculateBarDimensions(widgetHeight)
        
        # Position this bar at the correct Y location
        barTop = BAR_START_Y + barTopCalc
        barBottom = BAR_START_Y + barBottomCalc
        
        # Convert to integers for pixel-perfect alignment
        barTop = int(barTop)
        barBottom = int(barBottom)
        barLeft = int(barLeft)
        barWidth = int(BAR_WIDTH)
        
        # Calculate all threshold positions once with consistent rounding
        lowAlarmPixel = self._calculateThresholdPixel(LOW_ALARM, barTop, barBottom) if LOW_ALARM and LOW_ALARM >= LOW_RANGE else None
        lowWarnPixel = self._calculateThresholdPixel(LOW_WARN, barTop, barBottom) if LOW_WARN and LOW_WARN >= LOW_RANGE else None
        highWarnPixel = self._calculateThresholdPixel(HIGH_WARN, barTop, barBottom) if HIGH_WARN and HIGH_WARN <= HIGH_RANGE else None
        highAlarmPixel = self._calculateThresholdPixel(HIGH_ALARM, barTop, barBottom) if HIGH_ALARM and HIGH_ALARM <= HIGH_RANGE else None
        
        # Print debug info for first bar
        if barLabel == "BAR1":
            print(f"\n=== {barLabel} Debug ===")
            print(f"  Widget height: {widgetHeight}")
            print(f"  Small font size: {smallFont}, Big font size: {bigFont}")
            print(f"  Bar dimensions: top={barTop}, bottom={barBottom}, left={barLeft}, width={barWidth}, height={barBottom-barTop}")
            print(f"  Range: {LOW_RANGE} to {HIGH_RANGE}")
            print(f"  Thresholds: lowAlarm={LOW_ALARM}, lowWarn={LOW_WARN}, highWarn={HIGH_WARN}, highAlarm={HIGH_ALARM}")
            print(f"  Threshold pixels: lowAlarm={lowAlarmPixel}, lowWarn={lowWarnPixel}, highWarn={highWarnPixel}, highAlarm={highAlarmPixel}")
        
        # Print comparison for other bars
        if barIndex > 0:
            prevWidgetHeight = WIDGET_HEIGHTS[barIndex - 1] if (barIndex - 1) < len(WIDGET_HEIGHTS) else BAR_HEIGHT
            prevTop, prevBottom, prevHeight, _, _ = self._calculateBarDimensions(prevWidgetHeight)
            if barTopCalc != prevTop or barBottomCalc != prevBottom:
                print(f"  WARNING: {barLabel} has different dimensions than previous bar!")
                print(f"    This bar: top={barTopCalc}, bottom={barBottomCalc}, height={barHeightCalc}")
                print(f"    Prev bar: top={prevTop}, bottom={prevBottom}, height={prevHeight}")
                print(f"    Difference: top={barTopCalc - prevTop}, bottom={barBottomCalc - prevBottom}, height={barHeightCalc - prevHeight}")
        
        # Setup pen for drawing
        pen = QPen()
        pen.setWidth(0)
        #pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        
        # Disable antialiasing for pixel-perfect rendering
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Draw the bar in sections from top to bottom using integer coordinates
        currentTop = barTop
        
        # Top alarm zone (high alarm)
        if highAlarmPixel is not None:
            alarmHeight = highAlarmPixel - currentTop
            if alarmHeight > 0:
                if barLabel == "BAR1":
                    print(f"  High Alarm rect: x={barLeft}, y={currentTop}, w={barWidth}, h={alarmHeight}")
                pen.setColor(ALARM_COLOR)
                p.setPen(pen)
                p.setBrush(ALARM_COLOR)
                #p.drawRect(barLeft, currentTop, barWidth, alarmHeight)
                p.fillRect(QRectF(barLeft, currentTop, barWidth, alarmHeight),ALARM_COLOR) 
                currentTop = highAlarmPixel
        
        # High warning zone
        if highWarnPixel is not None:
            warnHeight = highWarnPixel - currentTop
            if warnHeight > 0:
                if barLabel == "BAR1":
                    print(f"  High Warn rect: x={barLeft}, y={currentTop}, w={barWidth}, h={warnHeight}")
                pen.setColor(WARN_COLOR)
                p.setPen(pen)
                p.setBrush(WARN_COLOR)
                #p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                p.fillRect(QRectF(barLeft, currentTop, barWidth, warnHeight), WARN_COLOR)
                currentTop = highWarnPixel
        
        # Safe zone (middle)
        safeBottom = lowWarnPixel if lowWarnPixel is not None else barBottom
        safeHeight = safeBottom - currentTop
        if safeHeight > 0:
            if barLabel == "BAR1":
                print(f"  Safe Zone rect: x={barLeft}, y={currentTop}, w={barWidth}, h={safeHeight}")
            pen.setColor(SAFE_COLOR)
            p.setPen(pen)
            p.setBrush(SAFE_COLOR)
            #p.drawRect(barLeft, currentTop, barWidth, safeHeight)
            p.fillRect(QRectF(barLeft, currentTop, barWidth, safeHeight), SAFE_COLOR)
            currentTop = safeBottom
        
        # Low warning zone
        if lowWarnPixel is not None:
            lowWarnBottom = lowAlarmPixel if lowAlarmPixel is not None else barBottom
            warnHeight = lowWarnBottom - currentTop
            if warnHeight > 0:
                if barLabel == "BAR1":
                    print(f"  Low Warn rect: x={barLeft}, y={currentTop}, w={barWidth}, h={warnHeight}")
                pen.setColor(WARN_COLOR)
                p.setPen(pen)
                p.setBrush(WARN_COLOR)
                #p.drawRect(barLeft, currentTop, barWidth, warnHeight)
                p.fillRect(QRectF(barLeft, currentTop, barWidth, warnHeight), WARN_COLOR)
                currentTop = lowWarnBottom
        
        # Bottom alarm zone (low alarm)
        if lowAlarmPixel is not None:
            alarmHeight = barBottom - currentTop
            if alarmHeight > 0:
                if barLabel == "BAR1":
                    print(f"  Low Alarm rect: x={barLeft}, y={currentTop}, w={barWidth}, h={alarmHeight}")
                pen.setColor(ALARM_COLOR)
                p.setPen(pen)
                p.setBrush(ALARM_COLOR)
                #p.drawRect(barLeft, currentTop, barWidth, alarmHeight)
                p.fillRect(QRectF(barLeft, currentTop, barWidth, alarmHeight), ALARM_COLOR)
        
        # Draw current value indicator
        # valuePixel = self._calculateThresholdPixel(CURRENT_VALUE, barTop, barBottom)
        # if valuePixel is not None:
        #     pen.setColor(QColor(255, 255, 255))  # White
        #     pen.setWidth(2)
        #     p.setPen(pen)
        #     lineLeft = barLeft - 5
        #     lineRight = barLeft + barWidth + 5
        #     p.drawLine(lineLeft, int(valuePixel), lineRight, int(valuePixel))
        
        # Draw label below bar
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen.setColor(QColor(255, 255, 255))
        pen.setWidth(1)
        p.setPen(pen)
        font = QFont(FONT_FAMILY, FONT_SIZE)
        p.setFont(font)
        labelRect = QRectF(barLeft - 10, barBottom + 10, barWidth + 20, 30)
        p.drawText(labelRect, Qt.AlignmentFlag.AlignCenter, barLabel)
        
        # Draw threshold labels
        #font.setPointSize(FONT_SIZE - 2)
        #p.setFont(font)
        #if HIGH_ALARM and highAlarmPixel:
        #    p.drawText(barLeft + barWidth + 5, highAlarmPixel + 5, f"{HIGH_ALARM}°C")
        #if HIGH_WARN and highWarnPixel:
        #    p.drawText(barLeft + barWidth + 5, highWarnPixel + 5, f"{HIGH_WARN}°C")
    
    def paintEvent(self, event):
        """Paint all the bars."""
        p = QPainter(self)
        
        # Draw title
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(255, 255, 255))
        p.setPen(pen)
        font = QFont(FONT_FAMILY, 16, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(20, 40, "Vertical Bar Alignment Test")
        
        font.setPointSize(12)
        p.setFont(font)
        p.drawText(20, 60, f"Value: {CURRENT_VALUE}°C  |  Warn: {HIGH_WARN}°C  |  Alarm: {HIGH_ALARM}°C")
        
        # Draw multiple bars side by side
        for i in range(BAR_COUNT):
            barLeft = BAR_START_X + i * (BAR_WIDTH + BAR_SPACING)
            barLabel = f"BAR{i+1}"
            self._drawSingleBar(p, barLeft, i, barLabel)
        
        # Draw alignment grid lines to help visualize
        # p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # pen.setColor(QColor(80, 80, 80))
        # pen.setWidth(1)
        # pen.setStyle(Qt.PenStyle.DotLine)
        # p.setPen(pen)
        
        # Draw horizontal grid lines at threshold positions for each bar
        # for i in range(BAR_COUNT):
        #     widgetHeight = WIDGET_HEIGHTS[i] if i < len(WIDGET_HEIGHTS) else BAR_HEIGHT
        #     barTopCalc, barBottomCalc, _, _, _ = self._calculateBarDimensions(widgetHeight)
        #     barTop = int(BAR_START_Y + barTopCalc)
        #     barBottom = int(BAR_START_Y + barBottomCalc)
            
        #     highWarnPixel = self._calculateThresholdPixel(HIGH_WARN, barTop, barBottom)
        #     highAlarmPixel = self._calculateThresholdPixel(HIGH_ALARM, barTop, barBottom)
            
        #     barLeft = BAR_START_X + i * (BAR_WIDTH + BAR_SPACING)
            
        #     # Draw line across this bar only
        #     if highWarnPixel:
        #         p.drawLine(barLeft, highWarnPixel, barLeft + BAR_WIDTH, highWarnPixel)
        #     if highAlarmPixel:
        #         p.drawLine(barLeft, highAlarmPixel, barLeft + BAR_WIDTH, highAlarmPixel)


def main():
    """Main entry point."""
    print("=" * 60)
    print("Vertical Bar Alignment Test - SIMULATING PYEFIS LOGIC")
    print("=" * 60)
    print(f"Window: {WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    print(f"Bars: {BAR_COUNT} bars, {BAR_WIDTH}px wide")
    print(f"Widget heights: {WIDGET_HEIGHTS} (simulating slight variations)")
    print(f"Range: {LOW_RANGE} to {HIGH_RANGE}")
    print(f"Thresholds: Warn={HIGH_WARN}, Alarm={HIGH_ALARM}")
    print(f"Current Value: {CURRENT_VALUE}")
    print(f"Font percents: small={SMALL_FONT_PERCENT}, big={BIG_FONT_PERCENT}")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    window = VerticalBarTest()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
