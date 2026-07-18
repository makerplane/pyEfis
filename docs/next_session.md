# Next session — opening moves

State as of 2026-06-12 end of session. Written for a cold start (a
fresh Claude/Opus session or Bill himself).

## Deployed state (the aircraft Pi) — HEALTHY, do not regress

- Branch `gpu-required` at origin HEAD; Pi pulls from it. Verified:
  water + highways draw 61/61 frames at the DFW pose.
- Pi-local config (`src/pyefis/config/includes/ahrs/virtual_vfr.yaml`,
  uncommitted): `range_nm: 80` (retreated from 215 — at 119 NM the
  passively-cooled Pi thermal-throttled at ~160% CPU; at 80 NM it runs
  ~64% and cool), `clipmap_levels: 9`, `svs_perf_log: false`,
  highways + paved_only on, all data on /data (NVMe).
- HARDWARE TODO: **active cooler for the Pi 5** (~$5 official
  fan/heatsink). The SoC hit its soft thermal limit (`vcgencmd
  get_throttled` showed the ACTIVE bit) during jet-config testing.
  Required before restoring long range.

## Opening move 1 — fix the parked optimization branch

Local branch **`wip-text-vbo-cache`** (commit 73dcc2c, NOT pushed,
marked DO NOT DEPLOY) contains two queued render-thread wins:

1. `_draw_text_quads` rewritten with per-slot cached VBOs (slots:
   "obst:N", "designators", "flagtext"; plus "flagpoles"/"flagquads"
   moved onto `_draw_overlay_cached`) — the text layers currently
   re-convert to ENU and re-upload every frame.
2. `_collect_runway_designator_quads` split into an async
   `_async_cache("designators", ...)` wrapper + `_build_designator_
   quads` builder — currently it loops every airport every frame.

**The bug**: under this branch, water + highways render only ~6 of 61
frames (the water cache returns empty most frames); at HEAD it is
61/61. Tests all pass — only the harness render shows it.

Repro (Windows, bash):

    git checkout wip-text-vbo-cache
    SVS_RENDERER=opengl SVS_TILE_PATH=D:/EarthData/glo30hgt \
    SVS_HIGHWAY_PATH=D:/EarthData/osm_roads/highway_rtree_co_tx.sqlite \
    SVS_SIM_MOTION=1 SVS_PERF_LOG=1 SVS_LAT=32.90 SVS_LON=-97.04 \
    SVS_ALT=2500 SVS_HEAD=175 SVS_RANGE=30 SVS_SCREENSHOT=/tmp/x.png \
    SVS_SCREENSHOT_DELAY_MS=8000 PYTHONPATH="C:/pylib;src" \
    python tests/visual_svs_test.py 2>&1 | grep water.gl_draw
    # bug = ~6 calls; fixed = ~61 calls

Bisect plan (the commit has two independent halves):

1. Revert ONLY the svs.py half (designators-async) — leading suspect:
   it is the first worker-calls-worker pattern (`_build_designator_
   quads` runs on the designators worker and calls
   `_get_airports_cached`, which itself goes through
   `_async_cache("airports", ...)`). Check `_async_cache` for a
   cross-slot interaction: the airports slot getting its result
   consumed/clobbered from two threads, starving every downstream
   collector (water is independent though — if reverting this half
   fixes water, figure out WHY before trusting the explanation).
2. If water is still broken, the svs_gl.py half: new text-slot VAO
   creation inside `_draw_text_quads` (binds prog/vao mid-pass) may
   corrupt the shared overlay-pass state the water draw depends on.
   Try creating text-slot VAOs eagerly in `_ensure_text_program`
   instead of lazily mid-frame.
3. After the fix: restore `range_nm: 120+` on the Pi (with the cooler
   installed) and re-measure — target is the full horizon at FL300
   (215 NM), expected to need these wins + possibly Track 1b.

## Opening move 2 — first real-aircraft test (Bonanza, Garmin)

Bill may bench the Pi in the Bonanza and try connecting the panel
Garmin. Notes:

- **fix-gateway side**: the gateway (not pyEfis) ingests position
  sources. For a panel Garmin the practical paths are (a) the unit's
  RS-232 serial output in NMEA 0183 mode (most GNS/GTN/G-series can
  emit NMEA on a serial port at 9600 baud — needs a USB-RS232 adapter
  on the Pi and the right two wires off the Garmin harness), or
  (b) "Aviation" (MapMX) format, which is richer but needs a format
  plugin. Check what plugins the installed fixgw has (`fixgw` snap or
  ~/fix-gateway checkout) — an NMEA/gpsd plugin covers (a):
  gpsd reads the USB serial, fixgw gpsd plugin publishes
  LAT/LONG/GS/TRACK/ALT(GPS).
- **No AHRS from a GPS** — PITCH/ROLL stay absent → the AI keeps the
  classic two-tone with SVS terrain at zero pitch/roll reference. For
  attitude, the Stratux path is the plan of record.
- **Power**: Pi 5 wants 5V/5A USB-C; a quality 12/14V-to-USB-C PD
  buck converter from the aircraft bus, or a USB-C battery bank that
  does 25W+, avoids brownouts (watch `vcgencmd get_throttled` bit 0).
- **Safety/affect**: advisory use only alongside certified equipment;
  nothing here is panel-mounted or connected to aircraft controls.
- Useful in-cockpit checks: GPS-only behavior of the P4 pose
  interpolation (real 1 Hz GPS!), DATA-driven SVS with no AHRS, sun
  readability of the display, thermal behavior in a closed cockpit.

## Standing queue (unchanged)

P8 Track 1b (streaming heightmap textures — far-range fidelity +
native 30 m), traffic via Stratux (P9), chart draping (P10),
data-manager (awaiting MakerPlane reply), svs/ package split.

## Feature request (Bill, 2026-06-12): GI-275-style autopilot command

Target capability: heading bug + altitude preselect on pyEfis, mode
switch between heading-hold and GPSS nav mode, with GPSS turn
compensation computed in the stack — i.e., what the Garmin GI-275
does as an autopilot commander.

Decomposition onto the existing architecture (audited 2026-06-12;
pyEfis itself contains NO autopilot — it is a control head over FIX
keys, see the MAVREQ* button configs):

1. Bug/preselect UI + HEADSEL/ALTSEL-style FIX keys (HSI has COURSE
   today; the old altsel branch poked at altitude select).
2. Mode buttons: reuse the declarative button/condition pattern from
   config/buttons/auto-pilot-*.yaml with new keys.
3. GPSS computation: fix-gateway plugin (cross-track/course/turn
   anticipation -> heading-error or roll command). ALTERNATIVE: the
   GNX 375 has ARINC 429 GPSS output — an ARINC adapter lets the
   Garmin compute steering and the gateway just mode-switch.
4. Output: (a) legacy analog autopilots need a heading-error voltage
   — a small CAN-FIX/I2C DAC hardware node (the genuinely new piece);
   (b) experimental aircraft: the existing MAVLink/CAN-FIX servo path.

SAFETY: command functionality is for EXPERIMENTAL-category aircraft
only. The certified Bonanza remains advisory-display-only.

## GNX-375 connection investigation (2026-06-13)

CORRECTION to the earlier Bonanza notes: the GNX-375 HAS an onboard
AHRS (it carries GTX 345 lineage; Bill has used its attitude with
ForeFlight SV on the iPad). So attitude IS available from this box —
but ONLY over Connext/Bluetooth, NOT over wired NMEA.

Two paths, different payloads:
- WIRED (`garmin_gnx375` fixgw plugin — Bill's own code, complete,
  config-enabled GARMIN_GNX375: true): NMEA "Aviation Output 1" over
  RS-232. Gives LAT/LONG/GS/TRACK/ALT + nav (XTRACK/CDI/COURSE). NO
  attitude (NMEA aviation format has none). Needs a USB-serial adapter
  (none attached) + GNX port set to "Aviation Output 1". Ready to fly.
- CONNEXT/BLUETOOTH: the ONLY path to the GNX's AHRS attitude (+ ADS-B
  traffic/weather). `gnx_bt_bridge.py` assumed GDL90-over-BT and fails;
  Bill confirmed planeside it connects but no usable data. Likely cause
  is a missing Connext SESSION HANDSHAKE (device waits for client hello
  before streaming) rather than purely a format mismatch.

Next planeside step: run `~/gnx_capture.py` on the Pi (GNX powered +
paired). Passive 30 s capture -> ~/gnx_capture_<ts>.bin + analysis.
  * 0 bytes  = handshake required; next capture what ForeFlight sends.
  * 0x7E-framed bytes = GDL90 (decode via stratux plugin / libGDL90;
    AHRS = ForeFlight ext msg 0x65, 5 Hz, spec foreflight.com/connect/spec).
  * other framing = Garmin Connext proprietary; needs a real decoder
    (prior art: github.com/mjsir911/GarminBLE).
Then scp the .bin back for decoding.

## GNX capture — field procedure (set up 2026-06-13)

AUTO-CAPTURE IS ARMED on the Pi (no planeside shell needed):
- `gnx-capture.service` ENABLED+active (runs ~/gnx_autocapture.py);
  `gnx-bt-bridge.service` DISABLED for the capture trip; autopair still
  enabled. On the next planeside power-up it auto-connects to the GNX and
  streams raw bytes to ~/gnx_cap/gnx_<ts>.bin (passive — sends nothing).
- Retrieve at home over Ethernet:
    scp 'pyefis:~/gnx_cap/*.bin' .
    ssh pyefis 'journalctl | grep gnx_autocapture | tail'   # byte counts
  Empty .bin / "0 bytes so far" => GNX needs a Connext handshake (it does
  not stream unprompted) -> next mission is capturing ForeFlight's hello.
  Non-empty => the real wire bytes; decode them (GDL90 0x7E framing vs
  Connext-proprietary).
- REVERT to normal bridge use after we have data:
    systemctl --user disable --now gnx-capture.service
    systemctl --user enable  --now gnx-bt-bridge.service

WIFI AP for planeside SSH (Bill enables shortly before the plane trip;
needs sudo; held off at the desk for RF reasons):
    sudo nmcli connection add type wifi ifname wlan0 con-name pyEfis-AP autoconnect yes ssid pyEfis
    sudo nmcli connection modify pyEfis-AP 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
    sudo nmcli connection modify pyEfis-AP wifi-sec.key-mgmt wpa-psk wifi-sec.psk "flymakerplane"
    sudo nmcli connection up pyEfis-AP        # Pi at 10.42.0.1
  iPhone joins WiFi "pyEfis" (pw flymakerplane); Terminus -> wpballard@10.42.0.1.
  Disable at home: sudo nmcli connection down pyEfis-AP

KEYBOARD note: wpballard IS in the input group and /dev/input/event* exist,
but NO X->quit keybinding is configured on the PFD screen — pressing X was
never wired to anything. Not needed once SSH (AP) works; a real quit key +
eglfs key-routing check is a future local-control nicety.
