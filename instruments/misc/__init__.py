#  Copyright (c) 2018 Phil Birkelbach
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

import fix

class StaticText(QWidget):
    """Represents a simple static text display.  This is very simple and is
       really just here to keep the individual screens from having to have
       a painter object and a redraw event handler"""
    def __init__(self, text="", fontsize=1.0, color=QColor(Qt.white), parent=None):
        super(StaticText, self).__init__(parent)
        self.alignment = Qt.AlignCenter
        self.fontPercent = fontsize
        self.text = text
        self.color = color

    def resizeEvent(self, event):
        self.Font = QFont()
        self.Font.setPixelSize(self.height()*self.fontPercent)
        self.textRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Text
        pen.setColor(self.color)
        p.setPen(pen)
        p.setFont(self.Font)
        opt = QTextOption(self.alignment)
        p.drawText(self.textRect, self.text, opt)


class ValueDisplay(QWidget):
    def __init__(self, parent=None):
        super(ValueDisplay, self).__init__(parent)
        self.name = None
        self._dbkey = None
        self._value = 0.0
        self.fail = False
        self.bad = False
        self.old = False
        self.annunciate = False
        self.alignment = Qt.AlignLeft | Qt.AlignVCenter
        self.conversionFunction = lambda x: x

        # These properties can be modified by the parent
        self.outlineColor = QColor(Qt.darkGray)
        # These are the colors that are used when the value's
        # quality is marked as good
        self.bgGoodColor = QColor(Qt.black)
        self.textGoodColor = QColor(Qt.white)
        self.highlightGoodColor = QColor(Qt.magenta)

        # These colors are used for bad and fail
        self.bgBadColor = QColor(Qt.black)
        self.textBadColor = QColor(Qt.gray)
        self.highlightBadColor = QColor(Qt.darkMagenta)

        # Annunciate changes the text color
        self.textAnnunciateColor = QColor(Qt.red)

        # The following properties should not be changed by the user.
        # These are the colors that are actually used
        # for drawing gauge.
        self.bgColor = self.bgGoodColor
        self.textColor = self.textGoodColor # Non value text like units
        self.highlightColor = self.highlightGoodColor

    def resizeEvent(self, event):
        self.font = QFont()
        self.font.setPixelSize(self.height())
        self.valueRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)

        # Draw Value
        pen.setColor(self.textColor)
        p.setPen(pen)
        p.setFont(self.font)
        opt = QTextOption(self.alignment)
        p.drawText(self.valueRect, self.valueText, opt)



    def getValue(self):
        return self._value

    def setValue(self, value):
        if self.fail:
            self._value = 0.0
        else:
            cvalue = self.conversionFunction(value)
            if cvalue != self._value:
                self._value = cvalue
                self.setColors()
                self.update()

    value = property(getValue, setValue)

    def getValueText(self):
        if self.fail:
            return 'xxx'
        else:
            return str(self.value)

    valueText = property(getValueText)

    def getDbkey(self):
        return self._dbkey

    def setDbkey(self, key):
        self.item = fix.db.get_item(key)
        self.item.reportReceived.connect(self.setupGauge)
        self.item.annunciateChanged.connect(self.annunciateFlag)
        self.item.oldChanged.connect(self.oldFlag)
        self.item.badChanged.connect(self.badFlag)
        self.item.failChanged.connect(self.failFlag)

        self._dbkey = key
        self.setupGauge()

    dbkey = property(getDbkey, setDbkey)


    # This should get called when the gauge is created and then again
    # anytime a new report of the db item is recieved from the server
    def setupGauge(self):
        # min and max should always be set for FIX Gateway data.
        # set the flags
        self.fail = self.item.fail
        self.bad = self.item.bad
        self.old = self.item.old
        self.annunciate = self.item.annunciate
        self.setColors()
        # set the axuliiary data and the value
        self.setValue(self.item.value)

        try:
            self.item.valueChanged[float].disconnect(self.setValue)
            self.item.valueChanged[int].disconnect(self.setValue)
            self.item.valueChanged[bool].disconnect(self.setValue)
            self.item.valueChanged[str].disconnect(self.setValue)
        except:
            pass # One will probably fail all the time

        self.item.valueChanged[self.item.dtype].connect(self.setValue)


    def setColors(self):
        if self.bad or self.fail or self.old:
            self.bgColor = self.bgBadColor
            self.textColor = self.textBadColor
            self.highlightColor = self.highlightBadColor
        else:
            self.bgColor = self.bgGoodColor
            self.textColor = self.textGoodColor
            self.highlightColor = self.highlightGoodColor
        if self.annunciate and not self.fail:
            self.textColor = self.textAnnunciateColor

        self.update()

    def annunciateFlag(self, flag):
        self.annunciate = flag
        self.setColors()

    def failFlag(self, flag):
        self.fail = flag
        if flag:
            self.setValue(0.0)
        else:
            self.setValue(fix.db.get_item(self.dbkey).value)
        self.setColors()

    def badFlag(self, flag):
        self.bad = flag
        self.setColors()

    def oldFlag(self, flag):
        self.old = flag
        self.setColors()
