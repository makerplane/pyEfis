# AI (Attitude Indicator) Widget Specification

Standards-grounded spec for the attitude indicator, focused on **flags, alerts, and
unusual-attitude recovery annunciation**. Companion to
[`avionics_reference.md`](avionics_reference.md) (the standards basis) and
[`hsi_widget_spec.md`](hsi_widget_spec.md) (the sibling instrument). Scope is the
**attitude/alerting layer**; the SVS terrain renderer that shares this widget is
specified separately (`svs_rendering.md`, `svs_structural_plan.md`).

## 1. Purpose

The AI is primary flight information — AC 25-11B ranks *loss of attitude* as
**Catastrophic** (Table 4-1, p.27). Beyond showing pitch/roll, a modern AI must
actively support **recovery from unusual attitudes** (recognize + initiate recovery
within one second — AC 25-11B §A.2.2) and give **envelope-awareness** cues (stall
margin, excessive bank/sideslip). This spec holds it to that bar and tracks the gaps.

## 2. Current state (implemented)

`instruments/ai/__init__.py` (a `QGraphicsView`; SVS rides at low z under the pitch
ladder). Already present:

- **Attitude** — pitch ladder + roll from `PITCH`/`ROLL`; `pitchDegreesShown` FOV;
  raised-horizon option (`horizon_position`) for the SVS.
- **Bank** — a moving bank scale + standard-rate-turn markers, clamped at
  `bankAngleMaximum` (25°).
- **Slip/skid ball** — from `ALAT` (lateral acceleration).
- **Aircraft symbol** + **Flight Path Marker** (FPM, gated below `_FPM_MIN_GS_KT`, #70).
- **Failure annunciation** — `setFail(fail, item)` swaps to a `fail_scene` that shows
  **"XXX"** (attitude removed); `old`/`bad` grey the sky/land; **SVS UNAVAIL**
  annunciates when GL is absent.
- **P4 frame clock** — setters store state + mark `_frame_dirty`; `_frame_tick`
  repaints.

## 3. Data contract

| Key | Use | Source |
|-----|-----|--------|
| `PITCH`, `ROLL` | attitude | AHRS |
| `ALAT` | slip/skid ball (lateral accel) | AHRS |
| `TAS` | standard-rate bank marker | ADC |
| `VS`,`GS`,`TRACK`,`HEAD`,`VPATH` | FPM solution | GPS/AHRS |
| **`AOA` / stall-margin** | **pitch-limit (AI-LIM-001) — not yet published by fix-gateway** | AOA vane / OnSpeed (future) |

Quality is tracked per key in `_AIOld`/`_AIBad`/`_AIFail` (`PITCH`/`ROLL`/`ALAT`/`TAS`);
`getAIFail()`/`getAIOld()`/`getAIBad()` aggregate.

## 4. Flags, alerts, and recovery annunciation (requirements)

Standards basis: AC 25-11B **Appendix A** §A.2.2–A.2.6 (p.70), **Table 4-1** (p.27),
the unusual-attitude **de-clutter** guidance (p.47), and **§25.1301** (continued
function in unusual attitudes / rapid maneuvers); `avionics_reference.md` §2.

**Governing rule.** Primary attitude must never present misleading information and must
*actively aid recovery* — the pilot should recognize an unusual attitude and initiate
recovery within one second (§A.2.2). IDs (`AI-<CLASS>-<NNN>`) are stable and anchor the
test catalog (§5). **Status** is the widget as of this writing.

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **AI-ANN-001** | Attitude-fail annunciation | `PITCH`/`ROLL` fail | Remove attitude; show a clear fail display ("XXX") | Table 4-1 p.27; §25.1301 | **DONE** — `fail_scene` |
| **AI-FAIL-001** | Degraded (stale/invalid) attitude greyed | `PITCH`/`ROLL`/`ALAT`/`TAS` old or bad | Grey sky/land | widget convention; AC 25-11B §4.2 | **DONE** |
| **AI-SLIP-001** | Sideslip shown (slip/skid ball) | `ALAT` | Ball deflects with lateral accel | App A §A.2.6 p.70 | **DONE** |
| **AI-CHEV-001** | Unusual-attitude **recovery chevrons** | pitch beyond the unusual-attitude threshold | Large chevrons pointing to the nearest horizon, enabling recovery < 1 s | App A §A.2.2 p.70 | **DONE** — amber chevrons, `_draw_recovery_chevrons` |
| **AI-BANK-001** | **Excessive-bank** annunciation | roll beyond threshold (before stall buffet) | Salient bank alert (amber/red) | App A §A.2.5 p.70 | **DONE** — amber bank scale |
| **AI-DCL-001** | **De-clutter** at unusual attitude | unusual attitude | Remove non-essential overlays, retain recovery info | AC 25-11B p.47; §A.2 | **DONE** — `_decluttered` suppresses FPM / standard-rate diamonds / horizon heading scale |
| **AI-SLIP-002** | **Excessive-sideslip** indication | `ALAT` beyond threshold | Salient slip alert | App A §A.2.6 p.70 | **DONE** — amber ball |
| **AI-LIM-001** | **Pitch-limit / stall-margin** indication | approaching stall AOA | Pitch-limit marker on the ladder | App A §A.2.4 p.70 | **GAP — data-blocked** (no `AOA`/stall-margin key yet; OnSpeed/AOA path) |

**Thresholds.** "Unusual attitude" follows common EFIS/Part 25 convention — all
configurable attributes:
- **Recovery chevrons + de-clutter** engage on pitch **> +30° / < −20°**
  (`unusualPitchHighDeg` / `unusualPitchLowDeg`); de-clutter *also* engages on a steep
  bank **> 65°** (`unusualBankDeg`), past the excessive-bank caution — the
  unusual-attitude regime, not a normal steep turn.
- **Excessive-bank caution** (amber bank scale) engages earlier, at bank **> 45°**
  (`excessiveBankDeg`); a 45–65° steep turn shows the caution but stays fully cluttered
  so the pilot keeps all cues.

The thresholds are pinned here and in the test catalog (AI-TC-101/103).

## 5. Test cases

The executable catalog is in
[`tests/instruments/ai/test_ai.py`](../tests/instruments/ai/test_ai.py), keyed to the §4
IDs. Passing tests verify shipped behaviour; `xfail(strict)` tests are the **gap
tracker** — each flips the run red when its alert is implemented, forcing the marker's
removal. `AI-LIM-001` stays `xfail` until an `AOA`/stall-margin key exists.

| AI-TC | Requirement | Test (`test_ai_cat_…`) | Status |
|-------|-------------|------------------------|--------|
| 001 | AI-ANN-001 | `attitude_fail_shows_fail_scene` | pass |
| 002 | AI-FAIL-001 | `degraded_attitude_stays_greyed` | pass |
| 003 | AI-SLIP-001 | `slip_ball_tracks_lateral_accel` | pass |
| 101 | **AI-CHEV-001** | `recovery_chevrons_at_extreme_pitch` | pass |
| 102 | **AI-BANK-001** | `excessive_bank_annunciation` | pass |
| 103 | **AI-DCL-001** | `declutter_at_unusual_attitude` | pass |
| 104 | **AI-SLIP-002** | `excessive_sideslip_annunciation` | pass |
| 105 | **AI-LIM-001** | `pitch_limit_indication` | xfail — data-blocked |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references (not vendor-proprietary):
**AC 25-11B** (Electronic Flight Displays) Appendix A + ch. 4 — attitude symbology,
unusual-attitude recovery, failure objectives; **14 CFR §25.1301** — continued function;
**FAA-H-8083-15B** (IFH) — attitude-indicator fundamentals; consolidated + page-cited in
[`avionics_reference.md`](avionics_reference.md). Match the *conventions* (unprotected,
a safety benefit); never copy a vendor's *expression*.

## 7. Open items

- Publish an `AOA`/stall-margin key from fix-gateway (unblocks AI-LIM-001 — the last AI
  gap).
- **De-clutter scope (decided):** AI-DCL-001 suppresses the AI's own non-essential 2D
  symbology (FPM, standard-rate turn diamonds, horizon heading scale) and retains all
  recovery-critical symbology (attitude, pitch ladder, bank scale + pointer, slip/skid
  ball, recovery chevrons). It deliberately **keeps the SVS terrain** on — at an unusual
  attitude the terrain is the primary attitude reference (all-sky / all-ground) rather
  than clutter, and suppressing the GL layer is the far more invasive change. Revisit
  SVS-layer de-clutter only if flight testing shows the terrain competing with the
  recovery cues.
