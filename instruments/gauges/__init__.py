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

import math
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import efis
import fix

def drawCircle(p, x, y, r, start, end):
    rect = QRect(x - r, y - r, r * 2, r * 2)
    p.drawArc(rect, start * 16, end * 16)


class AbstractGauge(QWidget):
    def __init__(self, parent=None):
        super(AbstractGauge, self).__init__(parent)
        self.name = None
        self.highWarn = None
        self.highAlarm = None
        self.lowWarn = None
        self.lowAlarm = None
        self.highRange = 100.0
        self.lowRange = 0.0
        self._dbkey = None
        self._value = 0.0
        self._units = ""
        self.fail = False
        self.bad = False
        self.old = False
        self.annunciate = False

        # These properties can be modified by the parent
        self.clipping = False
        self.unitsOverride = None
        self.conversionFunction = lambda x: x
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

        # These colors are used for bad and fail
        self.bgBadColor = QColor(Qt.black)
        self.safeBadColor = QColor(Qt.darkGray)
        self.warnBadColor = QColor(Qt.darkYellow)
        self.alarmBadColor = QColor(Qt.darkRed)
        self.textBadColor = QColor(Qt.gray)
        self.penBadColor = QColor(Qt.gray)

        # Annunciate changes the text color
        self.textAnnunciateColor = QColor(Qt.red)

        # The following properties should not be changed by the user.
        # These are the colors that are actually used
        # for drawing gauge.
        self.bgColor = self.bgGoodColor
        self.safeColor = self.safeGoodColor
        self.warnColor = self.warnGoodColor
        self.alarmColor = self.alarmGoodColor
        self.textColor = self.textGoodColor
        self.penColor = self.penGoodColor


    def interpolate(self, value, range_):
        h = float(range_)
        l = float(self.lowRange)
        m = float(self.highRange)
        return ((value - l) / (m - l)) * h

    def getValue(self):
        return self._value

    def setValue(self, value):
        if self.fail:
            self._value = 0.0
        else:
            cvalue = self.conversionFunction(value)
            if cvalue != self._value:
                if self.clipping:
                    self._value = efis.bounds(self.lowRange, self.highRange, cvalue)
                else:
                    self._value = cvalue
                self.update()

    value = property(getValue, setValue)

    def getValueText(self):
        if self.fail:
            return 'xxx'
        else:
            return '{0:.{1}f}'.format(float(self.value), self.decimalPlaces)

    valueText = property(getValueText)

    def getDbkey(self):
        return self._dbkey

    def setDbkey(self, key):
        #TODO Should disconnect any other signals
        # If this doesn't exist it will be a silent error.  We either have to
        # set the create flag to true or risk that we'll start before the database
        # is fully initialized.
        item = fix.db.get_item(key, True)
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
        item = fix.db.get_item(self.dbkey, True)
        # min and max should always be set for FIX Gateway data.
        if item.min: self.lowRange = item.min
        if item.max: self.highRange = item.max
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
        else:
            self.bgColor = self.bgGoodColor
            self.safeColor = self.safeGoodColor
            self.warnColor = self.warnGoodColor
            self.alarmColor = self.alarmGoodColor
            self.textColor = self.textGoodColor
            self.penColor = self.penGoodColor
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


class HorizontalBar(AbstractGauge):
    def __init__(self, parent=None):
        super(HorizontalBar, self).__init__(parent)
        self.setMinimumSize(100, 50)

    def resizeEvent(self, event):
        self.bigFont = QFont()
        self.bigFont.setPixelSize(self.height() / 2)
        self.smallFont = QFont()
        self.smallFont.setPixelSize(self.height() / 5)
        self.barHeight = self.height() / 6
        self.barTop = self.height() / 5 + 4
        self.nameTextRect = QRectF(1, 1, self.width(), self.height() / 5 + 10)
        self.valueTextRect = QRectF(1, self.barTop + self.barHeight + 4,
                                    self.width(), self.height() / 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(self.textColor)
        p.setPen(pen)
        p.setFont(self.smallFont)
        p.drawText(self.nameTextRect, self.name)
        # Main Value
        p.setFont(self.bigFont)
        opt = QTextOption(Qt.AlignLeft | Qt.AlignBottom)
        p.drawText(self.valueTextRect, self.valueText, opt)
        # Units
        p.setFont(self.smallFont)
        opt = QTextOption(Qt.AlignRight | Qt.AlignBottom)

        p.drawText(self.valueTextRect, self.units, opt)

        # Draws the bar
        p.setRenderHint(QPainter.Antialiasing, False)
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(0, self.barTop, self.width(), self.barHeight)
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn):
            p.drawRect(0, self.barTop,
                       self.interpolate(self.lowWarn, self.width()),
                       self.barHeight)
        if(self.highWarn):
            x = self.interpolate(self.highWarn, self.width())
            p.drawRect(x, self.barTop,
                       self.width() - x, self.barHeight)
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm):
            p.drawRect(0, self.barTop,
                       self.interpolate(self.lowAlarm, self.width()),
                       self.barHeight)
        if(self.highAlarm):
            x = self.interpolate(self.highAlarm, self.width())
            p.drawRect(x, self.barTop,
                       self.width() - x, self.barHeight)
        # Indicator Line
        pen.setColor(QColor(Qt.magenta))
        brush = QBrush()
        pen.setWidth(4)
        p.setPen(pen)
        p.setBrush(brush)
        x = self.interpolate(self._value, self.width())
        p.drawLine(x, self.barTop - 4,
                   x, self.barTop + self.barHeight + 4)


class ArcGauge(AbstractGauge):
    def __init__(self, parent=None):
        super(ArcGauge, self).__init__(parent)
        self.setMinimumSize(100, 50)
        self.startAngle = 45
        self.sweepAngle = 180 - 45

    def resizeEvent(self, event):
        self.arcCenter = QPoint(self.width() / 2, self.height())
        self.arcRadius = self.height() - 10

    def paintEvent(self, e):
        start = self.startAngle
        sweep = self.sweepAngle
        r = self.arcRadius
        if self.highWarn:
            warnAngle = sweep - self.interpolate(self.highWarn, sweep)
        else:
            warnAngle = 0
        if self.highAlarm:
            alarmAngle = sweep - self.interpolate(self.highAlarm, sweep)
        else:
            alarmAngle = 0
        centerX = self.arcCenter.x()
        centerY = self.arcCenter.y()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(10)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(self.alarmColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start, alarmAngle)
        pen.setColor(self.warnColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start + alarmAngle, warnAngle - alarmAngle)
        pen.setColor(self.safeColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start + warnAngle, sweep - warnAngle)
        # Now we draw the line pointer
        #pen.setColor(QColor(0xAA, 0xAA, 0xAA))
        pen.setColor(self.penColor)
        pen.setWidth(2)
        p.setPen(pen)
        valAngle = sweep - int(self.interpolate(self._value, sweep))
        theta = math.radians(start + valAngle)
        x = (r + 10) * math.sin(theta)
        y = (r + 10) * math.cos(theta)
        endPoint = QPoint(self.arcCenter.y() + y, self.arcCenter.x() - x)
        p.drawLine(self.arcCenter, endPoint)
        # Draw Text
        pen.setColor(self.textColor)
        pen.setWidth(1)
        p.setPen(pen)
        f = QFont()
        f.setPixelSize(self.height() / 5)
        p.setFont(f)
        p.drawText(QPoint(centerX - (r - 40), centerY - (r - 40)), self.name)

        f.setPixelSize(self.height() / 2)
        p.setFont(f)
        opt = QTextOption(Qt.AlignRight | Qt.AlignBottom)
        rect = QRectF(0, 0, self.width(), self.height())
        p.drawText(rect, self.valueText, opt)


class VerticalBar(AbstractGauge):
    def __init__(self, parent=None):
        super(VerticalBar, self).__init__(parent)
        self.setMinimumSize(10, 30)

    def paintEvent(self, e):
        p = QPainter()
        p.begin(self)
        p.setPen(self.outlineColor)
        p.setBrush(self.bgColor)
        height = self.height()  # keep from calling functions and shorten code
        width = self.width()
        p.drawRect(0, 0, width - 1, height - 1)
        # Calculate the positions of the setpoint lines
        if self.highWarn:
            highWarnLine = self.height() - int(self.interpolate(self.highWarn,
                                                                self.height()))
        if self.highAlarm:
            highAlarmLine = self.height() - int(self.interpolate(self.highAlarm,
                                                                 self.height()))
        # This calculates where the top of the graph should be
        valueLine = self.height() - int(self.interpolate(self._value,
                                                         self.height()))
        # Draws the Alarm (Red) part of the graph
        if self._value > self.highAlarm:
            p.setPen(self.alarmColor)
            p.setBrush(self.alarmColor)
            p.drawRect(1, valueLine, width - 3, highAlarmLine - valueLine - 1)
        # Draw the warning part of the graph if it's above the setpoint
        if self._value > self.highWarn:
            p.setPen(self.warnColor)
            p.setBrush(self.warnColor)
            start = max(valueLine, highAlarmLine)
            p.drawRect(1, start, width - 3, highWarnLine - start - 1)
        if self._value > 0:
            # Draw the green part of the graph
            p.setPen(self.safeColor)
            p.setBrush(self.safeColor)
            start = max(valueLine, highWarnLine)
            p.drawRect(1, start, width - 3, height - start - 2)
            # Draw the top of the graph
            p.setPen(QColor(Qt.white))
            p.drawLine(1, valueLine, width - 2, valueLine)
        # Draw Setpoint Lines
        if self.highWarn:
            p.setPen(self.warnColor)
            p.drawLine(1, highWarnLine, self.width() - 2, highWarnLine)
        if self.highAlarm:
            p.setPen(self.alarmColor)
            p.drawLine(1, highAlarmLine, self.width() - 2, highAlarmLine)
        p.end()
