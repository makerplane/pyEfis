# Open GCU — control head for pyEfis (design)

Status: DRAFT v1 (2026-07-03). Home: pyEfis docs for now; parts of this
contract belong in fix-gateway once implementation starts.

## 1. Purpose

A dedicated tactile control head for a pyEfis panel — the role Garmin's
GCU 47x keypad plays for Cirrus Perspective: baro, bugs, course, page/screen
selection and (later) frequency/FMS entry on real knobs and buttons, so the
displays stay clean and the pilot's hand has an anchor in turbulence.

Two implementations share one contract:

- **Bench bridge (now):** an Octavi IFR-1 (USB HID, real dual-concentric
  knob) driven by a small host-side daemon. Exists to *debug the interaction
  design by feel* against X-Plane + pyEfis before any hardware is built.
- **Open GCU (the product):** Pi 4 + 5" (800x480) touchscreen running a
  second pyEfis instance for the faceplate, plus a dual-concentric encoder
  head (MobiFlight-style parts) — GPIO first, then a Pico/Arduino CAN-FIX
  node (`can-fix-arduinolib`) so the knobs are a proper bus device.

## 2. Architecture — three layers, all existing machinery

```
  [knob head]        [mapper]                  [displays]
  Octavi HID daemon   fix-gateway "gcu" plugin  main PFD (pyEfis)
  GPIO encoder daemon  - owns edit focus        GCU faceplate (pyEfis #2,
  Pico CAN-FIX node    - inc/dec semantic keys    Pi 4 + 5", configurator
       |                    |                      device #2)
       v                    v                        ^
  raw input keys  ---> semantic set-point keys ------+   (all via FIX bus)
  (ENCn / BTNn)        (BARO, HEADBUG, COURSE, ...)
```

- **Dumb hardware.** Input devices publish only *raw* events on templated
  FIX keys that already exist in fix-gateway's database
  (`generic.yaml`): `ENCr` ("Generic Encoder %r", int pulses) and `BTNb`
  ("Generic Button %b", bool). No aircraft semantics in firmware — the
  Octavi bridge, the GPIO daemon and the CAN-FIX node all emit the same
  raw keys and are therefore interchangeable.
- **One mapper owns meaning.** A fix-gateway plugin (`gcu`) consumes the
  raw keys, holds the *edit focus* state machine, and writes the semantic
  set-point keys. This keeps the one-key/one-writer discipline: the mapper
  is the single writer of focus, and set-points are written on user action
  only (pyEfis touch edits can coexist).
- **Displays are just FIX clients.** The GCU faceplate is an ordinary
  pyEfis screen design (buttons, numeric readouts, listbox) on the Pi 4 —
  device #2 in the configurator, using every existing mechanism (design,
  preview, pull). The main PFD needs no code change to *show* set-points
  it already shows; both displays annunciate focus via one new key.

## 3. FIX-key contract (v1)

### Raw inputs (exist today, `generic.yaml`)

| Key | Meaning (GCU assignment) |
|---|---|
| `ENC1` | outer ring, pulses (+CW/-CCW) |
| `ENC2` | inner knob, pulses |
| `BTN1` | inner knob push |
| `BTN2..BTNn` | function buttons (Octavi: HDG/CRS/BARO/... — see appendix) |

Deltas, not positions: each pulse batch is written as a signed increment
and the mapper consumes it (encoder keys are relative by convention).

### Semantic set-points

| Key | Status | Notes |
|---|---|---|
| `BARO` | exists (`ahrs.yaml`) | inHg; fine 0.01, coarse 0.1 |
| `HEADBUG` | exists (`ahrs.yaml`) | degrees; wraps 0-359 (see `changeValueWrap`) |
| `COURSE` | exists (`ahrs.yaml`) | degrees; wraps; proven via X-Plane RREF work |
| `ALTSEL` | **to add** | selected altitude / altitude bug, ft; fine 100, coarse 1000. Add to `custom.yaml` first, upstream later |
| COM/NAV freqs | later | `com_radio.yaml` already defines radio keys; phase 3 |

### Edit focus (the one genuinely new idea)

- `GCUSEL` (**to add**, string): the currently focused edit target —
  `"BARO" | "HDG" | "CRS" | "ALT" | "NONE"` (extensible). Written ONLY by
  the mapper. TTL/auto-revert to `NONE` after ~10 s idle (mapper-enforced),
  so a bumped knob hours later doesn't silently retune something.
- Every display annunciates focus the same way (e.g. cyan highlight on the
  focused value) by subscribing to `GCUSEL`. pyEfis side: a small widget
  option or the existing DataBinding mechanism.
- Grammar (the Garmin muscle-memory set):
  - function button (or outer ring in menu context) selects focus
  - inner knob adjusts fine, outer ring adjusts coarse — a REAL
    dual-concentric maps naturally; a single push-dial (Stream Deck+)
    emulates with push-toggle coarse/fine
  - knob push = accept/toggle (context-dependent; for v1 set-points it
    just clears focus)

### Screen/page switching

pyEfis already supports bus-driven UI: `hmi/data.py` `DataBinding` watches
any FIX key and fires actions (`showScreen`, `setValue`, ...), configured
in the screen YAML. The GCU writes e.g. `BTN5`; a binding in the main
config maps it to `showScreen PFD` / `showNextScreen`. No new pyEfis
mechanism needed — v1 is pure configuration.

## 4. The mapper plugin (fix-gateway `gcu`)

Small state machine, YAML-configured:

```yaml
gcu:
  load: yes
  module: fixgw.plugins.gcu
  focus_timeout: 10          # s, revert GCUSEL to NONE
  buttons:
    BTN2: {focus: BARO}
    BTN3: {focus: HDG}
    BTN4: {focus: CRS}
    BTN5: {action: screen_next}   # consumed by pyEfis DataBinding
  targets:
    BARO: {key: BARO,    fine: 0.01, coarse: 0.1,  min: 27.5, max: 31.5}
    HDG:  {key: HEADBUG, fine: 1,    coarse: 10,   wrap: 360}
    CRS:  {key: COURSE,  fine: 1,    coarse: 10,   wrap: 360}
    ALT:  {key: ALTSEL,  fine: 100,  coarse: 1000, min: 0,    max: 25000}
```

Responsibilities: consume `ENCn` pulses -> apply increment to the focused
target with wrap/clamp; maintain `GCUSEL` + timeout; debounce buttons.
Deliberately NO direct pyEfis coupling.

## 5. Input device implementations

1. **Octavi IFR-1 bridge (bench, first):** host daemon (hidapi) -> netfix
   client writes `ENCn`/`BTNn`. Windows workstation first (X-Plane rig),
   trivially portable to the Pi. HID recon findings in the appendix.
2. **GPIO daemon (GCU bench prototype):** dual-concentric encoder pair +
   buttons on the Pi 4 header; python daemon -> same keys.
3. **CAN-FIX node (flight):** Pico/Arduino + `can-fix-arduinolib`
   publishing encoder/button parameters onto the CAN bus; fix-gateway's
   canfix connection maps them to the same `ENCn`/`BTNn`. Hardware becomes
   a first-class MakerPlane device ("open GCU head"), independent of any
   Pi USB stack.

## 6. The GCU faceplate device

- Pi 4 Model B + 5" 800x480 display, second pyEfis instance, netfix TCP to
  the same fix-gateway (proven pattern; pyEfis's sizing constants were
  originally tuned on exactly this panel class).
- Configurator: **device #2 in the same project** — no new configurator
  machinery. Content work only: a "GCU 800x480" starter template; later a
  purpose-built softkey-row widget and an FMS-style value/entry field
  (each with a twin, per the fidelity rule).
- v1 faceplate: focused-value readout strip (BARO/HDG/CRS/ALT with focus
  highlight), softkey labels matching the physical buttons, screen-select
  page.

## 7. Phases + acceptance

- **P0 — contract:** this doc; add `ALTSEL` + `GCUSEL` to fix-gateway
  custom.yaml. Accept: keys visible in netfix.
- **P1 — Octavi bridge + mapper:** daemon + `gcu` plugin; drive
  BARO/HEADBUG/COURSE/ALTSEL from the Octavi against X-Plane + main PFD.
  Accept: all four set-points editable by feel; focus annunciated on the
  PFD; 10 s revert works; X-Plane loop unaffected.
- **P2 — GCU faceplate:** Pi 4 + 5" pyEfis device designed in the
  configurator; shows set-points + focus. Accept: faceplate mirrors PFD
  values live; screen switching from GCU buttons.
- **P3 — GPIO knob head:** dual-concentric hardware replaces Octavi on the
  bench. Accept: identical behaviour with the mapper unchanged.
- **P4 — CAN-FIX head:** Pico node; bench CAN rig; vibration-sane mount.
- **P5 — extend contract:** radios (`com_radio.yaml`), FMS/entry, dimming.

## 8. Open questions

- `ALTSEL` naming vs any emerging upstream convention (check canfix spec
  for an existing selected-altitude parameter before inventing).
- Focus annunciation on instruments: widget option (`gcusel_highlight`) vs
  a generic screenbuilder decoration.
- Does the GCU faceplate need its own encoder-editable fields (touch +
  knob), or is it display/softkeys only? (v1: display + softkeys only.)
- Multi-GCU (two seats) — out of scope for v1; contract doesn't preclude.

## Appendix A — Octavi IFR-1 HID recon (2026-07-03, live device)

- **USB:** VID `0x04D8` (Microchip) PID `0xE6D6`, strings "Octavi | IFR1",
  serial "HIDCF". Single HID interface, Generic Desktop / Game Pad.
  Opens fine with `hidapi` WHILE the X-Plane integration is running
  (Windows HID reads are per-handle, non-exclusive).
- **Input report** (ID `0x0B`, 8 bytes, sent on change only — no idle
  traffic):

  | Bytes | Content |
  |---|---|
  | 0 | report ID `0x0B` |
  | 1-4 | 32 button bits (usage Button 1..32, LSB-first) |
  | 5 | **relative dial #1, int8 delta** (Usage 0x37 Dial, Rel) |
  | 6 | **relative dial #2, int8 delta** |
  | 7 bits 0-2 | buttons 33..35 (bits 3-7 const padding) |

  The two RELATIVE dials are the dual-concentric rings — the device
  natively reports signed pulse deltas, exactly the `ENCn` contract
  above. No position state to track, no wraparound handling in the
  bridge.
- **Output report** (1 byte, LED usage page): indicator/backlight
  control — usable for focus/mode feedback on the device itself.
- **Control map** (labelled capture, 2026-07-03):

  | HID | Physical control | Notes |
  |---|---|---|
  | DIAL1 | outer ring | +1/detent CW, -1 CCW |
  | DIAL2 | inner knob | +1/detent CW, -1 CCW |
  | BTN10 | inner knob push | momentary |
  | BTN09 | **shift/toggle key under the rotaries** | momentary (confirmed by two labelled presses) |
  | BTN05-BTN08 | function buttons (user's left-to-right order) | momentary |
  | BTN15-BTN20 | six-button row, left-to-right | momentary |
  | bits 33-35 | **3-bit knob-context STATE, not buttons** | changes atomically, counted 1..7 during the top-row pass |

- The 3-bit state matches the IFR-1's eight knob contexts
  (COM1/COM2/NAV1/NAV2/FMS1/FMS2/AP/XPDR): the top-row mode buttons do
  NOT emit their own button bits -- they set this state (value = button
  index, first/default context = 0 so its press is silent). Design
  gift: the mapper can read bits 33-35 DIRECTLY as the focus selector
  (mode -> `GCUSEL`), letting the Octavi's own context buttons drive
  edit focus with zero bridge-side state.
- Per-button physical labels beyond the above can be pinned
  interactively during P1 bring-up (the bridge forwards `BTNn`
  generically; only the mapper config needs labels).
- Bridge implication: the daemon is ~60 lines -- hidapi read loop ->
  `fixgw.netfix.Client` writes of `ENC1`/`ENC2` deltas + `BTNn`
  booleans + a `GCUSEL` hint from the mode bits.
