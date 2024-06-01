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
        self.encoder_set_real_time = False 
        self.encoder_set_value = None # None until user has selected a value.
 
        self.encoder_num_mask = False # defines what digits can be set ie 000.0000
        self.encoder_num_mask_blank_character = " "
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
        self.encoder_num_blink_time_on  = 300
        self.encoder_num_blink_time_off = 100
        self.encoder_num_8khz_channels = False
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
                if self.encoder_num_blink:
                    #if self.encoder_num_require_confirm and self.encoder_num_confirmed: #len(self.encoder_num_digit_options) == 0:
                    if self.encoder_num_confirmed and self.encoder_num_require_confirm and self.encoder_num_digit == len(self.encoder_num_mask) - 1:
                        # Confirm selection
                        return self.encoder_num_mask_blank_character * len(self.encoder_num_mask)
                    # Blank the digit being selected now
                    if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                        return  str(self.encoder_num_string[:self.encoder_num_digit]) + self.encoder_num_mask_blank_character + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
                    else:
                        return  str(self.encoder_num_string[:self.encoder_num_digit]) + self.encoder_num_mask_blank_character
                else:
                    # Return normal value
                    return self.encoder_num_string
            elif self.encoder_selected:
                # Return normal value
                return '{0:.{1}f}'.format(float(self.encoder_set_value), self.decimal_places)
            else:
                # return properly formatted value
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
            # Timed out to final value selected
            self.selectColor = None
            if self.encoder_selected:
                if self.encoder_revert:
                    # Timed out making selection, set value back to what it was before
                    self.encoder_item.value = self.encoder_start_value
                else:
                    # Set to value user selected
                    self.encoder_item.value = self.encoder_set_value
                # output the value to fix gateway
                self.encoder_item.output_value()
                # Reset the states
                self.encoder_selected = False
                self.encoder_num_blink_timer.stop()
                self.encoder_num_blink = False
        # update the display
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
            # User will select individual digits
            # Setup that state
            self.encoder_num_string = self.encoder_num_mask
            self.encoder_num_blink_timer.start(self.encoder_num_blink_time_on)
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
            # Change the selected digit
            if data > 0:
                if self.encoder_num_digit_selected == len(self.encoder_num_digit_options) - 1:
                    self.encoder_num_digit_selected = 0
                else:
                    self.encoder_num_digit_selected = self.encoder_num_digit_selected + 1
            elif data < 0:
                if self.encoder_num_digit_selected == 0:
                    self.encoder_num_digit_selected = len(self.encoder_num_digit_options) - 1
                else:
                    self.encoder_num_digit_selected = self.encoder_num_digit_selected - 1
            # Update the display
            self.set_encoder_value()
            self.update()
            return True
        else:
            # Set the value
            if self.clipping:
                self.encoder_set_value = common.bounds(self.lowRange, self.highRange, self.encoder_set_value + (self.encoder_multiplier * data))
            else:
                self.encoder_set_value = self.encoder_set_value + (self.encoder_multiplier * data)
            self.update()
            if self.encoder_set_real_time:
                self.encoder_item.value = self.encoder_set_value
                # output the value to fix gateway
                self.encoder_item.output_value()
            return True

    def enc_clicked(self):
        if self.encoder_num_mask:
            # make the selection permenant
            if self.encoder_num_confirmed: 
                # Need to finalize the selection
                self.encoder_revert = False 
            else:
                clicked = False
                # Move to the next digit
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit_selected = 0
                    self.encoder_num_digit = self.encoder_num_digit + 1
                    self.set_encoder_value(clicked=False)
                    if self.encoder_num_confirmed and not self.encoder_num_require_confirm:
                        # Only one digit was possible and we do not need final confirm
                        # Done
                        self.update()
                        self.encoder_revert = False
        
                else:
                    if not self.encoder_num_require_confirm:
                        # User selected last digit
                        # We do not need final confirm
                        # Done
                        self.update()
                        self.encoder_revert = False
                    else:
                        # We do need final confirm
                        if self.encoder_num_confirmed:
                            # We have final confirm
                            # Done
                            self.update()
                            self.encoder_revert = False
                        else:
                            # The user is selecting the last digit
                            # Wee need final confirmation
                            self.set_encoder_value(clicked=True)
                            self.update()
                            self.encoder_revert = True
            if not self.encoder_revert:
                # Something above decided we have a final selection
                # Save the current value
                if self.clipping:
                    self.encoder_set_value = common.bounds(self.lowRange, self.highRange, float(self.encoder_num_string))
                else:
                    self.encoder_set_value = float(self.encoder_num_string)
            # Return control to the caller, or not
            return self.encoder_revert
        else:
            # Return control back to caller
            self.encoder_revert = False
            return False

    def freq_to_channel(self,frequency):
        # Converts a 8,33khz frequency to the standard 3 decimal channel number
        # If the frequency match a 25khz spacign frequency, add 0.005 to the frequency to get the channel number
        # All other numbers are rounded to the nearest multiple of 0.005
        # The last two digits are always one of:
        # 0.005, 0.010, 0.015, 0.030, 0.035, 0.040, 0.055, 0.060, 0.065, 0.080, 0.085, 0.090
        # NOTE:
        # Need to do more research but it seems like a few 25khz channels are still valid on 8,33khz radios.
        # In some docs I've read 121.5Mhz is one exception, 123,1Mhz alt for search and rescue, 
        # and in NATO member states 122.100Mhz is to remain 25khz spacing
        # VHF digital link (VDL) frequencies (136,725 MHz, 136,775 MHz, 136,825MHz, 136,875 MHz, 136,925 MHz and 136,975 MHz)
        # ACARS 131,525 MHz, 131,725 MHz and 131,825 MHz)
        # I am not sure if that list is complete and also not sure if the 8.33Khz channels that occupy
        # those 25khz frequencies are not allowed, I'd assume so but I need to read more.

        m = 0.005
        i = frequency // m
        mult1 = (i + 1) * m
        mult2 = i * m
        if abs(mult2 - frequency) <= abs(mult1 - frequency):
            final = mult2
        else:
            final = mult1
        if (int(final * 1000) % 25 ) == 0:
            final = m + final
        return float(final)


    def calculate_selections(self):
        count = 0
        # builds a dict that will contain all valid digit selections.
        # We build a string of each valid value to populate the dict
        # Perhaps someone has some mathmatical way to calculate this?
        # While this is brute force, it does not add any noticable slowdown
        # to the application.
        #print(f"self.encoder_multiplier:{self.encoder_multiplier} self.decimal_places:{self.decimal_places} count:{count} self.encoder_num_8khz_channels:{self.encoder_num_8khz_channels}")

        while self.lowRange + ( count * self.encoder_multiplier ) <= self.highRange:
            # build a string for the number
            #print(f"self.encoder_multiplier:{self.encoder_multiplier} self.decimal_places:{self.decimal_places} count:{count} self.encoder_num_8khz_channels:{self.encoder_num_8khz_channels}")
            if self.decimal_places > 0:
                if self.encoder_num_8khz_channels:
                    # 8,33 spacing uses channels, not the actual frequency on the tuning display.
                    # This is to distinguish 8.33 frequencies from 25khz frequencies.
                    string = "{num:0{t}.{d}f}".format(num=self.freq_to_channel(self.lowRange + (count * self.encoder_multiplier)), t=len(self.encoder_num_mask), d=self.decimal_places)
                    print(string)
                else:
                    string = "{num:0{t}.{d}f}".format(num=(self.lowRange + (count * self.encoder_multiplier)), t=len(self.encoder_num_mask), d=self.decimal_places)
            else:
                string = "{num:0{t}".format(num=(self.lowRange + (count * self.encoder_multiplier)), t=len(self.encoder_num_mask))
            current = self.encoder_num_selectors
            # loop over each digit of the mask
            for x in range(0, len((self.encoder_num_mask))):
                # The last digit is added to an list in the dict
                if x == len(self.encoder_num_mask) - 1:
                    if string[x] not in current:
                        current.append(string[x])
                        continue
                # If this digit is not saved, save it to the dict.
                if string[x] not in current:
                    if x == len(self.encoder_num_mask) - 2:
                        # The nested dict ends with a list
                        current[string[x]] = []
                    else:
                        # add nested dict
                        current[string[x]] = dict()
                current=current[string[x]]
            # Increment to the next number and repeat
            count = count + 1

    def allowed_digits(self):
        # Returns the digits the user can select from
        current = self.encoder_num_selectors
        # First digit is the key names
        if self.encoder_num_digit == 0:
            return list(current.keys())
        # Follow the nested dict until we get to the digit we want
        for x in range(0, self.encoder_num_digit ):
            current = current[self.encoder_num_string[x]]
        if isinstance(current,list):
            # The last set of digits are a list already
            return current
        else:
            # All other digits the valid selections are the key names
            return list(current.keys())
        
    def set_encoder_value(self,clicked=False):
        # This set the string that will be displayed on the screen
        # when a user is selecting an individual digit
        start_digit = self.encoder_num_digit
        digit_found = False
        allow = []
        while not digit_found and self.encoder_num_digit <= len(self.encoder_num_mask) - 1:
            allow = self.allowed_digits()
            print(allow)
            if len(allow) == 0:
                # No valid digit, so skip it and move to next digit
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit = self.encoder_num_digit + 1
                else:
                    break
                self.encoder_num_digit_selected = 0
                continue
                
            if len(allow) == 1:
                # Only one digit is valid so it is auto-selected and we move to the next digit
                self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[0]) + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
                if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
                    self.encoder_num_digit = self.encoder_num_digit + 1
                else:
                    break
                self.encoder_num_digit_selected = 0
                continue
            digit_found = True
        self.encoder_num_digit_options = allow
        if self.encoder_num_digit < len(self.encoder_num_mask) - 1:
            # not the last digit
            # create the string with selected digit
            self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[self.encoder_num_digit_selected]) + str(self.encoder_num_string[int(self.encoder_num_digit) + 1:])
        else:
            # the last digit
            # create the screen with the selected digit
            self.encoder_num_string = str(self.encoder_num_string[:self.encoder_num_digit]) + str(allow[self.encoder_num_digit_selected])
            if start_digit == self.encoder_num_digit:
                print(2)
                # Came here with the same digit to select
                print(f"self.encoder_num_digit:{self.encoder_num_digit} len(self.encoder_num_mask) - 1:{len(self.encoder_num_mask) - 1}")
                if clicked:
                    # If we got here from click, rather than encoder change, confirm the click
                    self.encoder_num_confirmed = True
            elif len(allow) == 1:
                print(1)
                # We selected some previous digit and now the last digit can only be one value
                if not self.encoder_num_require_confirm:
                    # We do not require final confirm so confirm the final value for the user
                    self.encoder_num_confirmed = True
        # Set the list of digits the user can select from            
        #self.encoder_num_digit_options = allow
        print(f"self.encoder_num_digit_options:{self.encoder_num_digit_options} self.encoder_num_confirmed:{self.encoder_num_confirmed} clicked:{clicked} self.encoder_num_digit:{self.encoder_num_digit} start_digit:{start_digit} self.encoder_num_mask:{self.encoder_num_mask}:{len(self.encoder_num_mask)}")
       
    def encoder_blink_event(self):
        # Called from the blink timer
        self.encoder_num_blink = not self.encoder_num_blink 
        if self.encoder_num_blink:
            self.encoder_num_blink_timer.start(self.encoder_num_blink_time_off)
        else:
            self.encoder_num_blink_timer.start(self.encoder_num_blink_time_on)
        # update the display
        self.update()
