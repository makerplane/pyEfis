#  CAN-FIX Utilities - An Open Source CAN FIX Utility Package 
#  Copyright (c) 2012 Phil Birkelbach
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

from exceptions import *

class Adapter():
    """Class that represents a generic TCP/IP to CAN Bus Adapter"""
    def __init__(self):
        self.name = "Dumb Network Driver"
        self.shortname = "network"
        self.type = "network"
    
    def connect(self):
        print "Connecting to simulation adapter"

    def open(self):
        print "Opening CAN Port"

    def close(self):
        print "Closing CAN Port"

    def error(self):
        print "Closing CAN Port"

    def sendFrame(self, frame):
        if frame['id'] < 0 or frame['id'] > 2047:
            raise ValueError("Frame ID out of range")

    def recvFrame(self):
        frame = {}
        frame['id'] = int(result[1:4], 16)
        frame['data'] = []
        for n in range(int(result[4], 16)):
            frame['data'].append(int(result[5+n*2:7+n*2], 16))
        print frame
        return frame