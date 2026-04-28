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

import os
import yaml


def is_include(config):
    return 'include,' in config['type']


def include_name(config):
    return config['type'].split(',')[1]


def is_disabled(config, preferences):
    if 'disabled' not in config:
        return False

    disabled = config['disabled']
    if isinstance(disabled, bool):
        return disabled

    if isinstance(disabled, str):
        check_not = disabled.split(" ")
        enabled_preferences = preferences['enabled']
        if check_not[0].lower() == 'not':
            return enabled_preferences[check_not[1]]
        return not enabled_preferences[disabled]

    return False


def load_include_config(config_path, preferences, config):
    name = include_name(config)
    include_path = os.path.join(config_path, name)
    if os.path.exists(include_path):
        with open(include_path) as include_file:
            return yaml.load(include_file, Loader=yaml.SafeLoader)

    preference_include = preferences['includes'][name]
    if preference_include:
        with open(os.path.join(config_path, preference_include)) as include_file:
            return yaml.load(include_file, Loader=yaml.SafeLoader)

    raise Exception(f"Include file '{name}' not found")


def apply_replacements(instrument, replacements, parent=None):
    instrument_str = yaml.dump(instrument)
    this_replacements = replacements

    if parent and 'replace' in parent:
        for replacement in parent['replace']:
            this_replacements[f"{{{replacement}}}"] = str(parent['replace'][replacement])

    if 'replace' in instrument:
        for replacement in instrument['replace']:
            this_replacements[f"{{{replacement}}}"] = str(instrument['replace'][replacement])

    for replacement, value in this_replacements.items():
        instrument_str = instrument_str.replace(replacement, str(value))

    return yaml.load(instrument_str, Loader=yaml.SafeLoader), this_replacements


def apply_include_geometry(instrument, row_p, col_p, relative_x, relative_y, inst_rows, inst_cols):
    instrument['row'] = (instrument.get('row', 0) * row_p) + relative_x
    instrument['column'] = (instrument.get('column', 0) * col_p) + relative_y

    if 'span' in instrument:
        if 'rows' in instrument['span'] and instrument['span']['rows'] >= 0:
            instrument['span']['rows'] = instrument['span']['rows'] * row_p
        if 'columns' in instrument['span'] and instrument['span']['columns'] >= 0:
            instrument['span']['columns'] = instrument['span']['columns'] * col_p
    else:
        instrument['span'] = {
            'rows': inst_rows,
            'columns': inst_cols,
        }

    return instrument


class InstrumentExpander:
    def __init__(self, config_path, preferences, node_id, include_size_calculator):
        self.config_path = config_path
        self.preferences = preferences
        self.node_id = node_id
        self.include_size_calculator = include_size_calculator

    def calc_includes(self, include_config, parent_rows, parent_cols):
        iconfig = load_include_config(self.config_path, self.preferences, include_config)
        instruments = iconfig['instruments']
        inst_rows = 0
        inst_cols = 0

        for instrument in instruments:
            a_rows = parent_rows
            a_cols = parent_cols
            if 'span' in instrument:
                if 'rows' in instrument['span']:
                    a_rows = instrument['span']['rows']
                if 'columns' in instrument['span']:
                    a_cols = instrument['span']['columns']

                if a_rows + instrument.get('row', 0) > inst_rows:
                    inst_rows = a_rows + instrument.get('row', 0)
                if a_cols + instrument.get('column', 0) > inst_cols:
                    inst_cols = a_cols + instrument.get('column', 0)
            else:
                if is_include(instrument):
                    pp_rows = inst_rows
                    pp_cols = inst_cols
                    if inst_rows == 0:
                        pp_rows = parent_rows
                    if inst_cols == 0:
                        pp_cols = parent_cols
                    rows, cols = self.calc_includes(instrument, pp_rows, pp_cols)
                    if rows + instrument['row'] > inst_rows:
                        inst_rows = rows + instrument['row']
                    if cols + instrument['column'] > inst_cols:
                        inst_cols = cols + instrument['column']
                else:
                    inst_rows = parent_rows
                    inst_cols = parent_cols

        if inst_rows == 0:
            inst_rows = parent_rows
        if inst_cols == 0:
            inst_cols = parent_cols

        return [inst_rows, inst_cols]

    def expand(
        self,
        config,
        replacements=None,
        row_p=1,
        col_p=1,
        relative_x=0,
        relative_y=0,
        inst_rows=0,
        inst_cols=0,
        state=False,
    ):
        parent_state = state
        if not state:
            state = config.get('display_state', False)
            parent_state = state
        if not replacements:
            replacements = {'{id}': self.node_id}

        span_rows = 0
        span_cols = 0
        if is_include(config):
            if is_disabled(config, self.preferences):
                return []
            relative_x = config.get('row', 0)
            relative_y = config.get('column', 0)
            if 'span' in config:
                span_rows = config['span'].get('rows', 0)
                span_cols = config['span'].get('columns', 0)
            inst_rows, inst_cols = self.include_size_calculator(config, span_rows, span_cols)
            instruments = load_include_config(self.config_path, self.preferences, config)['instruments']
        else:
            instruments = [config]

        expanded = []
        for instrument in instruments:
            if is_disabled(instrument, self.preferences):
                continue

            instrument_state = state
            if not parent_state:
                instrument_state = instrument.get('display_state', False)
            elif instrument.get('display_state', False):
                instrument_state = instrument.get('display_state', False)

            instrument, this_replacements = apply_replacements(instrument, replacements, parent=config)

            include_row_p = row_p
            include_col_p = col_p
            if span_rows > 0 and inst_rows > 0:
                include_row_p = span_rows / inst_rows
            if span_cols > 0 and inst_cols > 0:
                include_col_p = span_cols / inst_cols

            instrument = apply_include_geometry(
                instrument,
                include_row_p,
                include_col_p,
                relative_x,
                relative_y,
                inst_rows,
                inst_cols,
            )

            if is_include(instrument):
                expanded.extend(
                    self.expand(
                        instrument,
                        this_replacements,
                        include_row_p,
                        include_col_p,
                        relative_x,
                        relative_y,
                        inst_rows,
                        inst_cols,
                        instrument_state,
                    )
                )
            else:
                expanded.append((instrument, this_replacements, instrument_state))

        return expanded
