#  Copyright (c) 2013 Neil Domalik, Phil Birkelbach
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
import math
import fix

class TurnCoordinator(QWidget):
    def __init__(self, parent=None):
        super(TurnCoordinator, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._rate = 0.0
        self._latAcc = 0.0
        item = fix.db.get_item("YAW", True) # find the correct Value.
        item.valueChanged[float].connect(self.setLatAcc)

    def resizeEvent(self, event):
        self.tick_thickness = self.height() / 32
        self.tick_length = self.width() / 12
        self.background = QPixmap(self.width(), self.height())

        p = QPainter(self.background)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(Qt.white))
        pen.setWidth(2)
        brush = QBrush(QColor(Qt.white))
        p.setPen(pen)
        self.center = QPointF(p.device().width() / 2, p.device().height() / 2)
        self.r = min(self.width(), self.height()) / 2 - 25

        p.fillRect(0, 0, self.width(), self.height(), Qt.black)
        p.drawEllipse(self.center, self.r, self.r)

        # this draws the tick boxes
        thickness = self.tick_thickness
        length = self.tick_length
        rect = QRect(-(self.r), 0 - thickness / 2,
                     length, thickness)
        p.setBrush(brush)
        p.save()
        p.translate(self.center)
        p.drawRect(rect)
        p.rotate(-30)
        p.drawRect(rect)
        p.rotate(210)
        p.drawRect(rect)
        p.rotate(30)
        p.drawRect(rect)
        p.restore()

        # TC Box
        self.boxHalfWidth = (self.r - length) * math.cos(math.radians(30))
        self.boxTop = self.center.y() + (self.r - length) * (
                      math.sin(math.radians(30))) + thickness
        rect = QRect(QPoint(self.center.x() - self.boxHalfWidth, self.boxTop),
                     QPoint(self.center.x() + self.boxHalfWidth,
                            self.boxTop + length))
        p.drawRect(rect)
        # Draw the little airplane center
        p.drawEllipse(self.center, thickness, thickness)
        # vertical black lines on TC
        pen.setColor(QColor(Qt.black))
        pen.setWidth(4)
        p.setPen(pen)
        p.drawLine(self.center.x() - length + 8, self.boxTop,
                   self.center.x() - length + 8, self.boxTop + length + 2)
        p.drawLine(self.center.x() + length - 8, self.boxTop,
                   self.center.x() + length - 8, self.boxTop + length + 2)

    def paintEvent(self, event):

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Just to make it a bit easier
        thickness = self.tick_thickness
        length = self.tick_length

        # Insert Background
        p.drawPixmap(0, 0, self.background)

        # Draw TC Ball
        pen = QPen(QColor(Qt.black))
        brush = QBrush(QColor(Qt.black))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(brush)
        centerball = self.center.x() + (self.boxHalfWidth - length / 2) * (self._latAcc / 5)
        if centerball < 83.3 or centerball > 257.7 :
            if centerball > 257.7: centerball = 257.7
            else: centerball = 83.3
        center = QPointF(centerball,
                         self.boxTop + length / 2)
        p.drawEllipse(center, length / 2, length / 2)

        # the little airplane
        pen.setColor(QColor(Qt.white))
        brush.setColor(QColor(Qt.white))
        p.setPen(pen)
        p.setBrush(brush)

        x = self.r - length - thickness / 2
        poly = QPolygon([QPoint(0, -thickness / 3),
                         QPoint(-x, -thickness / 8),
                         QPoint(-x, thickness / 8),
                         QPoint(0, thickness / 3),
                         QPoint(x, thickness / 8),
                         QPoint(x, -thickness / 8)])
        p.translate(self.center)
        p.rotate(self._rate * 10)
        p.drawPolygon(poly)
        pen.setWidth(2)
        p.setPen(pen)
        p.drawLine(-length / 2, -length / 2, length / 2, -length / 2)
        p.drawLine(0, 0, 0, -length)

    def getTurnRate(self):
        return self._rate

    def setTurnRate(self, rate):
        if rate != self._rate:
            self._rate = rate
            self.update()

    turnRate = property(getTurnRate, setTurnRate)

    def getLatAcc(self):
        return self._latAcc

    def setLatAcc(self, acc):
        if acc != self._latAcc:
            self._latAcc = acc
            self.update()

    latAcc = property(getLatAcc, setLatAcc)

class TurnCoordinator_Tape(QWidget):
    def __init__(self, parent=None):
        super(TurnCoordinator_Tape, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(32, 32, 32, 75%)")
        self.setFocusPolicy(Qt.NoFocus)
        self._rate = 0.0
        self._latAcc = 0.0

    def resizeEvent(self, event):
        self.tick_thickness = self.height() / 2
        self.tick_length = self.width() / 2
        self.background = QPixmap(self.width(), self.height())

        p = QPainter(self.background)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(Qt.white))
        pen.setWidth(2)
        brush = QBrush(QColor(Qt.white))
        p.setPen(pen)
        self.center = QPointF(p.device().width() / 2, p.device().height() / 2)
        self.r = min(self.width(), self.height()) / 2 - 25

        # this draws the tick boxes
        thickness = self.tick_thickness
        length = self.tick_length
        rect = QRect(-(self.r), 0 - thickness / 2,
                     length, thickness)
        p.setBrush(brush)
        p.save()
        p.translate(self.center)
        p.restore()

        # TC Box
        self.boxHalfWidth = (self.r - length) * math.cos(math.radians(30))
        self.boxTop = self.center.y() + (self.r -
                      length) * math.sin(math.radians(30)) + thickness
        rect = QRect(QPoint(self.center.x() - self.boxHalfWidth, self.boxTop),
                     QPoint(self.center.x() + self.boxHalfWidth,
                            self.boxTop + length))
        p.drawRect(rect)
        #Draw the little airplane center
        p.drawEllipse(self.center, thickness, thickness)
        # vertical black lines on TC
        pen.setColor(QColor(Qt.black))
        pen.setWidth(4)
        p.setPen(pen)
        p.drawLine(self.center.x() - 30, self.boxTop,
                   self.center.x() - 30, self.boxTop + length + 2)
        p.drawLine(self.center.x() + 30, self.boxTop,
                   self.center.x() + 30, self.boxTop + length + 2)

    def paintEvent(self, event):

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Just to make it a bit easier
        thickness = self.tick_thickness
        length = self.tick_length

        # Insert Background
        p.drawPixmap(0, 0, self.background)

        # Draw TC Ball
        pen = QPen(QColor(Qt.black))
        brush = QBrush(QColor(Qt.black))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(brush)
        center = QPointF(self.center.x() + self.boxHalfWidth * 4 * self._latAcc,
                         self.boxTop + length / 2)
        p.drawEllipse(center,thickness , thickness)


    def getLatAcc(self):
        return self._latAcc

    def setLatAcc(self, acc):
        if acc != self._latAcc:
            self._latAcc = acc
            self.update()

    latAcc = property(getLatAcc, setLatAcc)
