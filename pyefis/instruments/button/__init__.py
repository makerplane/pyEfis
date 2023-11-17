#  Copyright (c) 2023 Eric Blevins
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

import time
import threading
import pycond as pc

from PyQt5.QtGui import *
from PyQt5.QtCore import *
#from PyQt5 import QtCore
from PyQt5.QtWidgets import *

import logging
import pyavtools.fix as fix
logger=logging.getLogger(__name__)

import yaml
import os
import pathlib
import re
from pyefis import hmi

# TODO
# Import the actions/functions from hmi and use those for the actions
# This will keep syntax consistent across modules.
# We can also implement button specific actions like "Set background color" or "Set button text"
class Button(QWidget):
    def __init__(self, parent=None, config_file=None):
        super(Button, self).__init__(parent)

        config = yaml.load(open(config_file), Loader=yaml.SafeLoader)
        self._conditions = config.get('conditions', [])
        self.config = config
        self._button = QPushButton(self) #self.config['text'], self)
        self._style = dict()
        self._style['bg'] = QColor(self.config.get('bg_color',"lightgray"))
        self._style['fg'] = QColor(self.config.get('fg_color',"black"))
        #self._button.resize(self.width(), self.height())
#self.resizeEvent(None)
        #self._style['border_size'] = qRound(self._button.width() * 4/100)
        #self.font = QFont()
        #self.font.setPixelSize(qRound(self.height() * 40/100))
        self._title = ""
        #self.setStyle('set text', self.config['text'])
        #self._button.setFont(self.font)

        #print(self._button.styleSheet())
        #self._button.show()
        #print(self.config)
        #self.cornerRadius = 25 #TODO
        #self.fg_color = "000000" #TODO
        #self.bg_color = "FFFFFF" #TODO
        #self.font_size = 15 #TODO
        #self._title = "button" #TODO
        #self._button.resize(50, 50)
        self._toggle = False
        if self.config['type'] == 'toggle':
            self._toggle = True
            self._button.setCheckable(True)
            self._button.toggled.connect(self.buttonToggled)
        elif self.config['type'] == 'simple':
            self._button.setCheckable(False)
            self._button.clicked.connect(self.buttonToggled)

        #self.setTitle(self._title)
        #self._button.show()
        self._button.setEnabled(True)
        self._dbkey = fix.db.get_item(self.config['dbkey'])
        self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)

        self._db = dict() #All the fix db items
        self._db_data = dict() #All the fix db data for use in pycond
        self.condition_keys = self.config.get('condition_keys', [])
        #self.condition_keys.append(self.config['dbkey']) # Todo, do we need this? Maybe we do not need the connections above?
        self.initDB()
        self.setStyle('set text', self.config['text'])
        # On startup set button back to proper state
        self._button.setChecked(self._dbkey.value)
        self.processConditions()

        #self.buttonToggled()

    #def getRatio(self):
    #    return 2.5
    def initDB(self):
        
        # init self._db and connect to signals
        for key in self.condition_keys:
            #print(key)
            self._db[key] = fix.db.get_item(key)
            # Setup connections first
            self._db[key].valueChanged[bool].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[int].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[str].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))
            self._db[key].valueChanged[float].connect(lambda valueChanged, key=key, signal='value': self.dataChanged(key=key,signal=signal))

            self._db[key].oldChanged.connect(lambda oldChanged, key=key, signal='old': self.dataChanged(key=key,signal=signal))
            self._db[key].badChanged.connect(lambda badChanged, key=key, signal='bad': self.dataChanged(key=key,signal=signal))
            self._db[key].failChanged.connect(lambda failChanged, key=key, signal='fail': self.dataChanged(key=key,signal=signal))
            self._db[key].annunciateChanged.connect(lambda annunciateChanged, key=key, signal='annunciate': self.dataChanged(key=key,signal=signal))
            self._db[key].auxChanged.connect(lambda auxChanged, key=key, signal='aux': self.dataChanged(key=key,signal=signal))

            self._db_data[key] = self._db[key].value
            self._db_data[f"{key}.old"] = self._db[key].old
            self._db_data[f"{key}.bad"] = self._db[key].bad
            self._db_data[f"{key}.fail"] = self._db[key].fail
            self._db_data[f"{key}.annunciate"] = self._db[key].annunciate
            for aux in self._db[key].aux:
                self._db_data[f"{key}.aux.{aux}"] = self._db[key].aux[aux]
            #print(self._db_data)
        self._db_data[self._dbkey.key] = self._dbkey.value

    def dataChanged(self,key=None,signal=None):
        #print(f"{key}: signed: {signal}")
        if signal == 'value':
            self._db_data[key] = self._db[key].value
            #print(self._db_data[key])
        elif signal == 'old':
            self._db_data[f"{key}.old"] = self._db[key].old
        elif signal == 'bad':
            self._db_data[f"{key}.bad"] = self._db[key].bad
        elif signal == 'fail':
            self._db_data[f"{key}.fail"] = self._db[key].fail
        elif signal == 'annunciate':
            self._db_data[f"{key}.annunciate"] = self._db[key].annunciate
        elif signal == 'aux':
            for aux in self._db[key].aux:
                self._db_data[f"{key}.aux.{aux}"] = self._db[key].aux[aux]
        # TODO need to also include button state in _db_data
        #print(self._db_data)
        self.processConditions()

    def returnData(self):
        # returns dict used in pycond
        # BTN1: value
        # BTN1.aux.key: value
        # BTN1.old
        # BTN1.fail
        # BTN1.bad
        # BTN1.annunciate
        pass
    def resizeEvent(self,event):
        # TODO Need to allow setting size
        self._button.resize(self.width(), self.height())
        self.setStyle()

    def setTitle(self, title):
        if self._title != title:
            self._title = title
            for t,d in self._db_data.items():
                #print(f"sub {{{t}}} with {d}")
                self._title = re.sub(f"{{{t}}}", str(d), self._title)
            self._button.setText(self._title)

    def getTitle(self):
        return self._title

    title = property(getTitle,setTitle)

    def buttonClicked(self):
        pass
    def buttonToggled(self):
        #self._button.blockSignals(True)
        # Button can be toggled by _dbkey or by clicking the button
        # Make sure they stay in sync
        if self._toggle and self._button.isChecked() != self._dbkey.value:
            fix.db.set_value(self._dbkey.key, self._button.isChecked())
            #self._db_data[self._dbkey.key] = self._button.isChecked()  
            #print(f"toggled {self._button.isChecked()}")
            #print("###########################################################################################################################################################################################################################################")
        # Now we evaluate conditions and update the button style/text/state
        #self._db_data[self._dbkey.key] = self._button.isChecked()

        #print(self._title)
        self.processConditions(True)
        #self._db_data['CLICKED'] = False

        #if not self._toggle:
        #    self._button.setChecked(False)
        #self._button.blockSignals(False)

    def dbkeyChanged(self,data):
        # The same button configuration might be used on multiple screens
        # Only buttons on the active screen should be changing.
        self._db_data[self._dbkey.key] = self._dbkey.value
        if not self.isVisible(): return
        #return
        #if data != self._db_data[self._dbkey.key]:
        #    # The value of the button changed so it was clicked
        #    # But it could be from an internal action
        #    pass
         
        if self._toggle and self._button.isChecked() == data:
            #This is a recursive call do nothing
            #print(f"{self._dbkey.key} Duplicate")
            return
        else:
            #print(f"{self._dbkey.key} changed")
            self._button.setChecked(data)
        #print(self.config)
        #self.processConditions()

    def setInitialState(self):
        pass
        # Here we set the initial state by evaluating the current state of the data
        # Should we only execute style actions?

    def processConditions(self,clicked=False):
        #print(f"Clicked: {clicked}")
        self._db_data['CLICKED'] = clicked
        for cond in self._conditions:
            if 'when' in cond:
                #print(f"when: {cond['when']}")
                #print(self._db_data)
                if type(cond['when']) == str:
                    #print("Condition is true if expression is true")
                    expr = pc.to_struct(pc.tokenize(cond['when'], sep=' ', brkts='[]'))
                    if pc.pycond(expr)(state=self._db_data) == True:
                        self.processActions(cond['actions'])
                        if not cond.get('continue', False): return
                elif type(cond['when']) == bool:
                    if cond['when']:
                        #print("Condition true when button is on or clicked")
                        if self._button.isChecked() or self._toggle == False:
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return
                    else:
                        #print("Condition true when button is off")
                        if not self._button.isChecked():
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return


    def processActions(self,actions):
        for act in actions:
            for action,args in act.items():
                #print(f"action: {action} args: {args}")
                # TODO Process style actions
                try:
                    hmi.actions.trigger(action, args)            
                except:
                    self.setStyle(action,args)
#TODO def showEvent() to bring button state current when switching screens

    def setStyle(self,action='',args=None):

        if action.lower() == 'set bg color':
            self._style['bg'] = QColor(args)
        elif action.lower() == 'set fg color':
            self._style['fg'] = QColor(args)
        elif action.lower() == 'set text':
            self.setTitle(args)
        elif action.lower() == 'button':
            if args.lower() == 'disable':
              self._button.setEnabled(False)
            elif args.lower() == 'enable':
              self._button.setEnabled(True)
            elif args.lower() == 'checked':
                self._button.setChecked(True)
            elif args.lower() == 'unchecked':
                self._button.setChecked(False)

        #dark.setNamedColor(self._style['bg'])

        #pass
        # Actions:
        #  set bg color: FFFFFF
        #  set fg color: FFFFFF
        #  set text: Text string, how do we do multiple lines? and how do we do data? maybe {DBKEY}
        #  set button: enabled/disabled
        #print(self._style['font_size'])
        #font = QFont()
        #font.setPixelSize(qRound(self.height() * 40/100))
        #self._button.setFont(font)
        #self._button.setStyleSheet(f"QPushButton {{border: 2px solid {self._style['bg'].darker(130).name()};border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].lighter(110).name()}, stop: 1 {self._style['bg'].name()});border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()};font-size:{self._style['font_size']}px}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}}")
        self.font = QFont()
        self.font.setPixelSize(qRound(self.height() * 38/100))
        self._style['border_size'] = qRound(self._button.height() * 6/100)
        self._button.setStyleSheet(f"QPushButton {{border: 2px solid {self._style['bg'].darker(130).name()};border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].lighter(110).name()}, stop: 1 {self._style['bg'].name()});border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()}}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}}")

        self._button.setFont(self.font)

        #self._button.setStyleSheet(f"QPushButton {{border: 2px solid {bg_light.name()};border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_light.name()}, stop: 1 {bg_dark.name()}); min-width: 80px;border-style: outset; border-width: 10px}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_dark.name()}, stop: 1 {self._style['bg'].name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_dark.name()}, stop: 1 {self._style['bg'].name()});border-style:inset}}")
        #print(f"QPushButton {{border: 2px solid #8f8f91;border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {bg_dark.name()}); min-width: 80px;border-style: outset; border-width: 10px}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_dark.name()}, stop: 1 {self._style['bg'].name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_dark.name()}, stop: 1 {self._style['bg'].name()});border-style:inset}}")
