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
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import PyQt4.Qt
import math

class AI(QGraphicsView):
    def __init__(self, parent=None):
        super(AI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rollAngle = 0
        self._pitchAngle = 0
    
    def resizeEvent(self, event):
        #Setup the scene that we use for the background of the AI
        sceneHeight = self.height()*4.5
        sceneWidth = math.sqrt(self.width() * self.width() + self.height() * self.height())
        self.pixelsPerDeg = self.height()/60.0 #This makes about 30 deg appear on instrument
        self.scene = QGraphicsScene(0,0,sceneWidth, sceneHeight)
        #Draw the Blue and Brown rectangles
        pen = QPen(QColor(Qt.blue))
        brush = QBrush(QColor(Qt.blue))
        self.scene.addRect(0, 0, sceneWidth, sceneHeight/2, pen, brush) 
        self.setScene(self.scene)
        pen = QPen(QColor(160, 82, 45)) #Brown Color
        brush = QBrush(QColor(160, 82, 45))
        self.scene.addRect(0, sceneHeight/2+1, sceneWidth,sceneHeight, pen, brush) 
        self.setScene(self.scene)
        #Draw the main horizontal line
        pen = QPen(QColor(Qt.white))
        pen.setWidth(2)
        self.scene.addLine(0,sceneHeight/2,sceneWidth,sceneHeight/2, pen)
        #draw the degree hash marks
        pen.setWidth(1)
        w = self.scene.width()
        h = self.scene.height()
        for i in range(1, 10):
            left =  w / 2 - self.width() / 8
            right = w / 2 + self.width() / 8
            
            y = h / 2 - (self.pixelsPerDeg * 10) * i
            self.scene.addLine(left, y, right, y, pen)
            y = h / 2 + (self.pixelsPerDeg * 10) * i
            self.scene.addLine(left, y, right, y, pen)
            
            y = h / 2 + (self.pixelsPerDeg * 10) * i
            #pygame.draw.line(self.backGround, efis.WHITE, (left, y), (right ,y))
            #textSurf = font.render(str(i*-10), True, efis.WHITE)
            #self.backGround.blit(textSurf, (left-textSurf.get_width()-5, y - textSurf.get_height()/2))
            #self.backGround.blit(textSurf, (right+5, y - textSurf.get_height()/2))
    
    def redraw(self):
        self.resetTransform()
        self.centerOn(self.scene.width()/2, self.scene.height()/2 + self._pitchAngle * self.pixelsPerDeg)
        self.rotate(self._rollAngle)
    
    # We use the paintEvent to draw on the viewport the parts that aren't moving.
    def paintEvent(self, event):
        super(AI, self).paintEvent(event)
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        
        p.setPen(QColor(Qt.black))
        p.setBrush(QColor(Qt.yellow))
        p.drawRect(w/4,h/2-2,w/6,4)
        p.drawRect(w-w/4-w/6,h/2-2,w/6,4)
        p.drawRect(w/2-2, h/2-2, 4, 4)

	# Add non-moving Bank Angle Markers
	marks = QPen()
	marks.setBrush(QColor(Qt.black))
	marks.setWidth(2)
	p.translate(w/2 , h/2)
        p.setPen(marks)
	smallMarks = [10, 20, 45]
	largeMarks = [30, 60, 90]
	for angle in smallMarks:
		p.rotate(angle)
        	p.drawLine(0, -(h/2), 0 , -(h/2-10))
		p.rotate(-2*angle)
		p.drawLine(0, -(h/2), 0 , -(h/2-10))
		p.rotate(angle)
	for angle in largeMarks:
		p.rotate(angle)
		p.drawLine(0, -(h/2+10), 0 , -(h/2-10))
                p.rotate(-2*angle)
		p.drawLine(0, -(h/2+10), 0 , -(h/2-10))
		p.rotate(angle)

	triangle = QPolygon([QPoint(0+5, -(h/2)), QPoint(0-5, -(h/2)), 
QPoint( 0,
-(h/2-10))])
	p.drawPolygon(triangle)        
    
    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass 
        
    def setRollAngle(self, angle):
        if angle < -180:
            newAngle = -180
        elif angle > 180:
            newAngle = 180
        else:
            newAngle = angle
        if newAngle != self._rollAngle:
            self._rollAngle = newAngle
            self.redraw()
    
    def getRollAngle(self):
        return self._rollAngle
    
    rollAngle = property(getRollAngle, setRollAngle)
    
    def setPitchAngle(self, angle):
        if angle < -90:
            newAngle = -90
        elif angle > 90:
            newAngle = 90
        else:
            newAngle = angle
        if newAngle != self._pitchAngle:
            self._pitchAngle = newAngle
            self.redraw()
    
    def getPitchAngle(self):
        return self._pitchAngle
    
    pitchAngle = property(getPitchAngle, setPitchAngle)        
