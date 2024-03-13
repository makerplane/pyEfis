#  Copyright (c) 2013 Phil Birkelbach
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

import pyavtools.fix as fix
import pyefis.hmi as hmi

def drawCircle(p, x, y, r, start, end):
    rect = QRectF(x - r, y - r, r * 2, r * 2)
    p.drawArc(rect, qRound(start * 16), qRound(end * 16))

class AbstractGauge(QWidget):
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(AbstractGauge, self).__init__(parent)
        self.font_family = font_family
        self.font_ghost_mask = None
        self.font_ghost_alpha = 50
        self.font_mask = None
        self.name = None
        self.highWarn = None
        self.highAlarm = None
        self.lowWarn = None
        self.lowAlarm = None
        self.highRange = 100.0
        self.lowRange = 0.0
        self._dbkey = None
        self.highlightKey = None
        self._highlightValue = 0.0
        self._value = 0.0
        self._rawValue = 0.0
        self.peakValue = 0.0
        self._units = ""
        self.fail = False
        self.bad = False
        self.old = False
        self.annunciate = False
        self.highlight = False
        self.peakMode = False
        self.__unitSwitching = False
        self.unitGroup = ""


        # These properties can be modified by the parent
        self.clipping = False
        self.unitsOverride1 = None
        self.unitsOverride2 = None
        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.decimalPlaces = 1
        # All these colors can be modified by the parent
        self.outlineColor = QColor(Qt.darkGray)
        # These are the colors that are used when the value's
        # quality is marked as good
        self.bgGoodColor = QColor(Qt.black)
        self.safeGoodColor = QColor(Qt.green)
        self.warnGoodColor = QColor(Qt.yellow)
        self.alarmGoodColor = QColor(Qt.red)
        self.textGoodColor = QColor(Qt.white)
        self.penGoodColor = QColor(Qt.white)
        self.highlightGoodColor = QColor(Qt.magenta)

        # These colors are used for bad and fail
        self.bgBadColor = QColor(Qt.black)
        self.safeBadColor = QColor(Qt.darkGray)
        self.warnBadColor = QColor(Qt.darkYellow)
        self.alarmBadColor = QColor(Qt.darkRed)
        self.textBadColor = QColor(Qt.gray)
        self.penBadColor = QColor(Qt.gray)
        self.highlightBadColor = QColor(Qt.darkMagenta)

        # Annunciate changes the text color
        self.textAnnunciateColor = QColor(Qt.red)

        # The following properties should not be changed by the user.
        # These are set real time based on changes in different states
        # like data quality, selected units or modes
        self.bgColor = self.bgGoodColor
        self.safeColor = self.safeGoodColor
        self.warnColor = self.warnGoodColor
        self.alarmColor = self.alarmGoodColor
        self.textColor = self.textGoodColor # Non value text like units
        self.valueColor = self.textGoodColor # The actual value text
        self.penColor = self.penGoodColor # The line on the gauge
        self.highlightColor = self.highlightGoodColor
        self.unitsOverride = None
        self.conversionFunction = lambda x: x

    def interpolate(self, value, range_):
        h = float(range_)
        l = float(self.lowRange)
        m = float(self.highRange)
        if m != l:
            return ((value - l) / (m - l)) * h
        else:
            return 0

    def getValue(self):
        return self._value

    def setValue(self, value):
        self._rawValue = value
        if self.fail:
            self._value = 0.0
        else:
            cvalue = self.conversionFunction(value)
            if cvalue != self._value:
                if self.clipping:
                    self._value = common.bounds(self.lowRange, self.highRange, cvalue)
                else:
                    self._value = cvalue
                self.setColors()
                self.update()
        if self._value > self.peakValue:
            self.peakValue = self._value

    value = property(getValue, setValue)

    def getValueText(self):
        if self.fail:
            return 'xxx'
        else:
            return '{0:.{1}f}'.format(float(self.value), self.decimalPlaces)

    valueText = property(getValueText)

    def setHighlightValue(self,value):
        self._highlightValue = value
        self.update()

    def getDbkey(self):
        return self._dbkey

    def setDbkey(self, key):
        item = fix.db.get_item(key)
        item.auxChanged.connect(self.setAuxData)
        item.reportReceived.connect(self.setupGauge)
        item.annunciateChanged.connect(self.annunciateFlag)
        item.oldChanged.connect(self.oldFlag)
        item.badChanged.connect(self.badFlag)
        item.failChanged.connect(self.failFlag)

        self._dbkey = key
        self.setupGauge()

    dbkey = property(getDbkey, setDbkey)

    def getUnits(self):
        if self.unitsOverride:
            return self.unitsOverride
        else:
            return self._units

    def setUnits(self, value):
        self._units = value

    units = property(getUnits, setUnits)

    # This should get called when the gauge is created and then again
    # anytime a new report of the db item is recieved from the server
    def setupGauge(self):
        item = fix.db.get_item(self.dbkey)
        # min and max should always be set for FIX Gateway data.
        if item.min: self.lowRange = self.conversionFunction(item.min)
        if item.max: self.highRange = self.conversionFunction(item.max)
        self._units = item.units
        # set the flags
        self.fail = item.fail
        self.bad = item.bad
        self.old = item.old
        self.annunciate = item.annunciate
        self.setColors()
        # set the axuliiary data and the value
        self.setAuxData(item.aux)
        self.setValue(item.value)

        # TODO We have to redo the valueChanged signals because the
        # datatype may have changed
        try:
            item.valueChanged[float].disconnect(self.setValue)
        except:
            pass # One will probably fail all the time
        try:
            item.valueChanged[int].disconnect(self.setValue)
        except:
            pass # One will probably fail all the time

        if item.dtype == float:
            item.valueChanged[float].connect(self.setValue)
        elif item.dtype == int:
            item.valueChanged[int].connect(self.setValue)

        if self.highlightKey:
            highlightItem = fix.db.get_item(self.highlightKey)
            self.setHighlightValue(highlightItem.value)

            try:
                highlightItem.valueChanged[float].disconnect(self.setHighlightValue)
            except:
                pass # One will probably fail all the time
            try:
                highlightItem.valueChanged[int].disconnect(self.setHighlightValue)
            except:
                pass # One will probably fail all the time

            if highlightItem.dtype == float:
                highlightItem.valueChanged[float].connect(self.setHighlightValue)
            elif highlightItem.dtype == int:
                highlightItem.valueChanged[int].connect(self.setHighlightValue)


    def setAuxData(self, auxdata):
        if "Min" in auxdata and auxdata["Min"] != None:
            self.lowRange = self.conversionFunction(auxdata["Min"])
        if "Max" in auxdata and auxdata["Max"] != None:
            self.highRange = self.conversionFunction(auxdata["Max"])
        if "lowWarn" in auxdata and auxdata["lowWarn"] != None:
            self.lowWarn = self.conversionFunction(auxdata["lowWarn"])
        if "lowAlarm" in auxdata and auxdata["lowAlarm"] != None:
            self.lowAlarm = self.conversionFunction(auxdata["lowAlarm"])
        if "highWarn" in auxdata and auxdata["highWarn"] != None:
            self.highWarn = self.conversionFunction(auxdata["highWarn"])
        if "highAlarm" in auxdata and auxdata["highAlarm"] != None:
            self.highAlarm = self.conversionFunction(auxdata["highAlarm"])
        self.update()

    def setColors(self):
        if self.bad or self.fail or self.old:
            self.bgColor = self.bgBadColor
            self.safeColor = self.safeBadColor
            self.warnColor = self.warnBadColor
            self.alarmColor = self.alarmBadColor
            self.textColor = self.textBadColor
            self.penColor = self.penBadColor
            self.highlightColor = self.highlightBadColor
        else:
            self.bgColor = self.bgGoodColor
            self.safeColor = self.safeGoodColor
            self.warnColor = self.warnGoodColor
            self.alarmColor = self.alarmGoodColor
            self.textColor = self.textGoodColor
            self.penColor = self.penGoodColor
            self.highlightColor = self.highlightGoodColor
        if self.annunciate and not self.fail:
            self.textColor = self.textAnnunciateColor

        self.valueColor = self.textColor
        if self.lowWarn != None and self.value < self.lowWarn:
            self.valueColor = self.warnColor
        if self.highWarn != None and self.value > self.highWarn:
            self.valueColor = self.warnColor
        if self.lowAlarm != None and self.value < self.lowAlarm:
            self.valueColor = self.alarmColor
        if self.highAlarm != None and self.value > self.highAlarm:
            self.valueColor = self.alarmColor

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

    def resetPeak(self):
        self.peakValue = self.value
        self.update()

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        self.update()

    def setUnits(self, args):
        x = args.split(':')
        command = x[1].lower()
        names = x[0].split(',')
        if self.dbkey in names or '*' in names or self.unitGroup in names:
            item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            self.setAuxData(item.aux) # Trigger conversion for aux data
            self.value = item.value # Trigger the conversion for value
