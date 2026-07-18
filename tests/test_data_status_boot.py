#  Copyright (c) 2026 Bill Mallard
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

"""The nav-data management screen must boot universally, independent of the
configurable ``main.defaultScreen`` (a panel/config push can overwrite that
value -- which is how boards stopped showing it on boot). Guards
``gui._ensure_data_status_boot``: it forces DataStatus as the boot screen and
points its Continue button at the configured default flight screen."""

import logging

from pyefis import gui


def setup_module(module):
    # gui.log is normally created inside gui.initialize(); the helper logs.
    gui.log = logging.getLogger("test_data_status_boot")


def _cfg(default):
    return {
        "main": {"defaultScreen": default},
        "screens": {
            "DataStatus": {
                "module": "pyefis.screens.screenbuilder",
                "instruments": [
                    {"type": "data_status",
                     "options": {"continue_screen": "PFD"}},
                ],
            },
            "PFD_AI_ONLY": {"module": "pyefis.screens.screenbuilder"},
        },
    }


def _continue(cfg):
    return cfg["screens"]["DataStatus"]["instruments"][0]["options"][
        "continue_screen"]


def test_forces_data_status_boot_and_continue_to_configured_default():
    cfg = _cfg("PFD_AI_ONLY")
    assert gui._ensure_data_status_boot(cfg, "PFD_AI_ONLY") == "DataStatus"
    # Continue now takes the pilot to their configured screen, not the fallback.
    assert _continue(cfg) == "PFD_AI_ONLY"


def test_default_already_data_status_leaves_continue_alone():
    cfg = _cfg("DataStatus")
    assert gui._ensure_data_status_boot(cfg, "DataStatus") == "DataStatus"
    assert _continue(cfg) == "PFD"


def test_missing_default_screen_still_boots_data_status():
    cfg = _cfg(0)  # defaultScreen unset -> initialize() passes 0
    assert gui._ensure_data_status_boot(cfg, 0) == "DataStatus"
