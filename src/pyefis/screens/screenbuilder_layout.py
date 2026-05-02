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


def get_grid_margins(layout, width, height):
    topm = 0
    leftm = 0
    rightm = 0
    bottomm = 0

    if "margin" in layout:
        if (
            "top" in layout["margin"]
            and layout["margin"]["top"] > 0
            and layout["margin"]["top"] < 100
        ):
            topm = height * (layout["margin"]["top"] / 100)
        if (
            "bottom" in layout["margin"]
            and layout["margin"]["bottom"] > 0
            and layout["margin"]["bottom"] < 100
        ):
            bottomm = height * (layout["margin"]["bottom"] / 100)
        if (
            "left" in layout["margin"]
            and layout["margin"]["left"] > 0
            and layout["margin"]["left"] < 100
        ):
            leftm = height * (layout["margin"]["left"] / 100)
        if (
            "right" in layout["margin"]
            and layout["margin"]["right"] > 0
            and layout["margin"]["right"] < 100
        ):
            rightm = height * (layout["margin"]["right"] / 100)

    return topm, leftm, rightm, bottomm


def get_grid_coordinates(layout, screen_width, screen_height, column, row):
    topm, leftm, rightm, bottomm = get_grid_margins(layout, screen_width, screen_height)
    grid_width = (screen_width - leftm - rightm) / int(layout["columns"])
    grid_height = (screen_height - topm - bottomm) / int(layout["rows"])
    grid_x = leftm + grid_width * column
    grid_y = topm + grid_height * row
    return grid_x, grid_y, grid_width, grid_height


def apply_span(config, grid_width, grid_height):
    if "span" not in config:
        return grid_width, grid_height

    if "rows" in config["span"] and config["span"]["rows"] >= 0:
        grid_height = grid_height * config["span"]["rows"]
    if "columns" in config["span"] and config["span"]["columns"] >= 0:
        grid_width = grid_width * config["span"]["columns"]

    return grid_width, grid_height


def get_bounding_box(width, height, x, y, ratio):
    if width < height:
        r_height = width / ratio
        r_width = width
        if height < r_height:
            r_height = height
            r_width = height * ratio
    else:
        r_width = height * ratio
        r_height = height
        if width < r_width:
            r_height = width / ratio
            r_width = width

    if r_height == height:
        r_y = y
        r_x = x + ((width - r_width) / 2)
    else:
        r_x = x
        r_y = y + ((height - r_height) / 2)

    return r_width, r_height, r_x, r_y


def get_instrument_geometry(layout, screen_width, screen_height, config, ratio=False):
    grid_x, grid_y, grid_width, grid_height = get_grid_coordinates(
        layout,
        screen_width,
        screen_height,
        config["column"],
        config["row"],
    )
    grid_width, grid_height = apply_span(config, grid_width, grid_height)

    width = r_width = grid_width
    height = r_height = grid_height
    x = grid_x
    y = grid_y

    if ratio:
        r_width, r_height, _r_x, _r_y = get_bounding_box(width, height, x, y, ratio)

    if "move" in config:
        if "shrink" in config["move"]:
            shrink = config["move"].get("shrink", 0)
            if shrink < 99 and shrink >= 0:
                r_width = r_width - (r_width * shrink / 100)
                r_height = r_height - (r_height * shrink / 100)
            else:
                raise Exception("shrink must be a valid number between 1 and 99")

            justified_horizontal = False
            justified_vertical = False
            if "justify" in config["move"]:
                for justification in config["move"]["justify"]:
                    if justification == "left":
                        x = grid_x
                        justified_horizontal = True
                    elif justification == "right":
                        x = grid_x + (grid_width - r_width)
                        justified_horizontal = True
                    if justification == "top":
                        y = grid_y
                        justified_vertical = True
                    elif justification == "bottom":
                        y = grid_y + (grid_height - r_height)
                        justified_vertical = True

            if not justified_horizontal:
                x = grid_x + ((grid_width - r_width) / 2)
            if not justified_vertical:
                y = grid_y + ((grid_height - r_height) / 2)
    elif ratio:
        x = grid_x + ((grid_width - r_width) / 2)
        y = grid_y + ((grid_height - r_height) / 2)

    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "render_width": r_width,
        "render_height": r_height,
    }


def get_ganged_geometries(config, x, y, width, height, ratio=False):
    inst_count = 0
    groups = 0
    for group in config["groups"]:
        inst_count += len(group["instruments"])
        groups += 1

    if "horizontal" in config["gang_type"]:
        total_gaps = (groups - 1) * (width * (2 / 100))
    else:
        total_gaps = (groups - 1) * (height * (6 / 100))

    gap_size = 0
    if groups > 1:
        gap_size = total_gaps / (groups - 1)

    group_x = x
    group_y = y
    if "horizontal" in config["gang_type"]:
        group_width = (width - total_gaps) / inst_count
        group_height = height
    else:
        group_height = (height - total_gaps) / inst_count
        group_width = width

    geometries = []
    for group in config["groups"]:
        if "horizontal" in config["gang_type"]:
            hgap = group.get("gap", 0) / 100 * group_width
            vgap = 0
        else:
            vgap = group.get("gap", 0) / 100 * group_height
            hgap = 0

        for _child in group["instruments"]:
            g_width = group_width - (hgap * (len(group["instruments"]) - 1))
            g_height = group_height - (vgap * (len(group["instruments"]) - 1))
            g_x = group_x
            g_y = group_y
            if ratio:
                g_width, g_height, g_x, g_y = get_bounding_box(
                    g_width, g_height, g_x, g_y, ratio
                )

            geometries.append((g_x, g_y, g_width, g_height))

            if "horizontal" in config["gang_type"]:
                group_x += group_width + hgap
            else:
                group_y += group_height + vgap

        if "horizontal" in config["gang_type"]:
            group_x += gap_size
        else:
            group_y += gap_size

    return geometries
