#  Copyright (c) 2026 Eric Blevins
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


from PyQt6.QtCore import Qt, qRound, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QTextOption
from PyQt6.QtWidgets import QWidget

from pyefis.screens import screenbuilder_layout


class GridOverlay(QWidget):
    def __init__(self, parent=None, layout=None):
        super(GridOverlay, self).__init__(parent)
        self.layout = layout
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.Font = QFont()

    def paintEvent(self, event):
        topm, leftm, rightm, bottomm = screenbuilder_layout.get_grid_margins(
            self.layout,
            self.width(),
            self.height(),
        )

        grid_width = (self.width() - leftm - rightm) / int(self.layout["columns"])
        grid_height = (self.height() - topm - bottomm) / int(self.layout["rows"])
        grid_x = leftm  # + grid_width)
        grid_y = topm  # + grid_height)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.red, 1))
        self.Font.setPixelSize(qRound(grid_height * 5))
        painter.setFont(self.Font)
        x = 0
        self.textRect = QRectF(int(0), int(0), qRound(grid_width), qRound(grid_height))
        while x <= int(self.layout["columns"]):
            grid_x = leftm + grid_width * (x)
            painter.setPen(QPen(QColor("#99ff0000"), 1))
            if (x) % 10 == 0:
                painter.setPen(QPen(QColor("#9900ff00"), 3))
                self.textRect = QRectF(grid_x, grid_y, grid_width * 10, grid_height * 5)
                painter.drawText(
                    self.textRect, str(x), QTextOption(Qt.AlignmentFlag.AlignCenter)
                )
                painter.setPen(QPen(QColor("#99ff0000"), 3))
            painter.drawLine(
                qRound(grid_x), qRound(grid_y), qRound(grid_x), self.height()
            )
            x += 5
        y = 0
        grid_x = leftm
        while y <= int(self.layout["rows"]):
            grid_y = topm + grid_height * (y)
            painter.setPen(QPen(QColor("#99ff0000"), 1))
            if (y) % 10 == 0:
                if y > 0:
                    painter.setPen(QPen(QColor("#9900ff00"), 3))
                    self.textRect = QRectF(
                        grid_x, grid_y, grid_width * 10, grid_height * 5
                    )
                    painter.drawText(
                        self.textRect, str(y), QTextOption(Qt.AlignmentFlag.AlignCenter)
                    )

                painter.setPen(QPen(QColor("#99ff0000"), 3))
            painter.drawLine(
                qRound(grid_x), qRound(grid_y), self.width(), qRound(grid_y)
            )
            y += 5
