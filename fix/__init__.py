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

import logging
log = logging.getLogger(__name__)

import client

class DB_Item(object):
    def __init__(self, dtype='float'):
        types = {'float':float, 'int':int, 'bool':bool, 'str':str}
        try:
            self.dtype = types[dtype]
            self.typestring = dtype
        except:
            log.error("Unknown datatype - " + str(dtype))
            raise
        self._value = 0.0
        self.description = ""
        self.units = ""
        self.annunciate = False
        self.old = False
        self.bad = False
        self.fail = False
        self._max = None
        self._min = None
        self._tol = 100     # Time to live in milliseconds.  Any older and quality is bad
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


class Database(object):
    def __init__(self):
        items = {}





def initialize():
    global __thread
    db = Database()
    __thread = client.ClientThread('127.0.0.1', 3490, db)
    __thread.start()

def stop():
    __thread.stop()
    __thread.join()
