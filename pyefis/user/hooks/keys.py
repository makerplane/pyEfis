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

# TODO: This file should eventually be deleted in favor of the hmi.keys
#       functionality since that is more user configurable

try:
    from PyQt5.QtCore import *
except:
    from PyQt4.QtCore import *

import logging

import gui
import pyavtools.fix as fix
import hooks
from hmi import actions

log = logging.getLogger(__name__)


def keyPress(event):
    log.debug("KeyPress {} {}".format(event.key(),event.text()))

    if event.key() == Qt.Key_BracketRight:
        x = fix.db.get_item("BARO")
        x.value = x.value + 0.01

    #  Decrease Altimeter Setting
    elif event.key() == Qt.Key_BracketLeft:
        x = fix.db.get_item("BARO")
        x.value = x.value - 0.01


# def keyRelease(event):
#     if event.key() == Qt.Key_Q:
#         fix.db.set_value("BTN16", False)


gui.mainWindow.keyPress.connect(keyPress)
#gui.mainWindow.keyRelease.connect(keyRelease)
