#!/usr/bin/python3
#!/usr/bin/env python3

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

import sys, os

import logging
import logging.config
import argparse
# try:
#     import ConfigParser
# except:
#     import configparser as ConfigParser
try:
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    PYQT = 5
except:
    from PyQt4.QtGui import *
    PYQT = 4
import yaml

if "pyAvTools" not in ''.join(sys.path):
    neighbor_tools = os.path.join ('..', 'pyAvTools')
    if os.path.isdir (neighbor_tools):
        sys.path.append (neighbor_tools)
    elif 'TOOLS_PATH' in os.environ:
        sys.path.append (os.environ['TOOLS_PATH'])

try:
    import fix
except:
    print ("You need to have pyAvTools installed, or in an adjacent directory to pyEfis.")
    print ("Or set the environment variable 'TOOLS_PATH' to point to the location of pyAvTools.")
    sys.exit(-1)

import fix
import hooks
import hmi
import gui
import importlib


if __name__ == "__main__":
    app = QApplication(sys.argv)
    parser = argparse.ArgumentParser(description='pyEfis')
    parser.add_argument('-m', '--mode', choices=['test', 'normal'],
        default='normal', help='Run pyEFIS in specific mode')
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Run in verbose mode')
    parser.add_argument('--config-file', type=argparse.FileType('r'),
                        help='Alternate configuration file')
    parser.add_argument('--log-config', type=argparse.FileType('r'),
                        help='Alternate logger configuration file')

    args = parser.parse_args()

    config_file = args.config_file if args.config_file else 'config/main.yaml'
    log_config_file = args.log_config if args.log_config else config_file

    # if we passed in a configuration file on the command line...
    if args.config_file:
        cf = args.config_file
    else: # otherwise use the default
        cf = open(config_file)
    config = yaml.load(cf)

    # Either load the config file given as a command line argument or
    # look in the configuration for the logging object
    if args.log_config:
        logging.config.fileConfig(args.log_config)
    elif 'logging' in config:
        logging.config.dictConfig(config['logging'])
    else:
        logging.basicConfig()

    log = logging.getLogger()
    if args.verbose:
        log.setLevel(logging.INFO)
    if args.debug:
        log.setLevel(logging.DEBUG)
    log.info("Starting pyEFIS")

    log.debug("PyQT Version = %d" % PYQT)

    fix.initialize(config)
    hmi.initialize(config)

    if 'FMS' in config:
        sys.path.insert(0, config["FMS"]["module_dir"])
        fms = importlib.import_module ("FixIntf")
        fms.start(config["FMS"]["aircraft_config"])

    gui.initialize(config)
    hmi.keys.initialize(gui.mainWindow, config["keybindings"])
    #hmi.data.initialize(config["databindings"])
    hooks.initialize(config['hooks'])

    # Main program loop
    result = app.exec_()

    # Clean up and get out
    fix.stop()
    if 'FMS' in config:
        fms.stop()
    log.info("PyEFIS Exiting Normally")
    sys.exit(result)
