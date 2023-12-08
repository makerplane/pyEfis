#  Copyright (c) 2019 Phil Birkelbach
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


import pyefis.hmi as hmi
from .abstract import AbstractGauge
from .verticalBar import VerticalBar

class EGTGroup(QWidget):
    def __init__(self, parent=None, cylinders = 4, dbkeys = ["EGT11", "EGT12", "EGT13", "EGT14"], min_size=True):
        super(EGTGroup, self).__init__(parent)
        if min_size:
            self.setMinimumSize(50, 100)
        self.bars = []
        #self.conversionFunction = lambda x: x * (9.0/5.0) + 32.0
        self.normalizeMode = False
        self.peakMode = False
        for i in range(cylinders):
            bar = VerticalBar(self)
            bar.name = str(i+1)
            bar.decimalPlaces = 0
            bar.showUnits = False
            bar.peakMode = False
            bar.conversionFunction1 = lambda x: x * (9.0/5.0) + 32.0
            bar.conversionFunction2 = lambda x: x
            bar.unitsOverride1 = u'\N{DEGREE SIGN}F'
            bar.unitsOverride2 = u'\N{DEGREE SIGN}C'
            bar.setUnitSwitching()
            bar.unitGroup = "Temperature"
            bar.dbkey = dbkeys[i]
            bar.normalizeRange = 400
            self.bars.append(bar)
        self.smallFontPercent = 0.08
        self.bigFontPercent = 0.10
        hmi.actions.setEgtMode.connect(self.setMode)

    def setMode(self, args):
        if args.lower() == "normalize":
            if self.normalizeMode:
                self.normalizeMode = False
            else:
                self.normalizeMode = True
            for bar in self.bars:
                bar.normalizeMode = self.normalizeMode
        elif args.lower() == "peak":
            if self.peakMode:
                self.peakMode = False
            else:
                self.peakMode = True
            for bar in self.bars:
                bar.peakMode = self.peakMode
        elif args.lower() == "reset peak":
            for bar in self.bars:
                bar.resetPeak()
        elif args.lower() == "lean":
            self.normalizeMode = True
            self.peakMode = True
            for bar in self.bars:
                bar.resetPeak()
                bar.normalizeMode = self.normalizeMode
                bar.peakMode = self.peakMode
        elif args.lower() == "normal":
            self.normalizeMode = False
            self.peakMode = False
            for bar in self.bars:
                bar.normalizeMode = self.normalizeMode
                bar.peakMode = self.peakMode



    def resizeEvent(self, event):
        cylcount = len(self.bars)
        barwidth = self.width() / cylcount
        barheight = self.height()
        x = 0
        for bar in self.bars:
            bar.resize(qRound(barwidth), qRound(barheight))
            bar.move(qRound(barwidth * x), 0)
            x += 1
