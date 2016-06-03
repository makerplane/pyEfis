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
import scheduler


# This class represents a single data point in the database.  It contains
# all of the Qt signals for communicating the data as well as the properties
# and quality flags of each point.
class DB_Item(QObject):
    valueChanged = pyqtSignal([float],[int],[bool],[str])
    valueWrite = pyqtSignal([float],[int],[bool],[str])
    annunciateChanged = pyqtSignal(bool)
    oldChanged = pyqtSignal(bool)
    badChanged = pyqtSignal(bool)
    failChanged = pyqtSignal(bool)
    auxChanged = pyqtSignal(dict)
    reportReceived = pyqtSignal()

    def __init__(self, key, dtype='float'):
        super(DB_Item, self).__init__()
        self.dtype = dtype
        self.key = key
        self._value = 0.0
        self.description = ""
        self._units = ""
        self._annunciate = False
        self._old = False
        self._bad = True
        self._fail = True
        self._max = None
        self._min = None
        self._tol = 100     # Timeout lifetime in milliseconds.  Any older and quality is bad
        self.timestamp = datetime.utcnow()
        self.aux = {}
        self.output = False
        self.subscribe = True
        self.is_subscribed = False
        log.debug("Creating Item {0}".format(key))


    # initialize the auxiliary data dictionary.  aux should be a comma delimited
    # string of the items to include.
    def init_aux(self, aux):
        l = aux.split(',')
        for each in l:
            if each != "":
                self.aux[each.strip()] = None

    def get_aux_list(self):
        return list(self.aux.keys())

    def set_aux_value(self, name, value):
        try:
            last = self.aux[name]
            if value == None or value == "None":
                self.aux[name] = None
            else:
                self.aux[name] = self.dtype(value)
            if self.aux[name] != last:
                self.auxChanged.emit(self.aux)
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

    # Outputs the value to the send queue and on to the fixgw server
    def output_value(self):
        flags = "1" if self.annunciate else "0"
        flags += "0" # if self.old else "0"
        flags += "1" if self.bad else "0"
        flags += "1" if self.fail else "0"

        # TODO Handle the Aux data.
        db.queue_out("{0};{1};{2}\n".format(self.key, self.value, flags).encode())

    # return the age of the item in milliseconds
    @property
    def age(self):
        d = datetime.utcnow() - self.timestamp
        return d.total_seconds() * 1000 + d.microseconds / 1000

    @property
    def value(self):
        if self.age > self.tol and self.tol != 0:
            self.old = True
        else:
            self.old = False
        return self._value #, self.annunciate, self.old, self.bad, self.fail)

    @value.setter
    def value(self, x):
        last = self._value
        if self.dtype == bool:
            if type(x) == bool:
                self._value = x
            else:
                self._value = (x == True or x.lower() in ["yes", "true", "1", 1])
        else:
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
            if self.output:
                self.output_value()
        self.valueWrite.emit(self._value)

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
    def units(self):
        return self._units

    @units.setter
    def units(self, value):
        self._units = value.replace("deg",u'\N{DEGREE SIGN}')

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



# This Class represents the database itself.  Once instantiated it
# creates and starts the thread that handles all the communication to
# the server.
class Database(object):
    def __init__(self, host, port):
        self.__items = {}
        global log
        log = logging.getLogger(__name__)

        self.clientthread = client.ClientThread(host, port, self)
        self.clientthread.start()
        self.__configured_outputs = {}
        self.__timers = []

    # Either add an item or redefine the item if it already exists.
    #  This is mostly useful when the FIXGW client reconnects.  The
    #  server may have different information.
    def define_item(self, key, desc, dtype, min, max, units, tol, aux):
        if key in self.__items:
            log.debug("Redefining Item {0}".format(key))
            item = self.__items[key]
        else:
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
        if key in self.__configured_outputs:
            self.subscribe = False
            self.queue_out("@u{0}\n".format(key).encode())
            if self.__configured_outputs[key] in ["onchange", "both"]:
                item.output = True
                # TODO raise an error if the method is not 'interval' ?????
            if self.__configured_outputs[key] in ["interval", "both"]:
                t = int(tol)/2
                timer = scheduler.scheduler.getTimer(t)
                if timer:
                    timer.add_callback(item.output_value)
                else:
                    log.warning("Unable to find a scheduler timer with interval of {0}".format(t))
            # TODO Error for unknown output method
        else:
            # If we are not an output then subscribe to the point
            self.queue_out("@s{0}\n".format(key).encode())
        self.__items[key] = item

        # Send a read command to the server to get initial data
        self.queue_out("@r{0}\n".format(key).encode())
        for each in item.aux: # Read the Auxiliary data
            self.queue_out("@r{0}.{1}\n".format(key, each).encode())
        item.reportReceived.emit()

    # If the create flag is set to True this function will create an
    # item with the given key if it does not exist.  Otherwise just
    # return the item if found.
    def get_item(self, key, create=False):
        try:
            return self.__items[key]
        except KeyError:
            if create:
                newitem = DB_Item(key)
                self.__items[key] = newitem
                return newitem
            else:
                raise  # Send the exception up otherwise

    def set_value(self, key, value):
        self.__items[key].value = value

    def mark_all_fail(self):
        for each in self.__items:
            self.__items[each].fail = True

    def add_output(self, key, method):
        m = method.lower()
        if m not in ["interval", "onchange", "both"]:
            raise ValueError("Unknown output method for {0}".format(key))
        else:
            self.__configured_outputs[key] = m
            self.subscribe = False
            #self.queue_out("@u{0}\n".format(key).encode())
        log.debug("Adding output for {0}, method = {1}".format(key, method))

    def queue_out(self, output):
        self.clientthread.sendqueue.put(output)


    def stop(self):
        self.clientthread.stop()
        self.clientthread.wait()


def initialize(host, port):
    global db
    db = Database(host, port)
    log.info("Initializing FIX Client")

def stop():
    db.stop()
