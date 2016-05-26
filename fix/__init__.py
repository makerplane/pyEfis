#  Copyright (c) 2016 Phil Birkelbach
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

# This module is a FIX-Net client used primarily to get the flight data
# from FIX-Gateway.

try:
    from PyQt5.QtCore import *
except:
    from PyQt4.QtCore import *

import logging
from datetime import datetime

import client

class DB_Item(QObject):
    #valueChanged = pyqtSignal(float)
    valueChanged = pyqtSignal([float,int,bool,str])
    annunciateChanged = pyqtSignal(bool)
    oldChanged = pyqtSignal(bool)
    badChanged = pyqtSignal(bool)
    failChanged = pyqtSignal(bool)

    def __init__(self, key, dtype='float'):
        super(DB_Item, self).__init__()
        self.dtype = dtype
        self.key = key
        self._value = 0.0
        self.description = ""
        self.units = ""
        self._annunciate = False
        self._old = False
        self._bad = True
        self._fail = True
        self._max = None
        self._min = None
        self._tol = 100     # Timeout lifetime in milliseconds.  Any older and quality is bad
        self.timestamp = datetime.utcnow()
        self.aux = {}


    # initialize the auxiliary data dictionary.  aux should be a comma delimited
    # string of the items to include.
    def init_aux(self, aux):
        l = aux.split(',')
        for each in l:
            self.aux[each.strip()] = None

    def get_aux_list(self):
        return list(self.aux.keys())

    def set_aux_value(self, name, value):
        try:
            self.aux[name] = self.dtype(value)
        except ValueError:
            log.error("Bad Value for aux {0} {1}".format(name, value))
            raise
        except KeyError:
            log.error("No aux {0} for {1}".format(name, self.description))
            raise

    def get_aux_value(self, name):
        try:
            return self.aux[name]
        except KeyError:
            log.error("No aux {0} for {1}".format(name, self.description))
            raise


    # return the age of the item in milliseconds
    @property
    def age(self):
        d = datetime.utcnow() - self.timestamp
        return d.total_seconds() * 1000 + d.microseconds / 1000

    @property
    def value(self):
        if self.age > self.tol:
            self.old = True
        else:
            self.old = False
        return (self._value, self.annunciate, self.old, self.bad, self.fail)

    @value.setter
    def value(self, x):
        last = self._value
        try:
            self._value = self.dtype(x)
        except ValueError:
            log.error("Bad value '" + str(x) + "' given for " + self.description)
        # bounds check and cap
        try:
            if self._value < self._min: self._value = self._min
        except:  # Probably only fails if min has not been set
            pass  # ignore at this point
        try:
            if self._value > self._max: self._value = self._max
        except:  # Probably only fails if max has not been set
            pass  # ignore at this point
        # set the timestamp to right now
        self.timestamp = datetime.utcnow()
        if last != self._value:
            self.valueChanged.emit(self._value)

    @property
    def dtype(self):
        return self._dtype

    @dtype.setter
    def dtype(self, dtype):
        types = {'float':float, 'int':int, 'bool':bool, 'str':str}
        try:
            self._dtype = types[dtype]
            self._typestring = dtype
        except:
            log.error("Unknown datatype - " + str(dtype))
            raise

    @property
    def typestring(self):
        return self._typestring

    @property
    def min(self):
        return self._min

    @min.setter
    def min(self, x):
        try:
            self._min = self.dtype(x)
        except ValueError:
            log.error("Bad minimum value '" + str(x) + "' given for " + self.description)

    @property
    def max(self):
        return self._max

    @max.setter
    def max(self, x):
        try:
            self._max = self.dtype(x)
        except ValueError:
            log.error("Bad maximum value '" + str(x) + "' given for " + self.description)

    @property
    def tol(self):
        return self._tol

    @tol.setter
    def tol(self, x):
        try:
            self._tol = int(x)
        except ValueError:
            log.error("Time to live should be an integer for " + self.description)

    @property
    def annunciate(self):
        return self._annunciate

    @annunciate.setter
    def annunciate(self, x):
        last = self._annunciate
        self._annunciate = bool(x)
        if self._annunciate != last:
            self.annunciateChanged.emit(self._annunciate)

    @property
    def old(self):
        return self._old

    @old.setter
    def old(self, x):
        last = self._old
        self._old = bool(x)
        if self._old != last:
            self.oldChanged.emit(self._old)

    @property
    def bad(self):
        return self._bad

    @bad.setter
    def bad(self, x):
        last = self._bad
        self._bad = bool(x)
        if self._bad != last:
            self.badChanged.emit(self._bad)

    @property
    def fail(self):
        return self._fail

    @fail.setter
    def fail(self, x):
        last = self._fail
        self._fail = bool(x)
        if self._fail != last:
            self.failChanged.emit(self._fail)


class Database(object):
    def __init__(self):
        self.__items = {}

    # Either add an item or redefine the item if it already exists.
    #  This is mostly useful when the FIXGW client reconnects.  The
    #  server may have different information.
    def define_item(self, key, desc, dtype, min, max, units, tol, aux):
        if key in self.__items:
            log.debug("Redefining Item {0}".format(key))
            item = self.__items[key]
            item.dtype = dtype #Just in case it's different
        else:
            log.debug("Adding Item {0}".format(key))
            item = DB_Item(key, dtype)
        item.dtype = dtype
        item.annunciate = False
        item.old = False
        item.bad = True
        item.fail = True
        item.desc = desc
        item.min = min
        item.max = max
        item.units = units
        item.tol = tol
        item.init_aux(aux)
        self.__items[key] = item

    # If the create flag is set to True this function will create an
    # item with the given key if it does not exist.  Otherwise just
    # return the item if found.
    def get_item(self, key, create=False):
        try:
            return self.__items[key]
        except KeyError:
            if create:
                self.__items[key] = DB_Item(key)
            else:
                raise  # Send the exception up otherwise


    def mark_all_fail(self):
        for each in self.__items:
            self.__items[each].fail = True


def initialize():
    global __thread
    global log
    log = logging.getLogger(__name__)

    db = Database()
    __thread = client.ClientThread('127.0.0.1', 3490, db)
    __thread.start()

def stop():
    __thread.stop()
    __thread.join()
