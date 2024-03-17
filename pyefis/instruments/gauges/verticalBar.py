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

class VerticalBar(AbstractGauge):
    def __init__(self, parent=None,min_size=True, font_family="DejaVu Sans Condensed"):
        super(VerticalBar, self).__init__(parent)
        self.font_family = font_family
        if min_size:
            self.setMinimumSize(50, 100)
        self.showValue = True
        self.showUnits = True
        self.showName = True
        self.bar_width_percent = 0.3
        self.line_width_percent = 0.5
        self.textGap = 3
        self.smallFontPercent = 0.08
        self.big_font_percent = 0.10
        self.normalizePenColor = QColor(Qt.blue)
        self.normalize_range = 0
        self.normalizeReference = 0
        self._normalizeMode = False
        self.peakValue = 0.0
        self._peakMode = False
        self.peakColor = QColor(Qt.magenta)
        self._oldpencolor = self.penGoodColor
        self.segments = 0
        self.segment_gap_percent = 0.012
        self.segment_alpha = 180

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 0.35

    def getNormalizeMode(self):
        return self._normalizeMode

    def setNormalizeMode(self, x):
        if x:
            if self._normalizeMode: return
            self._normalizeMode = True
            self._oldpencolor = self.penGoodColor
            self.penGoodColor = self.normalizePenColor
            self.normalizeReference = self.value
        else:
            self._normalizeMode = False
            self.penGoodColor = self._oldpencolor
        self.setColors()
        self.update()

    normalizeMode = property(getNormalizeMode, setNormalizeMode)

    def getPeakMode(self):
        return self._peakMode

    def setPeakMode(self, x):
        if x:
            self._peakMode = True
        else:
            self._peakMode = False
        self.update()

    peakMode = property(getPeakMode, setPeakMode)


    def setMode(self, args):
        print(f"Seting mode for {self._dbkey}")
        if args.lower() == "normalize":
                self.normalizeMode = not self._normalizeMode
        elif args.lower() == "peak":
                self.peakMode = not self._peakMode
        elif args.lower() == "reset peak":
                self.resetPeak()
        elif args.lower() == "lean":
                self.resetPeak()
                self.normalizeMode = True
                self.peakMode = True
        elif args.lower() == "normal":
                self.normalizeMode = False
                self.peakMode = False



    def resizeEvent(self, event):
        self.barWidth = self.width() * self.bar_width_percent
        self.lineWidth = self.width() * self.line_width_percent
        self.bigFont = QFont(self.font_family)
        self.bigFont.setPixelSize(qRound(self.height() * self.big_font_percent))
        self.smallFont = QFont(self.font_family)
        self.smallFont.setPixelSize(qRound(self.height() * self.smallFontPercent))
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

        self.barLeft = (self.width() - self.barWidth) / 2
        self.barRight = self.barLeft + self.barWidth
        self.lineLeft = (self.width() - self.lineWidth) / 2
        self.lineRight = self.lineLeft + self.lineWidth
        self.barHeight = self.barBottom - self.barTop

        self.nameTextRect = QRectF(0, 0, self.width(), self.smallFont.pixelSize())
        self.valueTextRect = QRectF(0, self.barBottom + self.textGap, self.width(), self.bigFont.pixelSize())
        self.unitsTextRect = QRectF(0, self.height() - self.smallFont.pixelSize() - self.textGap, self.width(), self.smallFont.pixelSize() + self.textGap)
        self.ballRadius = self.barWidth * 0.40
        self.ballCenter = QPointF(self.barLeft + (self.barWidth / 2), self.barBottom - (self.barWidth/2))

    def drawValue(self, p, pen):
        pen.setColor(self.valueColor)
        p.setPen(pen)
        p.setFont(self.bigFont)
        p.drawText(self.valueTextRect, self.valueText, QTextOption(Qt.AlignCenter))

    def paintEvent(self, event):
        if self.highlight_key:
            if self._highlightValue == self._rawValue:
                self.highlight = True
            else:
                self.highlight = False

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
                # Draw Value
                self.drawValue(p, pen)
        if self.showUnits:
            # Units
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.setFont(self.smallFont)
            p.drawText(self.unitsTextRect, self.units, opt)

        # Draws the bar
        p.setRenderHint(QPainter.Antialiasing, False)
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(QRectF(self.barLeft, self.barTop, self.barWidth, self.barHeight))

        # Draw Warning Bands
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn and self.lowWarn >= self.lowRange):
            x = self.interpolate(self.lowWarn, self.barHeight)
            p.drawRect(QRectF(self.barLeft, self.barBottom - x,
                              self.barWidth,
                              x + 1))
        if(self.highWarn and self.highWarn <= self.highRange):
            p.drawRect(QRectF(self.barLeft, self.barTop,
                              self.barWidth,
                              self.barHeight - self.interpolate(self.highWarn, self.barHeight)))

        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm and self.lowAlarm >= self.lowRange):
            x = self.interpolate(self.lowAlarm, self.barHeight)
            p.drawRect(QRectF(self.barLeft, self.barBottom - x,
                              self.barWidth,
                              x + 1))
        if(self.highAlarm and self.highAlarm <= self.highRange):
            p.drawRect(QRectF(self.barLeft, self.barTop,
                              self.barWidth,
                              self.barHeight - self.interpolate(self.highAlarm, self.barHeight)))

        # Draw black bars to create segments
        if self.segments > 0:
            segment_gap = self.barHeight * self.segment_gap_percent
            segment_size = (self.barHeight - (segment_gap * (self.segments - 1)))/self.segments
            p.setRenderHint(QPainter.Antialiasing, False)
            pen.setColor(Qt.black)
            p.setPen(pen)
            p.setBrush(Qt.black)
            for segment in range(self.segments - 1):
                seg_top = self.barTop + ((segment + 1) * segment_size) + (segment * segment_gap)
                p.drawRect(QRectF(self.barLeft, seg_top, self.barWidth, segment_gap))
        # Highlight Ball
        if self.highlight:
            pen.setColor(Qt.black)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(self.highlightColor)
            p.drawEllipse(self.ballCenter, self.ballRadius, self.ballRadius)


        # Draw Peak Value Line and text
        if self.peakMode:
            pen.setColor(QColor(Qt.white))
            brush = QBrush(self.peakColor)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(brush)
            if self.normalizeMode:
                nval = self.peakValue - self.normalizeReference
                start = self.barTop + self.barHeight / 2
                y = start - (nval * self.barHeight / self.normalize_range)
            else:
                y = self.barTop + (self.barHeight - self.interpolate(self.peakValue, self.barHeight))
            if y < self.barTop: y = self.barTop
            if y > self.barBottom: y = self.barBottom
            p.drawRect(qRound(self.lineLeft), qRound(y-2), qRound(self.lineWidth), qRound(4))

        # Indicator Line
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setBrush(brush)
        if self.normalizeMode:
            pen.setColor(QColor(Qt.gray))
            p.setPen(pen)
            nval = self._value - self.normalizeReference
            start = self.barTop + self.barHeight / 2
            x = start - (nval * self.barHeight / self.normalize_range)
        else:
            pen.setColor(QColor(Qt.darkGray))
            p.setPen(pen)
            x = self.barTop + (self.barHeight - self.interpolate(self._value, self.barHeight))
        if x < self.barTop: x = self.barTop
        if x > self.barBottom: x = self.barBottom
        if not self.segments > 0:
            p.drawRect(QRectF(self.lineLeft, x-2,self.lineWidth, 4))
        else:
            # IF segmented, darken the top part of the bars from the line up
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            p.drawRect(QRectF(self.barLeft, self.barTop, self.barWidth, x - self.barTop))

