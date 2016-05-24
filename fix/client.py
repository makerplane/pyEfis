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

# This module is a FIX-Net client used primarily to get the flight data
# from FIX-Gateway.

import socket
import threading
import Queue


class SendThread(threading.Thread):
    def __init__(self, sock):
        super(SendThread, self).__init__()
        self.sock = sock
        self.queue = Queue.Queue()
        self.getout = False

    def run(self):
        self.running = True
        while True:
            data = self.queue.get()
            if data == 'exit': break
            self.sock.sendall(data)
        self.running = False

    def stop(self):
        self.queue.put('exit')
    


class ClientThread(threading.Thread):
    def __init__(self, host, port):
        super(ClientThread, self).__init__()
        self.host = host
        self.port = port
        self.getout = False
        self.timeout = 1.0

    def handle_request(self, data):
        print(data.decode())

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(self.timeout)

        try:
            s.connect((self.host, self.port))
        except Exception as e:
            print(e)

        self.sendthread = SendThread(s)
        self.sendthread.queue.put("@l\n")
        self.sendthread.start()

        while True:
            try:
                data = s.recv(1024)
                self.handle_request(data)
            except socket.timeout:
                if self.getout:
                    self.sendthread.stop()
                    break;
                print("Timeout")

            if not data:
                print("No Data, Bailing Out")
                self.sendthread.stop()
                break


    def stop(self):
        self.getout = True
