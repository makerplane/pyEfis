from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import subprocess
import time
import re
import os

class Weston(QWidget):
    def __init__(self, parent=None, socket=None, ini=None, command=None, args=None):
        super(Weston, self).__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.weston = QProcess(self)
        westenv = QProcessEnvironment.systemEnvironment()
            
        self.weston.setProcessEnvironment(westenv)
        self.weston.start('weston', [f"-c{ini}",'-i0','-Bx11-backend.so',f"-S{socket}"])
        loop_count = 0
        loop_limit = 15
        while loop_count < loop_limit:
            loop_count += 1
            time.sleep(0.07)
            p = subprocess.run(['xwininfo', '-tree', '-root'], stdout=subprocess.PIPE)
            if p.returncode > 0:
                continue
            for line in p.stdout.decode().splitlines():
                m = re.fullmatch(r'^.*(0x[0-9a-f]+) \"Weston Compositor - .*', line)
                if m:
                    win = QWindow.fromWinId(int(m.group(1), 16))
                    win.setFlag(Qt.FramelessWindowHint, True)
                    wid = QWidget.createWindowContainer(win, self, Qt.FramelessWindowHint)
                    self.layout().addWidget(wid)
                    loop_count = loop_limit + 1
                    break

    def closeEvent(self, event):
        self.weston.terminate()
        self.weston.waitForFinished(4000)

        super(QGraphicsView, self).closeEvent(event)


