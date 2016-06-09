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

# This is a really low brow scheduler.

try:
    from PyQt5.QtCore import *
except:
    from PyQt4.QtCore import *

import logging

class IntervalTimer(object):
    def __init__(self, interval):
        self.timer = QTimer()
        self.timer.setInterval(interval)
        self.callbacks = []
        self.timer.timeout.connect(self.fire_timer)

    def fire_timer(self):
        for func in self.callbacks:
            func()

    def add_callback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def start(self):
        self.timer.start()

# There are a fixed number of interval timers that are created.  This is
# probably not optimal but it may be easier to add intervals as needed than
# to deal with all the multithreading issues with these timers.
class ScheduleThread(QThread):
    def __init__(self):
        super(ScheduleThread, self).__init__()
        self.timers = []

    def run(self):
        self.timers.append(IntervalTimer(100))
        self.timers.append(IntervalTimer(500))
        self.timers.append(IntervalTimer(1000))

        for each in self.timers:
            each.start()

        self.exec_()

    def stop(self):
        pass

    def getTimer(self, interval):
        for each in self.timers:
            if each.timer.interval() == interval:
                return each

    # TODO: To create more interval timers we'd have to do it from
    # within this thread.  It would mean a job queue some locks and
    # all manner of complexity that may not be necessary.

def initialize():
    global scheduler
    global log
    log = logging.getLogger(__name__)
    log.info("Initializing Scheduler")
    scheduler = ScheduleThread()
    scheduler.start()
