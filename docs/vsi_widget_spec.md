# VSI (Vertical Speed Indicator) Widget Specification

Standards-grounded spec for the **vertical-speed display**, focused on **scale, sign
convention, and failure annunciation**. Companion to
[`avionics_reference.md`](avionics_reference.md) (the standards basis, §7) and the sibling
instrument specs. Scope is the VSI family in `instruments/vsi/__init__.py`: **`VSI_Dial`**
(round dial), **`VSI_PFD`** (vertical moving-dot scale), and **`Alt_Trend_Tape`** (the
PFD-side VS tape, dbkey `VS`).

## 1. Purpose

Vertical speed is secondary-but-important flight information: it drives level-off and
climb/descent management. AC 25-11B classes **loss of all vertical-speed displays** and
**display of misleading vertical-speed information** each as **Major** (Table 4-6), so the
VSI must (a) present a range consistent with the airplane's climb/descent performance, with
a clear zero and an unambiguous up=climb / down=descend sense, and (b) **annunciate when
its data is invalid** rather than present a stale or frozen value as if live. AC 23.1311-1C
§8.11 adds the placement + performance-scaled-range requirement. This spec holds the VSI to
that bar and tracks the gaps.

## 2. Current state (implemented)

Three VSI variants share the `VS` FIX item:

- **`VSI_Dial`** — round dial, moving needle, ±`maxRange` (2,000 fpm) over `maxAngle`
  (170°), labeled 100-ft/min ticks. **Annunciates**: `fail` → red `XXX`; `old`/`bad` →
  grey.
- **`VSI_PFD`** — a vertical scale with a **magenta moving dot**, mildly compressed
  (`scaleRoot` 0.8) so resolution is finer near zero; marks at 500/1000/1500/2000 fpm each
  side of a zero reference. **Annunciation: none** — the dot always draws magenta.
- **`Alt_Trend_Tape`** — a VS tape (label `VSI` + digital value + a white indicator bar
  growing up/down from zero). **Annunciates**: `fail` → red `XXX` + bar removed;
  `old`/`bad` → blank value.

## 3. Data contract

| Key | Use | Source | Notes |
|-----|-----|--------|-------|
| `VS` | vertical speed → needle / dot / bar + digital value | ADC (baro rate) | primary; quality via `old`/`bad`/`fail` |

Placement (VSI to the right of, or directly below, the altimeter — §8.11 / AC 25-11B) is a
**screen-layout** responsibility (the SVS PFD places the VSI tape right of the altimeter),
not a widget property. The **display range** is a widget/config property (see AL-style open
item): it should track the airplane's climb/descent capability.

## 4. Scale, sign, and annunciation (requirements)

Standards basis: AC 23.1311-1C **§8.11** (VSI placement + performance-appropriate scale,
p.24); AC 25-11B **§A.6** (display range consistent with climb/descent performance, p.74)
and **Table 4-6** (loss / misleading VS = **Major**, p.32); the governing "no misleading
information" principle (`avionics_reference.md` §2). Consolidated in `avionics_reference.md`
§7.

**Governing rule.** The VSI must show vertical speed unambiguously (clear zero, up=climb)
over a performance-appropriate range, and must **never present invalid VS as if valid** —
a Major hazard. IDs (`VSI-<CLASS>-<NNN>`) are stable and anchor the test catalog (§5).

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **VSI-DISP-001** | Performance-appropriate scale, clear zero, up=climb/down=descend | always | Zero reference + signed scale over a climb/descent-appropriate range | §8.11 p.24; §A.6 p.74 | **DONE** — `Alt_Trend_Tape` range + graduations now config (`maxvs`/`minorDiv`/`numberedDiv`); dial + PFD ranges still fixed (see §7) |
| **VSI-ANN-001** | VS-invalid annunciation on **every** variant | `VS` fail / old / bad | `fail` → remove the moving element + show a clear flag; `old`/`bad` → grey / blank (never a live-looking value) | Table 4-6 p.32 (Major); §2 | **DONE** — all three variants: `VSI_PFD` now flags fail (red X, no dot) + greys old/bad |

**Contract for the gap.** `VSI_PFD.paintEvent` must consume the `VS` item quality: on
`fail`, **do not draw the magenta dot** — draw a red failure flag (an `X`) so a frozen dot
cannot be read as a valid vertical speed; on `old`/`bad`, draw the dot **grey** rather than
magenta. (The item's `old`/`bad`/`fail` signals are already wired to `repaint`; only
`paintEvent` needs to honour them — the same fail/old/bad convention the dial and tape
already follow.) Colour per §22 / Table 5-1: red = the failure flag; grey = degraded.

## 5. Test cases

The executable catalog is in
[`tests/instruments/vsi/test_vsi.py`](../tests/instruments/vsi/test_vsi.py), keyed to the
§4 IDs. Passing tests verify shipped behaviour; the `xfail(strict)` test is the **gap
tracker** — it flips the run red when the `VSI_PFD` annunciation lands, forcing the marker's
removal.

| VSI-TC | Requirement | Test (`test_vsi_cat_…`) | Status |
|--------|-------------|-------------------------|--------|
| 001 | VSI-DISP-001 | `scale_zero_and_sign` | pass |
| 002 | VSI-ANN-001 (dial) | `dial_invalid_annunciation` | pass |
| 003 | VSI-ANN-001 (tape) | `tape_invalid_annunciation` | pass |
| 004 | **VSI-ANN-001 (PFD)** | `pfd_invalid_annunciation` | pass |
| 005 | VSI-DISP-001 (configurable scale) | `trend_tape_configurable_scale` | pass |
| 006 | display convention (bg opacity) | `trend_tape_bg_opacity` | pass |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references: **AC 23.1311-1C** §8.11
(VSI), §18 annunciation, §22 colour; **AC 25-11B** §A.6 + Table 4-6 (failure objectives);
consolidated + page-cited in [`avionics_reference.md`](avionics_reference.md) §7. Match the
*conventions* (unprotected, a safety benefit); never copy a vendor's *expression*.

## 7. Open items

- **Configurable range (VSI-DISP-001 / §A.6):** RESOLVED for `Alt_Trend_Tape`
  (2026-07-03): `maxvs` (full scale ±ft/min), `minorDiv` (tick interval) and
  `numberedDiv` (numbered-graduation interval) are editor/YAML options, with
  `bg_color`/`bg_opacity` face control; defaults preserve the shipped look
  (±2,500, ticks 100, numbers 200, solid black). `VSI_Dial` (2,000 fpm) and
  `VSI_PFD` (2,000) remain fixed — still tracked here.
- **TCAS RA bands (§A.6):** if a resolution advisory is ever integrated, the range must be
  sufficient to show the red/green RA bands — out of scope (no TCAS).
