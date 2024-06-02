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
        self.started = False
        self.socket = socket
        self.weston_cfg = ini
        self.command = command
        self.args = args

        self.weston = QProcess(self)
        westenv = QProcessEnvironment.systemEnvironment()
        self.weston.setProcessEnvironment(westenv)


    def startWeston(self):
        self.started = True
        print(self.weston_cfg)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        #self.weston.start('weston', [f"-c{self.weston_cfg}",'-i0',f"--width={self.width()}","--height={self.height()}",'-Bx11-backend.so',f"-S{self.socket}"])
        self.weston.start('weston', [f"-c{self.weston_cfg}",'-i0','-Bx11-backend.so',f"-S{self.socket}"])
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
        # Without this a 1px white border will show up on the left and top
        # But you can remove this line if this is the first screen to be displayed.
        # the border only shows up when it is not set as the main screen
        # Maybe it is a calculation issue
        # I did confirm it is not the skip grid_layout code causing it.
        self.move(-1,-1)
    def resizeEvent(self, event):
        if not self.started:
            self.startWeston()

    def closeEvent(self, event):
        self.weston.terminate()
        self.weston.waitForFinished(4000)

        super(QGraphicsView, self).closeEvent(event)

