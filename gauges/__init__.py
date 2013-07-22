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

import sys
import math
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.Qt
import efis

def drawCircle(p, x, y, r, start, end):
    rect = QRect(x-r, y-r, r*2, r*2)
    p.drawArc(rect, start*16, end*16)

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
        self._value = 0
        self.outlineColor = QColor(Qt.darkGray)
        self.bgColor = QColor(Qt.black)
        self.safeColor = QColor(Qt.green)
        self.warnColor = QColor(Qt.yellow)
        self.alarmColor = QColor(Qt.red)
    
    def interpolate(self, value, range_):
        h = float(range_)
        l = float(self.lowRange)
        m = float(self.highRange)
        return ((value - l) / (m - l)) * h

    def setValue(self, value):
        if value != self._value:
            self._value = efis.bounds(self.lowRange, self.highRange, value)
            self.update()
    
    def getValue(self):
        return self._value
        
    value = property(getValue, setValue) 

class HorizontalBar(AbstractGauge):
    def __init__(self, parent=None):
        super(HorizontalBar, self).__init__(parent)
        self.setMinimumSize(100,50)
        self.decimalPlaces = 1
        
    def resizeEvent(self,event):
        self.bigFont = QFont()
        self.bigFont.setPixelSize(self.height()/2)
        self.smallFont = QFont()
        self.smallFont.setPixelSize(self.height()/5)
        self.barHeight = self.height()/6
        self.barTop = self.height()/5 + 4
        self.nameTextRect = QRectF(1,1,self.width(),self.height()/5+10)
        self.valueTextRect = QRectF(1,self.barTop + self.barHeight+4, 
                                    self.width(), self.height()/2)
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(QColor(Qt.white))
        p.setPen(pen)
        p.setFont(self.smallFont)
        p.drawText(self.nameTextRect, self.name)
        # Main Value
        p.setFont(self.bigFont)
        s = '{0:.{1}f}'.format(float(self.value), self.decimalPlaces)
        opt = QTextOption(Qt.AlignLeft | Qt.AlignBottom)
        p.drawText(self.valueTextRect, s, opt)
        # Units
        p.setFont(self.smallFont)
        opt = QTextOption(Qt.AlignRight | Qt.AlignBottom)
        p.drawText(self.valueTextRect, self.units, opt)
        
        # Draws the bar
        p.setRenderHint(QPainter.Antialiasing, False)
        pen.setColor(QColor(Qt.green))
        brush= QColor(Qt.green)
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(0,self.barTop,self.width(), self.barHeight)
        pen.setColor(QColor(Qt.yellow))
        brush= QColor(Qt.yellow)
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowWarn):
            p.drawRect(0,self.barTop,
                       self.interpolate(self.lowWarn,self.width()),self.barHeight)
        if(self.highWarn):
            x = self.interpolate(self.highWarn,self.width())
            p.drawRect(x,self.barTop,
                       self.width()-x,self.barHeight)
        pen.setColor(QColor(Qt.red))
        brush= QColor(Qt.red)
        p.setPen(pen)
        p.setBrush(brush)
        if(self.lowAlarm):
            p.drawRect(0,self.barTop,
                       self.interpolate(self.lowAlarm,self.width()),self.barHeight)
        if(self.highAlarm):
            x = self.interpolate(self.highAlarm,self.width())
            p.drawRect(x,self.barTop,
                       self.width()-x,self.barHeight)
        # Indicator Line
        pen.setColor(QColor(Qt.magenta))
        brush = QBrush()
        pen.setWidth(4)
        p.setPen(pen)
        p.setBrush(brush)
        x = self.interpolate(self._value,self.width())
        p.drawLine(x, self.barTop - 4,
                   x, self.barTop + self.barHeight + 4)
        

class RoundGauge(AbstractGauge):
    def __init__(self, parent=None):
        super(RoundGauge, self).__init__(parent)
        self.setMinimumSize(100,50)
        self.startAngle = 45
        self.sweepAngle = 180-45
        self.decimalPlaces = 1
    
    def resizeEvent(self, event):
        self.arcCenter = QPoint(self.width()/2,self.height())
        self.arcRadius = self.height() - 10
        
    def paintEvent(self, e):
        start = self.startAngle
        sweep = self.sweepAngle
        r = self.arcRadius
        warnAngle = sweep - self.interpolate(self.highWarn, sweep)
        alarmAngle = sweep - self.interpolate(self.highAlarm, sweep)
        centerX = self.arcCenter.x()
        centerY = self.arcCenter.y()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(10)
        pen.setCapStyle(Qt.FlatCap)
        pen.setColor(QColor(Qt.red))
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r, start, alarmAngle)
        pen.setColor(QColor(Qt.yellow))
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r, start+alarmAngle, warnAngle-alarmAngle)
        pen.setColor(QColor(Qt.green))
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r, start+warnAngle, sweep-warnAngle)
        # Now we draw the line pointer
        pen.setColor(QColor(0xAA,0xAA,0xAA))
        pen.setWidth(2)
        p.setPen(pen)
        valAngle = sweep - int(self.interpolate(self._value, sweep))
        theta = math.radians(start + valAngle)
        x = (r+10) * math.sin(theta)
        y = (r+10) * math.cos(theta)
        endPoint = QPoint(self.arcCenter.y()+y, self.arcCenter.x()-x)
        p.drawLine(self.arcCenter, endPoint)
        # Draw Text
        pen.setColor(QColor(Qt.white))
        pen.setWidth(1)
        p.setPen(pen)
        f = QFont()
        f.setPixelSize(self.height()/5)
        p.setFont(f)
        p.drawText(QPoint(centerX-(r-40), centerY-(r-40)), self.name)
        
        f.setPixelSize(self.height()/2)
        p.setFont(f)
        s = '{0:.{1}f}'.format(float(self.value), self.decimalPlaces)
        opt = QTextOption(Qt.AlignRight | Qt.AlignBottom)
        rect = QRectF(0,0,self.width(), self.height())
        p.drawText(rect, s, opt)
        
class VerticalBar(AbstractGauge):
    def __init__(self, parent=None):
        super(VerticalBar, self).__init__(parent)
        self.setMinimumSize(10,30)
        
    def paintEvent(self, e):
        p = QPainter()
        p.begin(self)
        p.setPen(self.outlineColor)
        p.setBrush(self.bgColor)
        height = self.height() #keep from calling functions and shorten code
        width = self.width()
        p.drawRect(0,0,width-1,height-1)
        # Calculate the positions of the setpoint lines
        if self.highWarn:
            highWarnLine = self.height() - int(self.interpolate(self.highWarn, self.height()))
        if self.highAlarm:
            highAlarmLine = self.height() - int(self.interpolate(self.highAlarm, self.height()))
        # This calculates where the top of the graph should be
        valueLine = self.height() - int(self.interpolate(self._value, self.height()))
        # Draws the Alarm (Red) part of the graph
        if self._value > self.highAlarm:
            p.setPen(self.alarmColor)
            p.setBrush(self.alarmColor)
            p.drawRect(1, valueLine, width-3, highAlarmLine-valueLine-1)
        # Draw the warning part of the graph if it's above the setpoint
        if self._value > self.highWarn:
            p.setPen(self.warnColor)
            p.setBrush(self.warnColor)
            start = max(valueLine, highAlarmLine)
            p.drawRect(1, start, width-3, highWarnLine-start-1)  
        if self._value > 0:
            # Draw the green part of the graph
            p.setPen(self.safeColor)
            p.setBrush(self.safeColor)
            start = max(valueLine, highWarnLine)
            p.drawRect(1, start, width-3, height-start-2)  
            # Draw the top of the graph
            p.setPen(QColor(Qt.white))
            p.drawLine(1, valueLine, width-2, valueLine)
        # Draw Setpoint Lines
        if self.highWarn:
            p.setPen(self.warnColor)
            p.drawLine(1,highWarnLine,self.width()-2,highWarnLine)
        if self.highAlarm:
            p.setPen(self.alarmColor)
            p.drawLine(1,highAlarmLine,self.width()-2,highAlarmLine)
        p.end()
    
