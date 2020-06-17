#  Copyright (c) 2013 Neil Domalik, Phil Birkelbach; 2019 Garrett Herschleb
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

import math
import pyavtools.fix as fix
import pyavtools.filters as filters

class TurnCoordinator(QWidget):
    def __init__(self, parent=None, dial=True, ss_only=False, filter_depth=0):
        super(TurnCoordinator, self).__init__(parent)
        self.myparent = parent
        self.slip_skid_only = ss_only
        self.render_as_dial = dial
        if dial:
            self.setStyleSheet("border: 0px")
        else:
            pass
            #self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._rate = 0.0
        self._latAcc = 0.0
        if filter_depth:
            self.filter = filters.AvgFilter(filter_depth)
        else:
            self.filter = None
        self.alat_item = fix.db.get_item("ALAT")
        self.alat_item.valueChanged[float].connect(self.setLatAcc)
        self.alat_item.badChanged.connect(self.quality_change)
        self.alat_item.oldChanged.connect(self.quality_change)
        self.alat_item.failChanged.connect(self.quality_change)
        self.rot_item = fix.db.get_item("ROT")
        self.rot_item.valueChanged[float].connect(self.setROT)
        self.rot_item.badChanged.connect(self.quality_change)
        self.rot_item.oldChanged.connect(self.quality_change)
        self.rot_item.failChanged.connect(self.quality_change)
        self.alat_multiplier = 1.0 / (0.217)
        self.max_tc_displacement = 1.0 / self.alat_multiplier

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
        self.r = min(self.width(), self.height()) * .45

        p.fillRect(0, 0, self.width(), self.height(), Qt.black)
        if self.render_as_dial:
            p.drawEllipse(self.center, self.r, self.r)

        thickness = self.tick_thickness
        length = self.tick_length
        p.setBrush(brush)
        if not self.slip_skid_only:
            # this draws the tick boxes
            rect = QRect(-(self.r), 0 - thickness / 2,
                         length, thickness)
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
            # Draw the little airplane center
            p.drawEllipse(self.center, thickness, thickness)

        # TC Box
        self.boxHalfWidth = self.r * .6
        self.boxTop = self.center.y() + (self.r - length) * (
                      math.sin(math.radians(40))) + thickness
        self.boxHeight = self.boxHalfWidth * .25

        rect = QRect(QPoint(self.center.x() - self.boxHalfWidth, self.boxTop),
                     QPoint(self.center.x() + self.boxHalfWidth,
                            self.boxTop + self.boxHeight))
        p.drawRect(rect)
        # vertical black lines on TC
        pen.setColor(QColor(Qt.black))
        pen.setWidth(3)
        p.setPen(pen)
        ball_rad = self.boxHeight / 2
        p.drawLine(self.center.x() - ball_rad - 1.8, self.boxTop,
                   self.center.x() - ball_rad - 1.8, self.boxTop + self.boxHeight+1)
        p.drawLine(self.center.x() + ball_rad + 2.8, self.boxTop,
                   self.center.x() + ball_rad + 2.8, self.boxTop + self.boxHeight+1)

        filter_depth = self.myparent.get_config_item('alat_filter_depth')
        if filter_depth is not None and filter_depth > 0:
            self.filter = filters.AvgFilter(filter_depth)
        alat_multiplier = self.myparent.get_config_item('alat_multiplier')
        if alat_multiplier is not None and alat_multiplier > 0:
            self.alat_multiplier = alat_multiplier
            self.max_tc_displacement = 1.0 / self.alat_multiplier

    def paintEvent(self, event):

        p = QPainter(self)
        #p.setRenderHint(QPainter.Antialiasing)

        # Just to make it a bit easier
        thickness = self.tick_thickness
        length = self.tick_length

        # Insert Background
        if not self.render_as_dial:
            p.setCompositionMode(QPainter.CompositionMode_ColorDodge)
        p.drawPixmap(0, 0, self.background)

        # Draw TC Ball
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.Antialiasing)
        ball_rad = self.boxHeight / 2
        if self.alat_item.bad or self.alat_item.old:
            pen = QPen(QColor(Qt.gray))
            brush = QBrush(QColor(Qt.gray))
        else:
            pen = QPen(QColor(Qt.black))
            brush = QBrush(QColor(Qt.black))
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(brush)
        acc_displacement = self._latAcc
        if acc_displacement > self.max_tc_displacement:
            acc_displacement = self.max_tc_displacement
        if acc_displacement < -self.max_tc_displacement:
            acc_displacement = -self.max_tc_displacement
        centerball = self.center.x() + (self.boxHalfWidth - ball_rad) * (-(
                     acc_displacement * self.alat_multiplier))

        # /accelerations/pilot/y-accel-fps_sec
        # 32.185039370079 fps /sec = 1 G
        center = QPointF(centerball,
                         self.boxTop + ball_rad)
        if self.alat_item.fail:
            warn_font = QFont("FixedSys", self.boxHeight, QFont.Bold)
            p.setPen (QPen(QColor(Qt.red)))
            p.setBrush (QBrush(QColor(Qt.red)))
            p.setFont (warn_font)
            p.drawText (self.center.x()-self.boxHalfWidth,self.boxTop,self.boxHalfWidth*2,self.boxHeight,
                    Qt.AlignCenter, "XXX")
        else:
            p.drawEllipse(center, ball_rad, ball_rad)

        if self.slip_skid_only:
            return
        # the little airplane
        if self.rot_item.bad or self.rot_item.old:
            pen.setColor(QColor(Qt.gray))
            brush.setColor(QColor(Qt.gray))
        else:
            pen.setColor(QColor(Qt.white))
            brush.setColor(QColor(Qt.white))
        p.setPen(pen)
        p.setBrush(brush)

        if self._rate > 5:
            self._rate = 5
        elif self._rate < -5:
            self._rate = -5
        x = self.r - length - thickness / 2
        if self.rot_item.fail:
            warn_font = QFont("FixedSys", 20, QFont.Bold)
            p.setPen (QPen(QColor(Qt.red)))
            p.setBrush (QBrush(QColor(Qt.red)))
            p.setFont (warn_font)
            p.drawText (0,0,self.width(),self.height(),
                    Qt.AlignCenter, "XXX")
        else:
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

    def getROT(self):
        return self._rate

    def setROT(self, rot):
        if rot != self._rate:
            self._rate = rot
            self.update()

    rate = property(getROT, setROT)

    def getLatAcc(self):
        return self._latAcc

    def setLatAcc(self, acc):
        last_acc = self._latAcc
        if self.filter is not None:
            self._latAcc = self.filter.setValue(acc)
        else:
            self._latAcc = acc
        if last_acc != self._latAcc:
            self.update()

    latAcc = property(getLatAcc, setLatAcc)

    def quality_change(self, x):
        self.update()

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
        self.boxTop = self.center.y() + (self.r - length) * math.sin(
                      math.radians(30)) + thickness
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
        center = QPointF(self.center.x() + self.boxHalfWidth *
                         4 * self._latAcc, self.boxTop + length / 2)
        p.drawEllipse(center, thickness, thickness)

    def getLatAcc(self):
        return self._latAcc

    def setLatAcc(self, acc):
        if acc != self._latAcc:
            self._latAcc = acc
            self.update()

    latAcc = property(getLatAcc, setLatAcc)
