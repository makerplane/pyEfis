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
import logging
import time

class SendThread(threading.Thread):
    def __init__(self, sock):
        super(SendThread, self).__init__()
        self.sock = sock
        self.queue = Queue.Queue()
        self.getout = False

    def run(self):
        self.running = True
        log.debug("SendThread - Starting")
        while True:
            data = self.queue.get()
            if data == 'exit': break
            try:
                self.sock.sendall(data)
            except Exception as e:
                log.debug("SendThread: {0}".format(e))
        self.running = False
        log.debug("SendThread - Stopping")

    def stop(self):
        self.queue.put('exit')



class ClientThread(threading.Thread):
    def __init__(self, host, port, db):
        super(ClientThread, self).__init__()
        global log
        log = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.db = db  # Main FIX database
        self.getout = False
        self.timeout = 1.0

    def handle_request(self, data):
        print("data: " + data.decode())

    def run(self):
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(self.timeout)

            try:
                s.connect((self.host, self.port))
            except Exception as e:
                log.debug("Failed to connect {0}".format(e))
            else:
                log.info("Connected to {0}:{1}".format(self.host, self.port))
                self.sendthread = SendThread(s)
                self.sendthread.queue.put("@l\n")
                self.sendthread.start()

                while True:
                    try:
                        data = s.recv(1024)
                    except socket.timeout:
                        if self.getout:
                            self.sendthread.stop()
                            self.sendthread.join()
                            break;
                        print("client.py - Timeout")
                    except Exception as e:
                        log.debug("Receive Failure {0}".format(e))
                    else:
                        if not data:
                            log.debug("No Data, Bailing Out")
                            self.sendthread.stop()
                            self.sendthread.join()
                            break
                        else:
                            self.handle_request(data)
            if self.getout:
                break
            else:
                # TODO: Replace with configuration time
                time.sleep(2)
                log.info("Attempting to Reconnect to {0}:{1}".format(self.host, self.port))

    def stop(self):
        self.getout = True
