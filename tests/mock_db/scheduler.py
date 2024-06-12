class IntervalTimer:
    def __init__(self, interval):
        self.interval = interval
        self.callbacks = []

    def fire_timer(self):
        pass

    def add_callback(self, func):
        if func not in self.callbacks:
            self.callbacks.append(func)

    def start(self):
        pass

    def stop(self):
        pass

    def interval(self):
        return self.interval

class ScheduleThread:
    def __init__(self):
        self.timers = []

    def run(self):
        self.timers.append(IntervalTimer(100))
        self.timers.append(IntervalTimer(500))
        self.timers.append(IntervalTimer(1000))

    def stop(self):
        pass

    def getTimer(self, interval):
        for each in self.timers:
            if each.timer.interval() == interval:
                return each

    def start(self):
        pass

initialized=False
def initialize():
    global initialized
    scheduler = ScheduleThread()
    scheduler.start()
    initialized=True
    
