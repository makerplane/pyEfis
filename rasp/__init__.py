#from Adafruit_BMP085 import BMP085
import RPi.GPIO as GPIO, time, os
import xml.etree.ElementTree as ET
import threading

#bmp = BMP085(0x77, 2)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

class GPIO_Process(threading.Thread):

    def __init__(self, conn):
        threading.Thread.__init__(self)
        self.queue = conn

    def run(self):
        speed = 65
        pitch = 15
        roll = 30
        heading = 111
        alt = 1400
        co = 0
        volt = 12
        oat = 12
        data = [speed, pitch, roll, heading, alt, co, volt, oat]
        data_test = str(data).strip('[]')
        self.queue.put(data_test)
        

if __name__ == '__main__':
    import queue
    q = queue.Queue()
    t = GPIO_Process(q)
    t.start()

    f = 'pyefis_rasp.xml'
    tree = ET.parse(f)

    Name_List = []
    Name_Value = []

    for node in tree.findall('.//name'):
        Name_List.append(node.text)

    for node in tree.findall('.//node'):
        Name_Value.append(node.text)

    while True:
        try:
            data_test = q.get(0)
            for data in data_test:
                if len(Name_List) == len(Name_Value):
                    for l, a, d in zip(Name_List, Name_Value, data_test):
                        print((l, a, d))
                else:
                    print(('Name value mismatch in :', f))
        except queue.Empty:
            pass
    t.join()
