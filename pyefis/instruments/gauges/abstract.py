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

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

import pyavtools.fix as fix
import pyefis.hmi as hmi
from pyefis import common

def drawCircle(p, x, y, r, start, end):
    rect = QRectF(x - r, y - r, r * 2, r * 2)
    p.drawArc(rect, qRound(start * 16), qRound(end * 16))

class AbstractGauge(QWidget):
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(AbstractGauge, self).__init__(parent)
        self.font_family = font_family
        self.font_ghost_mask = None #Value
        self.font_ghost_alpha = 50
        self.font_mask = None #Value
        self.units_font_mask = None #units
        self.units_font_ghost_mask = None #units
        self.name_font_mask = None #name
        self.name_font_ghost_mask = None #name 
        self.name = None
        self.highWarn = None
        self.highAlarm = None
        self.lowWarn = None
        self.lowAlarm = None
        self.highRange = 100.0
        self.lowRange = 0.0
        self._dbkey = None
        self.highlight_key = None
        self._highlightValue = 0.0
        self._value = 0.0
        self._rawValue = 0.0
        self.peakValue = 0.0
        self._units = ""
        self.fail = False
        self.bad = False
        self.old = False
        self.annunciate = False
        self.highlight = False
        self.peakMode = False
        self.__unitSwitching = False
        self.unitGroup = ""

        self.encoder_set_key = None
        self.encoder_multiplier = 1
        self.encoder_start_value = None
        self.encoder_revert = False
        self.encoder_item = None
        self.encoder_selected = False
       
        self.encoder_set_value = None # None until user has selected a value.
 
        self.encoder_num_mask = False # defines what digits can be set ie 000.0000
        self.encoder_num_digit = 0 # current digit the user is setting
        self.encoder_num_selectors = dict() # dict that defines calid selections, used with multipl option
        self.encoder_num_enforce_multiplier = False # When true, the user can only select from digits that are valid based on the multiplier
        self.encoder_num_excluded = [] # Array of values that are not allowed, for example the frequencies above and belo 121.500
        self.encoder_num_string = str
        self.encoder_num_digit_selected = 0
        self.encoder_num_digit_options = []
        self.encoder_num_blink = False
        self.encoder_num_blink_timer = QTimer()
        self.encoder_num_blink_timer.timeout.connect(self.encoder_blink_event)
        self.encoder_num_require_confirm = False
        self.encoder_num_confirmed = False
        # These properties can be modified by the parent
        self.clipping = False
        self.unitsOverride1 = None
        self.unitsOverride2 = None
        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.decimal_places = 1
        # All these colors can be modified by the parent
        #self.outline_color = Qt.darkGray
        # These are the colors that are used when the value's
        # quality is marked as good
        self.bg_good_color = Qt.black
        self.safe_good_color = Qt.green
        self.warn_good_color = Qt.yellow
        self.alarm_good_color = Qt.red
        self.text_good_color = Qt.white
        self.pen_good_color = Qt.white
        self.highlight_good_color = Qt.magenta

        # These colors are used for bad and fail
        self.bg_bad_color = Qt.black
        self.safe_bad_color = Qt.darkGray
        self.warn_bad_color = Qt.darkYellow
        self.alarm_bad_color = Qt.darkRed
        self.text_bad_color = Qt.gray
        self.pen_bad_color = Qt.gray
        self.highlight_bad_color = Qt.darkMagenta

        # Annunciate changes the text color
        self.text_annunciate_color = Qt.red

        # The following properties should not be changed by the user.
        # These are set real time based on changes in different states
        # like data quality, selected units or modes
        self.selectColor = None
        #self.safeColor = self.safeGoodColor
        self.unitsOverride = None
        self.conversionFunction = lambda x: x

    def interpolate(self, value, range_):
        h = float(range_)
        l = float(self.lowRange)
        m = float(self.highRange)
        if m != l:
            return ((value - l) / (m - l)) * h
        else:
            return 0

    def getValue(self):
        return self._value

    def setValue(self, value):
        self._rawValue = value
        if self.fail:
            self._value = 0.0
        else:
            cvalue = self.conversionFunction(value)
            if cvalue != self._value:
                if self.clipping:
                    self._value = common.bounds(self.lowRange, self.highRange, cvalue)
                else:
                    self._value = cvalue
                self.setColors()
                self.update()
        if self._value > self.peakValue:
            self.peakValue = self._value

    value = property(getValue, setValue)

    def getValueText(self):
        if self.fail:
            return 'xxx'
        else:
            if self.encoder_selected and self.encoder_num_mask:
                # TODO, do we need to format here for highlighting the digit?
                # Also, we need to change how we keep track of the encoder_set_key or maybe just when we send it or not
                if self.encoder_num_blink:
                    print(f"self.encoder_num_require_confirm:{self.encoder_num_require_confirm} self.encoder_num_digit_options:{self.encoder_num_digit_options}")
                    #if self.encoder_num_require_confirm and self.encoder_num_confirmed: #len(self.encoder_num_digit_options) == 0:
                    if self.encoder_num_require_confirm and self.encoder_num_digit == len(self.encoder_num_mask) - 1:
                        return " " * len(self.encoder_num_mask)
                    if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                        print(  str(self.encoder_num_string[:self.encoder_num_digit]) + "_" + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:]))
                        return  str(self.encoder_num_string[:self.encoder_num_digit]) + " " + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
                    else:
                        # Are we selecting the last digit or confirming?
                        print(  str(self.encoder_num_string[:self.encoder_num_digit]) + "_")
                        return  str(self.encoder_num_string[:self.encoder_num_digit]) + " "
                else:    
                    return self.encoder_num_string
            else: 
                return '{0:.{1}f}'.format(float(self.value), self.decimal_places)

    valueText = property(getValueText)

    def setHighlightValue(self,value):
        self._highlightValue = value
        self.update()

    def getDbkey(self):
        return self._dbkey

    def setDbkey(self, key):
        item = fix.db.get_item(key)
        item.auxChanged.connect(self.setAuxData)
        item.reportReceived.connect(self.setupGauge)
        item.annunciateChanged.connect(self.annunciateFlag)
        item.oldChanged.connect(self.oldFlag)
        item.badChanged.connect(self.badFlag)
        item.failChanged.connect(self.failFlag)

        self._dbkey = key
        if not self.encoder_set_key:
            self.encoder_set_key = key
        self.encoder_item = fix.db.get_item(self.encoder_set_key)

        self.setupGauge()

    dbkey = property(getDbkey, setDbkey)

    def getUnits(self):
        if self.unitsOverride:
            return self.unitsOverride
        else:
            return self._units

    def setUnits(self, value):
        self._units = value

    units = property(getUnits, setUnits)

    # This should get called when the gauge is created and then again
    # anytime a new report of the db item is recieved from the server
    def setupGauge(self):
        item = fix.db.get_item(self.dbkey)
        # min and max should always be set for FIX Gateway data.
        if item.min: self.lowRange = self.conversionFunction(item.min)
        if item.max: self.highRange = self.conversionFunction(item.max)
        self._units = item.units
        # set the flags
        self.fail = item.fail
        self.bad = item.bad
        self.old = item.old
        self.annunciate = item.annunciate
        self.setColors()
        # set the axuliiary data and the value
        self.setAuxData(item.aux)
        self.setValue(item.value)

        # TODO We have to redo the valueChanged signals because the
        # datatype may have changed
        try:
            item.valueChanged[float].disconnect(self.setValue)
        except:
            pass # One will probably fail all the time
        try:
            item.valueChanged[int].disconnect(self.setValue)
        except:
            pass # One will probably fail all the time

        if item.dtype == float:
            item.valueChanged[float].connect(self.setValue)
        elif item.dtype == int:
            item.valueChanged[int].connect(self.setValue)

        if self.highlight_key:
            highlightItem = fix.db.get_item(self.highlight_key)
            self.setHighlightValue(highlightItem.value)

            try:
                highlightItem.valueChanged[float].disconnect(self.setHighlightValue)
            except:
                pass # One will probably fail all the time
            try:
                highlightItem.valueChanged[int].disconnect(self.setHighlightValue)
            except:
                pass # One will probably fail all the time

            if highlightItem.dtype == float:
                highlightItem.valueChanged[float].connect(self.setHighlightValue)
            elif highlightItem.dtype == int:
                highlightItem.valueChanged[int].connect(self.setHighlightValue)

        if self.encoder_num_mask and self.encoder_num_enforce_multiplier:
            # Recalculate selections
            self.calculate_selections()
    def setAuxData(self, auxdata):
        if "Min" in auxdata and auxdata["Min"] != None:
            self.lowRange = self.conversionFunction(auxdata["Min"])
        if "Max" in auxdata and auxdata["Max"] != None:
            self.highRange = self.conversionFunction(auxdata["Max"])
        if "lowWarn" in auxdata and auxdata["lowWarn"] != None:
            self.lowWarn = self.conversionFunction(auxdata["lowWarn"])
        if "lowAlarm" in auxdata and auxdata["lowAlarm"] != None:
            self.lowAlarm = self.conversionFunction(auxdata["lowAlarm"])
        if "highWarn" in auxdata and auxdata["highWarn"] != None:
            self.highWarn = self.conversionFunction(auxdata["highWarn"])
        if "highAlarm" in auxdata and auxdata["highAlarm"] != None:
            self.highAlarm = self.conversionFunction(auxdata["highAlarm"])
        self.update()

    def setColors(self):
        if self.bad or self.fail or self.old:
            self.bgColor = QColor(self.bg_bad_color)
            self.safeColor = self.selectColor or QColor(self.safe_bad_color)
            self.warnColor = QColor(self.warn_bad_color)
            self.alarmColor = QColor(self.alarm_bad_color)
            self.textColor = self.selectColor or QColor(self.text_bad_color)
            self.penColor = QColor(self.pen_bad_color)
            self.highlightColor = QColor(self.highlight_bad_color)
        else:
            self.bgColor = self.selectColor or QColor(self.bg_good_color)
            self.safeColor = self.selectColor or QColor(self.safe_good_color)
            self.warnColor = QColor(self.warn_good_color)
            self.alarmColor = QColor(self.alarm_good_color)
            self.textColor = self.selectColor or QColor(self.text_good_color)
            self.penColor = QColor(self.pen_good_color)
            self.highlightColor = QColor(self.highlight_good_color)
        if self.annunciate and not self.fail:
            self.textColor = self.selectColor or QColor(self.text_annunciate_color)

        self.valueColor = self.textColor
        if self.lowWarn != None and self.value < self.lowWarn:
            self.valueColor = self.warnColor
        if self.highWarn != None and self.value > self.highWarn:
            self.valueColor = self.warnColor
        if self.lowAlarm != None and self.value < self.lowAlarm:
            self.valueColor = self.alarmColor
        if self.highAlarm != None and self.value > self.highAlarm:
            self.valueColor = self.alarmColor

        self.update()

    def annunciateFlag(self, flag):
        self.annunciate = flag
        self.setColors()

    def failFlag(self, flag):
        self.fail = flag
        if flag:
            self.setValue(0.0)
        else:
            self.setValue(fix.db.get_item(self.dbkey).value)
        self.setColors()

    def badFlag(self, flag):
        self.bad = flag
        self.setColors()

    def oldFlag(self, flag):
        self.old = flag
        self.setColors()

    def resetPeak(self):
        self.peakValue = self.value
        self.update()

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        self.update()

    def setUnits(self, args):
        x = args.split(':')
        command = x[1].lower()
        names = x[0].split(',')
        if self.dbkey in names or '*' in names or self.unitGroup in names:
            item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            self.setAuxData(item.aux) # Trigger conversion for aux data
            self.value = item.value # Trigger the conversion for value


    # This instrument is selectable
    def enc_selectable(self):
        return True


    # Highlight this instrument to show it is the current selection
    def enc_highlight(self,onoff):
        if onoff:
            self.selectColor = QColor('orange')
        else:
            self.selectColor = None
            if self.encoder_selected:
                # Set the value:
                if self.encoder_revert:
                    # Timed out making selection
                    self.encoder_item.value = self.encoder_start_value
                else:
                    self.encoder_item.value = self.encoder_set_value
                # output the value
                self.encoder_item.output_value()
                self.encoder_selected = False
                self.encoder_num_blink_timer.stop()
                self.encoder_num_blink = False
        self.setColors()
        self.update()

    def enc_select(self):
        # Called when the user selects to interact with this item

        self.encoder_item = fix.db.get_item(self.encoder_set_key)
        # Save current value so it can be reverted
        self.encoder_start_value = self.value #encoder_item.value
        self.encoder_revert = True
        self.encoder_selected = True
        if self.encoder_num_mask:
            print("Setting value to mask")
            self.encoder_num_string = self.encoder_num_mask
            #self.calculate_selections()
            #self.set_encoder_value()
            #self.update()
            self.encoder_num_blink_timer.start(300)
            self.encoder_num_digit_selected = 0
            self.encoder_num_digit = 0
            self.encoder_num_confirmed = False
            self.set_encoder_value()
            self.update()
        else:
            # Set the initial value to the current value
            self.encoder_set_value = self.encoder_start_value
        return True


    def enc_changed(self,data):
        if self.encoder_num_mask:
            if len(self.encoder_num_digit_options) == 0:
                # We can only get here if confirm is required and while waiting for
                # user to confirm they turned the encoder
                # Treat this like they want to exit not confirm
                return False
            # Here we need to deal with changing individual digits.
            if data == 0:
                # Nothing to do if data is zero
                return True
            if data > 0:
                if self.encoder_num_digit_selected == len(self.encoder_num_digit_options) - 1:
                    self.encoder_num_digit_selected = 0
                else:
                    self.encoder_num_digit_selected = self.encoder_num_digit_selected + 1
            elif data < 0:
                if self.encoder_num_digit_selected == 0:
                    self.encoder_num_digit_selected = len(self.encoder_num_digit_options) -1
                else:
                    self.encoder_num_digit_selected = self.encoder_num_digit_selected - 1
            self.set_encoder_value()
            self.update()
            return True
        else:
            if self.clipping:
                self.encoder_set_value = common.bounds(self.lowRange, self.highRange, self.encoder_set_value + (self.encoder_multiplier * data))
            else:
                self.encoder_set_value = self.encoder_set_value + (self.encoder_multiplier * data)
            # TODO I think we should only output data on final selection.
            #self.encoder_item.output_value()
            return True

    def enc_clicked(self):
        if self.encoder_num_mask:
            # Here we need to deal with what digit to change or to
            # make the selection permenant
            if self.encoder_num_confirmed: #self.encoder_num_digit == len(self.encoder_num_mask) - 1: #Not sure this is right
                print(f"Final selection is: {self.encoder_num_string}")
                # Need to finalize the selection
                self.encoder_revert = False 
                #return False
            else:
                #self.encoder_num_digit_selected = 0
                # TODO Do we need to chck the value before changing?
                #if self.encoder_num_digit == len(self.encoder_num_mask) - 1:
                #    if len(self.encoder_num_digit_options) == 0:
                #        # We just selected the last digit
                #        self.encoder_num_confirmed = True
                #else:
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit = self.encoder_num_digit + 1
                self.set_encoder_value(clicked=True)
                
                self.update()
                if self.encoder_num_confirmed: #len(self.encoder_num_digit_options) == 1:
                    self.encoder_revert = False
            if not self.encoder_revert:
                # Something above decided we have a final selection
                if self.clipping:
                    self.encoder_set_value = common.bounds(self.lowRange, self.highRange, float(self.encoder_num_string))
                else:
                    self.encoder_set_value = float(self.encoder_num_string)

            return self.encoder_revert
        else:
            # Return control back to caller
            self.encoder_revert = False
            return False


    def calculate_selections(self):
        # Needs recalculated whenever min/max change
        count = 0
        #total = len(self.encoder_numeric_mask)
        # TODO, set decimans based on mak
        # OR we need to not use amask and get from some other valuid
        #mask = self.encoder_numeric_mask.split('.')
        #if len(mask) == 2:
        #    decimals = len(mask[1])
        #else:
        #    decimals = 0
        while self.lowRange + ( count * self.encoder_multiplier ) <= self.highRange:
            if self.decimal_places > 0:
                string = "{num:0{t}.{d}f}".format(num=(self.lowRange + (count * self.encoder_multiplier)), t=len(self.encoder_num_mask), d=self.decimal_places)
            else:
                string = "{num:0{t}".format(num=(self.lowRange + (count * self.encoder_multiplier)), t=len(self.encoder_num_mask))
            current = self.encoder_num_selectors
            #print(current)
            for x in range(0, len((self.encoder_num_mask))):
                if x == len(self.encoder_num_mask) - 1:
                    if string[x] not in current:
                        current.append(string[x])
                        continue
                if string[x] not in current:
                    if x == len(self.encoder_num_mask) - 2:
                        current[string[x]] = []
                    else:
                        current[string[x]] = dict()
                current=current[string[x]]
            count = count + 1
        #self.encoder_num_selectors = current
        print("#########################################")
        print(self.encoder_multiplier)
        print(self.encoder_num_selectors)
        print("########################################")

    def allowed_digits(self):
        current = self.encoder_num_selectors
        print(f"current:{current}")
        if self.encoder_num_digit == 0:
            return list(current.keys())
        print(f"self.encoder_num_string: {self.encoder_num_string}, self.encoder_num_digit:{self.encoder_num_digit} self.encoder_num_digit_selected:{self.encoder_num_digit_selected}")
        for x in range(0, self.encoder_num_digit ):
            current = current[self.encoder_num_string[x]]
        if isinstance(current,list):
            return current
        else:
            return list(current.keys())
        
    def set_encoder_value(self,clicked=False):
        start_digit = self.encoder_num_digit
        digit_found = False
        allow = []
        while not digit_found and self.encoder_num_digit <= len(self.encoder_num_mask) - 1:
            allow = self.allowed_digits()
            print(f"Allowed digits: {allow} self.encoder_num_digit:{self.encoder_num_digit}")
            if len(allow) == 0:
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit = self.encoder_num_digit + 1
                else:
                    break
                self.encoder_num_digit_selected = 0
                continue
                
            if len(allow) == 1:
                self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[0]) + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit = self.encoder_num_digit + 1
                else:
                    break
                self.encoder_num_digit_selected = 0
                continue
            digit_found = True
        print(f"Current selection: {self.encoder_num_string} digit:{self.encoder_num_digit} digit_found:{digit_found}")
        #if clicked and not self.encoder_num_require_confirm:
        #    # We do no require final confirmation we are done
        #    self.encoder_num_digit_options = []
        #    print(f"Final selection is: {self.encoder_num_string}")
        #elif clicked and self.encoder_num_require_confirm:
        #    # We do require confirm and this is the click to confirm
        #    self.encoder_num_digit_options = []
        #    print(f"The Final selection is: {self.encoder_num_string} and was confirmed by the user")
        
        #else:
            # We are just setting the last digit
            # Set the next digit, the one the user is selecting now
        if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
            self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[self.encoder_num_digit_selected]) + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
        else:
            # the last digit
            print(f"self.encoder_num_digit:{self.encoder_num_digit} self.encoder_num_string:{self.encoder_num_string} self.encoder_num_digit_selected:{self.encoder_num_digit_selected} allow:{allow} start_digit:{start_digit} self.encoder_num_require_confirm:{self.encoder_num_require_confirm}")
            self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[self.encoder_num_digit_selected])
            if start_digit == self.encoder_num_digit:
                # Came here with the same digit to select
                if clicked:
                    self.encoder_num_confirmed = True
            elif len(allow) == 1:
                # We selected some previous digit and now the last digit can only be one value
                if not self.encoder_num_require_confirm:
                    self.encoder_num_confirmed = True
 
            
        self.encoder_num_digit_options = allow
       
    def encoder_blink_event(self):
        self.encoder_num_blink = not self.encoder_num_blink 
        if self.encoder_num_blink:
          self.encoder_num_blink_timer.start(100)
        self.update()
