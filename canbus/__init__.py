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

# This module is to abstract the interface between the code and the
# CANBus communication adapters.


from exceptions import *
import serial
import threading
import Queue
import time

# Import and add each Adapter class from the files.  There may be a way
# to do this in a loop but for now this will work.
import simulate
import canfixusb
import easy
import network

def getSerialPortList():
    # Scan for available ports.
    available = []
    
    for i in config.portlist:
        try:
            s = serial.Serial(i)
            available.append(s.portstr)
            s.close()
        except serial.SerialException:
            pass
    return available


class Frame(object):
    """Class represents a CANBus frame"""
    def __init__(self, id=0, data=[]):
        self.id = id
        self.data = data
    def __str__(self):
        s = hex(self.id)[2:] + ':'
        for each in self.data:
            if each < 16: s = s + '0'
            s = s + hex(each)[2:]  + ' '
        return s.upper()

class SendThread(threading.Thread):
    def __init__(self, adapter, queue):
        threading.Thread.__init__(self)
        self.adapter = adapter
        self.sendQueue = queue
        self.getout = False
    
    def run(self):
        while(True):
            try:
                frame = self.sendQueue.get(timeout = 0.5)
                self.adapter.sendFrame(frame)
            except Queue.Empty:
                pass
            except BusError:
                # TODO: Should handle some of these
                pass
            finally:
                if(self.getout):
                    break
                #print "Send Thread", adapterIndex
        print "End of the Send Thread"
    
    def quit(self):
        self.getout = True


class RecvThread(threading.Thread):
    def __init__(self, adapter, queue):
        threading.Thread.__init__(self)
        self.adapter = adapter
        self.recvQueue = queue
        self.getout = False
    
    def run(self):
        while(True):
            try:
                frame = self.adapter.recvFrame()
                self.recvQueue.put(frame)
            except DeviceTimeout:
                pass
            except BusError:
                print "BussError"
                # TODO: Should probably handle some of these.
                pass
            finally:
                if(self.getout):
                    break
                #print "Receive Thread", adapterIndex
        print "End of the Receive thread"
        
    def quit(self):
        self.getout = True

class Config(object):
    def __init__(self):
        self.device = None
        self.bitrate = None
        self.ipaddress = '127.0.0.1'
        self.port = 63349 #NEFIX on keypad
        self.timeout = 0.25
    


class Connection(object):
    def __init__(self, adapter = None):
        self.adapterString = adapter
        self.device = None
        self.bitrate = 125
        self.ipaddress = '127.0.0.1'
        self.port = 63349 #NEFIX on keypad
        self.timeout = 0.25
        self.sendQueue = Queue.Queue()
        self.recvQueue = Queue.Queue()
        
        
    def connect(self):
        if self.adapterString.lower() == 'simulate':
            self.adapter = simulate.Adapter()
        elif self.adapterString.lower() == 'canfixusb':
            self.adapter = canfixusb.Adapter()
        elif self.adapterString.lower() == 'easy':
            self.adapter = easy.Adapter()
        elif self.adapterString.lower() == 'netowrk':
            self.adapter = network.Adapter()
        else:
            raise IndexError("Undefined CANBus Adapter " + str(adapter))
        config = Config()
        config.bitrate = self.bitrate
        config.device = self.device
        config.ipaddress = self.ipaddress
        config.port = self.port
        config.timeout = self.timeout
        self.adapter.connect(config)
        self.recvThread = RecvThread(self.adapter, self.recvQueue)
        self.sendThread = SendThread(self.adapter, self.sendQueue)
        self.recvThread.start()
        self.sendThread.start()

    def disconnect(self):
        if self.sendThread:
            self.sendThread.quit()
            self.sendThread.join()
        if self.recvThread:
            self.recvThread.quit()
            self.recvThread.join()
        self.sendThread = None
        self.recvThread = None
        
        self.adapter.disconnect()
        self.adapter = None
        
    def isConnected(self):
        if self.sendThread.isrunning() and self.recvThread.isrunning():
            return True
        else:
            return False


    def sendFrame(self, frame):
        if self.adapter == None:
            raise BusInitError("No Connection to CAN-Bus")
        self.sendQueue.put(frame)

    def recvFrame(self, timeout = 0.25):
        if self.adapter == None:
            raise BusInitError("No Connection to CAN-Bus")
        try:
            frame = self.recvQueue.get(timeout = timeout)
            return frame
        except Queue.Empty:
            raise DeviceTimeout()
