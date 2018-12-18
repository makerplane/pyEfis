#!/usr/bin/python
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

import sys
# TODO: Should remove and install AeroCalc Properly
sys.path.insert(0, './lib/AeroCalc-0.11/')

import logging
import logging.config
import argparse
try:
    import ConfigParser
except:
    import configparser as ConfigParser
try:
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    PYQT = 5
except:
    from PyQt4.QtGui import *
    PYQT = 4

import scheduler
import fix
import hooks
import gui
import importlib


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

    log.debug("PyQT Version = %d" % PYQT)
    scheduler.initialize()

    host = config.get("main", "FixServer")
    port = int(config.get("main", "FixPort"))

    fix.initialize(host, port)
    for each in config.items("Outputs"):
        try:
            fix.db.add_output(each[0].upper(), each[1])
        except ValueError as e:
            log.warning(e)

    if 'FMS' in config:
        sys.path.insert(0, config.get("FMS", "module_dir"))
        fms = importlib.import_module ("FixIntf")
        fms.start(config.get("FMS", "aircraft_config"))

    gui.initialize(config)
    hooks.initialize(config)

    # Main program loop
    result = app.exec_()

    # Clean up and get out
    fix.stop()
    if 'FMS' in config:
        fms.stop()
    log.info("PyEFIS Exiting Normally")
    sys.exit(result)
