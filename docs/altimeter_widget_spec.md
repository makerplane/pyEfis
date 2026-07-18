# Altimeter Tape Widget Specification

Standards-grounded spec for the **linear-tape altitude display**, focused on **markings,
altitude awareness cues (trend + reference bug), and failure annunciation**. Companion to
[`avionics_reference.md`](avionics_reference.md) (the standards basis, §6.5) and the
sibling tape spec [`airspeed_widget_spec.md`](airspeed_widget_spec.md). Scope is the
**`Altimeter_Tape`** class in `instruments/altimeter/__init__.py` (the same class also
drives a VS tape via `dbkey`); the round-dial `Altimeter` is secondary.

## 1. Purpose

Altitude is primary flight information. On a **linear tape** the present value sits under a
fixed pointer, so the display must be built to convey *unambiguously, at a glance, the
present altitude*, with enough scale length and markings to (a) give the resolution for
precise manual altitude tracking in level flight and (b) leave **look-ahead room to
predict and accomplish level-off** (AC 23.1311-1C §17.8.a). The standard therefore calls
for standard **500- and 1,000-foot** increment markings, a recommended **altitude
reference bug**, and a **6-second trend indicator** (unless a VSI sits adjacent to the
right). This spec holds the tape to that bar and tracks the gaps.

## 2. Current state (implemented)

`Altimeter_Tape` (a `QGraphicsView`; a tall `QGraphicsScene` scrolled under a fixed
pointer). Already present:

- **Linear moving-scale tape** with tick marks + numeric labels (major/minor via
  `majorDiv`/`minorDiv`), a **fixed read pointer** (index triangle) and an optional
  **digital read-out** (`NumericalDisplay`, `numeric_box`) — the §17.8 tape format.
- **Failure annunciation** on the read-out: `fail` → `XXX`, `old`/`bad` → blank/grey
  (`NumericalDisplay`), driven by the standard FIX signals; the round-dial `Altimeter`
  greys on `old`/`bad` and shows `XXX` on `fail`.
- **Value rounding** (`round_to`) so a jittery source (e.g. VS) snaps the box without the
  tape scroll losing smoothness; **unit switching** (ft/m).

## 3. Data contract

| Key / aux | Use | Source | Notes |
|-----------|-----|--------|-------|
| `ALT` (value) | present altitude → pointer + read-out + tape scroll | ADC (baro) | primary |
| `BARO` | altimeter (Kollsman) setting | pilot / ADC | shown by a separate baro widget; sets the `ALT` datum |
| **selected altitude** | **altitude reference bug (AL-BUG-001)** — not published by fix-gateway | autopilot / alt preselect (future) | **no FIX key yet** |

**Altitude markings are not V-speeds** — there are no per-airplane band values here; the
markings are geometric (every 500/1,000 ft) and the trend is derived from the `ALT` time
history. Quality (`old`/`bad`/`fail`) is tracked on the `ALT` item per the widget
convention.

## 4. Markings, awareness cues, and annunciation (requirements)

Standards basis: AC 23.1311-1C **§17.8** (linear-tape altimeter displays, p.43),
**§22.2 Table 4** (colour, p.45), and the governing "no misleading information" principle
(`avionics_reference.md` §2); consolidated in `avionics_reference.md` §6.5.

**Governing rule.** A linear-tape altimeter must convey the present altitude *unambiguously
at a glance*, give resolution for precise level-flight tracking, and provide **look-ahead**
to predict and accomplish level-off (§17.8.a). IDs (`AL-<CLASS>-<NNN>`) are stable and
anchor the test catalog (§5). **Status** is the widget as of this writing.

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **AL-DISP-001** | Linear moving-scale tape: scrolling scale, fixed pointer, digital read-out | always | Present-value read-out + fixed index over a moving scale | §17.8.a p.43 | **DONE** |
| **AL-ANN-001** | Altitude-invalid annunciation | `ALT` fail / old / bad | Read-out `XXX` on fail; blank (not a stale number) on old/bad | §18; §2 governing principle | **DONE** |
| **AL-MARK-001** | **Standard 500-/1,000-ft increment denotation** | always | Distinct emphasis at 1,000-ft (label + longest tick) and 500-ft (intermediate tick), above the minor ticks | §17.8.a p.43 | **DONE** — three tick tiers |
| **AL-TREND-001** | **6-second altitude-trend indicator** | always (unless a VSI is adjacent right) | A trend vector predicting altitude ~6 s ahead (level-off look-ahead) | §17.8.b p.43 | **DONE** — cyan trend vector (`show_trend`, ALT-default) |
| **AL-BUG-001** | **Altitude reference bug** | selected altitude set | A bug on the tape at the selected altitude (glance cue for level-off) | §17.8.a p.43 | **GAP — data-blocked** (no selected-altitude FIX key yet) |

**Contract for the gap cues.**

- **AL-TREND-001** — `Altimeter_Tape` gains `show_trend` (default on), `trend_lookahead`
  (default **6.0 s**, per §17.8.b), `trend_window`, `trend_min_change` (ft noise floor),
  a `_trend_history` of `(monotonic_time, alt)` samples and a derived `self._trend_px`
  (positive = climbing → vector up; negative = descending → down). `paintEvent` draws the
  trend vector from the read pointer when `abs(_trend_px)` clears the noise floor. Mirrors
  the airspeed tape's trend so the two tapes read the same.
- **AL-MARK-001** — the tape renders **three tick tiers**: 1,000-ft (longest + numeric
  label), 500-ft (intermediate length), and `minorDiv` (short), so the pilot gets the
  standard 500/1,000 sense of altitude independent of the `majorDiv` label spacing.
- **AL-BUG-001** — when a selected-altitude key exists, a reference bug is drawn on the
  tape edge at that altitude (clamped to the visible window with an off-scale indication).
  **Blocked** until fix-gateway publishes the key (autopilot / altitude-preselect path) —
  tracked, not yet implementable, like the AI's data-blocked pitch-limit.

Colour (§22.2 Table 4): scales/ticks **white**; the trend vector uses a **cyan** cue
(consistent with the airspeed tape); no red/amber here — altitude carries no
envelope-limit band on the tape. Colour is never the sole cue (§22.6).

## 5. Test cases

The executable catalog is in
[`tests/instruments/altimeter/test_altimeter.py`](../tests/instruments/altimeter/test_altimeter.py),
keyed to the §4 IDs. Passing tests verify shipped behaviour; the `xfail(strict)` tests are
the **gap tracker** — each flips the run red when its cue is implemented, forcing the
marker's removal. `AL-BUG-001` stays `xfail` until a selected-altitude key exists.

| AL-TC | Requirement | Test (`test_al_cat_…`) | Status |
|-------|-------------|------------------------|--------|
| 001 | AL-DISP-001 | `linear_tape_format` | pass |
| 002 | AL-ANN-001 | `altitude_invalid_annunciation` | pass |
| 003 | **AL-MARK-001** | `standard_500_1000_ticks` | pass |
| 004 | **AL-TREND-001** | `six_second_trend_indicator` (+ `trend_defaults_off_for_vs_tape`) | pass |
| 005 | **AL-BUG-001** | `altitude_reference_bug` | xfail — data-blocked |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references: **AC 23.1311-1C** §17.8
(linear-tape altimeter), §18 annunciation, §22 colour; consolidated + page-cited in
[`avionics_reference.md`](avionics_reference.md) §6.5. Match the *conventions*
(unprotected, a safety benefit); never copy a vendor's *expression*.

## 7. Open items

- **AL-BUG-001 is data-blocked:** publish a **selected-altitude** key from fix-gateway
  (autopilot / altitude-preselect) to unblock the reference bug — the same pattern as the
  AI's AOA-blocked pitch-limit.
- The `Altimeter_Tape` class is shared with the VS tape (`dbkey="VS"`); keep the trend
  opt-out-able so a VS instance (or a tape beside a VSI, §17.8.b) can disable it.
- **Baro (Kollsman) setting** display is a separate widget/requirement, not part of this
  tape spec; note it here so the altitude-setting chain is tracked end-to-end.
