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

import sys
import time

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import pyavtools.fix as fix
import pyefis.hmi as hmi
from pyefis.instruments.NumericalDisplay import NumericalDisplay

class Airspeed(QWidget):
    FULL_WIDTH = 400
    def __init__(self, parent=None, fontsize=20, data=None):
        super(Airspeed, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontsize = fontsize
        self._airspeed = 0
        if data:
            self.item = data
        else:
            self.item = fix.db.get_item("IAS")
            self.item.valueChanged[float].connect(self.setAirspeed)
            self.item.oldChanged[bool].connect(self.repaint)
            self.item.badChanged[bool].connect(self.repaint)
            self.item.failChanged[bool].connect(self.repaint)


    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        #Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        f = QFont()
        fs = int(round(self.fontsize * w / self.FULL_WIDTH))
        f.setPixelSize(fs)
        fontMetrics = QFontMetricsF(f)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        needleBrush = QBrush(QColor(Qt.white))

        vnePen = QPen(QColor(Qt.red))
        vnePen.setWidth(6)

        vsoPen = QPen(QColor(Qt.white))
        vsoPen.setWidth(4)

        vnoPen = QPen(QColor(Qt.green))
        vnoPen.setWidth(4)

        yellowPen = QPen(QColor(Qt.yellow))
        yellowPen.setWidth(4)

        # Dial Setup
        # V Speeds
        Vs = self.item.get_aux_value('Vs')
        Vs0 = self.item.get_aux_value('Vs0')
        Vno = self.item.get_aux_value('Vno')
        Vne = self.item.get_aux_value('Vne')
        #Va = 120
        Vfe = self.item.get_aux_value('Vfe')

        # VSpeed to angle for drawArc
        Vs0_angle = (-(((Vs0 - 30) * 2.5) + 26) + 90) * 16
        Vs_angle = (-(((Vs - 30) * 2.5) + 26) + 90) * 16
        Vfe_angle = (-(((Vfe - 30) * 2.5) + 25) + 90) * 16
        Vno_angle = (-(((Vno - 30) * 2.5) + 25) + 90) * 16
        Vne_angle = (-(((Vne - 30) * 2.5) + 25) + 90) * 16

        radius = int(round(min(w,h) * .45))
        diameter = radius*2
        inner_offset = 3
        center_x = w/2
        center_y = h/2

        # Vspeeds Arcs
        dial.setPen(vnoPen)
        dial_rect = QRectF(center_x-radius, center_y-radius,
                            diameter, diameter)
        dial.drawArc(dial_rect, qRound(Vs_angle), qRound(-(Vs_angle - Vno_angle)))
        dial.setPen(vsoPen)
        inner_rect = QRectF(center_x-radius+inner_offset, center_y-radius+inner_offset,
                            diameter-inner_offset*2, diameter-inner_offset*2)
        dial.drawArc(inner_rect,
                            qRound(Vs0_angle), qRound(-(Vs0_angle - Vfe_angle)))
        dial.setPen(yellowPen)
        dial.drawArc(dial_rect, qRound(Vno_angle), qRound(-(Vno_angle - Vne_angle)))
        dial.save()
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.translate(center_x, center_y)
        count = 0
        a_s = 0
        while count < 360:
            if count % 25 == 0 and a_s <= 140:
                dial.drawLine(0, -radius, 0, -(radius-15))
                x = fontMetrics.width(str(a_s)) / 2
                y = f.pixelSize()
                dial.drawText(qRound(-x), qRound(-(radius-15 - y)),
                           str(a_s))
                a_s += 10
                if count == 0:
                    a_s = 30
                    count = count + 19
                    dial.rotate(19)
            elif count % 12.5 == 0 and a_s <= 140:
                dial.drawLine(0, -(radius), 0, -(radius-10))
            if count == (-Vne_angle / 16) + 90:
                dial.setPen(vnePen)
                dial.drawLine(0, -(radius), 0, -(radius-15))
                dial.setPen(dialPen)
            dial.rotate(0.5)
            count += 0.5

        if self.item.fail:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dial.resetTransform()
            dial.setPen (QPen(QColor(Qt.red)))
            dial.setBrush (QBrush(QColor(Qt.red)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "XXX")
            dial.restore()
            return

        if self.item.old or self.item.bad:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dial.setPen(QPen(QColor(Qt.gray)))
            dial.setBrush(QBrush(QColor(Qt.gray)))
        else:
            dial.setPen(QPen(QColor(Qt.white)))
            dial.setBrush(QBrush(QColor(Qt.white)))
        #Needle Movement
        needle = QPolygon([QPoint(5, 0), QPoint(0, +5), QPoint(-5, 0),
                            QPoint(0, -(radius-15))])

        if self.airspeed <= 30:  # Airspeeds Below 30 Knots
            needle_angle = self._airspeed * 0.83
        else:  # Airspeeds above 30 Knots
            needle_angle = (self._airspeed - 30) * 2.5 + 25

        dial.rotate(needle_angle)
        dial.drawPolygon(needle)

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

        dial.restore()

    def getAirspeed(self):
        return self._airspeed

    def setAirspeed(self, airspeed):
        if airspeed != self._airspeed:
            self._airspeed = airspeed
            self.update()

    def setData(self, item, value):
            self.setAirspeed(value)

    airspeed = property(getAirspeed, setAirspeed)

    def setAsOld(self,b):
        pass

    def setAsBad(self,b):
        pass

    def setAsFail(self,b):
        pass


class Airspeed_Tape(QGraphicsView):
    def __init__(self, parent=None, data=None):
        super(Airspeed_Tape, self).__init__(parent)
        self.myparent = parent
        self.update_period = None
        # self.setStyleSheet("background-color: rgba(32, 32, 32, 0%)")
        self.setStyleSheet("background: transparent")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
      
        if data:
            self.item = data
        else:
            self.item = fix.db.get_item("IAS")
            self.item.valueChanged[float].connect(self.setAirspeed)
            self.item.oldChanged[bool].connect(self.setAsOld)
            self.item.badChanged[bool].connect(self.setAsBad)
            self.item.failChanged[bool].connect(self.setAsFail)
 
        self._airspeed = self.item.value

        # V Speeds
        self.Vs = self.item.get_aux_value('Vs')
        if self.Vs is None: self.Vs = 0
        self.Vs0 = self.item.get_aux_value('Vs0')
        if self.Vs0 is None: self.Vs0 = 0
        self.Vno = self.item.get_aux_value('Vno')
        if self.Vno is None: self.Vno = 0
        self.Vne = self.item.get_aux_value('Vne')
        if self.Vne is None: self.Vne = 200
        self.Vfe = self.item.get_aux_value('Vfe')
        if self.Vfe is None: self.Vfe = 0

        self.max = int(round(self.Vne*1.25))

        self.backgroundOpacity = 0.3
        self.foregroundOpacity = 0.6
        self.pph = 10 # Pixels per unit
        self.fontsize = 15
        self.majorDiv = 10
        self.minorDiv = 5

        self.numerical_display = NumericalDisplay(self)

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        self.markWidth = w / 5
        f = QFont()
        f.setPixelSize(self.fontsize)
        tape_height = self.max * self.pph + h
        tape_start = self.max * self.pph + h/2

        dialPen = QPen(QColor(Qt.white))

        self.scene = QGraphicsScene(0, 0, w, tape_height)
        x = self.scene.addRect(0, 0, w, tape_height,
                            QPen(QColor(32, 32, 32)), QBrush(QColor(32, 32, 32)))
        x.setOpacity(self.backgroundOpacity)

        # Add Markings
        # Green Bar
        r = QRectF(QPointF(0,              -self.Vno * self.pph + tape_start),
                   QPointF(self.markWidth, -self.Vs0 * self.pph + tape_start))
        x = self.scene.addRect(r, QPen(QColor(0,155,0)), QBrush(QColor(0,155,0)))
        x.setOpacity(self.foregroundOpacity)

        # White Bar
        r = QRectF(QPointF(self.markWidth / 2, -self.Vfe * self.pph + tape_start),
                   QPointF(self.markWidth,     -self.Vs0 * self.pph + tape_start))
        x = self.scene.addRect(r, QPen(Qt.white), QBrush(Qt.white))
        x.setOpacity(self.foregroundOpacity)


        # Yellow Bar
        r = QRectF(QPointF(0,              -self.Vno * self.pph + tape_start),
                   QPointF(self.markWidth, -self.Vne * self.pph + tape_start))
        x = self.scene.addRect(r, QPen(Qt.yellow), QBrush(Qt.yellow))
        x.setOpacity(self.foregroundOpacity)

        # Draw the little white lines and the text
        for i in range(self.max, -1, -1):
            if i % self.majorDiv == 0:
                l = self.scene.addLine(0, (- i * self.pph) + tape_start, w / 2,
                                      (- i * self.pph) + tape_start, dialPen)
                l.setOpacity(self.foregroundOpacity)
                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(w - t.boundingRect().width())
                t.setY(((- i * self.pph) + tape_start)
                       - t.boundingRect().height() / 2)
                t.setOpacity(self.foregroundOpacity)
            elif i % self.minorDiv ==0:
                l = self.scene.addLine(0, (- i * self.pph) + tape_start,
                                   w / 3, (- i * self.pph) + tape_start, dialPen)
                l.setOpacity(self.foregroundOpacity)
        # Red Line
        vnePen = QPen(QColor(Qt.red))
        vnePen.setWidth(4)
        l = self.scene.addLine(0, -self.Vne * self.pph + tape_start,
                               30, -self.Vne * self.pph + tape_start, vnePen)
        l.setOpacity(self.foregroundOpacity)

        nbh = 50
        self.numerical_display.resize (47, nbh)
        self.numeric_box_pos = QPoint(qRound(w-48), qRound(h/2-nbh/2))
        self.numerical_display.move(self.numeric_box_pos)
        self.numeric_box_pos.setY(qRound(self.numeric_box_pos.y()+nbh/2))
        self.numerical_display.show()
        self.numerical_display.value = self._airspeed
        self.setAsOld(self.item.old)
        self.setAsBad(self.item.bad)
        self.setAsFail(self.item.fail)

        self.setScene(self.scene)
        self.centerOn(self.scene.width() / 2,
                      -self._airspeed * self.pph + tape_start)

    def redraw(self):
        if not self.isVisible():
            return
        tape_start = self.max * self.pph + self.height()/2

        self.resetTransform()
        self.centerOn(self.scene.width() / 2,
                      -self._airspeed * self.pph + tape_start)
        self.numerical_display.value = self._airspeed

    #  Index Line that doesn't move to make it easy to read the airspeed.
    def paintEvent(self, event):
        super(Airspeed_Tape, self).paintEvent(event)
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.Antialiasing)

        marks = QPen(Qt.white, 1)
        p.translate(self.numeric_box_pos.x(), self.numeric_box_pos.y())
        p.setPen(marks)
        p.setBrush(QBrush(Qt.black))
        triangle_size = 11
        p.drawConvexPolygon(QPolygon([QPoint(0, -triangle_size-3),
                             QPoint(0, triangle_size-2),
                             QPoint(-triangle_size, -1)]))

    def getAirspeed(self):
        return self._airspeed

    def setAirspeed(self, airspeed):
        if airspeed != self._airspeed:
            self._airspeed = airspeed
            self.redraw()

    airspeed = property(getAirspeed, setAirspeed)

    def setAsOld(self,b):
        self.numerical_display.old = b

    def setAsBad(self,b):
        self.numerical_display.bad = b

    def setAsFail(self,b):
        self.numerical_display.fail = b


class Airspeed_Box(QWidget):
    """Represents a simple numeric display type gauge.  The benefit of using this
       over a normal text display is that this will change colors properly when
       limits are reached or when failures occur"""
    def __init__(self, parent=None, data=None):
        super(Airspeed_Box, self).__init__(parent)
        self.modes = ["TAS", "GS", "IAS"]
        self._modeIndicator = 0

        # Undecided how to handle decoupling the data here.
        # I think, when used the new way maybe we just disable mode
        # changing and handle that within the layer feeding data

        self.fix_items = [fix.db.get_item(mode) for mode in self.modes]
        self.fix_item = self.fix_items[self._modeIndicator]
        self.valueText = str(int(self.fix_item.value))
        self.fix_item.valueChanged[float].connect(self.setASData)

        self.alignment = Qt.AlignLeft | Qt.AlignVCenter
        self.valueAlignment = Qt.AlignRight  | Qt.AlignVCenter
        self.smallFontPercent = 0.4
        self.color = Qt.white
        self.modeText = self.modes[self._modeIndicator]
        hmi.actions.setAirspeedMode.connect(self.setMode)

    def resizeEvent(self, event):
        self.bigFont = QFont()
        self.bigFont.setPixelSize(qRound(self.height() * self.smallFontPercent))
        self.smallFont = QFont()
        self.smallFont.setPixelSize(qRound(self.height() * self.smallFontPercent))
        qm = QFontMetrics(self.smallFont)

        self.modeTextRect = QRectF(0, 0, self.width()-5, self.height()*0.4)
        self.valueTextRect = QRectF(0, self.height()*0.5,
                                        self.width()-5, self.height()*0.4)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Mode
        pen.setColor(self.color)
        p.setPen(pen)
        p.setFont(self.bigFont)
        opt = QTextOption(self.alignment)
        p.drawText(self.modeTextRect, self.modeText, opt)

        #Draw Value
        p.setFont(self.smallFont)
        opt = QTextOption(self.valueAlignment)
        p.drawText(self.valueTextRect, self.valueText, opt)

    def setMode(self, Mode):
        if Mode == "":
            self.fix_item.valueChanged[float].disconnect(self.setASData)
            self._modeIndicator += 1
            if self._modeIndicator == 3: self._modeIndicator = 0
        else:
            if Mode != self._modeIndicator:
                self.fix_item.valueChanged[float].disconnect(self.setASData)
                if Mode == 0:
                    self._modeIndicator = 0
                elif Mode == 1:
                    self._modeIndicator = 1
                elif Mode == 2:
                    self._modeIndicator = 2

        self.modeText = self.modes[self._modeIndicator]
        self.fix_item = self.fix_items[self._modeIndicator]
        self.fix_item.valueChanged[float].connect(self.setASData)
        self.setASData(self.fix_item.value)
        self.update()

    def setASData(self, d):
        if self.fix_item.fail:
            self.valueText = "XXX"
        elif self.fix_item.bad or self.fix_item.old:
            self.valueText = ""
        else:
            self.valueText = str(int(round(d)))
        if self.isVisible():
            self.update()
