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
from pyefis.instruments import helpers

class Button(QWidget):
    def __init__(self, parent=None, config_file=None, font_family="DejaVu Sans Condensed"):
        super(Button, self).__init__(parent)

        self.parent = parent
        self.font_family = font_family
        self.font_mask = None
        self.font_size = None
        config = yaml.load(open(config_file), Loader=yaml.SafeLoader)
        self._conditions = config.get('conditions', [])
        self.config = config
        self._button = QPushButton(self) #self.config['text'], self)
        self._style = dict()
        self._style['bg'] = QColor(self.config.get('bg_color',"lightgray"))
        self._style['fg'] = QColor(self.config.get('fg_color',"black"))
        self._style['transparent'] = self.config.get('transparent',False)
        self._buttonhide = self.config.get("hover_show", False)
        self._title = ""
        self._toggle = False
        # Repalce {id} in the dbkey so we can have different 
        # button names per node without having 
        # to duplicate all buttons.
        self._dbkey = fix.db.get_item(self.config['dbkey'].replace('{id}', str(self.parent.parent.nodeID)))
        self.block_data = False
        time.sleep(0.01)
        #self._button.setChecked(self._dbkey.value)

        #self._dbkey.valueChanged[bool].connect(self.dbkeyChanged)

        self._repeat = False
        self.simple_state = False
        if self.config['type'] == 'toggle':
            self._toggle = True
            self._button.setCheckable(True)
            # toggled reacts to setChecked where clicked does not
            # Helps to prevent erronious recursion
            # However not using toggled for toggle buttons breaks
            # things such as encoder navigation
            self._button.toggled.connect(self.buttonToggled)

        elif self.config['type'] == 'simple':
            self._button.setCheckable(False)
            self._button.clicked.connect(self.buttonToggled)
        elif self.config['type'] == 'repeat':
            self._repeat = True
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

    def enterEvent(self, QEvent):
        if self._buttonhide:
            # Show menu if hover over it
            fix.db.set_value('HIDEBUTTON', False)

    def isEnabled(self):
        return self._button.isEnabled()

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
        logger.debug(f"dataChanged key={key} signal={signal}")
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
        self.font_size = None
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
        if not self.isVisible(): return

        # Toggle button toggled
        if self._toggle and self._button.isChecked() != self._dbkey.value:
            self.block_data = True
            fix.db.set_value(self._dbkey.key, self._button.isChecked())
            #self._dbkey.set_value = self._button.isChecked()
            self._dbkey.output_value()
            self.block_data = False
            # Now we evaluate conditions and update the button style/text/state
            self.processConditions(True)
            #fix.db.set_value(self._dbkey.key, self._button.isChecked())

        elif not self._toggle:
            # Simple button
            self.processConditions(True)


    def dbkeyChanged(self,data):
        if self.block_data: 
            logger.debug(f"{self._button.text()}:dbkeyChanged:data={data}:self._button.isChecked({self._button.isChecked()}) - processing blocked!")
            return
        if self._dbkey.bad:
            return
        # The same button configuration might be used on multiple screens
        # Only buttons on the active screen should be changing.
        logger.debug(f"{self._button.text()}:dbkeyChanged:data={data}:self._button.isChecked({self._button.isChecked()})")
        self._db_data[self._dbkey.key] = self._dbkey.value
        #self._dbkey.output_value()

        if not self.isVisible(): return
        #self._db_data[self._dbkey.key] = self._dbkey.value
        if self._toggle and self._button.isChecked() == self._dbkey.value:
            #This is a recursive call do nothing
            logger.debug(f"{self._button.text()}:recursive:data={data}:self._button.isChecked({self._button.isChecked()})")
            return
        else:
            logger.debug(f"{self._button.text()}:toggled:data={data}:self._button.isChecked({self._button.isChecked()})")
            if not self._repeat and not self._toggle:
                # A simple button
                # The logic in here is for dealing with physical buttons
                # Only take action if changing from False to True
                if not self._dbkey.value: 
                    logger.debug(f"Data is: {data}")
                    # Always save current state when it is false
                    self.simple_state = False
                    return
                # Only take action if we are visible
                if not self.isVisible(): return

                logger.debug(f"data:{data} self._dbkey.value:{self._dbkey.value}")
                # If we are already True, nothing new to do, we need to become false before performing another action.
                if self.simple_state: return
                # Save current state
                self.simple_state = self._dbkey.value
                # Set value back to false to prevent recursive calls
                # Physical buttons should not repeat sending True for simple buttons
                self._dbkey.value = False
            self._button.setChecked(self._dbkey.value) 
            self.processConditions(True)
            if self._repeat:
                # Send press even while true, send release event when false
                # Physical button would need to only set True while button is pressed, then set to False when released
                if self._dbkey.value:
                    event = QMouseEvent(QEvent.MouseButtonPress, QPoint(0,0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier);
                else:
                    event = QMouseEvent(QEvent.MouseButtonRelease, QPoint(0,0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier);
                QApplication.sendEvent(self._button, event);

    def showEvent(self,event):
        self.processConditions()
        # Do we need to only do this for toggle buttons?
        if self._toggle: 
            self._button.setChecked(self._dbkey.value)

    def processConditions(self,clicked=False):
        self._db_data['SCREEN'] = self.parent.screenName
        self._db_data['CLICKED'] = clicked
        self._db_data['DBKEY'] = self._dbkey.value 
        self._db_data["PREVIOUS_CONDITION"] = False
        logger.debug(f"{self._dbkey.key}:{self._dbkey.value}")
        for cond in self._conditions:
            if 'when' in cond:
                if type(cond['when']) == str:
                    expr = pc.to_struct(pc.tokenize(cond['when'], sep=' ', brkts='[]'))
                    if pc.pycond(expr)(state=self._db_data) == True:
                        self._db_data["PREVIOUS_CONDITION"] = True
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} = True")
                        self.processActions(cond['actions'])
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} conditions processed")
                        if not cond.get('continue', False): 
                            logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} Does not continue")
                            return
                        else:
                            logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} continues")
                    else:
                        self._db_data["PREVIOUS_CONDITION"] = False
                        logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:{cond['when']} = False")
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
                set_block = False
                if action == 'set value':
                    args_data = args.split(',')
                    if args_data[0] in self._db or args_data[0] == self._dbkey.key:
                        self.block_data = True
                        set_block = True
                try:
                    logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:HMI:{action}:{args} Tried")
                    hmi.actions.trigger(action, args)
                    logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:HMI:{action}:{args} Success")
                except:
                    self.setStyle(action,args)
                    logger.debug(f"{self.parent.parent.getRunningScreen()}:{self._dbkey.key}:STYLE:{action}:{args}")
                if set_block:
                    self.block_data = False

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
            elif args.lower() == 'checked' and not self._button.isChecked():
                #fix.db.set_value(self._dbkey.key, True)
                self._button.blockSignals(True)
                self._button.setChecked(True)
                self._dbkey.value = True
                self._dbkey.output_value()
                self._button.blockSignals(False)

            elif args.lower() == 'unchecked' and self._button.isChecked():
                #fix.db.set_value(self._dbkey.key, False)
                self._button.blockSignals(True)
                self._button.setChecked(False)
                self._dbkey.value = False
                self._dbkey.output_value()
                self._button.blockSignals(False)

        self._style['border_size'] = qRound(self._button.height() * 6/100)
        self.font = QFont(self.font_family)
        if self.font_mask:
            if not self.font_size:
                self.font_size = helpers.fit_to_mask(self.width()-(self._style['border_size']*2.5),self.height()-(self._style['border_size']*2.5),self.font_mask,self.font_family)
            self.font.setPointSizeF(self.font_size)
        else:
            self.font.setPixelSize(qRound(self.height() * 38/100))
        bg_color = self._style.get('bg_override', None) or self._style['bg']
        if self._style['transparent']:
            self._button.setStyleSheet(f"QPushButton {{border: 1px solid {bg_color.name()}; background: transparent;border-radius: 6px}}")# border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()}}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {self._style['bg'].name()}, stop: 1 {self._style['bg'].lighter(110).name()});border-style:inset}}")
        else:
            self._button.setStyleSheet(f"QPushButton {{border: 2px solid {bg_color.darker(130).name()};border-radius: 6px; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.lighter(110).name()}, stop: 1 {bg_color.name()});border-style: outset; border-width: {self._style['border_size']}px;color:{self._style['fg'].name()}}} QPushButton:pressed {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.name()}, stop: 1 {bg_color.lighter(110).name()});border-style:inset}} QPushButton:checked {{background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 {bg_color.name()}, stop: 1 {bg_color.lighter(110).name()});border-style:inset}}")

        self._button.setFont(self.font)

    # This instrument is selectable
    def enc_selectable(self):
        return True

    # Highlight this instrument to show it is the current selection
    def enc_highlight(self,onoff):
        if onoff:
            self._style['bg_override'] = QColor('orange')
            fix.db.set_value('HIDEBUTTON', False) 
        else:
            self._style['bg_override'] = None 
        self.setStyle()
        # Change the bg color to the value passed in color
        # Will save old color so it can be returned to normal

    # Trigger a press of this button
    def enc_select(self):
        if self._toggle:
            self._button.setChecked(not self._button.isChecked())
        else:
            self.processConditions(clicked=True)
        # Will trigger as if the button was selected
        # Will return control back to the caller
        return False 
