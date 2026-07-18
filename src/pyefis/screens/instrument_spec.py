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
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Declarative instrument definitions -- the single source of truth for the
pyEfis instrument catalog.

One :class:`InstrumentSpec` record per instrument type is the contract that the
three "mirrors" derive from, so they can no longer drift apart:

  1. the screen-builder factory (constructs the widget, applies options),
  2. the editor schema exporter (:mod:`pyefis.editor.schema` -> ``schema.json``),
  3. the web configurator's instrument "twin" (renders the live preview).

An instrument has THREE distinct kinds of input; keeping them separate is the
whole point of this module (see ``docs/instrument_spec.md``):

  1. Config properties (:attr:`InstrumentSpec.properties`, list of :class:`Prop`)
     Layout / appearance / feature options the panel designer sets in the
     editor. Written into the screen YAML and applied to the widget.
     e.g. ``aircraft_symbol``, ``show_tas``, ``startAngle``, ``decimal_places``.

  2. FIX-database values (:attr:`InstrumentSpec.fix_values`, list of
     :class:`FixValue`)
     Runtime values the instrument reads from fix-gateway (the FIX item's
     ``min`` / ``max`` / ``aux``), NOT set in the panel editor.
     e.g. V-speeds (Vne...), gauge warn/alarm bands, range. Described here so a
     future FIX-database editor can drive them; the panel editor only reads
     them (as preview).

  3. Preview hints (:attr:`InstrumentSpec.preview`, dict)
     Representative sample data so the configurator twin can draw a realistic
     instrument with no live FIX connection. Never written to a device.

This module is intentionally **Qt-free** so the catalog can be validated and
the schema exported in CI without a display or the GL stack. The Qt-dependent
builder callable is bound onto the record in ``screenbuilder_factory.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Editor-facing field kinds; each maps to an input in the configurator's
# properties panel. ``fixkey`` is a free-text FIX-database key (rendered as a
# string input today, a key-picker once the FIX editor exists).
PROP_KINDS = frozenset({
    "string", "number", "integer", "boolean", "enum", "color", "fixkey",
})

# How a config property reaches the widget when a screen is built.
#   "attr"        -> setattr(widget, name, value)            (the common case)
#   "setter:<m>"  -> widget.<m>(value)                       (e.g. "setter:setDbkey")
#   "special"     -> handled explicitly in screenbuilder_options (unit switching,
#                    encoder ordering, nested svs config, ...)
APPLY_ATTR = "attr"

# Where a category-2 value lives on the FIX item.
FIX_SOURCES = frozenset({"aux", "min", "max"})

# How a bound FIX key's *value* maps onto a bindable property (control_bindings.md
# section 5). A "setting" (read-write, on the value channel) -- NOT a category-2
# reference value (read-only, on min/max/aux). See #64 for why they stay distinct.
BINDING_SEMANTICS = frozenset({"bool", "index_ladder", "enum", "scalar"})


@dataclass
class Binding:
    """Marks a :class:`Prop` as *live-bindable*: the setting can also be driven at
    runtime by a FIX key, not only set once in the editor. A control (button /
    knob) writes the key; the widget subscribes and derives the property.

    ``semantics`` says how the key value maps to the property:
      * ``bool``          -- 0/1 <-> a boolean setting (a map layer);
      * ``index_ladder``  -- an int index into a comma-list option (map range);
      * ``enum``          -- an int index into the Prop's ``enum`` (orientation);
      * ``scalar``        -- the float value directly.
    ``key_option`` is the option that names the FIX key (defaults to
    ``<prop>_key``). ``ladder_option`` (index_ladder only) names the comma-list
    option the index steps through.
    """

    semantics: str
    key_option: str = ""
    ladder_option: str = ""

    def __post_init__(self):
        if self.semantics not in BINDING_SEMANTICS:
            raise ValueError(
                f"Binding: unknown semantics {self.semantics!r} "
                f"(expected one of {sorted(BINDING_SEMANTICS)})")
        if self.semantics == "index_ladder" and not self.ladder_option:
            raise ValueError(
                "Binding: semantics 'index_ladder' requires ladder_option=")


@dataclass
class Prop:
    """One editor-configurable property (category 1).

    ``name`` is BOTH the YAML option key and the widget attribute it is applied
    to (for ``apply="attr"``), so a property name maps 1:1 to widget state.
    """

    name: str
    kind: str
    default: object = None
    label: str = ""
    enum: list | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    required: bool = False
    help: str = ""
    apply: str = APPLY_ATTR
    bindable: object = None   # a Binding when this setting is live-bindable

    def __post_init__(self):
        if self.kind not in PROP_KINDS:
            raise ValueError(
                f"Prop {self.name!r}: unknown kind {self.kind!r} "
                f"(expected one of {sorted(PROP_KINDS)})")
        if self.kind == "enum" and not self.enum:
            raise ValueError(
                f"Prop {self.name!r}: kind 'enum' requires a non-empty enum=[...]")
        if self.kind == "enum" and self.default is not None \
                and self.default not in self.enum:
            raise ValueError(
                f"Prop {self.name!r}: default {self.default!r} not in enum "
                f"{self.enum}")
        if not (self.apply == APPLY_ATTR
                or self.apply.startswith("setter:")
                or self.apply == "special"):
            raise ValueError(
                f"Prop {self.name!r}: bad apply {self.apply!r}")
        if self.bindable is not None:
            if not isinstance(self.bindable, Binding):
                raise ValueError(
                    f"Prop {self.name!r}: bindable must be a Binding")
            if not self.bindable.key_option:
                self.bindable.key_option = f"{self.name}_key"
            if self.bindable.semantics == "enum" and self.kind != "enum":
                raise ValueError(
                    f"Prop {self.name!r}: bindable semantics 'enum' needs kind "
                    f"'enum'")
        if not self.label:
            self.label = self.name.replace("_", " ").capitalize()


@dataclass
class FixValue:
    """One value the instrument reads from fix-gateway at runtime (category 2).

    Documented for the spec and the future FIX-database editor; the panel
    editor does not set these. ``dbkey`` names which FIX key carries the value
    (empty = the instrument's primary FIX key)."""

    name: str
    source: str = "aux"
    label: str = ""
    dbkey: str = ""
    units: str = ""
    help: str = ""

    def __post_init__(self):
        if self.source not in FIX_SOURCES:
            raise ValueError(
                f"FixValue {self.name!r}: bad source {self.source!r} "
                f"(expected one of {sorted(FIX_SOURCES)})")
        if not self.label:
            self.label = self.name


@dataclass
class InstrumentSpec:
    """The single source of truth for one instrument type.

    ``builder`` is the Qt factory callable; it is left ``None`` here and bound
    in ``screenbuilder_factory.py`` so this module stays Qt-free.
    """

    type: str
    label: str
    category: str
    builder: object = None
    dbkeys: list = field(default_factory=list)        # default FIX keys consumed
    properties: list = field(default_factory=list)    # category 1: list[Prop]
    fix_values: list = field(default_factory=list)    # category 2: list[FixValue]
    preview: dict = field(default_factory=dict)       # category 3: twin sample data
    keep_aspect: bool = False
    offscreen_renderable: bool = True
    svs_capable: bool = False
    # Can the widget be constructed standalone -- ``builder(None, {...})`` with
    # no live screen? False for widgets that dereference ``screen.parent`` (e.g.
    # for config_path), embed an external process, or whose GL surface hangs
    # under the offscreen platform. The registry gate skips building these (it
    # can still validate their metadata + schema); the running screen builder is
    # unaffected, since it always passes a real screen.
    builds_in_isolation: bool = True
    # Hidden from the configurator's instrument palette: a real, buildable type
    # that should not be offered for new placement -- either because it is
    # system-managed rather than user-placed (e.g. the data-management boot
    # screen) or because it has been deprecated in favour of a more capable type
    # (e.g. airspeed_box / heading_display, superseded by the Value Text widget).
    # It stays in the exported schema -- so the editor can still understand and
    # render a config that already uses it -- but is filtered out of the palette.
    hidden: bool = False

    def __post_init__(self):
        names = [p.name for p in self.properties]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(
                f"InstrumentSpec {self.type!r}: duplicate property names {dupes}")

    def prop(self, name):
        """Return the :class:`Prop` named *name*, or ``None``."""
        for p in self.properties:
            if p.name == name:
                return p
        return None

    def defaults(self):
        """``{name: default}`` for every property that declares a default."""
        return {p.name: p.default for p in self.properties
                if p.default is not None}
