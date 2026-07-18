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

"""The instrument-registry test gate -- makes drift between the three mirrors
impossible to merge.

The catalog's single source of truth is ``screenbuilder_factory.REGISTRY``
(``InstrumentSpec`` records). These tests assert:

  * every registered instrument is a real, buildable factory type;
  * a migrated instrument is removed from the legacy curated metadata in
    ``editor/schema.py`` (no double definition -> no drift);
  * the exported schema for a migrated type comes verbatim from its record;
  * the widget actually exposes every ``apply="attr"`` property the record
    declares -- so a renamed/typo'd property fails CI instead of silently
    doing nothing on the panel.

See docs/instrument_spec.md and docs/adding_an_instrument.md.
"""

import pytest

from PyQt6.QtGui import QColor

from pyefis.editor import schema as eschema
from pyefis.screens import instrument_spec as ispec
from pyefis.screens import screenbuilder_factory as factory


# Curated lookup tables in editor/schema.py that a migrated instrument must
# NOT also appear in (mapping name -> the container).
_CURATED = {
    "_CATEGORIES": eschema._CATEGORIES,
    "_LABELS": eschema._LABELS,
    "_REQUIRED_OPTIONS": eschema._REQUIRED_OPTIONS,
    "_OPTIONS": eschema._OPTIONS,
    "_NOT_OFFSCREEN_RENDERABLE": eschema._NOT_OFFSCREEN_RENDERABLE,
    "_SVS_CAPABLE": eschema._SVS_CAPABLE,
    "_KEEP_ASPECT": eschema._KEEP_ASPECT,
}


def _ctor_options(spec):
    """Minimal options a widget needs to construct -- its required props seeded
    with their declared defaults (e.g. static_text needs `text`)."""
    return {p.name: p.default for p in spec.properties
            if p.required and p.default is not None}


@pytest.fixture
def hmi_actions(qtbot):
    """Some widgets (e.g. Airspeed_Box) connect to the global hmi.actions signal
    hub in their constructor. Initialise it the way pyEfis does at startup (via
    hmi.initialize) so those widgets can be built in isolation."""
    from pyefis import hmi
    from pyefis.hmi import actionclass
    if hmi.actions is None:
        hmi.actions = actionclass.ActionClass()
        qtbot.addWidget(hmi.actions)
    return hmi.actions


def test_registry_types_are_real_factory_types():
    """A record can only describe an instrument the screen builder can build."""
    unknown = set(factory.REGISTRY) - set(factory.INSTRUMENT_FACTORIES)
    assert not unknown, f"REGISTRY has non-factory types: {unknown}"
    for t, spec in factory.REGISTRY.items():
        assert spec.type == t, f"REGISTRY key {t!r} != spec.type {spec.type!r}"
        assert callable(spec.builder), f"{t}: spec.builder is not callable"
        assert factory.INSTRUMENT_FACTORIES[t] is spec.builder, (
            f"{t}: INSTRUMENT_FACTORIES is not sourced from the registry")


def test_migrated_types_are_not_double_defined_in_curation():
    """Once an instrument is in the registry it owns the metadata; the curated
    fallback in editor/schema.py must not also define it."""
    for t in factory.REGISTRY:
        for name, container in _CURATED.items():
            assert t not in container, (
                f"{t} is migrated to REGISTRY but still in eschema.{name}; "
                f"remove it from the curated metadata")


def test_schema_entry_matches_record():
    """The exported schema for a migrated type is its record, verbatim."""
    s = eschema.build_schema()
    for t, spec in factory.REGISTRY.items():
        entry = s["instruments"][t]
        assert entry["label"] == spec.label
        assert entry["category"] == spec.category
        assert entry["dbkeys"] == list(spec.dbkeys)
        assert entry["keep_aspect"] == spec.keep_aspect
        assert entry["svs_capable"] == spec.svs_capable
        assert entry["offscreen_renderable"] == spec.offscreen_renderable
        assert entry["hidden"] == spec.hidden
        assert entry["preview"] == spec.preview
        # Options are exactly the declared properties, in order.
        assert list(entry["options"]) == [p.name for p in spec.properties]
        for p in spec.properties:
            field = entry["options"][p.name]
            assert "type" in field
            if p.kind == "enum":
                assert field["enum"] == list(p.enum)
                assert field["default"] in field["enum"]
        # Required options mirror the record.
        assert entry["required_options"] == [
            p.name for p in spec.properties if p.required]


def test_records_are_well_formed():
    """Every property kind is known and enum defaults are valid (the dataclass
    enforces this at construction; assert it stays true through export)."""
    for t, spec in factory.REGISTRY.items():
        names = [p.name for p in spec.properties]
        assert len(names) == len(set(names)), f"{t}: duplicate property names"
        for p in spec.properties:
            assert p.kind in ispec.PROP_KINDS, f"{t}.{p.name}: bad kind {p.kind}"
        for fv in spec.fix_values:
            assert fv.source in ispec.FIX_SOURCES, (
                f"{t}.{fv.name}: bad fix source {fv.source}")


def test_widget_exposes_declared_attr_properties(fix, qtbot, hmi_actions):
    """The keystone anti-drift check: build the real widget and assert it
    exposes every ``apply='attr'`` property the record declares. A renamed or
    misspelt property fails here instead of silently doing nothing in the
    cockpit. (``fix`` defines the FIX db; ``qtbot`` provides the QApplication.)"""
    for t, spec in factory.REGISTRY.items():
        if not spec.builds_in_isolation:
            continue  # needs a real screen / external process / GL; see the flag
        config = {"type": t, "options": _ctor_options(spec)}
        widget = spec.builder(
            None, config, font_percent=0.05,
            font_family="DejaVu Sans Condensed", replace=None)
        qtbot.addWidget(widget)
        for p in spec.properties:
            if p.apply != ispec.APPLY_ATTR:
                continue
            assert hasattr(widget, p.name), (
                f"{t}: widget has no attribute '{p.name}' declared by its "
                f"InstrumentSpec -- the property would silently do nothing")


def test_attr_property_defaults_match_widget(fix, qtbot, hmi_actions):
    """Defaults rule: every apply='attr' property's default matches the widget's
    own constructor default, so the editor seeds exactly what the widget uses
    when an option is absent. Colours are compared by value (the editor uses hex,
    widgets sometimes use named colours); a widget default of None (free-text
    keys / names) is exempt."""
    for t, spec in factory.REGISTRY.items():
        if not spec.builds_in_isolation:
            continue  # needs a real screen / external process / GL; see the flag
        widget = spec.builder(
            None, {"type": t, "options": _ctor_options(spec)}, font_percent=0.05,
            font_family="DejaVu Sans Condensed", replace=None)
        qtbot.addWidget(widget)
        for p in spec.properties:
            if p.apply != ispec.APPLY_ATTR or p.default is None:
                continue
            actual = getattr(widget, p.name)
            if actual is None:
                continue  # widget carries no default for this knob -- exempt
            if p.kind == "color":
                assert QColor(actual) == QColor(p.default), (
                    f"{t}.{p.name}: widget default {actual!r} != spec "
                    f"default {p.default!r}")
            elif p.kind in ("number", "integer"):
                assert float(actual) == float(p.default), (
                    f"{t}.{p.name}: widget default {actual!r} != spec "
                    f"default {p.default!r}")
            else:
                assert actual == p.default, (
                    f"{t}.{p.name}: widget default {actual!r} != spec "
                    f"default {p.default!r}")


def test_action_catalogue_matches_hmi_registry(qtbot, hmi_actions):
    """The Button action catalogue (schema._ACTIONS, soft-controls Phase B) must
    stay in lockstep with the real HMI action registry, so the configurator can
    never offer a verb the runtime doesn't handle -- or miss one it does. The
    three "style" verbs are handled locally by the Button widget, not the HMI
    hub, so they are exempt from the registry comparison."""
    from pyefis import hmi
    real = set(hmi.actions.signalMap)
    hmi_verbs = {a["verb"] for a in eschema._ACTIONS if a["group"] != "style"}
    assert hmi_verbs == real, (
        f"catalogue drift from HMI registry -- missing: {sorted(real - hmi_verbs)}, "
        f"extra: {sorted(hmi_verbs - real)}")
    catalogue = {a["verb"] for a in eschema._ACTIONS}
    assert {"set bg color", "set fg color", "set text"} <= catalogue


def test_data_status_is_hidden_from_the_palette():
    """The data-management boot screen is system-managed (gui forces it on
    boot), so data_status is hidden from the configurator palette, while the
    data-currency annunciator placed on flight screens stays visible."""
    s = eschema.build_schema()
    assert factory.REGISTRY["data_status"].hidden is True
    assert s["instruments"]["data_status"]["hidden"] is True
    assert s["instruments"]["data_annunciation"]["hidden"] is False
    hidden = {t for t, e in s["instruments"].items() if e.get("hidden")}
    assert "data_status" in hidden


def test_superseded_types_are_hidden_from_the_palette():
    """airspeed_box and heading_display are deprecated in favour of the Value
    Text widget, so they are hidden from the palette -- but they remain real,
    buildable types in the schema so panels that already place them still load
    and render."""
    s = eschema.build_schema()
    for t in ("airspeed_box", "heading_display"):
        assert factory.REGISTRY[t].hidden is True, t
        assert s["instruments"][t]["hidden"] is True, t
        # still present + buildable -- hidden only suppresses palette placement
        assert t in factory.INSTRUMENT_FACTORIES, t
