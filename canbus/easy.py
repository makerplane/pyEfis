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
import serial
import time
#from serial.tools.list_ports import comports

class Adapter():
    """Class that represents an EasySync USB2-F-7x01 USB to CANBus adapter"""
    def __init__(self):
        self.name = "EasySync USB2-F-7x01"
        self.shortname = "easy"
        self.type = "serial"
        self.ser = None
        
    def __readResponse(self):
        str = ""

        while 1:
            x = self.ser.read()
            if len(x) == 0:
                raise DeviceTimeout
            else:
                str = str + x
                if x == "\r": # Good Response
                    return str
                if x == "\x07": # Bell is error
                    raise BusReadError("USB2-F-7x01 Returned Bell")

    def connect(self, config):
        try:
            self.bitrate = config['bitrate']
        except KeyError:
            self.bitrate = 125
        bitrates = {10:"S0\r", 20:"S1\r", 50:"S2\r", 100:"S3\r", 
                    125:"S4\r", 250:"S5\r", 500:"S6\r", 800:"S7\r", 1000:"S8\r"}
        try:
            self.portname = config['port']
        except KeyError:
            self.portname = comports[0][0]
        
        try:
            self.timeout = config['timeout']
        except KeyError:
            self.timeout = 0.25
            
        self.ser = serial.Serial(self.portname, 115200, timeout=self.timeout)
                
        print "Reseting USB2-F-7x01"
        self.ser.write("R\r")
        try:
            result = self.__readResponse()
        except DeviceTimeout:
            raise BusInitError("Timeout waiting for USB2-F-7x01")
        except BusReadError:
            raise BusInitError("Unable to Reset USB2-F-7x01")
        time.sleep(2)

        print "Setting Bit Rate"
        self.ser.write(bitrates[self.bitrate])
        try:
            result = self.__readResponse()
        except DeviceTimeout:
            raise BusInitError("Timeout waiting for USB2-F-7x01")
        except BusReadError:
            raise BusInitError("Unable to set CAN Bit rate")
        self.open()
    
    def disconnect(self):
        self.close()

    def open(self):
        print "Opening CAN Port"
        self.ser.write("O\r")
        try:
            result = self.__readResponse()
        except DeviceTimeout:
            raise BusInitError("Timeout waiting for USB2-F-7x01")
        except BusReadError:
            raise BusInitError("Unable to Open CAN Port")

    def close(self):
        print "Closing CAN Port"
        self.ser.write("C\r")
        try:
            result = self.__readResponse()
        except DeviceTimeout:
            raise BusInitError("Timeout waiting for USB2-F-7x01")
        except BusReadError:
            raise BusInitError("Unable to Close CAN Port")

    def error(self):
        print "Closing CAN Port"
        self.ser.write("F\r")
        try:
            result = self.__readResponse()
        except DeviceTimeout:
            raise BusInitError("Timeout waiting for USB2-F-7x01")
        except BusReadError:
            raise BusInitError("Unable to Close CAN Port")
        return int(result, 16)

    def sendFrame(self, frame):
        if frame['id'] < 0 or frame['id'] > 2047:
            raise ValueError("Frame ID out of range")
        xmit = "t"
        xmit = xmit + '%03X' % (frame['id'])
        xmit = xmit + str(len(frame['data']))
        for each in frame['data']:
            xmit = xmit + '%02X' % each
        xmit = xmit + '\r'
        self.ser.write(xmit)
        while True:
            try:
                result = self.__readResponse()
            except DeviceTimeout:
                raise BusWriteError("Timeout waiting for USB2-F-7x01")
            if result[0] == 't':
                continue
            elif result != 'z\r':
                print "result =", result
                raise BusWriteError("Bad response from USB2-F-7x01")
            else:
                break


    def recvFrame(self):
        result = self.__readResponse()
        print result, 
        if result[0] != 't':
            raise BusReadError("Unknown response from USB2-F-7x01")
        frame = {}
        frame['id'] = int(result[1:4], 16)
        frame['data'] = []
        for n in range(int(result[4], 16)):
            frame['data'].append(int(result[5+n*2:7+n*2], 16))
        print frame
        return frame