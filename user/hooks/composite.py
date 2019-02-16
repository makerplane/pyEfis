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

# This is a file that shows how to composite data points for doing
# averages, sums, highs, lows etc.

# TODO This is not the cleanest mechanism.  It needs some love and thought

import fix

class CompositeFloatItem(object):
    def __init__(self, key, itemkeys):
        self.key = key # This is our key name
        self.items = []
        self.item = fix.db.get_item(key)
        self.item.type = 'float'

        for key in itemkeys:
            item = fix.db.get_item(key)
            self.items.append(item)
            item.valueChanged[float].connect(self.calcValue)
            #valueWrite = pyqtSignal([float],[int],[bool],[str])
            item.annunciateChanged.connect(self.annunciateFlag)
            item.oldChanged.connect(self.oldFlag)
            item.badChanged.connect(self.badFlag)
            item.failChanged.connect(self.failFlag)

        self.items[0].auxChanged.connect(self.setup)


    def getAuxData(self):
        for each in self.items[0].aux:
            self.item.aux[each] = self.items[0].aux[each]


    def setup(self):
        self.item.min = self.items[0].min
        self.item.max = self.items[0].max
        self.item.units = self.items[0].units
        self.item.tol = self.items[0].tol
        self.item.description = self.items[0].description

        self.getAuxData()

        self.annunciateFlag(False)
        self.badFlag(False)
        self.failFlag(False)
        self.oldFlag(False)
        self.calcValue(0.0)

        self.item.reportReceived.emit()

    # These deal with the quality flags.  We pretty much just ignore
    # the flag that was sent and check all the items.
    def annunciateFlag(self, flag):
        a = False
        for each in self.items:
            if each.annunciate:
                a = True
                break
        self.item.annunciate = a

    def badFlag(self, flag):
        a = False
        for each in self.items:
            if each.bad:
                a = True
                break
        self.item.bad = a

    def failFlag(self, flag):
        a = False
        for each in self.items:
            if each.fail:
                a = True
                break
        self.item.fail = a

    def oldFlag(self, flag):
        a = False
        for each in self.items:
            if each.old:
                a = True
                break
        self.item.old = a


    # This function should be reimplemented in the child class
    def calcValue(self, value):
        raise NotImplemented



class CompositeSumItem(CompositeFloatItem):
    def __init__(self, key, itemkeys):
        super(CompositeSumItem, self).__init__(key, itemkeys)

    def getAuxData(self):  #The Auxiliary data might not make sense for sum
        pass

    # We redefine the annunciate because we'll handle it ourselves
    def annunciateFlag(self, flag):
        pass


    def calcValue(self, value):
        total = 0.0
        for each in self.items:
            total += each.value
        self.item.value = total
        if self.item.value < self.item.aux["lowAlarm"] or self.item.value > self.item.aux["highAlarm"]:
            self.item.annunciate = True
        else:
            self.item.annunciate = False


class CompositeAvgItem(CompositeFloatItem):
    def __init__(self, key, itemkeys):
        super(CompositeAvgItem, self).__init__(key, itemkeys)

    def calcValue(self, value):
        total = 0.0
        for each in self.items:
            total += each.value
        self.item.value = total / len(self.items)


class CompositeMaxItem(CompositeFloatItem):
    def __init__(self, key, itemkeys):
        super(CompositeMaxItem, self).__init__(key, itemkeys)

    def calcValue(self, value):
        self.item.value = max(item.value for item in self.items)



fuel_total = CompositeSumItem("FUELQT", ["FUELQ1", "FUELQ2"])
# TODO Should have a way to do this automatically if needed
fuel_total.item.min = 0.0
fuel_total.item.max = 42.0
fuel_total.item.aux["Max"] = 42.0
fuel_total.item.aux["Min"] = 0.0
fuel_total.item.aux["lowWarn"] = 5.0
fuel_total.item.aux["lowAlarm"] = 2.0
fuel_total.item.aux["highAlarm"] = 42.0
fuel_total.setup() # Force an update

cht_max = CompositeMaxItem("CHTMAX1", ["CHT11", "CHT12", "CHT13", "CHT14"])
cht_max.setup()

egt_avg = CompositeAvgItem("EGTAVG1", ["EGT11", "EGT12", "EGT13", "EGT14"])
egt_avg.setup()
