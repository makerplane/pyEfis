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

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import fix
from .abstract import AbstractGauge

class NumericDisplay(AbstractGauge):
    """Represents a simple numeric display type gauge.  The benefit of using this
       over a normal text display is that this will change colors properly when
       limits are reached or when failures occur"""
    def __init__(self, parent=None):
        super(NumericDisplay, self).__init__(parent)
        self.alignment = Qt.AlignLeft | Qt.AlignVCenter
        self.unitsAlignment = Qt.AlignRight  | Qt.AlignVCenter
        self.showUnits = False
        self.smallFontPercent = 0.4

    def resizeEvent(self, event):
        self.bigFont = QFont()
        self.bigFont.setPixelSize(self.height())
        self.smallFont = QFont()
        self.smallFont.setPixelSize(self.height() * self.smallFontPercent)

        self.valueTextRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Value
        pen.setColor(self.valueColor)
        p.setPen(pen)
        p.setFont(self.bigFont)
        opt = QTextOption(self.alignment)
        p.drawText(self.valueTextRect, self.valueText, opt)

        # Draw Units
        p.setFont(self.smallFont)
        opt = QTextOption(self.unitsAlignment)
        p.drawText(self.valueTextRect, self.units, opt)
