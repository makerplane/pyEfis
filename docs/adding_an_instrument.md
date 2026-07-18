# Adding (or changing) an instrument

A step-by-step for getting a new instrument — or a new option on an existing one
— into pyEfis **and** the web configurator, faithfully and without drift. Read
[instrument_spec.md](instrument_spec.md) first for the model; this is the recipe.

The golden rule: **define the instrument once** in the registry record, let the
schema and (by hand, but tracked) the configurator twin derive from it, and let
the test gate keep them honest.

---

## Where things live

| Thing | File |
|------|------|
| Descriptor types (`InstrumentSpec`, `Prop`, `FixValue`) | `src/pyefis/screens/instrument_spec.py` |
| The registry + builders | `src/pyefis/screens/screenbuilder_factory.py` |
| Option application | `src/pyefis/screens/screenbuilder_options.py` |
| Schema exporter | `src/pyefis/editor/schema.py` |
| Test gate | `tests/editor/test_registry.py` |
| Reference render (real widget) | `tools/render_instrument.py` |
| Asset bundle builder | `tools/build_editor_assets.py` |
| The configurator twin | `makerplane-data/configurator/public/editor.html` (`build*`) |

---

## Step 1 — the widget

Either reuse an existing widget under `src/pyefis/instruments/<x>/` or add one.
Conventions every instrument follows:

- It is a `QWidget` / `QGraphicsView` that consumes one or more FIX keys via
  `fix.db.get_item(KEY)` and the `valueChanged` / `oldChanged` / `badChanged` /
  `failChanged` signals.
- It renders **fail** as a red "XXX", **old/bad** greyed — keep that convention.
- **Each configurable knob is a plain attribute** set in `__init__` to its
  default (e.g. `self.show_tas = True`). The property `name` in the record maps
  to that attribute, and its `default` must equal the attribute's initial value
  (the defaults rule).
- Decide each knob's **category** (see the spec): panel option (category 1) vs
  FIX value (category 2). Do not add an editor option for something that is
  really aircraft data in fix-gateway.

Sanity-check the real look (this is the twin's target):

```bash
PYTHONPATH="<pylib>;src" python tools/render_instrument.py <type> --safe -o /tmp/<type>.png
```

## Step 2 — the registry record

Add (or extend) an `_register(InstrumentSpec(...))` in
`screenbuilder_factory.py`. Bind the `builder` here (the only Qt-aware part).
Declare category-1 `properties`, document category-2 `fix_values`, and give
category-3 `preview` sample data so the twin can draw something realistic.

```python
_register(InstrumentSpec(
    type="arc_gauge",
    label="Arc Gauge",
    category="gauge",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: gauges.ArcGauge(
                 screen, min_size=False, font_family=font_family)),
    keep_aspect=True,
    properties=[
        Prop("dbkey", "fixkey", default="", label="FIX key",
             apply="setter:setDbkey"),
        Prop("name", "string", default="", label="Name"),
        Prop("decimal_places", "integer", default=1, label="Decimal places"),
        Prop("show_units", "boolean", default=False, label="Show units"),
        Prop("segments", "integer", default=0, label="Segments"),
        Prop("name_location", "enum", default="top", enum=["top", "right"]),
    ],
    fix_values=[                      # category 2 -- fix-gateway, NOT the editor
        FixValue("Min", source="min", label="Range minimum"),
        FixValue("Max", source="max", label="Range maximum"),
        FixValue("lowWarn", source="aux", label="Low warning (yellow)"),
        FixValue("highWarn", source="aux", label="High warning (yellow)"),
        FixValue("lowAlarm", source="aux", label="Low alarm (red)"),
        FixValue("highAlarm", source="aux", label="High alarm (red)"),
    ],
    preview={"value": "2350", "fill": 0.72, "green_to": 0.62, "yellow_to": 0.83},
))
```

Rules of thumb:
- Every `Prop` has a `default` matching the widget's `__init__` default (§5 of
  the spec).
- `apply`: plain attributes use `attr` (the default); a gauge key uses
  `setter:setDbkey`; unit-switching / encoder / nested `svs` are `special`.
- Only declare a property you intend the twin to honor (the fidelity rule).
- Don't redeclare `font_family` / `font_percent` — they are common options.

## Step 3 — if migrating an existing instrument, remove the curated copy

A type must live in exactly one place. When you move an instrument into the
registry, delete its entries from the curated dicts in `editor/schema.py`
(`_CATEGORIES`, `_LABELS`, `_OPTIONS`, `_REQUIRED_OPTIONS`, `_KEEP_ASPECT`,
`_SVS_CAPABLE`, `_NOT_OFFSCREEN_RENDERABLE`) and from the `INSTRUMENT_FACTORIES`
/ `INSTRUMENT_DEFAULTS` literals in `screenbuilder_factory.py` (the fold-back
re-supplies them from the record). The gate fails if you forget — that's the
point.

## Step 4 — run the gate

```bash
PYTHONPATH="<pylib>;src" python -m pytest tests/editor --no-cov -q
```

It verifies the record is a real factory type, isn't double-defined, matches the
exported schema, and that the **real widget exposes every `attr` property** you
declared. Fix anything red before moving on.

## Step 5 — the configurator twin (fidelity)

In `makerplane-data/configurator/public/editor.html`, the `build*(inst)` function
for your type draws the preview. It must **match the real widget** (render it
first in Step 1) and read from the schema, not hard-code:

- read options from `inst.options`;
- read category-3 sample data from the schema:
  `const meta = state.schema.instruments[inst.type] || {}; const pv = meta.preview || {};`
- honor **every** category-1 option you exposed (a boolean toggle must visibly
  toggle; an enum must switch the drawing). If the twin can't yet honor an
  option, don't expose it in the record.

For a brand-new type also add: a `renderCanvas()` dispatch branch, a palette
entry is automatic (schema-driven), and a palette SVG is generated in Step 6.

GL/SVS widgets (`virtual_vfr`) can't render in a browser; the twin uses a
captured `svs/<scene>.webp` instead (see the configurator README).

## Step 6 — regenerate + deploy assets

```bash
# pyEfis: rebuild schema.json (+ groups.json + palette/<type>.svg)
PYTHONPATH="<pylib>;src" python tools/build_editor_assets.py --out work/editor_assets

# makerplane-data/configurator (wrangler OAuth already set up on the dev machine):
npx wrangler r2 object put makerplane-configs/assets/editor/schema.json \
    --file=../../pyEfis/work/editor_assets/schema.json \
    --content-type application/json --remote
#   ...repeat for groups.json and any new palette/<type>.svg ...
npm run deploy        # publishes public/editor.html
```

Assets are **not committed** to `makerplane-data` (they live in R2, sourced from
pyEfis). After deploy, re-fetch a couple of times when verifying with `curl` —
the edge cache serves the previous file for a few seconds.

## Step 7 — commit (two repos move together)

- pyEfis (`display-changes`): the widget + record (+ curated removals) + tests.
- makerplane-data (`feat/accounts-auth`): the twin change.

Focused commit per change; note both SHAs when an editor change spans repos. No
emojis in commit messages. Do not push to upstream `makerplane/*` without
explicit authorisation.

---

## Checklist

- [ ] Widget renders fail/old/bad correctly; each knob is an `__init__` attribute.
- [ ] Each knob categorised (1 panel option vs 2 FIX value) — correctly.
- [ ] `InstrumentSpec` registered; `properties` defaults match widget defaults.
- [ ] `fix_values` document the category-2 inputs; `preview` lets the twin draw.
- [ ] If migrating: removed from every curated dict + the legacy literals.
- [ ] `pytest tests/editor` green (the gate).
- [ ] Twin `build*` matches the real widget and honors every exposed option.
- [ ] Assets regenerated + uploaded to R2; Worker deployed; verified at origin.
- [ ] Committed in both repos with focused messages.

---

## Worked example: a new "oil pressure arc" is just config

Most "new instruments" are an existing widget with different FIX wiring and
options — no new widget code. An oil-pressure gauge is just an `arc_gauge` placed
in the editor with `dbkey: OILP`, `name: "OIL"`, and the warn/alarm bands set in
fix-gateway (category 2). Nothing to add here. Reach for a **new widget +
record** only when the *visual form* is genuinely new (a new dial face, a new
tape style); then follow Steps 1-7.
