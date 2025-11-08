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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *


from .abstract import AbstractGauge
from pyefis.instruments import helpers

class HorizontalBar(AbstractGauge):
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super(HorizontalBar, self).__init__(parent)
        self.font_family = font_family
        if min_size:
            self.setMinimumSize(100, 50)
        self.show_value = True
        self.show_units = True
        self.show_name = True
        self.segments = 0 
        self.segment_gap_percent = 0.01
        self.segment_alpha = 180
        self.bar_divisor = 4.5
        # New options: place value/dbkey text on the left side of the bar
        self.value_on_bar_left = False
        self.value_on_bar_left_width_percent = 0.25  # portion of width reserved for left label
        self.show_dbkey_text = False  # when true, show dbkey text instead of numeric value on left label
        # Internals computed on resize
        self._bar_left = 0
        self._bar_width = 0
        self.barValueRect = QRectF()
    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 2

    def resizeEvent(self, event):
        self.bigFont = QFont(self.font_family)
        self.section_size = self.height() / 12
        self.bigFont.setPixelSize( qRound(self.section_size * 4))
        if self.font_mask:
            self.bigFont.setPointSizeF(helpers.fit_to_mask(self.width()-5, self.section_size * 4, self.font_mask, self.font_family))
        self.smallFont = QFont(self.font_family)
        self.smallFont.setPixelSize(qRound(self.section_size * 2))
        if self.name_font_mask:
            self.smallFont.setPointSizeF(helpers.fit_to_mask(self.width(), self.section_size * 2.4, self.name_font_mask, self.font_family))
        self.unitsFont = QFont(self.font_family)
        self.unitsFont.setPixelSize(qRound(self.section_size * 2))
        if self.units_font_mask:
            self.unitsFont.setPointSizeF(helpers.fit_to_mask(self.width(), self.section_size * 2.4, self.name_font_mask, self.font_family))

        self.barHeight = self.section_size * self.bar_divisor
        self.barTop = self.section_size * 2.7
        self.nameTextRect = QRectF(1, 0, self.width(), self.section_size * 2.4)
        self.valueTextRect = QRectF(1, self.section_size * 8, self.width()-5, self.section_size * 4)
        # Geometry is recalculated in paintEvent as well to reflect dynamic late-applied flags
        self._recompute_geometry()

    def _recompute_geometry(self):
        """Recalculate geometry based on current flags.
        Called in resizeEvent and paintEvent to handle preferences applied after initial resize."""
        self._bar_left = 0
        self._bar_width = self.width()
        if self.value_on_bar_left:
            pct = max(0.05, min(0.5, float(getattr(self, 'value_on_bar_left_width_percent', 0.25) or 0.25)))
            left_w = int(self.width() * pct)
            gap = 4
            self.barValueRect = QRectF(2, self.barTop, max(0, left_w - gap), self.barHeight)
            self._bar_left = left_w
            self._bar_width = max(0, self.width() - self._bar_left)
        else:
            self.barValueRect = QRectF()

    def get_bar_geometry(self):
        """Return (left, top, width, height) for the drawable bar region, respecting left label space."""
        return (int(self._bar_left), int(self.barTop), int(self._bar_width), int(self.barHeight))

    def paintEvent(self, event):
        # Ensure geometry reflects any preference attributes set after construction
        self._recompute_geometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        #pen.setColor(self.textColor)
        #p.setPen(pen)
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

        # Units
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

        # Main Value (standard position) unless moved to left of bar
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
            # Draw value or dbkey as a label area to the left of the bar
            label_text = self.dbkey if self.show_dbkey_text else self.valueText
            p.setFont(self.bigFont)
            pen.setColor(self.valueColor if not self.show_dbkey_text else self.textColor)
            p.setPen(pen)
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.drawText(self.barValueRect, label_text, opt_left)

        # Draws the bar
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        bar_left, bar_top, bar_width, bar_height = self.get_bar_geometry()
        p.drawRect(QRectF(bar_left, bar_top, bar_width, bar_height))
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn):
            p.drawRect(QRectF(bar_left, bar_top,
                              self.interpolate(self.lowWarn, bar_width),
                              bar_height))
        if(self.highWarn):
            x = bar_left + self.interpolate(self.highWarn, bar_width)
            p.drawRect(QRectF(x, bar_top,
                              (bar_left + bar_width) - x, bar_height))
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm):
            p.drawRect(QRectF(bar_left, bar_top,
                              self.interpolate(self.lowAlarm, bar_width),
                              bar_height))
        if(self.highAlarm):
            x = bar_left + self.interpolate(self.highAlarm, bar_width)
            p.drawRect(QRectF(x, bar_top,
                              (bar_left + bar_width) - x, bar_height))


        # Draw black bars to create segments
        if self.segments > 0:
            segment_gap = bar_width * self.segment_gap_percent
            segment_size = (bar_width - (segment_gap * (self.segments - 1)))/self.segments
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)
            for segment in range(self.segments - 1):
                seg_left = bar_left + (((segment + 1) * segment_size) + (segment * segment_gap))
                p.drawRect(QRectF(seg_left, bar_top, segment_gap, bar_height))

        # Indicator Line
        pen.setColor(QColor(Qt.GlobalColor.darkGray))
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        x = bar_left + self.interpolate(self._value, bar_width)
        if x < 0: x = 0
        if x > (bar_left + bar_width): x = (bar_left + bar_width)
        if not self.segments > 0:
            p.drawRect(QRectF(x-2, bar_top-4, 4, bar_height+8))
        else:
            # IF segmented, darken the top part of the bars from the line up
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            p.drawRect(QRectF(x, bar_top, (bar_left + bar_width) - x, bar_height))

