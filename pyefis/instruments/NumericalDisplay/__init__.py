#  Copyright (c) 2018-2019 Garrett Herschleb
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

class NumericalDisplay(QGraphicsView):
    def __init__(self, parent=None, total_decimals=3, scroll_decimal=1, font_family="Sans", font_size=15):
        super(NumericalDisplay, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.scroll_decimal = scroll_decimal
        self.total_decimals = total_decimals
        self.f = QFont(font_family, font_size)
        self.font_family = font_family
        self.font_size = font_size
        self._value = 0
        self.myparent = parent
        self._bad = False
        self._old = False
        self._fail = False

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()

        t = QGraphicsSimpleTextItem ("9")
        t.setFont (self.f)
        font_width = t.boundingRect().width()
        font_height = t.boundingRect().height()
        while font_width * (self.total_decimals) >= self.w - 0.1:
                self.font_size -= 0.1
                self.f.setPointSizeF(self.font_size)
                t.setFont (self.f)
                font_width = t.boundingRect().width()
                font_height = t.boundingRect().height()
        self.font_size = qRound(self.font_size)
        self.f = QFont(self.font_family, self.font_size)

        while font_width * (self.total_decimals) <= self.w - 0.1:
                self.font_size += 0.1
                self.f.setPointSizeF(self.font_size) 
                t.setFont (self.f)
                font_width = t.boundingRect().width()
                font_height = t.boundingRect().height()
        self.font_size = qRound(self.font_size)
        self.f = QFont(self.font_family, self.font_size)

        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        border_width = 1
        top = (self.h - font_height) / 2
        rect_pen = QPen(QColor(Qt.white))
        rect_pen.setWidth (border_width)
        self.scene.addRect(0, top, self.w, font_height,
                           rect_pen, QBrush(QColor(Qt.black)))
        self.setScene(self.scene)
        self.scrolling_area = NumericalScrollDisplay(self, self.scroll_decimal,
                                            self.font_family, self.font_size)
        self.scene.addWidget (self.scrolling_area)
        self.digit_vertical_spacing = font_height
        self.scrolling_area.resize(qRound(font_width*self.scroll_decimal+border_width), self.h)
        sax = qRound(self.w-font_width*self.scroll_decimal-border_width)
        self.scrolling_area.move(sax, 0)
        prest = '0' * (self.total_decimals - self.scroll_decimal)
        if self._bad or self._old:
            prest = ''
        self.pre_scroll_text = self.scene.addSimpleText (prest, self.f)
        self.pre_scroll_text.setPen(QPen(QColor(Qt.white)))
        self.pre_scroll_text.setBrush(QBrush(QColor(Qt.white)))
        self.pre_scroll_text.setX (0)
        self.pre_scroll_text.setY ((self.h-font_height)/2.0)

        x = sax-border_width/2
        l = self.scene.addLine (x,0, x,top)
        l.setPen(rect_pen)
        top += font_height
        l = self.scene.addLine (x,top, x,self.h)
        l.setPen(rect_pen)
        l = self.scene.addLine (x,0, self.w,0)
        l.setPen(rect_pen)
        l = self.scene.addLine (x,self.h, self.w,self.h)
        l.setPen(rect_pen)

        # Get a failure scene ready in case it's needed
        self.fail_scene = QGraphicsScene(0, 0, self.w, self.h)
        self.fail_scene.addRect(0,0, self.w, self.h, QPen(QColor(Qt.white)), QBrush(QColor(50,50,50)))
        warn_font = QFont("FixedSys", 10, QFont.Bold)
        t = self.fail_scene.addSimpleText("XXX", warn_font)
        t.setPen (QPen(QColor(Qt.red)))
        t.setBrush (QBrush(QColor(Qt.red)))
        r = t.boundingRect()
        t.setPos ((self.w-r.width())/2, (self.h-r.height())/2)

        """ Not sure if this is needed:
        self.bad_text = self.scene.addSimpleText("BAD", warn_font)
        warn_pen = QPen(QColor(255, 150, 0))
        warn_brush = QBrush(QColor(255, 150, 0))
        self.bad_text.setPen (warn_pen)
        self.bad_text.setBrush (warn_brush)
        r = self.bad_text.boundingRect()
        self.bad_text.setPos ((self.w-r.width())/2, (self.h-r.height())/2)
        if not self._bad:
            self.bad_text.hide()

        self.old_text = self.scene.addSimpleText("OLD", warn_font)
        self.old_text.setPen (warn_pen)
        self.old_text.setBrush (warn_brush)
        r = self.old_text.boundingRect()
        self.old_text.setPos ((self.w-r.width())/2, (self.h-r.height())/2)
        if not self._old:
            self.old_text.hide()
        """


    def redraw(self):
        prevalue = int(self._value / (10 ** self.scroll_decimal))
        scroll_value = self._value - (prevalue * (10 ** self.scroll_decimal))
        if self.scroll_decimal > 1:
            scroll_value = (scroll_value / (10 ** (self.scroll_decimal-1)))
        # Handle special case where prevalue is about to roll over
        if scroll_value >= 9.6:
            prevalue += 1
        prest = str(prevalue)
        prelen = self.total_decimals - self.scroll_decimal
        if len(prest) < prelen:
            prest = '0' * (prelen - len(prest)) + prest
        if self._bad or self._old:
            prest = ''
        self.pre_scroll_text.setText(prest)
        if not (self._bad or self._old or self._fail):
            self.scrolling_area.value = scroll_value

    def getValue(self):
        return self._value

    def setValue(self, val):
        self._value = val
        if self.isVisible():
            self.redraw()

    value = property(getValue, setValue)

    def flagDisplay(self):
        if (self._bad or self._old or self._fail):
            self.pre_scroll_text.setText('')
            self.scrolling_area.hide()
        else:
            self.pre_scroll_text.setBrush(QBrush(QColor(Qt.white)))
            self.redraw()
            self.scrolling_area.show()

    def getBad(self):
        return self._bad
    def setBad(self, b):
        if self._bad != b:
            self._bad = b
            #if b:
            #    self.bad_text.show()
            #else:
            #    self.bad_text.hide()
            self.flagDisplay()
    bad = property(getBad, setBad)

    def getOld(self):
        return self._old
    def setOld(self, b):
        if self._old != b:
            self._old = b
            #if b:
            #    self.old_text.show()
            #else:
            #    self.old_text.hide()
            self.flagDisplay()
    old = property(getOld, setOld)

    def getFail(self):
        return self._fail
    def setFail(self, b):
        if self._fail != b:
            self._fail = b
            if b:
                self.setScene(self.fail_scene)
            else:
                self.setScene(self.scene)
                self.flagDisplay()
    fail = property(getFail, setFail)

class NumericalScrollDisplay(QGraphicsView):
    def __init__(self, parent=None, scroll_decimal=1, font_family="Sans", font_size=10):
        super(NumericalScrollDisplay, self).__init__()
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.scroll_decimal = scroll_decimal
        self.f = QFont(font_family, font_size)
        self._value = 0

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()

        t = QGraphicsSimpleTextItem ("9")
        t.setFont (self.f)
        font_width = t.boundingRect().width()
        font_height = t.boundingRect().height()
        self.digit_vertical_spacing = font_height * 0.8
        nsh = self.digit_vertical_spacing * 12 + self.h
        self.scene = QGraphicsScene(0,0,self.w, nsh)
        self.scene.addRect(0, 0, self.w, nsh,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        for i in range(20):
            y = self.y_offset(i) - font_height/2
            if y < 0:
                break
            text = str(i%10)
            if len(text) < self.scroll_decimal:
                add0s = self.scroll_decimal - len(text)
                text = text + "0"*add0s
            t = self.scene.addSimpleText(text, self.f)
            t.setX(2)
            t.setPen(QPen(QColor(Qt.white)))
            t.setBrush(QBrush(QColor(Qt.white)))
            t.setY(y)
        for i in range(9,0,-1):
            sv = i-10
            y = self.y_offset(sv) - font_height/2
            if y > nsh-font_height:
                break
            text = str(i)
            if len(text) < self.scroll_decimal:
                add0s = self.scroll_decimal - len(text)
                text = text + "0"*add0s
            t = self.scene.addSimpleText(text, self.f)
            t.setPen(QPen(QColor(Qt.white)))
            t.setBrush(QBrush(QColor(Qt.white)))
            t.setX(2)
            t.setY(y)
        self.setScene (self.scene)

    def y_offset(self, sv):
        return ((10.0 - (sv)) * self.digit_vertical_spacing + self.h/2)

    def redraw(self):
        scroll_value = self._value
        self.resetTransform()
        self.centerOn(self.width() / 2, self.y_offset(scroll_value))

    def getValue(self):
        return self._value

    def setValue(self, val):
        self._value = val
        if self.isVisible():
            self.redraw()

    value = property(getValue, setValue)
