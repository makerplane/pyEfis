# Instrument bugs — design (selected-value markers)

Status: DRAFT v1 (2026-07-05). Companion to `gcu_design.md` (who *sets*
the values this document *displays*).

## 1. Purpose

"Bugs" are settable target markers drawn on an instrument's scale: the
heading bug on the HSI (shipped), an airspeed bug for FLC targets, an
altitude bug for altitude pre-select/hold, later a vertical-speed bug.
This document fixes the architecture before more of them accrete:
**what is shared, what stays per-instrument, and what the data contract
is.**

## 2. Decision

**No provider/registry model, and no independent hand-rolls.** Bugs get
a shared *binding + glyph kit* while *placement stays native to each
instrument*:

- The map layer registry earns its keep because layers are independent
  painters sharing ONE transform. Bugs are the inverse: one datum each,
  painted into N *different* geometries (rotating compass card,
  scrolling tapes). A registry cannot place a marker without asking the
  host instrument for its scale math anyway, so it would only add
  indirection.
- The part of the problem that IS provider-shaped — who owns the
  values — is already solved by the FIX bus and the GCU contract:
  instruments only **display** set-points; writers (GCU mapper, later
  an autopilot) own the semantics. FLC/ALT-hold mode logic never
  enters pyEfis.

## 3. What is shared (one implementation each)

Home: `src/pyefis/instruments/helpers/` (e.g. `bugs.py`).

1. **`BugBinding`** — the data plumbing every bug repeats: guarded
   `fix.db.get_item` (a database without the key must not break
   construction), `valueChanged`/`oldChanged`/`badChanged`/
   `failChanged` subscriptions, cached value, and the visibility
   policy (hidden on fail; greyed on old/bad). The HSI already carries
   four hand-rolled copies of this block (`hsi/__init__.py` — HEADBUG,
   TRACKM, GS, ...); new bugs must not add more.
2. **Marker glyphs** — the shared shape vocabulary, one draw function
   per glyph: the notched heading-bug trapezoid (compass card) and the
   tape-edge pentagon/house (airspeed/altitude/VS tapes). Default
   color: Garmin cyan (`#00ffff`, matching `heading_bug_color`).
   Configurator twins mirror the same glyph geometry (fidelity rule).
3. **Off-scale policy** — when the target is beyond the visible tape
   span, the bug pegs half-visible at the tape edge (Garmin behavior).
   Clamping lives in the helper, not per instrument, so every tape
   feels identical.
4. **Options grammar** — one naming convention across instruments:

   | Option | Meaning | Default |
   |---|---|---|
   | `<name>_bug_enabled` | draw the marker | `False` (not every panel has a writer) |
   | `<name>_bug_color` | marker color | `#00ffff` |
   | `<name>_bug_dbkey` | FIX key override | per-instrument default (section 4) |

   Matches the shipped `heading_bug_enabled` / `heading_bug_color` on
   the HSI.

## 4. What stays per-instrument

**Placement.** Each instrument already owns its value→pixel math — the
compass-card rotation on the HSI, `pph` scroll offset on the tapes.
A bug costs the instrument ~10 lines: construct the binding(s) in
`__init__`, and in paint, place the shared glyph using its own scale
mapping. Numeric readouts of the same keys are NOT the instrument's
job — the existing `value_text` instrument already does that (the
HDG/CRS chips on the panel are the proof).

## 5. FIX-key contract

The bus is the interface. CAN-FIX already defines the canonical
set-point parameters, so FIX keys mirror them 1:1:

| Bug | FIX key | Status | CAN-FIX parameter |
|---|---|---|---|
| Heading | `HEADBUG` | exists (`ahrs.yaml`) | **gap — no Selected Heading in the spec** (candidate addition via the canfix-spec fork) |
| Course | `COURSE` | exists (`ahrs.yaml`) | 61 Selected Course |
| Altitude | `ALTSEL` | exists (`custom.yaml`, GCU P0) | 65 Selected Altitude |
| Airspeed (FLC) | `IASSEL` | **to add** (fix-gateway) | 64 Selected Airspeed |
| Vertical speed | `VSSEL` | later | 63 Selected Vertical Speed |
| Glidepath | — | later | 62 Selected Glidepath Angle |

Notes:

- `ALTSEL` naming vs upstream (open question in `gcu_design.md` §8) is
  resolved by alignment with CAN-FIX 65 Selected Altitude.
- fix-gateway's `canfix/map.yaml` gets entries for 63/64/65 when the
  bus actually carries them; keys work via netfix writers (GCU mapper,
  X-Plane datarefs) meanwhile.
- One key, one writer: set-points are written on user action by the
  GCU mapper (or an AP); pyEfis touch/encoder edits coexist through the
  same keys. Displays never write bugs implicitly.
- Autopilot *mode* annunciation (which target FLC/ALT-hold is actually
  flying) is a separate display concern on separate keys — not part of
  the bug contract.

## 6. Build order

1. `BugBinding` + glyph/clamp helpers; refactor the HSI heading bug
   onto them (no behavior change — covered by the existing HSI
   verification catalog).
2. **Altitude bug** on the altimeter tape against `ALTSEL` — first,
   because GCU P1 (Octavi bridge) gives it a live writer, so the
   interaction gets end-to-end feel-testing immediately.
3. **Airspeed bug** against a new `IASSEL` (add key in fix-gateway).
4. Configurator twins for each as they land; `value_text` readout
   chips where panels want numeric targets.

Branch note: instrument work of this kind belongs with the
display-changes workstream; the fix-gateway key additions ride the
GCU plugin work.

## 7. Open questions

- Focus annunciation (`GCUSEL` highlight on the focused bug/readout):
  widget option vs generic screenbuilder decoration — inherited from
  `gcu_design.md` §8, unresolved, and shared-helper-shaped when it
  lands.
- Whether the heading bug's dashed "selected heading" reference line
  (some EFISes draw bug-to-center) is wanted — cosmetic, defer.
- Multiple bugs per scale (e.g. dual-pilot targets) — out of scope;
  `<name>_bug_dbkey` overrides leave the door open without new
  machinery.
