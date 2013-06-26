#!/usr/bin/env python

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
import guages
import ai
    
def main():
    app = QApplication(sys.argv)
    w = QWidget()
    w.resize(800, 480)
    w.move(20,50)
    w.setWindowTitle('PFD')
    a = ai.AI(w)
    a.resize(300,300)
    a.move(100,30)
    roll = QSlider(Qt.Horizontal,w)
    roll.setMinimum(-180)
    roll.setMaximum(180)
    roll.setValue(0)
    roll.valueChanged.connect(a.setRollAngle)
    roll.resize(200,20)
    roll.move(100,0)
    
    
    pitch = QSlider(Qt.Vertical,w)
    pitch.setMinimum(-90)
    pitch.setMaximum(90)
    pitch.setValue(0)
    pitch.valueChanged.connect(a.setPitchAngle)
    pitch.resize(20,200)
    pitch.move(20,100)
    
    vb = guages.VerticalBar(w)
    vb.resize(10,150)
    vb.move(480,100)
    vb.highWarn = 75
    vb.highAlarm = 85
    vb.value = 0
    
    v = QSlider(Qt.Vertical,w)
    v.setMinimum(0)
    v.setMaximum(100)
    v.setValue(0)
    v.valueChanged.connect(vb.setValue)
    v.resize(20,150)
    v.move(500,100)
    
    w.show()
    sys.exit(app.exec_())

main()