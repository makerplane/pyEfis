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


try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import pyavtools.fix as fix

from instruments.NumericalDisplay import NumericalDisplay

class Altimeter(QWidget):
    FULL_WIDTH = 300
    def __init__(self, parent=None):
        super(Altimeter, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self._altimeter = 0
        self.item = fix.db.get_item("ALT")
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.repaint)
        self.item.badChanged[bool].connect(self.repaint)
        self.item.failChanged[bool].connect(self.repaint)

    # TODO We continuously draw things that don't change.  Should draw the
    # background save to pixmap or something and then blit it and draw arrows.
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        # Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Setup Pens
        if self.item.old or self.item.bad:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dialPen = QPen(QColor(Qt.gray))
            dialBrush = QBrush(QColor(Qt.gray))
        else:
            dialPen = QPen(QColor(Qt.white))
            dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)

        # Dial Setup
        dial.setPen(dialPen)
        dial.drawEllipse(25, 25, w - 50, h - 50)

        f = QFont()
        fs = int(round(30 * w / self.FULL_WIDTH))
        f.setPixelSize(fs)
        dial.setFont(f)
        dial.setPen(dialPen)
        dial.setBrush(dialBrush)

        dial.translate(w / 2, h / 2)
        count = 0
        altimeter_numbers = 0
        while count < 360:
            if count % 36 == 0:
                dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 40))

                dial.drawText(-9.5, -(h / 2 - 67),
                              str(altimeter_numbers))
                altimeter_numbers += 1
            else:
                dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 35))

            dial.rotate(36)
            count += 36
        count = 0
        while count < 360:
            dial.drawLine(0, -(h / 2 - 25), 0, -(h / 2 - 35))

            dial.rotate(7.2)
            count += 7.2

        if self.item.fail:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dial.resetTransform()
            dial.setPen (QPen(QColor(Qt.red)))
            dial.setBrush (QBrush(QColor(Qt.red)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "XXX")
            return

        dial.setBrush(dialBrush)
        # Needle Movement
        sm_dial = QPolygon([QPoint(5, 0), QPoint(0, +5), QPoint(-5, 0),
                            QPoint(0, -(h / 2 - 40))])
        lg_dial = QPolygon([QPoint(10, -(h / 2 - 120)), QPoint(5, 0),
                            QPoint(0, +5), QPoint(-5, 0),
                            QPoint(-10, -(h / 2 - 120)),
                            QPoint(0, -(h / 2 - 100))])
        outside_dial = QPolygon([QPoint( 7.5, -(h / 2 - 25)), QPoint( -7.5 , -(h /2 - 25)),
                                 QPoint(0, -(h / 2 - 35))])

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


    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            self.update()

    altimeter = property(getAltimeter, setAltimeter)


class Altimeter_Tape(QGraphicsView):
    def __init__(self, parent=None, maxalt=50000, fontsize=15):
        super(Altimeter_Tape, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(32, 32, 32, 75%)")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontsize = fontsize
        self.item = fix.db.get_item("ALT")
        self._altimeter = self.item.value
        self.maxalt = maxalt
        self.pph = 0.3
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.setAltOld)
        self.item.badChanged[bool].connect(self.setAltBad)
        self.item.failChanged[bool].connect(self.setAltFail)


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
        self.scene.addRect(0, 0, w, self.height_pixel,
                           QPen(QColor(32, 32, 32, 10)), QBrush(QColor(32, 32, 32, 10)))

        for i in range(self.maxalt, -1, -100):
            y = self.y_offset(i)
            if i % 200 == 0:
                self.scene.addLine(w_2 + 15, y, w, y, dialPen)
                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(0)
                t.setY(y - t.boundingRect().height() / 2)
            else:
                self.scene.addLine(w_2 + 30, y, w, y, dialPen)
        self.setScene(self.scene)

        self.numerical_display = NumericalDisplay(self, total_decimals=5, scroll_decimal=2)
        nbh=50
        self.numerical_display.resize (50, nbh)
        self.numeric_box_pos = QPoint(3, h/2-nbh/2)
        self.numerical_display.move(self.numeric_box_pos)
        self.numeric_box_pos.setX(self.numeric_box_pos.x()+self.numerical_display.width())
        self.numeric_box_pos.setY(self.numeric_box_pos.y()+nbh/2)
        self.numerical_display.show()
        self.numerical_display.value = self._altimeter
        self.centerOn(self.scene.width() / 2, self.y_offset(self._altimeter))
        self.setAltOld(self.item.old)
        self.setAltBad(self.item.bad)
        self.setAltFail(self.item.fail)

    def y_offset(self, alt):
        return self.height_pixel - (alt*self.pph) - self.height()/2

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

        marks = QPen(Qt.white, 3)
        p.translate(self.numeric_box_pos.x(), self.numeric_box_pos.y())
        p.setPen(marks)
        p.setBrush(QBrush(Qt.black))
        triangle_size = 6
        p.drawConvexPolygon(QPolygon([QPoint(0, -triangle_size),
                             QPoint(0, triangle_size),
                             QPoint(triangle_size, 0)]))

    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        if altimeter != self._altimeter:
            self._altimeter = altimeter
            self.redraw()

    altimeter = property(getAltimeter, setAltimeter)

    def setAltOld(self,b):
        self.numerical_display.old = b

    def setAltBad(self,b):
        self.numerical_display.bad = b

    def setAltFail(self,b):
        self.numerical_display.fail = b

class Altimeter_Setting(QGraphicsView):
    def __init__(self, parent=None):
        super(Altimeter_Setting, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        item1 = fix.db.get_item("BARO")
        self._altimeter_setting = item1.value
        item1.valueChanged[float].connect(self.setAltimeter_Setting)


    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()
        self.f = QFont()
        self.f.setPixelSize(20)

        dialPen = QPen(QColor(Qt.white))
        dialPen.setWidth(2)

        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        self.scene.addRect(0, 0, self.w, self.h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))

        t = self.scene.addText("%0.2f" % self._altimeter_setting)
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY((self.h - t.boundingRect().height()) / 2)
        self.setScene(self.scene)

    def redraw(self):
        self.scene.clear()
        self.scene.addRect(0, 0, self.w, self.h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        t = self.scene.addText("%0.2f" % self._altimeter_setting)
        t.setFont(self.f)
        self.scene.setFont(self.f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX((self.w - t.boundingRect().width()) / 2)
        t.setY((self.h - t.boundingRect().height()) / 2)
        self.setScene(self.scene)

    def getAltimeter_Setting(self):
        return self._altimeter_setting

    def setAltimeter_Setting(self, altimeter_setting):
        if altimeter_setting != self._altimeter_setting:
            self._altimeter_setting = altimeter_setting
            self.redraw()

    altimeter_setting = property(getAltimeter_Setting, setAltimeter_Setting)
