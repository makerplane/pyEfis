#  Copyright (c) 2018 Phil Birkelbach
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

class StaticText(QWidget):
    """Represents a simple static text display.  This is very simple and is
       really just here to keep the individual screens from having to have
       a painter object and a redraw event handler"""
    def __init__(self, text="", fontsize=1.0, color=QColor(Qt.white), parent=None):
        super(StaticText, self).__init__(parent)
        self.alignment = Qt.AlignCenter
        self.fontPercent = fontsize
        self.text = text
        self.color = color

    def resizeEvent(self, event):
        self.Font = QFont()
        self.Font.setPixelSize(self.height()*self.fontPercent)
        self.textRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Text
        pen.setColor(self.color)
        p.setPen(pen)
        p.setFont(self.Font)
        opt = QTextOption(self.alignment)
        p.drawText(self.textRect, self.text, opt)
