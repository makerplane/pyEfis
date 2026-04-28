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

import time
from operator import itemgetter


class EncoderController:
    def __init__(self, screen):
        self.screen = screen

    def configure_inputs(self, fix_module):
        if len(self.screen.encoder_list) == 0:
            return

        if self.screen.encoder and self.screen.encoder_button:
            self.screen.encoder_list_sorted = [
                inst["inst"]
                for inst in sorted(self.screen.encoder_list, key=itemgetter("order"))
            ]
            self.screen.encoder_current_selection = 0

            self.screen.encoder_input = fix_module.db.get_item(self.screen.encoder)
            self.screen.encoder_input.valueWrite[int].connect(
                self.screen.encoderChanged
            )

            self.screen.encoder_button_input = fix_module.db.get_item(
                self.screen.encoder_button
            )
            self.screen.encoder_button_input.valueChanged[bool].connect(
                self.screen.encoderButtonChanged
            )

            self.screen.encoder_timer.timeout.connect(self.screen.encoderChanged)

    def changed(self, value=0):
        curr_time = time.time_ns() // 1000000
        if value == 0:
            if curr_time - self.screen.encoder_timeout >= self.screen.encoder_timestamp:
                self._selected_instrument().enc_highlight(False)
                self.screen.encoder_control = False
                self.screen.encoder_timer.stop()
                self.screen.encoder_timestamp = 0
            return

        if not self.screen.isVisible():
            return

        if self.screen.encoder_control:
            self.screen.encoder_control = self._selected_instrument().enc_changed(value)
            if self.screen.encoder_control:
                self.screen.encoder_timestamp = curr_time
                self.screen.encoder_timer.start(self.screen.encoder_timeout + 500)
            else:
                self.screen.encoder_timer.stop()
                self.screen.encoder_timestamp = 0
                self._selected_instrument().enc_highlight(False)
            return

        val = self.screen.encoder_current_selection
        if not (
            curr_time - self.screen.encoder_timeout >= self.screen.encoder_timestamp
        ):
            val = self.screen.encoder_current_selection + value

        val = self._wrap_selection(val)

        loop = 0
        if not self.screen.instruments[
            self.screen.encoder_list_sorted[val]
        ].isEnabled():
            while (
                not self.screen.instruments[
                    self.screen.encoder_list_sorted[val]
                ].isEnabled()
                and loop < 2
            ):
                adder = -1
                if value > 0:
                    adder = 1

                val = val + adder

                if val < 0:
                    val = len(self.screen.encoder_list_sorted) - 1
                    loop += 1
                elif val == len(self.screen.encoder_list_sorted):
                    val = 0
                    loop += 1

        self._selected_instrument().enc_highlight(False)
        self.screen.encoder_control = False
        self.screen.encoder_current_selection = val
        if loop < 2:
            self._selected_instrument().enc_highlight(True)
            self.screen.encoder_timestamp = curr_time
            self.screen.encoder_timer.start(self.screen.encoder_timeout + 500)

    def button_changed(self, value):
        if not self.screen.isVisible():
            return

        if value and not (
            (time.time_ns() // 1000000) - self.screen.encoder_timeout
            >= self.screen.encoder_timestamp
        ):
            if self.screen.encoder_control:
                self.screen.encoder_control = self._selected_instrument().enc_clicked()
                if self.screen.encoder_control:
                    self.screen.encoder_timestamp = time.time_ns() // 1000000
                    self.screen.encoder_timer.start(self.screen.encoder_timeout + 500)
                else:
                    self.screen.encoder_timer.stop()
                    self.screen.encoder_timestamp = 0
                    self._selected_instrument().enc_highlight(False)
            else:
                self.screen.encoder_control = self._selected_instrument().enc_select()
                if self.screen.encoder_control:
                    self.screen.encoder_timestamp = time.time_ns() // 1000000
                    self.screen.encoder_timer.start(self.screen.encoder_timeout + 500)
                else:
                    self.screen.encoder_timer.stop()
                    self.screen.encoder_timestamp = 0
                    self._selected_instrument().enc_highlight(False)

    def _selected_instrument(self):
        return self.screen.instruments[
            self.screen.encoder_list_sorted[self.screen.encoder_current_selection]
        ]

    def _wrap_selection(self, val):
        if val < 0:
            while val < 0:
                val = len(self.screen.encoder_list_sorted) + val
        elif val > len(self.screen.encoder_list_sorted) - 1:
            while val > len(self.screen.encoder_list_sorted) - 1:
                val = val - len(self.screen.encoder_list_sorted)
        return val
