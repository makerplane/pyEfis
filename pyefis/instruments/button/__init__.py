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

# This implements a dynamice interactive button.
# It can change states based on data in FIX, it can display data and act as a button for user iput.
# 
import time
import threading
import pycond as pc

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import logging
import pyavtools.fix as fix
logger=logging.getLogger(__name__)

import yaml
import os
import pathlib
import re
from pyefis import hmi
import time

class Button(QWidget):
    def __init__(self, parent=None, config_file=None):
        super(Button, self).__init__(parent)

        self.parent = parent
        config = yaml.load(open(config_file), Loader=yaml.SafeLoader)
        self._conditions = config.get('conditions', [])
        self.config = config
        self._button = QPushButton(self) #self.config['text'], self)
        self._style = dict()
        self._style['bg'] = QColor(self.config.get('bg_color',"lightgray"))
        self._style['fg'] = QColor(self.config.get('fg_color',"black"))
        self._style['transparent'] = self.config.get('transparent',False)

        self._title = ""
        self._toggle = False

        self._dbkey = fix.db.get_item(self.config['dbkey'])
        time.sleep(0.01)
        #self._button.setChecked(self._dbkey.value)

        #self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)


        if self.config['type'] == 'toggle':
            self._toggle = True
            self._button.setCheckable(True)
            self._button.toggled.connect(self.buttonToggled)
        elif self.config['type'] == 'simple':
            self._button.setCheckable(False)
            self._button.clicked.connect(self.buttonToggled)
        elif self.config['type'] == 'repeat':
            self._button.pressed.connect(self.buttonToggled)
            self._button.setAutoRepeat(True)
            self._button.setAutoRepeatInterval(self.config.get('repeat_interval', 300))
            self._button.setAutoRepeatDelay(self.config.get('repeat_delay', 300))

        self._button.setEnabled(True)
        #self._dbkey = fix.db.get_item(self.config['dbkey'])
        #self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)

        self._db = dict() #All the fix db items
        self._db_data = dict() #All the fix db data for use in pycond
        self.condition_keys = self.config.get('condition_keys', [])
        self.initDB()
        self.setStyle('set text', self.config['text'])
        # On startup set button back to proper state
        self._button.setChecked(self._dbkey.value)
        self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)
        self.processConditions()


    def initDB(self):
        
        # init self._db and connect to signals
        for key in self.condition_keys:
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
        self._db_data[self._dbkey.key] = self._dbkey.value
        time.sleep(0.01)

    def dataChanged(self,key=None,signal=None):
        if signal == 'value':
            self._db_data[key] = self._db[key].value
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
        self.processConditions()

    def resizeEvent(self,event):
        self._button.resize(self.width(), self.height())
        self.setStyle()

    def setTitle(self, title):
        if self._title != title:
            self._title = title
            for t,d in self._db_data.items():
                self._title = re.sub(f"{{{t}}}", str(d), self._title)
            self._button.setText(self._title)

    def getTitle(self):
        return self._title

    title = property(getTitle,setTitle)

    def buttonToggled(self):
        # Button can be toggled by _dbkey or by clicking the button
        # Make sure they stay in sync
        logger.debug(f"{self._button.text()}:buttonToggled:self._button.isChecked({self._button.isChecked()})")
        #if not self.isVisible(): return

        # Toggle button toggled
        if self._toggle and self._button.isChecked() != self._dbkey.value:
            fix.db.set_value(self._dbkey.key, self._button.isChecked())
            # Now we evaluate conditions and update the button style/text/state
            self.processConditions(True)
            #fix.db.set_value(self._dbkey.key, self._button.isChecked())

        elif not self._toggle:
            # Simple button
            self.processConditions(True)


    def dbkeyChanged(self,data):
        if self._dbkey.bad:
            return
        # The same button configuration might be used on multiple screens
        # Only buttons on the active screen should be changing.
        logger.debug(f"{self._button.text()}:dbkeyChanged:data={data}:self._button.isChecked({self._button.isChecked()})")
        self._db_data[self._dbkey.key] = self._dbkey.value
        #if not self.isVisible(): return
        #self._db_data[self._dbkey.key] = self._dbkey.value
        if self._toggle and self._button.isChecked() == self._dbkey.value:
            #This is a recursive call do nothing
            logger.debug(f"{self._button.text()}:recursive:data={data}:self._button.isChecked({self._button.isChecked()})")
            return
        else:
            logger.debug(f"{self._button.text()}:toggled:data={data}:self._button.isChecked({self._button.isChecked()})")
            self._button.setChecked(self._dbkey.value)
            self.processConditions(True)

    def showEvent(self,event):
        self.processConditions()
        self._button.setChecked(self._dbkey.value)

    def processConditions(self,clicked=False):
        self._db_data['SCREEN'] = self.parent.parent.getRunningScreen()
        self._db_data['CLICKED'] = clicked
        for cond in self._conditions:
            if 'when' in cond:
                if type(cond['when']) == str:
                    expr = pc.to_struct(pc.tokenize(cond['when'], sep=' ', brkts='[]'))
                    if pc.pycond(expr)(state=self._db_data) == True:
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{cond['when']}")
                        self.processActions(cond['actions'])
                        if not cond.get('continue', False): return
                elif type(cond['when']) == bool:
                    if cond['when']:
                        if self._button.isChecked() or self._toggle == False:
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return
                    else:
                        if not self._button.isChecked():
                            self.processActions(cond['actions'])
                            if not cond.get('continue', False): return


    def processActions(self,actions):
        for act in actions:
            for action,args in act.items():
                try:
                    logger.debug(f"{self.parent.parent.getRunningScreen()}:HMI:{action}:{args}")
                    hmi.actions.trigger(action, args)
                except:
                    self.setStyle(action,args)
                    logger.debug(f"{self.parent.parent.getRunningScreen()}:STYLE:{action}:{args}")

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

        self.font = QFont()
        self.font.setPixelSize(qRound(self.height() * 38/100))
        self._style['border_size'] = qRound(self._button.height() * 6/100)
        print(f"transparent:{self._style['transparent']}")
        if self._style['transparent']:
            self._button.setStyleSheet(f"QPushButton {{border: 1px solid {self._style['bg'].name()}; background: transparent;border-radius: 6px}}")# border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()}}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}}")
        else:
            self._button.setStyleSheet(f"QPushButton {{border: 2px solid {self._style['bg'].darker(130).name()};border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].lighter(110).name()}, stop: 1 {self._style['bg'].name()});border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()}}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}}")

        self._button.setFont(self.font)

