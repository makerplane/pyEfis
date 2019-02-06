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

try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import logging

import hooks
import fix

logger=logging.getLogger(__name__)

TheMenuObject=None

class Menu(QWidget):
    def __init__(self, parent, config):
        global TheMenuObject
        super(Menu, self).__init__(parent)
        self.config = config
        self.myparent = parent
        self.registered_targets = dict()
        self.buttons = list()
        self.button_actions = list()
        self.focused_object = None
        self.focus_button = -1
        self.last_button_clicked = -1
        last_x = self.config['left_margin']
        for b in range(self.config['number_of_buttons']):
            self.buttons.append(QPushButton("", self))
            self.button_actions.append(None)
            button_function = eval("self.button_clicked" + str(b+1))
            self.buttons[-1].clicked.connect(button_function)
            self.buttons[-1].move (last_x, self.config['top_margin'])
            last_x += self.config['buttons_spacing']
            button_function = eval("button" + str(b+1))
            fix.db.get_item("BTN" + str(b+1), True).valueChanged[bool].connect(button_function)
        self.adjustSize()
        self.register_target("BARO", BaroProxy())
        TheMenuObject = self

    def start(self):
        start_menu = self.config['start_menu']
        self.activate_menu (start_menu)

    def activate_menu(self, menu_name):
        logger.debug ("Menu.activate_menu (%s)", menu_name)
        self.current_menu = self.config['menus'][menu_name]
        for i,(label,actions) in enumerate(self.current_menu):
            self.set_button (i, label, actions)
            self.buttons[i].show()
            last_i = i
        last_i += 1
        while last_i < len(self.buttons):
            self.buttons[last_i].hide()
            last_i += 1

    def register_target(self, key, obj):
        self.registered_targets[key] = obj

    def focus(self, target):
        former_focus = None
        if self.focused_object is not None:
            self.focused_object.defocus()
            self.buttons[self.focus_button].setText(self.current_menu[self.focus_button][0])
            former_focus = self.focused_object
            self.focused_object = None
        if target is not None and ((former_focus is None) or (former_focus != self.registered_targets[target])):
            self.focused_object = self.registered_targets[target]
            self.focused_object.focus()
            self.focus_button = self.last_button_clicked
            self.buttons[self.focus_button].setText(self.current_menu[self.focus_button][0] + " Done")
        else:
            self.focused_object = None

    def set_button(self, i, label, actions):
        self.buttons[i].setText(label)
        self.button_actions[i] = actions

    def perform_action(self, actions):
        logger.debug ("perform_action: %s", str(actions))
        if actions is None:
            return
        if isinstance(actions,int):
            self.perform_action (self.button_actions[actions])
        elif isinstance(actions,list):
            for a in actions:
                self.perform_action(a)
        elif isinstance(actions,str):
            eval(actions)
        else:
            actions()

    def toggle_db_bool(self, key):
        db = fix.db.get_item(key)
        db.value = not db.value
        if db.value and self.last_button_clicked >= 0:
            self.buttons[self.last_button_clicked].setStyleSheet ("color: green")
        else:
            self.buttons[self.last_button_clicked].setStyleSheet ("color: black")


    def button_clicked(self, btn_num):
        if btn_num >= 0:
            self.last_button_clicked = btn_num
            self.perform_action(self.button_actions[btn_num])

    def button_clicked1(self, _):
        self.button_clicked(0)

    def button_clicked2(self, _):
        self.button_clicked(1)

    def button_clicked3(self, _):
        self.button_clicked(2)

    def button_clicked4(self, _):
        self.button_clicked(3)

    def button_clicked5(self, _):
        self.button_clicked(4)

    def button_clicked6(self, _):
        self.button_clicked(5)

def button1():
    btn_item = fix.db.get_item("BTN1", True)
    if btn_item.value:
        TheMenuObject.button_clicked(0)

def button2():
    btn_item = fix.db.get_item("BTN2", True)
    if btn_item.value:
        TheMenuObject.button_clicked(1)

def button3():
    btn_item = fix.db.get_item("BTN3", True)
    if btn_item.value:
        TheMenuObject.button_clicked(2)

def button4():
    btn_item = fix.db.get_item("BTN4", True)
    if btn_item.value:
        TheMenuObject.button_clicked(3)

def button5():
    btn_item = fix.db.get_item("BTN5", True)
    if btn_item.value:
        TheMenuObject.button_clicked(4)

def button6():
    btn_item = fix.db.get_item("BTN6", True)
    if btn_item.value:
        TheMenuObject.button_clicked(5)

class BaroProxy:
    def __init__(self):
        self.enc = fix.db.get_item("ENC1", True)
        self.baro = fix.db.get_item("BARO", True)

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
