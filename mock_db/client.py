from unittest import mock


class SendThread:
    def __init__(self, sock, queue):
        pass

    def run(self):
        pass

    def stop(self):
        pass

class ClientThread:
    def __init__(self, host, port, db):
        super(ClientThread, self).__init__()
        self.sendqueue = mock.MagicMock()
        self.db = db  # Main FIX database

    def handle_value(self, d):
        pass

    def handle_request(self, d):
        self.db.init_event.set()

    def run(self):
        pass

    def stop(self):
        pass

    def join(self):
        pass

    def start(Self):
        pass

