#  Copyright (c) 2013 Phil Birkelbach
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

# The idea behind this file is to create an interface to generic aircraft
# data, regardless of how that data is retrieved.  Right now it is simply
# an extra layer on top of CANFIX but it's here is a place to allow for
# other interfaces.

import threading

import canbus
from . import canfix


class Parameter(object):
    def __init__(self, name=None, value=None):
        self.name = name
        self.value = value
        self.failed = False
        self.quaility = False
        self.annunciate = False


class Fix(threading.Thread):
    def __init__(self, adapter=None, device=None, bitrate=125):
        threading.Thread.__init__(self)
        self.getout = False
        self.adapter = adapter
        self.device = device
        self.bitrate = bitrate
        self.can = canbus.Connection(self.adapter)
        self.can.device = self.device
        self.can.bitrate = self.bitrate
        self._parameterCallback = None

    def setParameterCallback(self, function):
        if isinstance(function, collections.Callable):
            self._parameterCallback = function
        else:
            raise ValueError("Argument is supposed to be callable")

    def run(self):
        self.can.connect()
        while(True):
            try:
                frame = self.can.recvFrame()
                # Once we get a frame we parse it through canfix then
                # if the frame represents a CAN-FIX parameter then we make
                # a generic FIX parameter and send that to the callback
                cfobj = canfix.parseFrame(frame)
                print("Fix Thread parseFrame() returned", cfobj)
                if isinstance(cfobj, canfix.Parameter):
                    p = Parameter(cfobj.name, cfobj.value)
                    if self._parameterCallback:
                        self._parameterCallback(cfobj)
                    else:
                        print(frame)
            except canbus.exceptions.DeviceTimeout:
                pass
            except canbus.exceptions.BusError:
                # TODO: Should handle some of these
                # Maybe after ten or se we
                pass
            finally:
                if(self.getout):
                    break
        print("End of the FIX Thread")
        self.can.disconnect()

    def quit(self):
        self.getout = True
        self.join()

