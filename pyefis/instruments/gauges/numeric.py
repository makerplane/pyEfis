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
from pyefis.instruments import helpers

class NumericDisplay(AbstractGauge):
    """Represents a simple numeric display type gauge.  The benefit of using this
       over a normal text display is that this will change colors properly when
       limits are reached or when failures occur"""
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(NumericDisplay, self).__init__(parent)
        self.font_family = font_family
        self.alignment = Qt.AlignLeft | Qt.AlignVCenter
        self.unitsAlignment = Qt.AlignRight  | Qt.AlignVCenter
        self.showUnits = False
        self.smallFontPercent = 0.4
        self.units_font_mask = None

    def resizeEvent(self, event):
        self.font_size = self.height()
        
        if self.font_mask:
            self.font_size = helpers.fit_to_mask(self.width(),self.height(),self.font_mask,self.font_family,self.units_font_mask,self.smallFontPercent)
        self.bigFont = QFont(self.font_family)
        self.bigFont.setPointSizeF(self.font_size)
        self.smallFont = QFont(self.font_family)
        self.smallFont.setPointSizeF(qRound(self.font_size * self.smallFontPercent))
        qm = QFontMetrics(self.smallFont)
        unitsWidth = qm.width(self.units)

        if self.showUnits:
            # TODO Edit to get the units closer to the value 
            self.valueTextRect = QRectF(0, 0, self.width()-unitsWidth-5, self.height())
            self.unitsTextRect = QRectF(self.valueTextRect.width(), 0,
                                        self.width()-self.valueTextRect.width(), self.height())
        else:
            self.valueTextRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Value
        p.setFont(self.bigFont)
        opt = QTextOption(self.alignment)
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

        # Draw Units
        if self.showUnits:
            p.setFont(self.smallFont)
            opt = QTextOption(self.unitsAlignment)
            p.drawText(self.unitsTextRect, self.units, opt)
