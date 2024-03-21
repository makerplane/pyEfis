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
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from .abstract import AbstractGauge, drawCircle
from pyefis.instruments import helpers


class ArcGauge(AbstractGauge):
    def __init__(self, parent=None,min_size=True, font_family="DejaVu Sans Condensed"):
        super(ArcGauge, self).__init__(parent)
        self.font_family = font_family
        if min_size:
            self.setMinimumSize(100, 50)
        self.startAngle = 45
        self.sweepAngle = 180 - 45
        self.show_units = False
        self.name_location = 'top' # can also be 'right' above the value
        self.segments = 0
        self.segment_gap_percent = 0.01
        self.segment_alpha = 180

    def get_height(self, width):
        return width/ 2

    def get_width(self, height):
        return height * 2

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 2

    def resizeEvent(self, event):
        #Properly pick a center and arc that will fit the area defined
        if self.width() < self.height():
            self.r_height = self.get_height(self.width())
            self.r_width = self.width()
            if self.height() < self.r_height:
                self.r_height = self.height()
                self.r_width = self.get_width(self.height())
        else:
            self.r_width = self.get_width(self.height())
            self.r_height = self.height()
            if self.width() < self.r_width:
                self.r_height = self.get_height(self.width())
                self.r_width = self.width()

        c_height = ((self.height() - self.r_height)  / 2) + self.r_height
        self.lrcx = self.width() - ((self.width()  - self.r_width)  / 2)
        self.lrcy =  self.height() - ((self.height() - self.r_height)  / 2)
        self.tlcx = 0 +  ((self.width() - self.r_width)   / 2)
        self.tlcy = 0 + ((self.height() - self.r_height)  / 2)

        self.pointer_width = self.r_height / 20
        self.arcCenter = QPointF(self.r_width / 2, self.r_height -  self.pointer_width)

        self.arcRadius = (self.r_height * 0.9) - self.pointer_width

        # A polygon for the pointer
        self.arrow = QPolygonF()
        self.arrow.append(QPointF(0,self.arcRadius * .4))
        self.arrow.append(QPointF(self.pointer_width,self.pointer_width+self.arcRadius * .5))
        self.arrow.append(QPointF(1, self.arcRadius * 1.1))
        self.arrow.append(QPointF(-1, self.arcRadius * 1.1))
        self.arrow.append(QPointF(-self.pointer_width,self.pointer_width+self.arcRadius * .5))
        self.arrow.append(QPointF(0,self.arcRadius * .4))
        self.valueFontSize = self.r_height / 3
        if self.font_mask:
            self.valueFontSize = helpers.fit_to_mask(self.r_width / 1.7, self.r_height / 2.8, self.font_mask, self.font_family)
        self.unitsFontSize = qRound(self.height() / 4)
        if self.units_font_mask:
            self.unitsFontSize = helpers.fit_to_mask(self.r_width / 6, (self.r_height / 2.8)/2, self.units_font_mask, self.font_family)
        self.nameFontSize = qRound(self.r_height / 6)
        if self.name_font_mask:
            if self.name_location == 'top':
                self.nameFontSize = helpers.fit_to_mask(self.r_width / 6, (self.r_height / 2.8)/2, self.name_font_mask, self.font_family)
            elif self.name_location == 'right':
                self.nameFontSize = helpers.fit_to_mask(self.r_width / 2.1, (self.r_height / 2.8)/2, self.name_font_mask, self.font_family)

        
    def paintEvent(self, e):
        start = self.startAngle
        sweep = self.sweepAngle
        r = self.arcRadius
        if self.lowWarn:
            lowWarnAngle = self.interpolate(self.lowWarn, sweep)
            if lowWarnAngle < 0: lowWarnAngle = 0
        else:
            lowWarnAngle = 0
        if self.lowAlarm:
            lowAlarmAngle = self.interpolate(self.lowAlarm, sweep)
            if lowAlarmAngle < 0: lowAlarmAngle = 0
        else:
            lowAlarmAngle = 0

        if self.highWarn:
            highWarnAngle = self.interpolate(self.highWarn, sweep)
            if highWarnAngle > sweep: highWarnAngle = sweep
        else:
            highWarnAngle = sweep
        if self.highAlarm:
            highAlarmAngle = self.interpolate(self.highAlarm, sweep)
            if highAlarmAngle > sweep: highAlarmAngle = sweep
        else:
            highAlarmAngle = sweep
        centerX = self.arcCenter.x()
        centerY = self.arcCenter.y()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen()
        pen.setWidth(qRound(self.r_height * 0.18))
        pen.setCapStyle(Qt.FlatCap)

        # Red Arcs
        pen.setColor(self.alarmColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start, sweep - highAlarmAngle)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                   start+sweep, -lowAlarmAngle)

        # Yellow Arcs
        pen.setColor(self.warnColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start + (sweep-highAlarmAngle), -(highWarnAngle - highAlarmAngle))
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start+sweep-lowAlarmAngle, -(lowWarnAngle-lowAlarmAngle))

        # Green Arc
        pen.setColor(self.safeColor)
        p.setPen(pen)
        drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
        start + (sweep - highWarnAngle), highWarnAngle-lowWarnAngle)

        # Draw segments
        if self.segments > 0:
            pen.setWidth(qRound(self.r_height * 0.2))
            segment_gap = (sweep) * self.segment_gap_percent
            segment_size = ((sweep) - (segment_gap * (self.segments - 1)))/self.segments
            pen.setColor(Qt.black)
            p.setPen(pen)
            for segment in range(self.segments - 1):
                ds = start + ((segment + 1) * segment_size) + (segment * segment_gap)
                drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
                ds, segment_gap)
        # Now we draw the line pointer
        valAngle = 90 + self.interpolate(self._value, sweep)
        t = QTransform()
        t.translate(self.arcCenter.x(), self.arcCenter.y())
        t.rotate(valAngle)
        arrow = t.map(self.arrow)
        #if not self.segments > 0:
        if self.segments > 0:
            pen.setWidth(qRound(self.r_height * 0.2))
            pen.setCapStyle(Qt.FlatCap)
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            drawCircle(p, self.arcCenter.x(), self.arcCenter.y(), r,
            180+90-valAngle,-(180+90-valAngle-45+1))


        brush = QBrush(self.penColor)
        pen.setColor(QColor(Qt.black))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        p.drawPolygon(arrow)

        # Draw Text
        pen.setColor(self.textColor)
        pen.setWidth(1)
        p.setPen(pen)
        f = QFont(self.font_family)
        #f.setPixelSize(qRound(self.r_height / 2))
        y = f.pixelSize()
        if self.name_font_mask:
            f.setPointSizeF(self.nameFontSize)
        else:
            f.setPixelSize(self.nameFontSize)
        fm = QFontMetrics(f)
        if self.name_font_mask:
            if self.name_font_ghost_mask:
                x = fm.width(self.name_font_ghost_mask)
            else: 
                x = fm.width(self.name_font_mask)
        else:
            x = fm.width(self.name)
        p.setFont(f)
        #if self.font_ghost_mask:
        #    alpha = self.textColor.alpha()
        #    self.textColor.setAlpha(self.font_ghost_alpha)
            
        if self.name_location == 'top':
            if self.name_font_mask:
                opt = QTextOption(Qt.AlignLeft)
                if self.name_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(QRectF(self.tlcx,self.tlcy,(self.r_width / 6), self.r_height / 6),self.name_font_ghost_mask, opt)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(QRectF(self.tlcx,self.tlcy,(self.r_width / 6), self.r_height / 6),self.name, opt)
            else:
                p.drawText(QPointF(self.tlcx + (self.r_width / 20),self.tlcy + f.pixelSize()), self.name)
        elif self.name_location == 'right':
            if self.name_font_mask:
                opt = QTextOption(Qt.AlignRight)
                if self.name_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    #p.drawText(QRectF(self.tlcx,self.tlcy,(self.r_width / 2), self.r_height / 6),self.name_font_ghost_mask, opt)
                    #p.drawText(QPointF( self.lrcx - x, self.lrcy - (y/1.2)  ), self.name_font_ghost_mask)
                    p.drawText(QRectF(x, self.tlcy + (self.r_height /2.2) ,(self.r_width / 2), self.r_height / 6),self.name_font_ghost_mask, opt)

                    #p.drawText(QRectF(
                    self.textColor.setAlpha(alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(QRectF(x, self.tlcy + (self.r_height /2.2) ,(self.r_width / 2), self.r_height / 6),self.name, opt)
                #p.drawText(QPointF( self.lrcx - x, self.lrcy - (y/1.2)  ), self.name)
            else:
                p.drawText(QPointF( self.lrcx - x, self.lrcy - (y/1.2)  ), self.name)
        # Main value text
        if self.font_mask:
            opt = QTextOption(Qt.AlignRight)
        else:
            opt = QTextOption(Qt.AlignCenter)
        path = QPainterPath()
        brush = QBrush(self.valueColor)
        p.setBrush(brush)
        pen.setColor(self.valueColor)
        #pen.setColor(QColor(Qt.black))
        p.setPen(pen)

        #f.setPixelSize(qRound(self.r_height / 2.6))
        if self.font_mask:
            f.setPointSizeF(self.valueFontSize)
        else:
            f.setPixelSize(qRound(self.r_height / 2))

        fm = QFontMetrics(f)
        if self.font_mask:
            x = fm.width(self.font_mask)
        else:
            x = fm.width(self.valueText)
        ux = 0
        if self.show_units:
            #f.setPixelSize(qRound(self.height() / 4))
            #f.setPointSizeF(self.valueFontSize/2)
            #fmu = QFontMetrics(f)
            if self.units_font_mask:
                f.setPointSizeF(self.unitsFontSize)
                fmu = QFontMetrics(f)
                ux = fmu.width(self.units_font_mask)
            else:
                #f.setPointSizeF(self.valueFontSize/2)
                f.setPixelSize(qRound(self.height() / 4))
                fmu = QFontMetrics(f)
                ux = fmu.width(self.units)
            uy = fmu.ascent() - fmu.descent()
            #path.addText(QPointF( self.lrcx - ux, self.lrcy - uy),f, self.units)
            if self.units_font_ghost_mask:
                alpha = self.valueColor.alpha()
                self.valueColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.valueColor)
                p.setPen(pen)
                p.drawText(QPointF( self.lrcx - ux, self.lrcy - uy), self.units_font_ghost_mask)
                self.valueColor.setAlpha(alpha)

            pen.setColor(self.valueColor)
            p.setPen(pen)
            p.drawText(QPointF( self.lrcx - ux, self.lrcy - uy), self.units)

        if self.font_mask:
            f.setPointSizeF(self.valueFontSize)
        else:
            f.setPixelSize(qRound(self.height() / 2))
        #f.setPointSizeF(self.valueFontSize)
        #f.setPointSizeF(self.valueFontSize)
        p.setFont(f)
        if self.font_ghost_mask:
            alpha = self.valueColor.alpha()
            self.valueColor.setAlpha(self.font_ghost_alpha)
            #abrush = QBrush(self.valueColor)
            #p.setBrush(abrush)
            #path2 = QPainterPath()
            #path2.addText(QPointF( self.lrcx - x -ux , self.lrcy - 1),f, self.font_ghost_mask)
            pen.setColor(self.valueColor)
            p.setPen(pen)

            #p.drawPath(path2)
            p.drawText(QRectF( self.lrcx - x -ux, self.lrcy - 1 - (self.r_height / 2.8) , (self.r_width / 1.7) , self.r_height / 2.8),self.font_ghost_mask, opt)
            self.valueColor.setAlpha(alpha)
            #brush = QBrush(self.valueColor)
        #p.setBrush(brush)
        pen.setColor(self.valueColor)
        p.setPen(pen)
        if self.font_mask:
            p.drawText(QRectF( self.lrcx - x -ux , self.lrcy - 1 - (self.r_height / 2.8) , (self.r_width / 1.7) , self.r_height / 2.8),self.valueText, opt)
        else:
            path.addText(QPointF( self.lrcx - x -ux , self.lrcy - 1),f, self.valueText)
            p.drawPath(path)

        #p.drawPath(path)

