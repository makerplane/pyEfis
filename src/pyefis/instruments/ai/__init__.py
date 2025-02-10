#  Copyright (c) 2013 Phil Birkelbach; 2018-2019 Garrett Herschleb
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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import math
import time
import logging

import pyavtools.fix as fix
from pyefis import common

log = logging.getLogger(__name__)

# TODO:
#   Check TAS quality and revert to turn rate indication
#   Fix quality indications
#   Add quality flags to indicate the actual failures
#   Remove internal assignments of database items.  Should be a normal
#      Qt widget and these things done externally.
#   Add configuration for bank angle tick sizes

class AI(QGraphicsView):
    def __init__(self, parent=None,font_percent=None, font_family="DejaVu Sans Condensed"):
        super(AI, self).__init__(parent)
        self.myparent = parent
        self.font_family = font_family
        # The following information is meant to be configurable from the screen
        # definition file
        self.font_percent = font_percent
        if self.font_percent:
            self.fontSize = qRound(self.width() * self.font_percent)
        else:
            self.fontSize = 30
        # Number of degrees shown from top to bottom
        self.pitchDegreesShown = 60
        # Pitch tick mark configurations
        self.minorDiv = 1   # Degrees between minor divisions
        self.majorDiv = 5  # Degrees between major divisions
        self.numberedDiv = 10 # Degrees between numbered divisions
        # Line widths of the pitch tick marks
        self.minorDivWidth = 10
        self.majorDivWidth = 40
        self.numberedDivWidth = 50
        self.visiblePitchAngle = 15 # Amount of visible pitch angle marks
        self.pitchOpacity = 0.6
        # Bank angle tick indicators
        self.bankMarkSize = 10
        # Standard rate turn bank angle indicators.
        self.drawBankMarkers = True
        self.bankAngleRadius = None # Radius of the bank angle markings
        self.bankAngleMaximum = 25  # Largest bank angle that will be indicated

        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Assume True until told otherwise
        self._AIOld = dict()
        self._AIBad = dict()
        self._AIFail = dict()
        for p in ['PITCH', 'ROLL','ALAT','TAS']:
            self._AIOld[p] = True
            self._AIBad[p] = True
            self._AIFail[p] = True
        pitch = fix.db.get_item("PITCH")
        pitch.valueChanged[float].connect(self.setPitchAngle)
        pitch.oldChanged[bool].connect(self.setAIOldPitch)
        pitch.badChanged[bool].connect(self.setAIBadPitch)
        pitch.failChanged[bool].connect(self.setAIFailPitch)
        self._AIOld['PITCH'] = pitch.old
        self._AIBad['PITCH'] = pitch.bad
        self._AIFail['PITCH'] = pitch.fail
        self._pitchAngle = pitch.value
        roll = fix.db.get_item("ROLL")
        roll.valueChanged[float].connect(self.setRollAngle)
        roll.oldChanged[bool].connect(self.setAIOldRoll)
        roll.badChanged[bool].connect(self.setAIBadRoll)
        roll.failChanged[bool].connect(self.setAIFailRoll)
        self._rollAngle = roll.value
        self._AIOld['ROLL'] = roll.old
        self._AIBad['ROLL'] = roll.bad
        self._AIFail['ROLL'] = roll.fail
        alat = fix.db.get_item("ALAT")
        alat.valueChanged[float].connect(self.setLateralAcceleration)
        alat.oldChanged[bool].connect(self.setAIOldLAcc)
        alat.badChanged[bool].connect(self.setAIBadLAcc)
        alat.failChanged[bool].connect(self.setAIFailLAcc)
        self._AIOld['ALAT'] = alat.old
        self._AIBad['ALAT'] = alat.bad
        self._AIFail['ALAT'] = alat.fail
        self._latAccel = alat.value
        tas = fix.db.get_item("TAS")
        tas.valueChanged[float].connect(self.setTrueAirspeed)
        tas.oldChanged[bool].connect(self.setAIOldTAS)
        tas.badChanged[bool].connect(self.setAIBadTAS)
        tas.failChanged[bool].connect(self.setAIFailTAS)
        self._AIOld['TAS'] = tas.old
        self._AIBad['TAS'] = tas.bad
        self._AIFail['TAS'] = tas.fail

        self._tas = tas.value

        # We store all the pitch tick marks and text in a list so that
        # we can adjust the opacity of the items.
        self.pitchItems = []

    def resizeEvent(self, event):
        if self.font_percent:
            self.fontSize = qRound(self.width() * self.font_percent)
            self.minorDivWidth = qRound(self.fontSize * 0.3)
            self.majorDivWidth = self.minorDivWidth * 4
            self.numberedDivWidth = self.minorDivWidth * 5
            self.bankMarkSize = qRound(self.fontSize * 0.3 )
        #Setup the scene that we use for the background of the AI
        sceneHeight = self.height() * 4.5
        sceneWidth = math.sqrt(self.width() * self.width() +
                               self.height() * self.height())
        self.pixelsPerDeg = self.height() / self.pitchDegreesShown
        self.scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)
        # Setup default values
        if self.bankAngleRadius is None:
            self.bankAngleRadius = self.height() / 3
        # Get a failure scene ready in case it's needed
        self.fail_scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)
        self.fail_scene.addRect(0,0, sceneWidth, sceneHeight, QPen(QColor(Qt.GlobalColor.white)), QBrush(QColor(50,50,50)))
        font = QFont(self.font_family, 80, QFont.Weight.Bold)
        t = self.fail_scene.addSimpleText("XXX", font)
        t.setPen (QPen(QColor(Qt.GlobalColor.red)))
        t.setBrush (QBrush(QColor(Qt.GlobalColor.red)))
        r = t.boundingRect()
        t.setPos ((sceneWidth-r.width())/2, (sceneHeight-r.height())/2)

        #Draw the Blue and Brown rectangles
        gradientBlue = QLinearGradient(0, 0, 0, sceneHeight / 2)
        gradientBlue.setColorAt(0.7, QColor(0, 51, 102))
        gradientBlue.setColorAt(1.0, QColor(51, 153, 255))
        gradientBlue.setSpread(QGradient.Spread.PadSpread)
        self.blue_pen = QPen(QColor(Qt.GlobalColor.blue))
        self.gblue_brush = QBrush(gradientBlue)
        gradientLGray = QLinearGradient(0, 0, 0, sceneHeight / 2)
        gradientLGray.setColorAt(0.7, QColor(100, 100, 100))
        gradientLGray.setColorAt(1.0, QColor(153, 153, 153))
        gradientLGray.setSpread(QGradient.Spread.PadSpread)
        self.gray_sky = QBrush(gradientLGray)
        if self.getAIOld() or self.getAIBad():
            brush = self.gray_sky
        else:
            brush = self.gblue_brush
        self.sky_rect = self.scene.addRect(0, 0, sceneWidth, sceneHeight / 2, self.blue_pen, brush)
        self.setScene(self.scene)
        gradientBrown = QLinearGradient(0, sceneHeight / 2, 0, sceneHeight)
        gradientBrown.setColorAt(0.0, QColor(105, 46, 1))
        gradientBrown.setColorAt(0.3, QColor(244, 164, 96))
        gradientBrown.setSpread(QGradient.Spread.PadSpread)
        self.brown_pen = QPen(QColor(160, 82, 45))  # Brown Color
        self.gbrown_brush = QBrush(gradientBrown)
        gradientDGray = QLinearGradient(0, sceneHeight / 2, 0, sceneHeight)
        gradientDGray.setColorAt(0.0, QColor(20, 20, 20))
        gradientDGray.setColorAt(0.2, QColor(75, 75, 75))
        gradientDGray.setSpread(QGradient.Spread.PadSpread)
        self.gray_land = QBrush(gradientDGray)
        if self.getAIOld() or self.getAIBad():
            brush = self.gray_land
        else:
            brush = self.gbrown_brush
        self.land_rect = self.scene.addRect(0, sceneHeight / 2 + 1, sceneWidth, sceneHeight,
                           self.brown_pen, brush)

        self.setScene(self.scene)

        #Draw the main horizontal line
        pen = QPen(QColor(Qt.GlobalColor.white))
        pen.setWidth(qRound(self.fontSize * 0.05))
        self.scene.addLine(0, sceneHeight / 2, sceneWidth, sceneHeight / 2, pen)
        # draw the degree hash marks
        pen.setColor(Qt.GlobalColor.white)
        w = self.scene.width()
        h = self.scene.height()
        f = QFont(self.font_family)
        f.setPixelSize(self.fontSize)

        # Draw the tick mark lines on the scene
        for i in range(-90, 91):
            if i == 0:  # Don't draw a line at zero
                pass
            elif i % self.numberedDiv == 0:
                left = w / 2 - self.numberedDivWidth / 2
                right = w / 2 + self.numberedDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i

                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))
                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(Qt.GlobalColor.white)
                t.setX(right + 5)
                t.setY(y - t.boundingRect().height() / 2)
                t.setZValue(1)
                self.pitchItems.append((i, t))

                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(Qt.GlobalColor.white)
                t.setX(left - (t.boundingRect().width() + 5))
                t.setY(y - t.boundingRect().height() / 2)
                t.setZValue(1)
                self.pitchItems.append((i, t))

            elif i % self.majorDiv == 0:
                left = w / 2 - self.majorDivWidth / 2
                right = w / 2 + self.majorDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i
                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))

            elif i % self.minorDiv == 0:
                left = w / 2 - self.minorDivWidth / 2
                right = w / 2 + self.minorDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i
                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))
        self.setPitchItems()

        # Draws the static overlay stuff to a pixmap
        self.map = QPixmap(self.width(), self.height())
        self.map.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.map)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # change width and height to the view instead of the scene
        w = self.width()
        h = self.height()
        r = self.bankAngleRadius
        p.setPen(QColor(Qt.GlobalColor.black))
        p.setBrush(QColor(Qt.GlobalColor.yellow))
        p.drawRect(QRectF(w / 4, h / 2 - 3, w / 6, 6))
        p.drawRect(QRectF(w - w / 4 - w / 6, h / 2 - 3, w / 6, 6))
        p.drawEllipse(QRectF(w / 2 - 3, h / 2 - 3, 9, 9))
        # p.setPen(QColor(Qt.GlobalColor.black))
        # p.setBrush(QColor(Qt.GlobalColor.white))

        m = self.bankMarkSize
        p.setBrush(QColor(Qt.GlobalColor.white))
        p.translate(w / 2, h/2 - r)
        triangle = QPolygonF([QPointF(m,  m*2),
                             QPointF(-m, m*2),
                             QPointF(0,  m/2)])
        p.drawPolygon(triangle)


        self.overlay = self.map.toImage()

        self.redraw()

    # the pitchItems list contains a tuple that represents all of the tick marks
    # and text of the Pitch graducations.  The first item of the tuple is the angle
    # and the second is the item reference.  We use this to make the tick marks
    # disappear when they are a certain distance from the current pitch angle
    def setPitchItems(self):
        for each in self.pitchItems:
            if abs(each[0] - self._pitchAngle) < self.visiblePitchAngle:
                each[1].setOpacity(self.pitchOpacity)
            else:
                each[1].setOpacity(0)

    def redraw(self):
        self.resetTransform()
        self.centerOn(self.scene.width() / 2,
                      self.scene.height() / 2 +
                      self._pitchAngle * self.pixelsPerDeg * - 1.0)
        self.rotate(self._rollAngle * -1.0)

# We use the paintEvent to draw on the viewport the parts that aren't moving.
    def paintEvent(self, event):
        super(AI, self).paintEvent(event)
        w = self.width()
        h = self.height()
        r = self.bankAngleRadius
        m = self.bankMarkSize
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Put the static overlay image on the view
        p.drawImage(self.rect(), self.overlay)

        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(qRound(self.fontSize * 0.025))
        p.setPen(pen)
        p.setBrush(QColor(Qt.GlobalColor.white))
        marks = QPen(Qt.GlobalColor.white)

        p.translate(w / 2, h / 2)

        # Slip / Skid ball
        p.setPen(QColor(Qt.GlobalColor.black))
        p.setBrush(QColor(Qt.GlobalColor.white))
        p.drawEllipse(QPointF(self._latAccel * -m*12, -r + m*3), m*0.8, m*0.8)

        p.rotate(self._rollAngle * -1.0)
        # Add moving Bank Angle Markers
        marks.setWidth(qRound(self.fontSize * 0.05))
        p.setPen(marks)
        p.setBrush(QColor(Qt.GlobalColor.white))
        smallMarks = [10, 20, 45]
        largeMarks = [30, 60]
        shortLine = QLineF(0, -r, 0, -(r-m))
        longLine = QLineF(0, -(r+m), 0, -(r-m))
        for angle in smallMarks:
            p.rotate(angle)
            p.drawLine(shortLine)
            p.rotate(- 2 * angle)
            p.drawLine(shortLine)
            p.rotate(angle)
        for angle in largeMarks:
            p.rotate(angle)
            p.drawLine(longLine)
            p.rotate(- 2 * angle)
            p.drawLine(longLine)
            p.rotate(angle)
        triangle = QPolygonF([QPointF(m/2, -(r+m/2)),
                             QPointF(-m/2, -(r+m/2)),
                             QPointF(0, -(r - m/2))])
        p.drawPolygon(triangle)
        # Draw standard rate turn markers
        if self.drawBankMarkers:
            a = math.degrees(math.atan(self._tas/364.0))
            if a > self.bankAngleMaximum:
                a = self.bankAngleMaximum
            diamond = QPolygonF([QPointF(0, -r),
                                QPointF(-m*0.8, -(r+m*0.8)),
                                QPointF(-0, -r - m*1.6),
                                QPointF(m*0.8, -(r+m*0.8))])
            p.setBrush(Qt.GlobalColor.transparent)
            p.rotate(a)
            p.drawPolygon(diamond)
            p.rotate(-2 * a)
            p.drawPolygon(diamond)

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

    def showEvent(self, event):
        self.redraw()

    def setRollAngle(self, angle):
        if angle != self._rollAngle and not self.getAIFail():
            self._rollAngle = common.bounds(-180, 180, angle)
            if self.isVisible():
                self.redraw()

    def getRollAngle(self):
        return self._rollAngle

    rollAngle = property(getRollAngle, setRollAngle)

    def setLateralAcceleration(self, value):
        if value != self._latAccel:
            self._latAccel = common.bounds(-0.3, 0.3, value)
            if self.isVisible():
                self.update()

    def setTrueAirspeed(self, value):
        if value != self._tas:
            self._tas = value
            if self.isVisible():
                self.update()

    def getPitchAngle(self):
        return self._pitchAngle

    def setPitchAngle(self, angle):
        if angle != self._pitchAngle and not self.getAIFail():
            self._pitchAngle = common.bounds(-90, 90, angle)
            self.setPitchItems()
            if self.isVisible():
                self.redraw()

    pitchAngle = property(getPitchAngle, setPitchAngle)

    def getPitchAngle(self):
        return self._pitchAngle

    def getAIFail(self):
        return True in self._AIFail.values()

    def setAIFailRoll(self, fail):
        self.setFail(fail,'ROLL')

    def setAIFailPitch(self, fail):
        self.setFail(fail,'PITCH')

    def setAIFailLAcc(self, fail):
        self.setFail(fail,'ALAT')

    def setAIFailTAS(self, fail):
        self.setFail(fail,'TAS')

    def setFail(self, fail,item=None):
        if fail != self._AIFail[item]:
            self._AIFail[item] = fail
            if hasattr(self, 'fail_scene'):
                if self.getAIFail():
                    self.resetTransform()
                    self.setScene (self.fail_scene)
                else:
                    self.setScene (self.scene)
                    # Initially set to grey
                    # we may have old data while recovering
                    if hasattr(self, 'sky_rect'):
                        if self.getAIFail():
                            self.sky_rect.setBrush (self.gray_sky)
                            self.land_rect.setBrush (self.gray_land)
                        else:
                            self.sky_rect.setBrush (self.gblue_brush)
                            self.land_rect.setBrush (self.gbrown_brush)
                    self.redraw()

    def getAIOld(self):
        return True in self._AIOld.values()

    def setAIOldRoll(self, old):
        self.setOld(old,'ROLL')

    def setAIOldPitch(self, old):
        self.setOld(old,'PITCH')

    def setAIOldLAcc(self, old):
        self.setOld(old,'ALAT')

    def setAIOldTAS(self, old):
        self.setOld(old,'TAS')

    def setOld(self, old, item=None):
        log.debug("Set AI Old")
        if old != self._AIOld[item]:
            self._AIOld[item] = old
            if hasattr(self, 'sky_rect'):
                if self.getAIOld():
                    self.sky_rect.setBrush (self.gray_sky)
                    self.land_rect.setBrush (self.gray_land)
                    #self.old_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    self.land_rect.setBrush (self.gbrown_brush)
                    #self.old_text.hide()
                self.redraw()

    def getAIBad(self):
        return True in self._AIBad.values()

    def setAIBadRoll(self, bad):
        self.setBad(bad,'ROLL')

    def setAIBadPitch(self, bad):
        self.setBad(bad,'PITCH')

    def setAIBadLAcc(self, bad):
        self.setBad(bad,'ALAT')

    def setAIBadTAS(self, bad):
        self.setBad(bad,'TAS')

    def setBad(self, bad, item=None):
        log.debug("Set AI Bad")
        if bad != self._AIBad[item]:
            self._AIBad[item] = bad
            if hasattr(self, 'sky_rect'):
                if self.getAIBad():
                    self.sky_rect.setBrush (self.gray_sky)
                    self.land_rect.setBrush (self.gray_land)
                    #self.bad_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    self.land_rect.setBrush (self.gbrown_brush)
                    #self.bad_text.hide()
                self.redraw()




class FDTarget(QGraphicsView):
    def __init__(self, center, pixelsPerDeg, parent=None):
        super(FDTarget, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.aicenter = center
        self.pixelsPerDeg = pixelsPerDeg

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()
        polyheight = 8
        self.poly_points = [(-self.w/2,-polyheight/2)
                           ,( self.w/2,-polyheight/2)
                           ,( self.w/2, polyheight/2)
                           ,(-self.w/2, polyheight/2)]

        self.scene = QGraphicsScene(0, 0, self.w*2, self.w*2)
        pen = QPen(QColor(Qt.GlobalColor.black))
        brush = QBrush (QColor (Qt.GlobalColor.magenta))
        ps = [QPointF (x,y) for x,y in self.poly_points]
        fdpoly = QPolygonF (ps)
        self.poly = self.scene.addPolygon (fdpoly, pen, brush)
        self.poly.setX(self.w)
        self.poly.setY(self.w)

        self.setScene(self.scene)
        self.aicenter.setX (self.aicenter.x()-self.w/2)
        self.aicenter.setY (self.aicenter.y()-self.h/2)
        self.centerOn (self.w, self.w)

    def update(self, fdpitch, fdroll):
        self.move (self.aicenter.x(), (self.aicenter.y() - fdpitch * self.pixelsPerDeg))
        roll = fdroll * math.pi / 180
        sinroll = math.sin(roll)
        cosroll = math.cos(roll)
        ps = [QPointF (cosroll*x - sinroll*y, sinroll*x + cosroll*y) for x,y in self.poly_points]
        fdpoly = QPolygonF (ps)
        self.poly.setPolygon (fdpoly)
