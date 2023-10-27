#  Copyright (c) 2018 Garrett Herschleb
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
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QKeySequence

from collections import defaultdict


import logging

import pyavtools.fix as fix

from pyefis import hmi

logger=logging.getLogger(__name__)

TheMenuObject=None

class Menu(QWidget):
    def __init__(self, parent, config):
        global TheMenuObject
        super(Menu, self).__init__(parent)
        self.config = config
        self.myparent = parent
        self.colors = dict()
        self.buttons = dict()      
        self.button_conditions = defaultdict(list)
        self.button_current_action = dict()
        self.button_hide_on = defaultdict(list)
        self.button_screen_titles = dict()
        self.button_style = dict()
        self.menu_hidden = self.config['defaults']['hide_menu']
        self.menu_buttons = list()
        #self.buttons_disabled = dict()
        self.db_items = defaultdict(list)
        self.db = dict()

        # Get the default values for the buttons:
        x = self.config['defaults']['left_margin']
        button_spacing = self.config['defaults']['button_spacing']
        button_width = self.config['defaults']['width']
        button_height = self.config['defaults']['height']
        left_margin=self.config['defaults']['left_margin']
        top_margin=self.config['defaults']['top_margin']
        fg_color=self.config['defaults']['fg_color']
        bg_color=self.config['defaults']['bg_color']
        font_size=self.config['defaults']['font_size']
        corner_radius=self.config['defaults']['corner_radius']
        button_order = dict()
        shortcuts = dict()
        for c in self.config['colors']:
            self.colors[c] = self.config['colors'][c]
        # Create each button
        for b_name,b in self.config['buttons'].items():
            # TODO Perhaps we can validate that the button is defined properly and throw exception if not?
            logger.debug(f"Button name: {b_name}")
            self.buttons[b_name] = QPushButton(b_name, self)
            self.buttons[b_name].clicked.connect(lambda checked, name=b_name: self.button_clicked(name))
            if 'shortcut' in b:
              if b['shortcut'] in shortcuts:
                  raise Exception(f"Button '{b_name}' and '{shortcuts[b['shortcut']]}' share the same shortcut '{b['shortcut']}', please correct!")
              self.buttons[b_name].addAction(QAction(b['shortcut'], self, shortcut=QKeySequence(b['shortcut']), triggered=(lambda checked, name=b_name: self.button_clicked(name))))
              shortcuts[b['shortcut']] = b_name
            if 'titles' in b:
                self.button_screen_titles[b_name] = b['titles']
                self.button_screen_titles[b_name]['default'] = b['title']
            else:
                self.button_screen_titles[b_name] = dict()
                self.button_screen_titles[b_name]['default'] = b['title']
            if 'menubutton' in b:
                self.menu_buttons.append(b_name)
            if 'order' in b:
                if b['order'] in button_order:
                   raise Exception(f"Button '{b_name}' and '{button_order[b['order']]}' share the same order '{b['order']}', please correct!")
                if b['order'] <= 0:
                   raise Exception(f"Button '{b_name}' order value must be a positive integer greater than 0")
                if b['order'] > 20:
                   raise Exception(f"Button '{b_name}' order value must be less than 21")
                button_order[b['order']] = b_name
                if b['order'] >= 2:
                    self.menu_buttons.append(b_name) 
            if 'hide_on' in b:
                # Build dict of what screens a button hides on
                # _ALL_ will be recognized to hide it on all screens
                if type(b['hide_on']) is list:
                    for scr in b['hide_on']:
                      self.button_hide_on[b_name].append(scr)
                else:
                    self.button_hide_on[b_name].append(b['hide_on'])
            else: 
                self.button_hide_on[b_name] = []
            if ('x' in b and 'y' in b ) and not 'order' in b:
                self.buttons[b_name].move(b['x'], b['y'])
                self.buttons[b_name].resize(b.get('width', button_width), b.get('height', button_height))
            else:
                if not 'order' in b:
                    # explicitly provide x/y location or an order
                    raise Exception(f"Button {b_name} needs an explicit location x/y defined or an order")
                # if order specified, width is from default
                self.buttons[b_name].move(x + ((b['order'] -1 ) * button_spacing) + (b['order'] -1 ) * button_width, top_margin)
                self.buttons[b_name].resize(button_width, button_height)
            
            self.button_style[b_name] = dict()
            self.button_style[b_name]['fg_color'] = b.get('fg_color',fg_color)
            self.button_style[b_name]['bg_color'] = b.get('bg_color',bg_color)
            self.button_style[b_name]['font_size'] = b.get('font_size', font_size)
            self.button_style[b_name]['corner_radius'] = b.get('corner_radius', corner_radius)
 
            self.button_style[b_name]['message'] = ""
            self.update_button_style(b_name)

            if 'db_items' in b:
                # Keep track of what buttons use what data items
                if type(b['db_items']) is list:
                    for item in b['db_items']:
                      self.db_items[item].append(b_name)
                else:
                    self.db_items[b['db_items']].append(b_name)
            if 'conditions' in b:
                #This button has logical conditions
                for cond in b['conditions']:
                    self.button_conditions[b_name].append(cond)
            if 'action' in b:
                # This button has a default action, maybe does not involve any conditions
                self.button_current_action[b_name] = b['action']

        self.adjustSize()
        self.init_db() # Collect current data
        self.init_buttons() #Process each button's conditions to bring them current
        #The initial state of buttons is wrong because we do not know what screen we are on yet as it is not created.

        self.change_button_visibility()

    def update_button_style(self,b_name):
            # TODO Set title based on screen name when defined
            cur_screen = self.myparent.getRunningScreen()
            title = self.button_screen_titles[b_name]['default']
            if cur_screen in self.button_screen_titles[b_name]:
                title = self.button_screen_titles[b_name][cur_screen]

            self.buttons[b_name].setStyleSheet(f"Text-align:top;font:bold;color:#{self.colors[self.button_style[b_name]['fg_color']]};background-color:#{self.colors[self.button_style[b_name]['bg_color']]};font-size:{self.button_style[b_name]['font_size']}px;border-radius:{self.button_style[b_name]['corner_radius']}px;") #TODO Set proper style
            self.buttons[b_name].setText(f"{title}\n{self.button_style[b_name]['message']}")


    def button_clicked(self,name):
        logger.debug(f"Clicked button {name}")
        # Need to process action here
        if name in self.button_current_action:
            # This button has an action defined
            # TODO Need to check if this exists first!
            if 'update_data' in self.button_current_action[name]:
                logger.debug(f"loop over update_data {self.button_current_action[name]['update_data']}")
                for d in self.button_current_action[name]['update_data']:
                    logger.debug(f"{d}")
                    if d['type'] == 'set':
                        fix.db.set_value(d['db_item'], d['value']) 
                        logger.debug(f"Updated {d['db_item']} with value {d['value']}")
            # Need to check if this exists first
            if 'internal' in self.button_current_action[name]:
                logger.debug(f"Processing internal action {self.button_current_action[name]['internal']}")
                if self.button_current_action[name]['internal'] == 'next':
                    logger.debug("Next screen")
                    hmi.actions.trigger("show next screen")
                    self.change_button_visibility()
                elif self.button_current_action[name]['internal'] == 'back':
                    logger.debug("Previous screen")
                    hmi.actions.trigger("show previous screen")
                    self.change_button_visibility()
                elif self.button_current_action[name]['internal'] == 'exit':
                    logger.debug("Exit")
                    hmi.actions.trigger("exit")
                elif self.button_current_action[name]['internal'] == 'togglehide':
                    self.menu_hidden = not self.menu_hidden
                    if self.menu_hidden:
                        self.button_screen_titles[name]['default'] = "Show"
                    else:
                        self.button_screen_titles[name]['default'] = "Hide"
                    logger.debug("toggle hide")
                    self.change_button_visibility()
                    self.update_button_style(name)
                elif self.button_current_action[name]['internal'] == 'toggle_airspeed_mode':
                    logger.debug("toggle_airspeed_mode")
                    hmi.actions.trigger("set airspeed mode")

            if 'goto' in self.button_current_action[name]:
                cur_screen = self.myparent.getRunningScreen()
                if type(self.button_current_action[name]['goto']) is dict:
                    if cur_screen in self.button_current_action[name]['goto']:
                        goto = self.button_current_action[name]['goto'][cur_screen]
                    else:
                        goto = self.button_current_action[name]['goto']['default']
                else:
                    goto = self.button_current_action[name]['goto']
                logger.debug(f"Changing to screen {goto}")
                hmi.actions.trigger("show screen",goto)        
                self.change_button_visibility()
        #TODO implement this
            
    def set_value(self,db_item,value):
        logger.debug(f"Writing {value} to {db_item}")
        fix.db.set_value(db_item,value)

    def change_button_visibility(self):
        new_screen = self.myparent.getRunningScreen()
        for btn,hide_list in self.button_hide_on.items():
            if new_screen in hide_list:
                logger.debug(f"Hiding button {btn} on screen {new_screen}")
                self.buttons[btn].hide()
            else:
                logger.debug(f"Unhiding button {btn} on screen {new_screen}")
                self.buttons[btn].setEnabled(True)
                self.buttons[btn].show()
            self.update_button_style(btn)
        if self.menu_hidden:
            for b_name,b in self.config['buttons'].items():
                if b_name in self.menu_buttons:
                    logger.debug(f"Hiding {b_name}")
                    self.buttons[b_name].hide()
               
    def init_db(self):
        logger.debug("init db")
        for key in self.db_items:
            logger.debug(f"init db item {key}")
            item = fix.db.get_item(key)
            self.db[key] = item.value
            item.valueChanged[bool].connect(lambda valueChanged, key=key: self.data_modified(db_item=key))
            item.valueChanged[int].connect(lambda valueChanged, key=key: self.data_modified(db_item=key))
            item.valueChanged[str].connect(lambda valueChanged, key=key: self.data_modified(db_item=key))
            #item.annunciateChanged.connect(self.annunciateFlag)
            #item.oldChanged.connect(self.oldFlag)
            #item.badChanged.connect(self.badFlag)
            #item.failChanged.connect(self.failFlag)
         
    def init_buttons(self):
         # Process conditions for each button
         for b_name,b in self.config['buttons'].items():
             self.update_button(b_name)

    def data_modified(self,db_item):
        logger.debug(f"data modified for db item {db_item}")
        # Update the value so it can be used in conditions
        self.db[db_item] = fix.db.get_item(db_item).value
        # Update all buttons that use this value
        for b in self.db_items[db_item]:
        #    if b in self.buttons_disabled and self.buttons_disabled[b] == False:
                self.update_button(b)

    def update_button(self,button):
        logger.debug(f"Updating button {button}")
        if button in self.button_conditions:
            #This button has conditions that need evaluated
            logger.debug(f"Evaluating conditions for button {button}")
            for cond in self.button_conditions[button]:
                logger.debug(cond)
                if 'expression' in cond and 'action' in cond:
                    #This condition has an expression to evaluate
                    logger.debug(f"Evaluating expression: {cond['expression']}")
                    logger.debug(self.db)
                    expr = pc.to_struct(pc.tokenize(cond['expression'], sep=' ', brkts='()'))
                    logger.debug(expr)
                    if pc.pycond(expr)(state=self.db) == True:
                        logger.debug("Expression matched")
                        # TODO TODO TODO IMPORTANT!!@!! Exit the loop, first match wins!
                        # Update this buttons action, it will be processed when clicked
                        self.button_current_action[button] = cond['action']
                        if 'simulate_click' in cond['action']:
                            if cond['action']['simulate_click'] == True:
                                self.button_clicked(button)
                        if 'fg_color' in cond['action']:
                            self.button_style[button]['fg_color'] = cond['action']['fg_color']
                        if 'bg_color' in cond['action']:
                            self.button_style[button]['bg_color'] = cond['action']['bg_color']
                        if 'message' in cond['action']:
                            self.button_style[button]['message'] = cond['action']['message']
                        if 'title' in cond['action']:
                            self.button_style[button]['title'] = cond['action']['title']
                        self.update_button_style(button)
                        break

class BaroProxy:
    def __init__(self):
        self.enc = fix.db.get_item("ENC1")
        self.baro = fix.db.get_item("BARO")

    def focus(self):
        self.last_value = self.enc.value
        self.enc.valueChanged[int].connect(self.change)

    def defocus(self):
        self.enc.valueChanged[int].disconnect(self.change)

    def change(self, _):
        val = self.enc.value
        diff = val - self.last_value
        self.baro.value += (diff * .01)
        self.last_value = val

#def activateMenu(arg):
#    TheMenuObject.activate_menu(arg)
