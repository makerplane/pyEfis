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
        rect_pen = QPen(QColor(Qt.white))
        rect_pen.setWidth (border_width)
        self.scene.addRect(0, 0, self.w, self.h,
                           rect_pen, QBrush(QColor(Qt.black)))
        self.setScene(self.scene)
        self.scrolling_area = NumericalScrollDisplay(self, self.font_family, self.font_size)
        self.scene.addWidget (self.scrolling_area)
        self.digit_vertical_spacing = font_height * 0.8
        self.scrolling_area.resize(font_width+border_width, self.h-2*border_width)
        self.scrolling_area.move(self.w-font_width*self.scroll_decimal-border_width, border_width)
        prest = '0' * (self.total_decimals - self.scroll_decimal)
        self.pre_scroll_text = self.scene.addSimpleText (prest, self.f)
        self.pre_scroll_text.setPen(QPen(QColor(Qt.white)))
        self.pre_scroll_text.setBrush(QBrush(QColor(Qt.white)))
        self.pre_scroll_text.setX (font_width / 2.0)
        self.pre_scroll_text.setY ((self.h-font_height)/2.0)

        if self.scroll_decimal > 1:
            pst_width = font_width*(self.scroll_decimal-1)
            x = self.w-pst_width-border_width
            self.scene.addRect(x, border_width,
                              pst_width, self.h-2*border_width,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
            post = '0' * (self.scroll_decimal - 1)
            post_text = self.scene.addSimpleText (post, self.f)
            post_text.setPen(QPen(QColor(Qt.white)))
            post_text.setBrush(QBrush(QColor(Qt.white)))
            post_text.setX (x)
            post_text.setY ((self.h-font_height)/2.0)

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
    def __init__(self, parent=None, font_family="Sans", font_size=10):
        super(NumericalScrollDisplay, self).__init__()
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.f = QFont(font_family, font_size)
        self._value = 0

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()

        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        self.scene.addRect(0, 0, self.w, self.h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        t = QGraphicsSimpleTextItem ("9")
        t.setFont (self.f)
        font_width = t.boundingRect().width()
        font_height = t.boundingRect().height()
        self.digit_vertical_spacing = font_height * 0.8
        nsh = self.digit_vertical_spacing * 12
        self.scene = QGraphicsScene(0,0,self.w, nsh)
        self.scene.addRect(0, 0, self.w, nsh,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        y = self.scene.height() - self.digit_vertical_spacing
        t = self.scene.addSimpleText("9", self.f)
        t.setPen(QPen(QColor(Qt.white)))
        t.setBrush(QBrush(QColor(Qt.white)))
        t.setY(y)
        y -= self.digit_vertical_spacing
        for i in range(10):
            t = self.scene.addSimpleText(str(i), self.f)
            t.setPen(QPen(QColor(Qt.white)))
            t.setBrush(QBrush(QColor(Qt.white)))
            t.setY(y)
            y -= self.digit_vertical_spacing
        t = self.scene.addSimpleText("0", self.f)
        t.setPen(QPen(QColor(Qt.white)))
        t.setBrush(QBrush(QColor(Qt.white)))
        assert(y==0)
        t.setY(y)
        self.setScene (self.scene)

    def redraw(self):
        scroll_value = self._value
        self.resetTransform()
        self.centerOn(self.width() / 2,
                      (10.6 - (scroll_value)) * self.digit_vertical_spacing)

    def paintEvent(self, event):
        super(NumericalScrollDisplay, self).paintEvent(event)

    def getValue(self):
        return self._value

    def setValue(self, val):
        self._value = val
        if self.isVisible():
            self.redraw()

    value = property(getValue, setValue)
