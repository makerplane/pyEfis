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

import re


def apply_preferences(config, preferences):
    if 'preferences' in config:
        specific_pref = dict()
        if config['preferences'] in preferences['gauges']:
            specific_pref = preferences['gauges'][config['preferences']]

        preference_name = re.sub("[^A-Za-z]","",config['preferences'])
        for style in preferences['style']:
            if not preferences['style'][style]:
                continue
            if preference_name in preferences['styles']:
                if style in preferences['styles'][preference_name]:
                    pref = preferences['styles'][preference_name][style]
                    if pref is not None:
                        config['options'] = config.get('options',dict())|pref

        config['options'] = config.get('options',dict())|specific_pref

        if 'styles' in specific_pref:
            for style in preferences['style']:
                if not preferences['style'][style]:
                    continue
                pref = specific_pref['styles'].get(style,None)
                if pref is not None:
                    config['options'] = config.get('options',dict())|pref

    font_percent = None
    font_family = "DejaVu Sans Condensed"
    if 'options' in config:
        if 'font_percent' in config['options']:
            font_percent = config['options']['font_percent']
        if 'font_family' in config['options']:
            font_family = config['options']['font_family']

    return font_percent, font_family
