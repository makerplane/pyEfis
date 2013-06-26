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
import Queue
import random
import time
import struct
import canbus

import inspect # For TESTING Only

class Node():
    def __init__(self, name = None):
        self.name = name
        self.nodeID = 255
        self.deviceType = 0
        self.model = 0xAABBCC
        self.FWRevision = 1
        self.FWVCode = 0x0000
        self.FWChannel = None
        self.frameFunction = None
        
    def setFunction(self, function):
        if callable(function):
            self.frameFunction = function
        else:
            raise TypeError("Argument passed is not a function")
        
    def doFrame(self, frame):
        """Function that handles incoming frames for the node"""
        if frame.id > 0x700 and frame.data[0] == self.nodeID:
            # We start a response frame in case we need it
            f = canbus.Frame(self.nodeID + 0x700, [frame.id - 0x700, frame.data[1]])
            cmd = frame.data[1]
            if cmd == 0: #Node identification
                # TODO: Fix the model number part
                f.data.extend([0x01, self.deviceType % 255, 1, 0 , 0, 0])
            elif cmd == 1: # Bitrate Set Command
                return None
            elif cmd == 2: # Node Set Command
                self.nodeID = frame.data[2]
                f.data.append(0x00)
            #TODO: Fix these so they work??
            elif cmd == 3: # Disable Parameter
                return None
            elif cmd == 4: # Enable Parameter
                return None
            elif cmd == 5: # Node Report
                return None
            elif cmd == 7: # Firmware Update
                FCode = frame.data[3]<<8 | frame.data[2]
                if FCode == self.FWVCode:
                    FWChannel = frame.data[4]
                    f.data.append(0x00)
            return f
        
        return None
        
    def getFrame(self):
        """Function that produces a frame for the node."""
        if self.frameFunction:
            return self.frameFunction(self.nodeID)
        else:
            pass
        

# These are just functions that generate messages for each of the 
# nodes that we've created.

r_fuel_qty = 22.0
l_fuel_qty = 22.0
fuel_flow = 7.0

def __func_fuel(node):
    pass

engine = {}
engine['lasttime'] = time.time() + 0.25
engine['cht'] = (357 - 32 ) * 5/9
engine['egt'] = (1340 - 32) * 5/9
engine['oil_press'] = 78
engine['oil_temp'] = (180-32) * 5/9
engine['rpm'] = 2400
engine['man_press'] = 24
engine['n'] = 0
engine['i'] = 0

def __func_engine(node):
    global engine
    t = time.time()
    frame = canbus.Frame()
    if t > engine['lasttime'] + 1:
        if engine['n'] == 0:
            o = (int(time.time()*100) % 10) - 5
            x = struct.pack('<H', (engine['cht']+o)*10)
            frame.id = 0x500 #Cylinder Head Temperature
            frame.data = [node, engine['i'], 0, ord(x[0]), ord(x[1])]
            engine['i'] += 1
            if engine['i'] == 4:
                engine['i'] = 0
                engine['n'] += 1
        else:
            engine['n'] = 0
            engine['lasttime'] = t
            return None
        return frame
            
    
airdata = {}
airdata['lasttime'] = 0.0
airdata['airspeed'] = 165
airdata['altitude'] = 8500
airdata['oat'] = 10.5
airdata['n'] = 0

def __func_airdata(node):
    global airdata
    t = time.time()
    frame = canbus.Frame()
    if t > airdata['lasttime'] + 1:
        if airdata['n'] == 0:
            o = (int(time.time()*1000.0) % 40) - 20
            x = struct.pack('<H', (airdata['airspeed']*10 + o))
            frame.id = 0x183 #Indicated Airspeed
            frame.data = [node, 0, 0, ord(x[0]), ord(x[1])]
            airdata['n'] += 1
        elif airdata['n'] == 1:
            o = (int(time.time()*1000.0) % 20) - 10
            x = struct.pack('<l', (airdata['altitude']+o))
            frame.id = 0x184 #Indicated Altitude
            frame.data = [node, 0, 0, ord(x[0]), ord(x[1]), ord(x[2]), ord(x[3])]
            airdata['n'] += 1
        elif airdata['n'] == 2:
            o = (int(time.time()*1000.0) % 100) - 50
            x = struct.pack('<H', airdata['oat'] * 100 + o)
            frame.id = 0x407 #OAT
            frame.data = [node, 0, 0, ord(x[0]), ord(x[1])]
            airdata['n'] += 1
        else:
            airdata['n'] = 0
            airdata['lasttime'] = t
            return None
        return frame
    
def configNodes():
    nodelist = []
    for each in range(3):
        node = Node()
        node.nodeID = each + 1
        node.deviceType = 0x60
        node.model = 0x001
        nodelist.append(node)
    nodelist[0].setFunction(__func_airdata)
    nodelist[1].setFunction(__func_engine)
    #nodelist[0].FMVCode = 
    return nodelist
    
    
class Adapter():
    """Class that represents a CAN Bus simulation adapter"""
    def __init__(self):
        self.name = "CAN Device Simulator"
        self.shortname = "simulate"
        self.type = "None"
        self.__rQueue = Queue.Queue()
        random.seed()
        self.nodes = configNodes()
    
    def connect(self, config):
        print "Connecting to simulation adapter"
        self.open()    
    
    def disconnect(self):
        print "Disconnecting from simulation adapter"
        self.close()
        
    def open(self):
        print "Opening CAN Port"

    def close(self):
        print "Closing CAN Port"

    def error(self):
        print "Closing CAN Port"

    def sendFrame(self, frame):
        if frame.id < 0 or frame.id > 2047:
            raise ValueError("Frame ID out of range")
        else:
            for each in self.nodes:
                result = each.doFrame(frame)
                if result:
                    self.__rQueue.put(result)

    def recvFrame(self):
        for each in self.nodes:
            result = each.getFrame()
            if result:
                self.__rQueue.put(result)
            
        try:
            return self.__rQueue.get(timeout = 0.25)
        except Queue.Empty:
            raise DeviceTimeout()
        
                
        