#  Copyright (c) 2026 Eric Blevins
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

from collections import defaultdict


class DisplayStateController:
    def __init__(self, screen):
        self.screen = screen

    def configure(self, layout, scheduler_module):
        self.screen.display_timer = None
        self.screen.display_states = 0
        self.screen.display_state_current = 0
        self.screen.display_state_inst = defaultdict(list)

        if layout.get("display_state", False):
            scheduler_module.initialize()
            self.screen.timer = scheduler_module.scheduler.getTimer(
                layout["display_state"]["interval"]
            )
            if not self.screen.timer:
                scheduler_module.scheduler.timers.append(
                    scheduler_module.IntervalTimer(layout["display_state"]["interval"])
                )
                scheduler_module.scheduler.timers[-1].start()
                self.screen.timer = scheduler_module.scheduler.getTimer(
                    layout["display_state"]["interval"]
                )
            self.screen.display_states = layout["display_state"]["states"]
            self.screen.display_state_current = 1

    def register_callback(self, layout):
        if layout.get("display_state", False):
            self.screen.timer.add_callback(self.screen.change_display_states)

    def change(self):
        if self.screen.display_states < 2:
            return

        for index in self.screen.display_state_inst[self.screen.display_state_current]:
            self.screen.instruments[index].setVisible(False)

        if self.screen.display_state_current == self.screen.display_states:
            self.screen.display_state_current = 1
        else:
            self.screen.display_state_current += 1

        for index in self.screen.display_state_inst[self.screen.display_state_current]:
            self.screen.instruments[index].setVisible(True)
