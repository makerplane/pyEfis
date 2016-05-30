#!/usr/bin/env python

#  Copyright (c) 2013 Phil Birkelbach
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

import sys
# TODO: Should remove and install AeroCalc Properly
sys.path.insert(0, './lib/AeroCalc-0.11/')

import logging
import logging.config
import argparse
import ConfigParser  # configparser for Python 3
try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import importlib

import fix
import hooks

_screens = []

class Screen(object):
    def __init__(self, name, module, config):
        # strings here remove the options from the list before it is
        # sent to the plugin.
        print("Screen class __init__({0},{1},{2})".format(name, module, config))
        exclude_options = ["module"]
        self.module = importlib.import_module(module)
        # Here items winds up being a list of tuples [('key', 'value'),...]
        items = [item for item in config.items("Screen." + name)
                 if item[0] not in exclude_options]
        # Append the command line arguments to the items list as a tuple
        items.append(('argv', sys.argv))
        # Convert this to a dictionary before passing to the plugin
        self.config = {}
        for each in items:
            self.config[each[0]] = each[1]

        # This would hold the instantiated Screen object from the module.
        self.object = None
        self.default = False

class Main(QMainWindow):
    keyPress = pyqtSignal()

    def __init__(self, test, parent=None):
        super(Main, self).__init__(parent)

        self.width = int(config.get("mainscreen", "screenSize.Width"))
        self.height = int(config.get("mainscreen", "screenSize.Height"))
        self.screenColor = config.get("mainscreen", "screenColor")

        self.setObjectName("PFD")
        self.resize(self.width, self.height)
        w = QWidget(self)
        w.setGeometry(0, 0, self.width, self.height)

        p = w.palette()
        if self.screenColor:
             p.setColor(w.backgroundRole(), QColor(self.screenColor))
             w.setPalette(p)
             w.setAutoFillBackground(True)

        for scr in _screens:
            scr.object = scr.module.Screen(self)
            # TODO Figure out how to have different size screens
            scr.object.resize(self.width, self.height)
            scr.object.move(0,0)
            if scr.default:
                scr.object.show()


    def closeEvent(self, event):
        pass

    def keyReleaseEvent(self, event):
        #  Increase Altimeter Setting
        hooks.signals.keyPressEmit(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    parser = argparse.ArgumentParser(description='pyEfis')
    parser.add_argument('-m', '--mode', choices=['test', 'normal'],
        default='normal', help='Run pyEFIS in specific mode')
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    parser.add_argument('--config-file',
                        help='Alternate configuration file')
    parser.add_argument('--log-config',
                        help='Alternate logger configuration file')

    args = parser.parse_args()

    config_file = args.config_file if args.config_file else 'config/main.cfg'
    log_config_file = args.log_config if args.log_config else config_file
    config = ConfigParser.RawConfigParser()

    config.read(config_file)

    # Initialize Logger
    logging.config.fileConfig(log_config_file)
    log = logging.getLogger()

    # Quick way to set the logger to debug using command line argument
    if args.debug:
        log.setLevel(logging.DEBUG)
        log.info("Starting PyEFIS in %s Mode" % (args.mode,))

    # Load the Screens
    for each in config.sections():
        if each[:7] == "Screen.":
            module = config.get(each, "module")
            try:
                name = each[7:]
                _screens.append( Screen(name, module, config) )
                #load_screen(each[7:], module, config)
            except Exception as e:
                logging.critical("Unable to load module - " + module + ": " + str(e))
                raise
    # TODO Use configuration instead of defaulting to first
    _screens[0].default = True


    host = config.get("main", "FixServer")
    port = int(config.get("main", "FixPort"))

    fix.initialize(host, port)
    hooks.initialize()

    mainWindow = Main(args.mode)
    mainWindow.show()

    # Main program loop
    result = app.exec_()

    # Clean up and get out
    fix.stop()
    log.info("PyEFIS Exiting Normally")
    sys.exit(result)
