# Turn Coordinator / Slip-Skid Widget Specification

Standards-grounded spec for the **turn coordinator** (rate-of-turn + integral slip-skid),
focused on **rate-of-turn symbology, the slip-skid ball, and annunciation**. Companion to
[`avionics_reference.md`](avionics_reference.md) (the standards basis, §8) and the sibling
instrument specs. Scope is **`TurnCoordinator`** in `instruments/tc/__init__.py` (the
factory-registered `turn_coordinator`); `TurnCoordinator_Tape` is an unregistered,
unwired legacy variant (§7).

## 1. Purpose

The turn coordinator is a required IFR instrument: **14 CFR §91.205(d)** lists a
*gyroscopic rate-of-turn indicator combined with an integral slip-skid indicator
(turn-and-bank indicator)*, and **§91.205(d)(4)** makes the slip-skid mandatory. It shows
(a) **rate of turn** — the airplane symbol banks toward the turn against standard-rate
index marks (a standard-rate turn = 3°/s = a 2-minute 360) — and (b) **slip-skid** — a
ball that centers in coordinated flight and deflects toward a slip or skid. AC 23.1311-1C
§8.9/§8.10 give placement + the required-instrument basis; AC 25-11B §A.2.6 adds that an
**excessive sideslip** should be clearly indicated. This spec holds the widget to that bar.

## 2. Current state (implemented)

`TurnCoordinator` (a `QWidget`; a static background pixmap + a dynamic ball/airplane).
Already present:

- **Rate-of-turn** — an airplane symbol rotating with `ROT` (`self._rate * 10°`, clamped
  ±5), against fixed **standard-rate index marks** (the tick boxes at the wing-level and
  standard-rate positions).
- **Integral slip-skid ball** — from `ALAT` (lateral acceleration), riding in a box between
  two **coordinated-flight reference lines** (the "cage"); deflects toward slip/skid, with
  a configurable `alat_multiplier` / filter.
- **Failure annunciation** — `ALAT` fail → red `XXX` (ball removed), `old`/`bad` → grey
  ball; `ROT` fail → red `XXX`, `old`/`bad` → grey airplane. Each wired to `repaint`.
- **Modes** — `render_as_dial` (round face) and `ss_only` (slip-skid only).

## 3. Data contract

| Key | Use | Source | Notes |
|-----|-----|--------|-------|
| `ROT` | rate of turn → airplane-symbol bank | AHRS (turn rate) | quality: `old`/`bad`/`fail` |
| `ALAT` | slip-skid ball (lateral accel) | AHRS | quality: `old`/`bad`/`fail`; shared with the AI slip/skid |

Placement (slip-skid below/near the rate-of-turn, or within the primary attitude — §8.10)
is a **screen-layout** responsibility. The slip-skid ball and the AI's slip/skid ball both
consume `ALAT` and should agree.

## 4. Rate-of-turn, slip-skid, and annunciation (requirements)

Standards basis: AC 23.1311-1C **§8.9** (rate-of-turn, p.26) and **§8.10** (slip-skid,
p.26); **14 CFR §91.205(d)/(d)(4)** (required turn-and-bank / slip-skid); AC 25-11B
**§A.2.6** (excessive sideslip, p.70); the governing "no misleading information" principle
(`avionics_reference.md` §2). Consolidated in `avionics_reference.md` §8.

**Governing rule.** The turn coordinator must show rate of turn against standard-rate marks
and slip-skid against a coordinated (centered) reference, and must **annunciate invalid
data** rather than present it as live. IDs (`TC-<CLASS>-<NNN>`) are stable and anchor the
test catalog (§5).

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **TC-DISP-001** | Rate-of-turn symbol + standard-rate index marks | always | Airplane banks with `ROT` against fixed standard-rate marks; rate clamped to scale | §8.9 p.26; §91.205(d) | **DONE** |
| **TC-SLIP-001** | Integral slip-skid ball with coordinated reference | always | Ball deflects with `ALAT`, centered between the reference lines in coordinated flight | §8.10 p.26; §91.205(d)(4) | **DONE** |
| **TC-ANN-001** | Invalid annunciation on both sources | `ROT`/`ALAT` fail / old / bad | fail → red `XXX` (element removed); old/bad → grey | §2 governing principle | **DONE** (`TurnCoordinator`); see §7 for the unwired tape variant |
| **TC-SLIP-002** | **Excessive-slip indication** | `ALAT` beyond threshold | Salient (amber) slip alert on the ball, consistent with the AI's slip/skid | §A.2.6 p.70 | **DONE** — amber ball past `excessiveSlipFraction` |

**Contract for the gap.** `TurnCoordinator.paintEvent` sets `self._excessive_slip` and
draws the ball **amber** (`QColor(255,150,0)`) once the deflection reaches
`excessiveSlipFraction` (0.85) of the ball's full-scale displacement — matching the AI's
`AI-SLIP-002` treatment (same `ALAT` source, same amber salience). Degraded (`old`/`bad`)
still greys and `fail` still shows `XXX` — the amber cue applies only to a valid, drawn
ball. The threshold scales with the configured `alat_multiplier`.

## 5. Test cases

The executable catalog is in
[`tests/instruments/tc/test_tc.py`](../tests/instruments/tc/test_tc.py), keyed to the §4
IDs. Passing tests verify shipped behaviour; the `xfail(strict)` test is the **gap
tracker** — it flips the run red when the excessive-slip cue lands, forcing the marker's
removal.

| TC-TC | Requirement | Test (`test_tc_cat_…`) | Status |
|-------|-------------|------------------------|--------|
| 001 | TC-DISP-001 | `rate_of_turn_and_standard_rate` | pass |
| 002 | TC-SLIP-001 | `slip_skid_ball_tracks_alat` | pass |
| 003 | TC-ANN-001 | `invalid_annunciation` | pass |
| 004 | **TC-SLIP-002** | `excessive_slip_annunciation` | pass |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references: **AC 23.1311-1C** §8.9/§8.10;
**14 CFR §91.205(d)**; **AC 25-11B** §A.2.6 (excessive sideslip); consolidated + page-cited
in [`avionics_reference.md`](avionics_reference.md) §8. Match the *conventions*; never copy
a vendor's *expression*.

## 7. Open items

- **`TurnCoordinator_Tape` (latent):** a legacy slip-skid tape that is **not registered in
  the screenbuilder factory and not wired to `ALAT`** (its `setLatAcc` is driven externally
  and its ball ignores quality). Not on any screen, so no live impact — but if it is ever
  wired up, it needs the same TC-ANN-001 annunciation the main widget has. Tracked.
- **Configurable standard-rate scale:** the rate clamp (±5) and `alat_multiplier` are fixed
  / config-driven; fine for GA. No change planned.
