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

class Altimeter(QWidget):
    FULL_WIDTH = 300
    def __init__(self, parent=None, data=None):
        super(Altimeter, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._altimeter = 0
        # Assume bad state when starting
        self._altOld = True
        self._altBad = True
        self._altFail = True
        if data:
            self._altimeter = data
        else:
            self.item = fix.db.get_item("ALT")
            self._altimeter = self.item.value

            self.item.valueChanged[float].connect(self.setAltimeter)
            self.item.oldChanged[bool].connect(self.setOld)
            self.item.badChanged[bool].connect(self.setBad)
            self.item.failChanged[bool].connect(self.setFail)
            self._altOld = self.item.old
            self._altBad = self.item.bad
            self._altFail = self.item.fail

    # TODO We continuously draw things that don't change.  Should draw the
    # background save to pixmap or something and then blit it and draw arrows.
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)
        radius = int(round(min(w,h)*.45))
        diameter = radius * 2
        center_x = w/2
        center_y = h/2

        # Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        if self._altOld or self._altBad:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dialPen = QPen(QColor(Qt.gray))
            dialBrush = QBrush(QColor(Qt.gray))
        else:
            dialPen = QPen(QColor(Qt.white))
            dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)

        # Dial Setup
        dial.setPen(dialPen)
        dial.drawEllipse(QRectF(center_x-radius, center_y-radius, diameter, diameter))

        f = QFont()
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
                dial.drawLine(0, -(radius), 0, -(radius-15))
                x = fontMetrics.width(str(altimeter_numbers)) / 2
                y = f.pixelSize()
                dial.drawText(qRound(-x), qRound(-(radius-15-y)),
                              str(altimeter_numbers))
                altimeter_numbers += 1
            else:
                dial.drawLine(0, -(radius), 0, -(radius-10))

            dial.rotate(36)
            count += 36
        count = 0
        while count < 360:
            dial.drawLine(0, -(radius), 0, -(radius-10))

            dial.rotate(7.2)
            count += 7.2

        if self._altFail:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dial.resetTransform()
            dial.setPen (QPen(QColor(Qt.red)))
            dial.setBrush (QBrush(QColor(Qt.red)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "XXX")
            return

        dial.setBrush(dialBrush)
        # Needle Movement
        sm_dial = QPolygonF([QPointF(5, 0), QPointF(0, +5), QPointF(-5, 0),
                            QPointF(0, -(radius-15))])
        lg_dial = QPolygonF([QPointF(10, -(radius/9)), QPointF(5, 0),
                            QPointF(0, +5), QPointF(-5, 0),
                            QPointF(-10, -(radius/9)),
                            QPointF(0, -int(round((radius*.6))))])
        outside_dial = QPolygonF([QPointF( 7.5, -(radius)), QPointF( -7.5 , -(radius)),
                                 QPointF(0, -(radius-10))])

        sm_dial_angle = self._altimeter * .36 - 7.2
        lg_dial_angle = self._altimeter / 10 * .36 - 7.2
        outside_dial_angle = self._altimeter / 100 * .36 - 7.2

        dial.rotate(sm_dial_angle)
        dial.drawPolygon(sm_dial)
        dial.rotate(-sm_dial_angle)
        dial.rotate(lg_dial_angle)
        dial.drawPolygon(lg_dial)
        dial.rotate(-lg_dial_angle)
        dial.rotate(outside_dial_angle)
        dial.drawPolygon(outside_dial)

        """ Not sure if this is needed
        if self._altBad:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "BAD")
        elif self._altOld:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "OLD")
        """


    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            self.update()

    altimeter = property(getAltimeter, setAltimeter)

    def setData(self, item, value):
        self.setAltimeter(value)

    def setBad(self, bad, item=None):
        self._altBad = bad
        if self.isVisible(): self.repaint()

    def setFail(self,fail, item=None):
        self._altFail = fail
        if self.isVisible(): self.repaint()

    def setOld(self, old, item=None):
        self._altOld = old
        if self.isVisible(): self.repaint()


class Altimeter_Tape(QGraphicsView):
    def __init__(self, parent=None, maxalt=50000, fontsize=15, data=None):
        super(Altimeter_Tape, self).__init__(parent)
        self.setStyleSheet("background: transparent")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontsize = fontsize

        # Assume bad state when starting
        self._altOld = True
        self._altBad = True
        self._altFail = True
        if data:
            self._altimeter = data
        else:
            self.item = fix.db.get_item("ALT")
            self._altimeter = self.item.value

            self.item.valueChanged[float].connect(self.setAltimeter)
            self.item.oldChanged[bool].connect(self.setOld)
            self.item.badChanged[bool].connect(self.setBad)
            self.item.failChanged[bool].connect(self.setFail)
            self._altOld = self.item.old
            self._altBad = self.item.bad
            self._altFail = self.item.fail

        self.backgroundOpacity = 0.3
        self.foregroundOpacity = 0.6
        self.pph = 0.3
        self.majorDiv = 200
        self.minorDiv = 100


        self.maxalt = maxalt
        self.myparent = parent

        self.numerical_display = NumericalDisplay(self, total_decimals=5, scroll_decimal=2)
        self.numerical_display.value = self._altimeter

        # Ensure all vars are init so paint events do not cause crash 
        self.resizeEvent(None)

    def resizeEvent(self, event):
        w = self.width()
        w_2 = w/2
        h = self.height()
        f = QFont()
        f.setPixelSize(self.fontsize)
        self.height_pixel = self.maxalt*self.pph + h

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        self.scene = QGraphicsScene(0, 0, w, self.height_pixel)
        x = self.scene.addRect(0, 0, w, self.height_pixel,
                           QPen(QColor(32, 32, 32)), QBrush(QColor(32, 32, 32)))
        x.setOpacity(self.backgroundOpacity)

        for i in range(self.maxalt, -1, -self.minorDiv):
            y = self.y_offset(i)
            if i % self.majorDiv == 0:
                l = self.scene.addLine(w_2 + 15, y, w, y, dialPen)
                l.setOpacity(self.foregroundOpacity)
                t = self.scene.addText(str(i))
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

        nbh=50
        self.numerical_display.resize (70, nbh)
        self.numeric_box_pos = QPoint(2, qRound(h/2-nbh/2))
        self.numerical_display.move(self.numeric_box_pos)
        self.numeric_box_pos.setX(self.numeric_box_pos.x()+self.numerical_display.width())
        self.numeric_box_pos.setY(qRound(self.numeric_box_pos.y()+nbh/2))
        self.numerical_display.show()
        self.numerical_display.value = self._altimeter
        self.centerOn(self.scene.width() / 2, self.y_offset(self._altimeter))

    def y_offset(self, alt):
        return self.height_pixel - (alt*self.pph) - self.height()/2

    def showEvent(self, event):
        self.redraw()

    def redraw(self):
        self.resetTransform()
        self.centerOn(self.scene.width() / 2, self.y_offset(self._altimeter))
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
        triangle_size = 11
        p.drawConvexPolygon(QPolygonF([QPointF(0, -triangle_size),
                             QPointF(0, triangle_size),
                             QPointF(triangle_size, 0)]))

    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            self.numerical_display.value = altimeter
            if self.isVisible(): self.redraw()

    altimeter = property(getAltimeter, setAltimeter)

    def setData(self, item, value):
        self.setAltimeter(value)

    def setBad(self, bad, item=None):
        self._altBad = bad
        self.numerical_display.bad = bad

    def setFail(self,fail, item=None):
        self._altFail = fail
        self.numerical_display.fail = fail

    def setOld(self, old, item=None):
        self._altOld = old
        self.numerical_display.old = old



