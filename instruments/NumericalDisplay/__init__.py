#  Copyright (c) 2018 Garrett Herschleb
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

class NumericalDisplay(QGraphicsView):
    def __init__(self, parent=None, total_decimals=3, scroll_decimal=1, font_family="Sans", font_size=10):
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

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()

        t = QGraphicsSimpleTextItem ("9")
        t.setFont (self.f)
        font_width = t.boundingRect().width()
        font_height = t.boundingRect().height()

        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        border_width = 3
        top = (self.h - font_height) / 2
        rect_pen = QPen(QColor(Qt.white))
        rect_pen.setWidth (border_width)
        self.scene.addRect(0, top, self.w, font_height,
                           rect_pen, QBrush(QColor(Qt.black)))
        self.setScene(self.scene)
        self.scrolling_area = NumericalScrollDisplay(self, self.scroll_decimal,
                                            self.font_family, self.font_size)
        self.scene.addWidget (self.scrolling_area)
        self.digit_vertical_spacing = font_height * 0.8
        self.scrolling_area.resize(font_width*self.scroll_decimal+border_width, self.h)
        sax = self.w-font_width*self.scroll_decimal-border_width
        self.scrolling_area.move(sax, 0)
        prest = '0' * (self.total_decimals - self.scroll_decimal)
        self.pre_scroll_text = self.scene.addSimpleText (prest, self.f)
        self.pre_scroll_text.setPen(QPen(QColor(Qt.white)))
        self.pre_scroll_text.setBrush(QBrush(QColor(Qt.white)))
        self.pre_scroll_text.setX (font_width / 2.0)
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
        self.pre_scroll_text.setText(prest)
        self.scrolling_area.value = scroll_value

    def getValue(self):
        return self._value

    def setValue(self, val):
        self._value = val
        if self.isVisible():
            self.redraw()

    value = property(getValue, setValue)

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
