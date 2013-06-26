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
import config
import threading
import Queue
import time
    

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
        
# Import and add each Adapter class from the files.  There may be a way
# to do this in a loop but for now this will work.
import simulate
import canfixusb
import easy
import network


class SendThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.getout = False
    
    def run(self):
        while(True):
            try:
                frame = sendQueue.get(timeout = 0.5)
                adapters[adapterIndex].sendFrame(frame)
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
    def __init__(self):
        threading.Thread.__init__(self)
        self.getout = False
    
    def run(self):
        while(True):
            try:
                frame = adapters[adapterIndex].recvFrame()
                n = 0
                for each in recvQueueActive:
                    if each:
                        recvQueueList[n].put(frame)
                        n+=1
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

def connect(index = None, config = None, adapter = None):
    global adapters
    global adapterIndex
    global sendThread
    global recvThread
    
    print "canbus.connect() has been called"
    if adapterIndex != None:
        if index == None:
            #return a new Receive Queue
            pass
        else:
            #Raise an exception that we already have a connection
            pass
    else:
        if index == None:
            if adapter != None:
                n = 0
                for each in adapters:
                    if adapters[n].shortname == adapter:
                        index = n
                        break
            else:
                raise BusInitError("Not enough information to make connection")
                pass
       
        sendThread = SendThread()
        recvThread = RecvThread()
        adapters[index].connect(config)
        adapterIndex = index
        sendThread.start()
        recvThread.start()
    return True
    
def disconnect():
    global adapters
    global adapterIndex
    global sendThread
    global recvThread
    
    if adapterIndex != None:
        if sendThread:
            sendThread.quit()
            sendThread.join()
        if recvThread:
            recvThread.quit()
            recvThread.join()
        sendThread = None
        recvThread = None
        
        # I know there is a more pythonic way to do this but this is what I know.
        for each in range(len(recvQueueActive)):
            recvQueueActive[each] = False

        adapters[adapterIndex].disconnect()
        adapterIndex = None

    
def sendFrame(frame):
    if adapterIndex == None:
        raise BusInitError("No Connection to CAN-Bus")
    sendQueue.put(frame)

def recvFrame(index, timeout = 0.25):
    if adapterIndex == None:
        raise BusInitError("No Connection to CAN-Bus")
    if index < 0 or index > len(recvQueueList):
        raise IndexError("No Such Receive Queue")
    if recvQueueActive[index] == False:
        raise BusInitError("Queue is not active")
    
    try:
        frame = recvQueueList[index].get(timeout = timeout)
        return frame
    except Queue.Empty:
        raise DeviceTimeout()
    
def enableRecvQueue(index):
    global listLock
    global recvQueueList
    global recvQueueActive
    
    with listLock:
        if index < 0 or index > len(recvQueueActive):
            raise IndexError("No Such Receive Queue")
        else:
            print "Enabling Receive Queue # " + str(index)
            recvQueueActive[index] = True
            
def disableRecvQueue(index):
    global listLock
    global recvQueueList
    global recvQueueActive
    
    with listLock:
        if index < 0 or index > len(recvQueueActive):
            raise IndexError("No Such Receive Queue")
        else:
            print "Disabling Receive Queue # " + str(index)
            recvQueueActive[index] = False
            

def __addRecvQueue():
    """Adds a new Queue to the recvQueueList"""
    global listLock
    global recvQueueList
    global recvQueueActive
    
    with listLock:
        newQueue = Queue.Queue()
        recvQueueList.append(newQueue)
        recvQueueActive.append(False)

def isConnected():
    if sendThread.isrunning() and recvThread.isrunning():
        return True
    else:
        return False

     
adapters = []
adapters.append(simulate.Adapter())
adapters.append(canfixusb.Adapter())
adapters.append(easy.Adapter())
adapters.append(network.Adapter())

adapterIndex = None
sendQueue = Queue.Queue()
recvQueueList = []
recvQueueActive = []
listLock = threading.Lock()
sendThread = None
recvThread = None
srcNode = 255

for each in range(3):
    __addRecvQueue()

