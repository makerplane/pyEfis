#  Copyright (c) 2013 Neil Domalik, 2018-2019 Garrett Herschleb
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

import time

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import pyavtools.fix as fix

from pyefis.instruments.NumericalDisplay import NumericalDisplay
import pyefis.hmi as hmi
from pyefis.instruments import helpers


class Altimeter(QWidget):
    FULL_WIDTH = 300

    def __init__(
        self, parent=None, bg_color=Qt.black, font_family="DejaVu Sans Condensed"
    ):
        super(Altimeter, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.font_family = font_family
        self.setFocusPolicy(Qt.NoFocus)
        self._altimeter = 0
        self.bg_color = bg_color
        self.item = fix.db.get_item("ALT")
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.repaint)
        self.item.badChanged[bool].connect(self.repaint)
        self.item.failChanged[bool].connect(self.repaint)

        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.conversionFunction = lambda x: x

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 1

    # TODO We continuously draw things that don't change.  Should draw the
    # background save to pixmap or something and then blit it and draw arrows.
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)
        radius = int(round(min(w, h) * 0.45))
        diameter = radius * 2
        center_x = w / 2
        center_y = h / 2

        # Draw the Black Background
        dial.fillRect(0, 0, w, h, QColor(self.bg_color))

        # Setup Pens
        if self.item.old or self.item.bad:
            warn_font = QFont(self.font_family, 30, QFont.Bold)
            dialPen = QPen(QColor(Qt.gray))
            dialBrush = QBrush(QColor(Qt.gray))
        else:
            dialPen = QPen(QColor(Qt.white))
            dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)

        # Dial Setup
        dial.setPen(dialPen)
        dial.drawEllipse(
            QRectF(center_x - radius, center_y - radius, diameter, diameter)
        )

        f = QFont(self.font_family)
        fs = int(round(20 * w / self.FULL_WIDTH))
        f.setPixelSize(fs)
        fontMetrics = QFontMetricsF(f)
        dial.setFont(f)
        dial.setPen(dialPen)
        dial.setBrush(dialBrush)

        dial.translate(w / 2, h / 2)
        count = 0
        altimeter_numbers = 0
        while count < 360:
            if count % 36 == 0:
                dial.drawLine(0, -(radius), 0, -(radius - 15))
                x = fontMetrics.width(str(altimeter_numbers)) / 2
                y = f.pixelSize()
                dial.drawText(
                    qRound(-x), qRound(-(radius - 15 - y)), str(altimeter_numbers)
                )
                altimeter_numbers += 1
            else:
                dial.drawLine(0, -(radius), 0, -(radius - 10))

            dial.rotate(36)
            count += 36
        count = 0
        while count < 360:
            dial.drawLine(0, -(radius), 0, -(radius - 10))

            dial.rotate(7.2)
            count += 7.2

        if self.item.fail:
            warn_font = QFont(self.font_family, 30, QFont.Bold)
            dial.resetTransform()
            dial.setPen(QPen(QColor(Qt.red)))
            dial.setBrush(QBrush(QColor(Qt.red)))
            dial.setFont(warn_font)
            dial.drawText(0, 0, w, h, Qt.AlignCenter, "XXX")
            return

        dial.setBrush(dialBrush)
        # Needle Movement
        sm_dial = QPolygonF(
            [QPointF(5, 0), QPointF(0, +5), QPointF(-5, 0), QPointF(0, -(radius - 15))]
        )
        lg_dial = QPolygonF(
            [
                QPointF(10, -(radius / 9)),
                QPointF(5, 0),
                QPointF(0, +5),
                QPointF(-5, 0),
                QPointF(-10, -(radius / 9)),
                QPointF(0, -int(round((radius * 0.6)))),
            ]
        )
        outside_dial = QPolygonF(
            [
                QPointF(7.5, -(radius)),
                QPointF(-7.5, -(radius)),
                QPointF(0, -(radius - 10)),
            ]
        )

        sm_dial_angle = self._altimeter * 0.36 - 7.2
        lg_dial_angle = self._altimeter / 10 * 0.36 - 7.2
        outside_dial_angle = self._altimeter / 100 * 0.36 - 7.2

        dial.rotate(sm_dial_angle)
        dial.drawPolygon(sm_dial)
        dial.rotate(-sm_dial_angle)
        dial.rotate(lg_dial_angle)
        dial.drawPolygon(lg_dial)
        dial.rotate(-lg_dial_angle)
        dial.rotate(outside_dial_angle)
        dial.drawPolygon(outside_dial)

        """ Not sure if this is needed
        if self.item.bad:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "BAD")
        elif self.item.old:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "OLD")
        """

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        self.update()

    def setUnits(self, args):
        x = args.split(":")
        command = x[1].lower()
        names = x[0].split(",")
        if self.item.key in names or "*" in names or self.unitGroup in names:
            # item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            # self.setAuxData(item.aux) # Trigger conversion for aux data
            self.altimeter = self.item.value  # Trigger the conversion for value

    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        cvalue = self.conversionFunction(altimeter)
        if cvalue != self._altimeter:
            self._altimeter = cvalue
            self.update()

    altimeter = property(getAltimeter, setAltimeter)


class Altimeter_Tape(QGraphicsView):
    def __init__(
        self,
        parent=None,
        dbkey="ALT",
        maxalt=50000,
        fontsize=15,
        font_percent=None,
        font_family="DejaVu Sans Condensed",
    ):
        super(Altimeter_Tape, self).__init__(parent)
        self.setStyleSheet("background: transparent")
        self.font_family = font_family
        self.font_mask = "00000"
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.font_percent = font_percent
        if self.font_percent:
            self.fontsize = qRound(self.width() * self.font_percent)
            self.pph = self.fontsize / 50
        else:
            self.fontsize = fontsize
            self.pph = 0.3

        self.item = fix.db.get_item(dbkey)
        self._altimeter = self.item.value
        self.backgroundOpacity = 0.3
        self.foregroundOpacity = 0.6
        self.majorDiv = 200
        self.minorDiv = 100

        self.maxalt = maxalt
        self._maxalt = maxalt
        self.total_decimals = 5
        self.myparent = parent

        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.conversionFunction = lambda x: x

    def resizeEvent(self, event):
        if self.font_percent:
            self.fontsize = qRound(self.width() * self.font_percent)
        self.pph = self.fontsize / (self.height() / 20)

        w = self.width()
        w_2 = w / 2
        h = self.height()
        f = QFont(self.font_family)
        if self.font_mask:
            self.font_size = helpers.fit_to_mask(
                self.width() * 0.55,
                self.height() * 0.05,
                self.font_mask,
                self.font_family,
            )
            f.setPointSizeF(self.font_size)
        else:
            f.setPixelSize(self.fontsize)
        self.height_pixel = (
            self.maxalt * 2 * self.pph + h
        )  # + abs(self.minalt*self.pph)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(int(self.height() * 0.005))

        self.scene = QGraphicsScene(0, 0, w, self.height_pixel)
        x = self.scene.addRect(
            0,
            0,
            w,
            self.height_pixel,
            QPen(QColor(32, 32, 32)),
            QBrush(QColor(32, 32, 32)),
        )
        x.setOpacity(self.backgroundOpacity)

        for i in range(self.maxalt * 2, -1, -self.minorDiv):
            y = self.y_offset(i)
            if (i - self.maxalt) % self.majorDiv == 0:
                l = self.scene.addLine(w_2 + 15, y, w, y, dialPen)
                l.setOpacity(self.foregroundOpacity)
                t = self.scene.addText(str(i - self.maxalt))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(0)
                t.setY(y - t.boundingRect().height() / 2)
                t.setOpacity(self.foregroundOpacity)

            else:
                l = self.scene.addLine(w_2 + 30, y, w, y, dialPen)
                l.setOpacity(self.foregroundOpacity)
        self.setScene(self.scene)

        self.numerical_display = NumericalDisplay(
            self, total_decimals=self.total_decimals, scroll_decimal=2
        )
        nbh = w / 1.20
        self.numerical_display.resize(qRound(w / 1.20), qRound(nbh / 1.45))
        self.numeric_box_pos = QPoint(0, qRound(h / 2 - (nbh / 1.45) / 2))
        self.numerical_display.move(self.numeric_box_pos)
        self.numeric_box_pos.setX(
            self.numeric_box_pos.x() + self.numerical_display.width()
        )
        self.numeric_box_pos.setY(
            qRound(self.numeric_box_pos.y() + (nbh / 1.45) / 2) + 1
        )
        self.numerical_display.show()
        self.numerical_display.value = self._altimeter
        self.centerOn(
            self.scene.width() / 2, self.y_offset(self._altimeter + self.maxalt)
        )
        self.setAltOld(self.item.old)
        self.setAltBad(self.item.bad)
        self.setAltFail(self.item.fail)
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.setAltOld)
        self.item.badChanged[bool].connect(self.setAltBad)
        self.item.failChanged[bool].connect(self.setAltFail)

    def y_offset(self, alt):
        return self.height_pixel - (alt * self.pph) - self.height()

    def redraw(self):
        if not self.isVisible():
            return
        self.resetTransform()
        self.centerOn(
            self.scene.width() / 2, self.y_offset(self._altimeter + self.maxalt)
        )
        self.numerical_display.value = self._altimeter

    #  Index Line that doesn't move to make it easy to read the altimeter.
    def paintEvent(self, event):
        super(Altimeter_Tape, self).paintEvent(event)
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)

        marks = QPen(Qt.white, 1)
        p.translate(self.numeric_box_pos.x(), self.numeric_box_pos.y())
        p.setPen(marks)
        p.setBrush(QBrush(Qt.black))
        triangle_size = w / 8
        p.drawConvexPolygon(
            QPolygonF(
                [
                    QPointF(0, -triangle_size),
                    QPointF(0, triangle_size),
                    QPointF(triangle_size, 0),
                ]
            )
        )

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        if self.isVisible():
            self.update()

    def setUnits(self, args):
        x = args.split(":")
        command = x[1].lower()
        names = x[0].split(",")
        if self.item.key in names or "*" in names or self.unitGroup in names:
            # item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            # self.setAuxData(item.aux) # Trigger conversion for aux data
            self.altimeter = self.item.value  # Trigger the conversion for value

    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        cvalue = self.conversionFunction(altimeter)
        if cvalue != self._altimeter:
            self._altimeter = cvalue
            self.redraw()

    altimeter = property(getAltimeter, setAltimeter)

    def setAltOld(self, b):
        self.numerical_display.old = b

    def setAltBad(self, b):
        self.numerical_display.bad = b

    def setAltFail(self, b):
        self.numerical_display.fail = b

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass
