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

try:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
except:
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *

import logging
log = logging.getLogger(__name__)


import hmi

__bindings = []

class DataBinding(object):
    def __init__(self, config):
        self.key = config['key']
        self.condition = None
        self.args = ""
        self.__value = None

        a = config['action']
        if hmi.actions.findAction(a):
            self.action = a
        else:
            log.error("Action Not Found - {}".format(a))
            return None

        if 'args' in config:
            self.args = config['args']
        if self.args == None: self.args = ""


    def __str__(self):
        s = "Data Binding: {} - {}({})".format(self.key, self.action, self.args)
        return(s)

def initialize(config):
    for x in config:
        try:
            d = DataBinding(x)
            print(d)
        except:
            log.error("Unable to load Data Binding {}".format(x))
            raise
