# Heading / Compass Display Widget Specification

Standards-grounded spec for the **standalone heading displays** — the boxed numeric heading
readout (**`HeadingDisplay`**) and the moving heading tape / directional gyro
(**`DG_Tape`**), both in `instruments/hsi/__init__.py`. Companion to
[`avionics_reference.md`](avionics_reference.md) (§4.4) and the sibling
[`hsi_widget_spec.md`](hsi_widget_spec.md) (the full HSI, which carries the compass rose +
the heading warning flag). Scope here is the **direction (heading) presentation and its
annunciation** for the two standalone widgets.

## 1. Purpose

Heading is **Primary Flight Information** (AC 23.1311-1C §8.2, p.20) and a required
instrument: **14 CFR §91.205** requires a magnetic direction indicator (VFR) / a
gyroscopically-stabilized heading system (IFR). §8.6 (Display of Direction) requires a
*clear and unmistakable display of aircraft symbol and heading*, a primary heading **scale
mode presenting at least 120° of arc**, and — because *loss of direction could reduce the
pilot's capability to cope with adverse conditions* (§8.6.a) — the display must not present
a lost/stale heading as if valid. This spec holds the two standalone heading widgets to
that bar.

## 2. Current state (implemented)

- **`HeadingDisplay`** — a boxed **numeric** heading readout, formatted as three
  zero-padded magnetic degrees + a degree sign (`_fmt_heading`: `30 -> "030°"`,
  `360/0 -> "000°"`). **Annunciates**: `HEAD` fail → red `XXX`; `old`/`bad` → blank amber.
  On all shipped SVS/PFD + six-pack screens.
- **`DG_Tape`** — a horizontal **heading tape** (moving scale): 10-degree ticks + numeric
  labels, cardinal **N/E/S/W in cyan**, wrapping through 360, read under the centre. The
  §8.6 "heading scale" presentation. **Annunciation: none** — it wires only `valueChanged`,
  not `old`/`bad`/`fail` (there is a literal `TODO` in the code). Registered as
  `heading_tape` (user-selectable), not on a shipped screen today.

## 3. Data contract

| Key | Use | Source | Notes |
|-----|-----|--------|-------|
| `HEAD` | magnetic heading → numeric readout + tape position | AHRS / magnetometer (gyro-stabilized) | quality: `old`/`bad`/`fail`; §8.8 sets the source accuracy target |

Heading **source accuracy** (§8.8: ±4° ground / ±6° flight gyro-stabilized; ±10°
non-stabilized) is a *data-source* obligation on the AHRS/magnetometer, not a display
property — the widget presents whatever `HEAD` carries and annunciates when it is invalid.
The full HSI compass rose (its own spec) provides the ≥120°-of-arc scale on shipped screens.

## 4. Heading presentation and annunciation (requirements)

Standards basis: AC 23.1311-1C **§8.2** (heading is PFI, p.20), **§8.6** (display of
direction — clear heading, ≥120° arc scale mode, source indicated, p.23), **§8.8**
(magnetic-heading accuracy, p.24); **14 CFR §91.205**; the governing "no misleading
information" principle (`avionics_reference.md` §2). Consolidated in `avionics_reference.md`
§4.4.

**Governing rule.** The heading display must show heading clearly and unmistakably and must
**annunciate an invalid heading** rather than present a frozen/stale value as if live
(§8.6.a loss-of-direction; §2). IDs (`HDG-<CLASS>-<NNN>`) are stable and anchor the test
catalog (§5).

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **HDG-DISP-001** | Clear heading presentation: numeric readout + heading scale/tape with cardinal points | always | Boxed `NNN°` readout; a heading scale (tape ticks/labels + N/E/S/W) read under a fixed index | §8.6.b p.23 | **DONE** |
| **HDG-FMT-001** | Magnetic heading formatted 000–359 (3-digit), wrapping at 360 | always | `_fmt_heading` → `"030°"`, `360/0 → "000°"` | §8.6.b p.23 | **DONE** |
| **HDG-ANN-001** | Heading-invalid annunciation on **every** heading widget | `HEAD` fail / old / bad | fail → remove/flag (`XXX`); old/bad → grey / blank (never a live-looking heading) | §8.6.a p.23; §2 | **DONE** — `HeadingDisplay` + `DG_Tape` (red `XXX` mask on fail, grey wash + amber `HDG` on old/bad) |

**Contract for the gap.** `DG_Tape` must consume the `HEAD` item quality: wire
`old`/`bad`/`fail` (init from the item) and, in a `paintEvent` overlay, **flag** an invalid
heading — on `fail` a red `XXX` masking the centre heading window (so a frozen tape can't be
read as valid), on `old`/`bad` a grey wash over the tape + an amber `HDG` flag. Same
fail/old/bad convention `HeadingDisplay` and the tapes already follow. Colour per §22 /
Table 5-1: red = failure flag; amber = degraded.

## 5. Test cases

The executable catalog is in
[`tests/instruments/hsi/test_hsi.py`](../tests/instruments/hsi/test_hsi.py), keyed to the §4
IDs. Passing tests verify shipped behaviour; the `xfail(strict)` test is the **gap
tracker** — it flips the run red when the `DG_Tape` annunciation lands.

| HDG-TC | Requirement | Test (`test_hdg_cat_…`) | Status |
|--------|-------------|-------------------------|--------|
| 001 | HDG-DISP-001 | `heading_presentation` | pass |
| 002 | HDG-FMT-001 | `heading_format_wraps` | pass |
| 003 | HDG-ANN-001 (numeric) | `numeric_invalid_annunciation` | pass |
| 004 | **HDG-ANN-001 (tape)** | `tape_invalid_annunciation` | pass |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references: **AC 23.1311-1C** §8.2/§8.6/
§8.8; **14 CFR §91.205**; consolidated + page-cited in
[`avionics_reference.md`](avionics_reference.md) §4.4. Match the *conventions*; never copy a
vendor's *expression*.

## 7. Open items

- **Data source indication (§8.6.b):** the standard wants the direction source (heading vs
  track) clearly indicated when track is a selectable option. The stack has no track-up /
  heading-vs-track selection today — tracked, not a current gap.
- **≥120° arc mode (§8.6.b):** provided by the HSI compass rose on shipped screens; the
  `DG_Tape` arc span is width/`dpp`-driven. No change planned.
