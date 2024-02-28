from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import subprocess
import time
import re
import os

class Weston(QGraphicsView):
    def __init__(self, parent=None, socket=None, ini=None, command=None, args=None):
        super(Weston, self).__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.weston = QProcess(self)
        westenv = QProcessEnvironment.systemEnvironment()
            
        self.weston.setProcessEnvironment(westenv)
        self.weston.start('weston', [f"-c{ini}",'-Bx11-backend.so',f"-S{socket}"])
        time.sleep(1)
        p = subprocess.run(['xprop', '-root'], stdout=subprocess.PIPE)
        for line in p.stdout.decode().splitlines():
            m = re.fullmatch(r'^_NET_ACTIVE_WINDOW.*[)].*window id # (0x[0-9a-f]+)', line)
            if m:
                win = QWindow.fromWinId(int(m.group(1), 16))
                win.setFlag(Qt.FramelessWindowHint, True)
                wid = QWidget.createWindowContainer(win, self, Qt.FramelessWindowHint)
                self.layout().addWidget(wid)
                break

    def closeEvent(self, event):
        self.weston.terminate()
        self.weston.waitForFinished(4000)

        super(QGraphicsView, self).closeEvent(event)

