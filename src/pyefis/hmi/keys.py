#  Copyright (c) 2018 Phil Birkelbach
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

import logging
log = logging.getLogger(__name__)

from pyefis import hmi

__keypress = []
__keyrelease = []

class KeyBinding(object):
    def __init__(self, config):
        self.key = QKeySequence(config['key'])
        self.args = ""
        self.direction = 'DN'

        if self.key.toString() == '':
            log.error("Invalid Key {}".format(config['key']))
            return None
        a = config['action']
        if hmi.actions.findAction(a):
            self.action = a
        else:
            log.error("Action Not Found - {}".format(a))
            return None
        if 'args' in config:
            self.args = config['args']
        if self.args == None: self.args = ""
        if 'direction' in config:
            d = config['direction'].lower()
            if d == 'up':
                self.direction = "UP"

    def __str__(self):
        s = "Key Binding: {} - {}({})".format(self.key.toString(), self.action, self.args)
        return(s)


def keyPress(event):
    for each in __keypress:
        if event.key() == each.key and not event.isAutoRepeat():
            hmi.actions.trigger(each.action, each.args)


def keyRelease(event):
    for each in __keyrelease:
        if event.key() == each.key and not event.isAutoRepeat():
            hmi.actions.trigger(each.action, each.args)


def initialize(window, config):
    for x in config:
        try:
            k = KeyBinding(x)
        except:
            log.error("Unable to load Key Binding {}".format(x))
        if k:
            if k.direction == 'DN':
                __keypress.append(k)
            else:
                __keyrelease.append(k)


    window.keyPress.connect(keyPress)
    window.keyRelease.connect(keyRelease)
