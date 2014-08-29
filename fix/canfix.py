#!/usr/bin/env python

#  CAN-FIX Protocol Module - An Open Source Module that abstracts communication
#  with the CAN-FIX Aviation Protocol
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

import os
import xml.etree.ElementTree as ET
import copy
import struct
import time
import canbus

class NodeAlarm(object):
    """Represents a Node Alarm"""
    def __init__(self, frame=None):
        if frame != None:
            self.setFrame(frame)
            
    def setFrame(self, frame):
        self.node = frame.id
        self.alarm = frame.data[0] + frame.data[1]*256
        self.data = frame.data[2:]
        self.data += [0] * (5-len(self.data)) # Pad data with zeros
    
    def getFrame(self):
        frame = canbus.Frame()
        frame.id = self.node
        frame.data.append(self.alarm % 256)
        frame.data.append(self.alarm / 256)
        for each in self.data:
            frame.data.append(each)
        return frame
    
    frame = property(getFrame, setFrame)
    
    def __str__(self):
        s = "[" + str(self.node) + "] Node Alarm " + str(self.alarm) + " Data " + str(self.data)
        return s

class Parameter(object):
    """Represents a normal parameter update frame"""
    def __init__(self, frame=None):
        if frame != None:
            if len(frame.data) < 4: return None
            self.setFrame(frame)
        else:
            self.__failure = False
            self.__quality = False
            self.__annunciate = False
            self.value = 0
            self.index = 0
            self.node = 0
            self.__meta = None
            self.function = 0

    def __parameterData(self, frameID):
        # This function gets the data from the XML file dictionary
        p = parameters[frameID]
        self.__name = p.name
        self.units = p.units
        self.type = p.type
        self.min = p.min
        self.max = p.max
        self.format = p.format
        self.indexName = p.index
        self.multiplier = p.multiplier
        if self.multiplier == None:
            self.multiplier = 1
            
    def setIdentifier(self, identifier):
        """Set the identifier of the Parameter, identifier can be either
        the actual integer identifier or the name of the parameter"""
        if identifier in parameters:
            self.frame = canbus.Frame(identifier)
        else:
            raise ValueError("Bad Parameter Identifier Given")
            
        self.__identifier = self.frame.id
        self.__parameterData(self.frame.id)
        
    def getIdentifier(self):
        return self.__identifier
    
    identifier = property(getIdentifier, setIdentifier)
    
    def setName(self, name):
        s = name.upper()
        for i in parameters:
            if parameters[i].name.upper() == s:
                self.__frame = canbus.Frame(i)
                self.__identifier = i
                self.__parameterData(self.__frame.id)
                return
        raise ValueError("Unknown Parameter Name")
        
    def getName(self):
        return self.__name

    name = property(getName, setName)
    
    def setFailure(self, failure):
        if failure:
            self.function |= 0x04
            self.__failure = True
        else:
            self.function &= ~0x04
            self.__failure = False
    
    def getFailure(self):
        return self.__failure
    
    failure = property(getFailure, setFailure)
    
    def setQuality(self, quality):
        if quality:
            self.function |= 0x02
            self.__quality = True
        else:
            self.function &= ~0x02
            self.__quality = False
    
    def getQuality(self):
        return self.__quality
    
    quality = property(getQuality, setQuality)
    
    def setAnnunciate(self, annunciate):
        if annunciate:
            self.function |= 0x01
            self.__annunciate = True
        else:
            self.function &= ~0x01
            self.__annunciate = False
    
    def getAnnunciate(self):
        return self.__annunciate
    
    annunciate = property(getAnnunciate, setAnnunciate)
    
    def setMeta(self, meta):
        if isinstance(meta, int):
            self.function &= 0x0F
            self.function |= meta << 4
            self.__meta = parameters[self.__frame.id].auxdata[meta]
        elif isinstance(meta, str):
            p = parameters[self.__frame.id]
            for each in p.auxdata:
                if p.auxdata[each].upper() == meta.upper():
                    self.function &= 0x0F
                    self.function |= each << 4
                    self.__meta = p.auxdata[each] # Get's the case right 
        else:
            self.__meta = None
        
    def getMeta(self):
        return self.__meta
        
    meta = property(getMeta, setMeta)
    
    def setFrame(self, frame):
        self.__frame = frame
        p = parameters[frame.id]
        self.__identifier = frame.id
        self.__parameterData(frame.id)
        self.node = frame.data[0]
        self.index = frame.data[1]
        self.function = frame.data[2]
        self.data = bytearray(frame.data[3:])
        if self.function & 0x04:
            self.__failure = True
        else:
            self.__failure = False
        if self.function & 0x02:
            self.quality = True
        else:
            self.quality = False
        if self.function & 0x01:
            self.annunciate = True
        else:
            self.annunciate = False
        self.value = self.unpack()
        try:
            self.meta = p.auxdata[self.function>>4]
        except KeyError:
            self.meta = None
        
        self.updated = time.time()
        
    def getFrame(self):
        self.data = []
        self.data.append(self.node % 256)
        if self.index:
            self.data.append(self.index % 256)
        else:
            self.data.append(0)
        
        self.data.append(self.function)
        self.data.extend(self.pack())
        self.__frame.data = self.data
        return self.__frame
    
    frame = property(getFrame, setFrame)
    
    def getFullName(self):
        if self.indexName:
            return "%s %s %i" % (self.__name, self.indexName, self.index + 1)
        else:
            return self.__name 
        
    fullName = property(getFullName)
    
    def valueStr(self, units=False):
        if self.__identifier == 0x580: #Time  
            return "%02i:%02i:%02i" % (self.value[0], self.value[1], self.value[2])
        elif self.__identifier == 0x581: #Date
            return "%i-%i-%i" % (self.value[0], self.value[1], self.value[2])
        else:
            if self.units:
                return str(self.value) + " " + self.units
            else:
                return str(self.value)
        
    def unpack(self):
        if self.type == "UINT, USHORT[2]": #Unusual case of the date
            x = []
            x.append(getValue("UINT", self.data[0:2],1))
            x.append(getValue("USHORT", self.data[2:3], 1))
            x.append(getValue("USHORT", self.data[3:4], 1))
            for each in x:
                if each==None: self.__failure=True
        elif '[' in self.type:
            y = self.type.strip(']').split('[')
            if y[0] == 'CHAR':
                x = getValue(self.type, self.data, self.multiplier)
            else:
                x = []
                size = getTypeSize(y[0])
                for n in range(int(y[1])):
                    x.append(getValue(y[0], self.data[size*n:size*n+size], self.multiplier))
                for each in x:
                    if each==None: self.__failure=True
        else:
            x = getValue(self.type, self.data, self.multiplier)
            if x == None: self.__failure = True
        return x
    
    def pack(self):
        if self.type == "UINT, USHORT[2]": # unusual case of the date
           x=[]
           x.extend(setValue("UINT", self.value[0]))
           x.extend(setValue("USHORT", self.value[1]))
           x.extend(setValue("USHORT", self.value[2]))
           return x
        elif '[' in self.type:
            y = self.type.strip(']').split('[')
            #if y[0] == 'CHAR':
            #    return setValue(self.type, self.value)
            #else:
            x = []
            for n in range(int(y[1])):
                x.extend(setValue(y[0], self.value[n]))
            return x
        else:
            return setValue(self.type, self.value, self.multiplier)
    
    def __cmp__(self, other):
        if self.__identifier < other.__identifier:
            return -1
        elif self.__identifier > other.__identifier:
            return 1
        else:
            if self.index < other.index:
                return -1
            elif self.index > other.index:
                return 1
            else:
                return 0

    
    def __str__(self):
        s = '[' + str(self.node) + '] ' + self.name
        if self.meta: s = s + ' ' + self.meta
        if self.indexName:
            s = s + ' ' + self.indexName + ' ' + str(self.index+1)
        s = s + ': '
        if self.value != None:
            if isinstance(self.value, list):
                if self.type == "BYTE" or self.type == "WORD":
                    n = 0 #loop counter
                    for each in reversed(self.value):
                        if each == True:
                            s = s+'1'
                        else:
                            s = s+'0'
                        n += 1
                        if n % 4 == 0: #add a space every four bits
                            s = s+' '
                else:
                    for each in self.value:
                        s = s + str(each) + ','
                s = s.strip(', ')
            else:
               s = s + str(self.value)
            if self.units != None:
                s = s + ' ' + self.units
            if self.failure:
                s = s + ' [FAIL]'
            if self.quality:
                s = s + ' [QUAL]'
            if self.annunciate:
                s = s + ' [ANNUNC]'
        return s
        
class TwoWayMsg(object):
    """Represents 2 Way communication channel data"""
    def __init__(self, frame=None):
        if frame != None:
            self.setFrame(frame)
        else:
            self.type = "Request"
    
    def setFrame(self, frame):
        self.channel = (frame.id - 1760) /2
        self.data = frame.data
        if frame.id % 2 == 0:
            self.type = "Request"
        else:
            self.type = "Response"
    
    def getFrame(self):
        frame = canbus.Frame()
        frame.id = self.channel*2 + 1760
        if self.type == "Response":
            frame.id += 1
        frame.data = self.data
        return frame
    
    frame = property(getFrame, setFrame)

    def __str__(self):
        s = self.type + " on channel " + str(self.channel) + ': ' + str(self.data)
        return s

class NodeSpecific(object):
    """Represents a Node Specific Message"""
    codes = ["Node Identification", "Bit Rate Set", "Node ID Set", "Disable Parameter",
             "Enable Parameter", "Node Report", "Node Status", "Update Firmware",
             "Connection Request", "Node Configuration Set", "Node Configuration Query"]
    
    def __init__(self, frame=None):
        if frame != None:
            self.setFrame(frame)
        else:
            self.controlCode = 0
            self.data = []

    def setFrame(self, frame):
        self.sendNode = frame.id -1792
        self.destNode = frame.data[0]
        self.controlCode = frame.data[1]
        self.data = frame.data[2:]
    
    def getFrame(self):
        f = canbus.Frame(self.sendNode + 1792)
        f.data.append(self.destNode)
        f.data.append(self.controlCode)
        for each in self.data:
            f.data.append(each)
        return f
    
    frame = property(getFrame, setFrame)
    
    def __str__(self):
        s = '[' + str(self.sendNode) + ']'
        s = s + "->[" + str(self.destNode) + '] '
        try:
            s = s + self.codes[self.controlCode]
        except IndexError:
            if self.controlCode < 128:
                s = s + "Reserved NSM "
            else:
                s = s + "User Defined NSM "
            s = s + str(self.controlCode)
        s = s + ": " + str(self.data)
        return s

def getTypeSize(datatype):
    """Return the size of the CAN-FIX datatype in bytes"""
    table = {"BYTE":1, "WORD":2, "SHORT":1, "USHORT":1, "UINT":2,
             "INT":2, "DINT":4, "UDINT":4, "FLOAT":4, "CHAR":1}
    return table[datatype]


# This function takes the bytearray that is in data and converts it into a value.
# The table is a dictionary that contains the CAN-FIX datatype string as the
# key and a format string for the stuct.unpack function.
def getValue(datatype, data, multiplier):
    table = {"SHORT":"<b", "USHORT":"<B", "UINT":"<H",
             "INT":"<h", "DINT":"<l", "UDINT":"<L", "FLOAT":"<f"}
    x = None
    
    #This code handles the bit type data types
    if datatype == "BYTE":
        x = []
        for bit in range(8):
            if data[0] & (0x01 << bit):
                x.append(True)
            else:
                x.append(False)
        return x
    elif datatype == "WORD":
        x = []
        for bit in range(8):
            if data[0] & (0x01 << bit):
                x.append(True)
            else:
                x.append(False)
        for bit in range(8):
            if data[1] & (0x01 << bit):
                x.append(True)
            else:
                x.append(False)
        return x
    # If we get here then the data type is a numeric type or a CHAR
    try:
        x = struct.unpack(table[datatype], str(data))[0]
        return x * multiplier
    except KeyError:
        # If we get a KeyError on the dict then it's a CHAR
        if "CHAR" in datatype:
            return str(data)
        return None
    except struct.error:
        return None
        
def setValue(datatype, value, multiplier=1):
    table = {"SHORT":"<b", "USHORT":"<B", "UINT":"<H",
             "INT":"<h", "DINT":"<l", "UDINT":"<L", "FLOAT":"<f"}
    
    if datatype == "BYTE":
        return None
    elif datatype == "WORD":
        return None
    try:
        x = struct.pack(table[datatype], value / multiplier)
        return [ord(y) for y in x] # Convert packed string into ints
    except KeyError:
        if "CHAR" in datatype:
            return [ord(value)]
        return None
        
def parseFrame(frame):
    """Determine what type of CAN-FIX frame this is and return an object
       that represents that frame type properly.  Returns None on error"""
    if frame.id ==0: # Undefined
        return None
    elif frame.id < 256:
        return NodeAlarm(frame)
    elif frame.id < 1760:
        return Parameter(frame)
    elif frame.id < 1792:
        return TwoWayMsg(frame)
    elif frame.id < 2048:
        return NodeSpecific(frame)
    else:
        return None

        
def __getText(element, text):
    try:
        return element.find(text).text
    except AttributeError:
        return None

def __getFloat(s):
    """Take string 's,' remove any commas and return a float"""
    if s:
        return float(s.replace(",",""))
    else:
        return None


class ParameterDef():
    """Defines an individual CANFIX parameter.  The database would
    essentially be a list of these objects"""
    def __init__(self, name):
        self.name = name
        self.units = None
        self.type = None
        self.multiplier = 1.0
        self.offset = None
        self.min = None
        self.max = None
        self.index = None
        self.format = None
        self.auxdata = {}
        self.remarks = []
    
    def __str__(self):
        s = "(0x%03X, %d) %s\n" % (self.id, self.id, self.name)
        if self.type:
            s = s + "  Data Type: %s\n" % self.type
        if self.units:
            if self.multiplier == 1.0:
                s = s + "  Units:     %s\n" % self.units
            else:
                s = s + "  Units:     %s x %s\n" % (self.units, str(self.multiplier))
        if self.offset:
            s = s + "  Offset:    %s\n" % str(self.offset)
        if self.min:
            s = s + "  Min:       %s\n" % str(self.min)
        if self.max:
            s = s + "  Max:       %s\n" % str(self.max)
        if self.format:
            s = s + "  Format:    %s\n" % self.format
        
        if self.index:
            s = s + "  Index:     %s\n" % self.index
        if self.auxdata:
            s = s + "  Auxilliary Data:\n"
            for each in self.auxdata:
                s = s + "   0x%02X - %s\n" % (each, self.auxdata[each])
        if self.remarks:
            s = s + "  Remarks:\n"
            for each in self.remarks:
                s = s + "    " + each + "\n"
        return s
    
        
tree = ET.parse(os.path.dirname(__file__)+"/canfix.xml")
root = tree.getroot()            
if root.tag != "protocol":
    raise ValueError("Root Tag is not protocol'")

child = root.find("name")
if child.text != "CANFIX":
    raise ValueError("Not a CANFIX Protocol File")

child = root.find("version")
version = child.text

groups = []
parameters = {}

def __add_group(element):
    child = element.find("name")
    x = {}
    x['name'] = element.find("name").text
    x['startid'] = int(element.find("startid").text)
    x['endid'] = int(element.find("endid").text)
    groups.append(x)

def __add_parameter(element):
    pid = int(element.find("id").text)
    count = int(element.find("count").text)
    
    p = ParameterDef(element.find("name").text)
    p.units = __getText(element, "units")
    p.format = __getText(element, "format")
    p.type = __getText(element, "type")
    p.multiplier = __getFloat(__getText(element, "multiplier"))
    p.offset = __getFloat(__getText(element, "offset"))
    p.min = __getFloat(__getText(element, "min"))
    p.max = __getFloat(__getText(element, "max"))
    p.index = __getText(element, "index")
    
    l = element.findall('aux')
    for each in l:
        p.auxdata[int(each.attrib['id'])] = each.text
    l = element.findall('remarks')
    
    for each in l:
        p.remarks.append(each.text)

    if count > 1:
        for n in range(count):
            np = copy.copy(p)
            np.name = p.name + " #" + str(n+1)
            np.id = pid + n
            parameters[pid+n] = np
    else:
        p.id = pid
        parameters[pid] = p
    
for child in root:
    if child.tag == "group":
        __add_group(child)
    elif child.tag == "parameter":
        __add_parameter(child)

def getGroup(id):
    for each in groups:
        if id >= each['startid'] and id <= each['endid']:
            return each
            
#if __name__ == "__main__":
    #print "CANFIX Protocol Version " + version
    #print "Groups:"
    #for each in groups:
        #print "  %s %d-%d" % (each["name"], each["startid"], each["endid"])
    
    #print "Parameters:"
    #for each in parameters:
        #print parameters[each]