# pyEfis Requirements

This document defines requirements for pyEfis display features. Requirements here
represent intended behavior for the pyEfis EFIS display system and are tracked
separately from upstream MakerPlane development.

## Requirement IDs

Format: `EFIS-<AREA>-<NNN>`

---

### True Airspeed Display

- **EFIS-TAS-001:** The PFD shall display True Airspeed (TAS) as a numeric value with a `TAS` label.
- **EFIS-TAS-002:** TAS shall be sourced from the FIX database key `TAS`; if unavailable the display shall show dashes and not blank the field silently.
- **EFIS-TAS-003:** TAS shall be displayed in the same unit system as IAS (knots by default, configurable).
- **EFIS-TAS-004:** TAS display shall be positioned near the airspeed tape so the relationship between IAS and TAS is visually clear without occluding primary IAS readout.
- **EFIS-TAS-005:** TAS display shall be independently enable/disable-able via the preferences system without code changes.

---

### Airspeed Trend

- **EFIS-TREND-001:** The airspeed tape shall include a trend indicator showing predicted airspeed at a configurable look-ahead time (default 6 seconds).
- **EFIS-TREND-002:** The trend indicator shall be rendered as an arrow or line extending from the current airspeed bug along the tape axis, in the direction of acceleration or deceleration.
- **EFIS-TREND-003:** Trend magnitude shall be computed from the rate of change of IAS, smoothed over a configurable averaging window (default 3 seconds) to suppress sensor noise.
- **EFIS-TREND-004:** The trend indicator shall not be displayed when the computed rate of change is below a configurable noise floor threshold.
- **EFIS-TREND-005:** The trend look-ahead time, averaging window, and noise floor shall be configurable via the preferences system.
- **EFIS-TREND-006:** Trend indicator shall be independently enable/disable-able via the preferences system.

---

### Synthetic Vision System (SVS)

- **EFIS-SVS-001:** The attitude indicator background shall support an optional Synthetic Vision System (SVS) mode that replaces the solid sky/ground gradient with a 3D terrain representation.
- **EFIS-SVS-002:** SVS shall use aircraft position (latitude, longitude, altitude) from the FIX database to determine terrain viewpoint.
- **EFIS-SVS-003:** SVS shall use aircraft attitude (pitch, roll, heading) from the FIX database to orient the terrain view.
- **EFIS-SVS-004:** The standard terrain data source shall be NASA SRTMGL3 V003 (3 arc-second / 90 m resolution), distributed as 1°×1° HGT tiles (big-endian signed 16-bit integers, 1201×1201 samples). The full global dataset (14,297 land tiles, ~13.6 GB) fits on a 32 GB microSD card. Higher-resolution sources (e.g., USGS 1/3 arc-second for the US) may be substituted via the terrain provider interface without code changes.
- **EFIS-SVS-005:** SVS terrain rendering shall apply colour coding to distinguish terrain clearance zones relative to current aircraft altitude: green ≥ 1000 ft clearance, yellow 500–999 ft, red < 500 ft, magenta at or above aircraft altitude. Thresholds shall be configurable.
- **EFIS-SVS-006:** When SVS terrain data is unavailable or outside the loaded tile area, the display shall fall back to the standard sky/ground gradient without error annunciation.
- **EFIS-SVS-007:** SVS rendering shall not degrade the PFD attitude indicator update rate below 20 Hz on the reference hardware platform.
- **EFIS-SVS-008:** SVS shall be independently enable/disable-able via screen YAML config (`svs: enabled: false`). Default is **disabled**; users explicitly enable it after verifying their hardware meets performance requirements. The standard AI shall remain fully functional when SVS is disabled.
- **EFIS-SVS-009:** The SVS implementation shall define a terrain data provider interface so alternative terrain backends can be substituted without changes to the rendering layer.
- **EFIS-SVS-010:** SVS shall include configurable display of terrain-referenced obstacles (towers, buildings) when an obstacle database is provided via the data management tool.
- **EFIS-SVS-011:** SVS shall support three rendering tiers selectable via config (`renderer: cpu_sparse | cpu_dense | opengl`): **cpu_sparse** projects a 48×48 terrain grid using NumPy (suitable for Raspberry Pi 4, ~15 Hz); **cpu_dense** projects a 128×128 grid (Raspberry Pi 5 / x86, ~20 Hz); **opengl** renders a full terrain mesh via QOpenGLWidget (any OpenGL ES 3.1 GPU, 20+ Hz). Default tier is `cpu_sparse`.
- **EFIS-SVS-012:** SVS lookahead range shall be configurable in nautical miles (`range_nm`, default 30). Terrain data shall be loaded for a radius of `range_nm` around the current aircraft position; tiles outside this radius shall be unloaded to bound memory use.
- **EFIS-SVS-013:** SVS configuration shall follow this schema in the screen YAML:
  ```yaml
  svs:
    enabled: false
    renderer: cpu_sparse     # cpu_sparse | cpu_dense | opengl
    range_nm: 30
    tile_path: /media/terrain/srtm3
    obstacle_path: /media/terrain/obstacles
    clearance_green_ft: 1000
    clearance_yellow_ft: 500
    clearance_red_ft: 0
  ```
- **EFIS-SVS-014:** The SVS position computation shall reuse the same `pixelsPerDeg` coordinate frame established by the FPM feature: terrain grid points are projected into the AI viewport using pitch/roll transforms identical to the FPM symbol, ensuring SVS terrain and FPM are geometrically consistent.
- **EFIS-SVS-015:** SVS is recommended for display sizes of 7 inches or larger; on displays smaller than 7 inches the terrain detail is resolution-limited and the feature may be disabled by default in the relevant screen YAML layouts.

---

### Wind Components Display

- **EFIS-WIND-001:** The PFD shall display headwind (HW) and crosswind (XW) components in the bottom-left area of the display, adjacent to the airspeed tape.
- **EFIS-WIND-002:** Headwind component shall be sourced from FIX database key `HWIND`; positive values indicate headwind, negative values indicate tailwind.
- **EFIS-WIND-003:** Crosswind component shall be sourced from FIX database key `XWIND`; positive values indicate wind from the right, negative values indicate wind from the left.
- **EFIS-WIND-004:** `HWIND` and `XWIND` shall be computed by fix-gateway from `WINDSPD` and `WINDDIR` via the `wind_components` compute function.
- **EFIS-WIND-005:** `WINDSPD` and `WINDDIR` shall be computed by fix-gateway from GPS inputs `GS`, `TRACK`, `TAS`, and `HEAD` via the `wind_triangle` compute function (GPS wind triangle baseline).
- **EFIS-WIND-006:** External sources (ADS-B wind, dedicated sensors) may override `WINDSPD` and `WINDDIR` directly; the display and component calculation are decoupled from the wind source.
- **EFIS-WIND-007:** When `HWIND` or `XWIND` data is unavailable or marked failed, the respective display field shall show dashes and a muted arrow indicator.
- **EFIS-WIND-008:** Each component row shall display a directional arrow indicating headwind/tailwind or left/right crosswind, updated in real time.

---

### Flight Path Marker (FPM)

The Flight Path Marker (also known as the velocity vector or flight path vector) shows where the aircraft's center of gravity is actually moving through space, as distinct from where the nose is pointed. This provides immediate intuitive feedback on energy state, angle of attack margin, and departure from desired flight path — particularly valuable in IMC, turbulence, and unusual attitudes.

Two computation methods are defined. GPS-based FPM (implemented first) uses GPS ground speed and track versus magnetic heading to derive flight path angle and drift. Aerodynamic FPM (future) uses True Airspeed and inertial vertical speed for an air-mass-referenced indication; the architecture shall accommodate both without redesign.

- **EFIS-FPM-001:** The attitude indicator shall display a Flight Path Marker (FPM) symbol showing the aircraft's actual flight path direction within the AI coordinate frame.
- **EFIS-FPM-002:** The FPM symbol shall be a circle with two short horizontal stub wings extending left and right, and a short vertical stem extending upward — consistent with conventional EFIS FPM symbology (Garmin, Honeywell style).
- **EFIS-FPM-003 (GPS FPM):** FPM vertical position shall be computed as flight path angle γ = arctan(VS / GS), where VS is in ft/min and GS is in ft/min (GS_knots × 101.269). Positive γ displaces the marker above the horizon; negative below.
- **EFIS-FPM-004 (GPS FPM):** FPM horizontal position shall be computed as drift angle = TRACK − HEAD, normalised to ±180°. Positive drift (wind from left, crabbing right) displaces the marker right of center.
- **EFIS-FPM-005:** FPM position shall use the same pixels-per-degree scale as the AI pitch ladder (`pixelsPerDeg`) so the marker reads directly against the pitch graduation marks.
- **EFIS-FPM-006:** The FPM marker shall be positioned within the rolled AI coordinate frame (it moves with the horizon line as the aircraft banks) but the symbol itself shall remain upright (wings horizontal in display space at all bank angles).
- **EFIS-FPM-007:** The FPM shall be clamped to the visible AI area; it shall not be drawn outside the widget boundary.
- **EFIS-FPM-008:** FIX database keys required for GPS FPM: `VS` (ft/min), `GS` (knots), `TRACK` (degrees magnetic), `HEAD` (degrees magnetic). When any required key carries a fail flag, the FPM shall not be drawn.
- **EFIS-FPM-009:** The FPM shall be independently enable/disable-able via the AI instrument options in the screen YAML (`show_fpm: true/false`, default true).
- **EFIS-FPM-010:** The implementation shall define a clear separation between the FPM position computation and the symbol drawing so that a future aerodynamic FPM variant (using `TAS` and inertial `VS`) can be substituted by changing the computation method only, without altering the drawing code.
- **EFIS-FPM-011:** When GPS FPM data is valid, the FPM symbol shall be rendered in lime green. When data quality is degraded (bad flag set on any input) but not failed, the symbol shall be rendered in amber to indicate reduced confidence.

---

### Selected Altitude (Altitude Alerting)

- **EFIS-ALTSEL-001:** The altimeter tape shall display a selected (target) altitude bug as a white box at the tape position corresponding to the selected altitude value.
- **EFIS-ALTSEL-002:** Selected altitude shall be sourced from FIX database key `ALT_SEL`; if the key is absent or has no value set, no bug shall be drawn.
- **EFIS-ALTSEL-003:** The selected altitude value shall be displayed numerically inside or adjacent to the bug box for unambiguous readout.
- **EFIS-ALTSEL-004:** When the bug is outside the visible tape range, a caret or clipped indicator shall appear at the appropriate tape edge to indicate direction to the selected altitude.
- **EFIS-ALTSEL-005:** fix-gateway shall compute altitude deviation as `ALT - ALT_SEL` and set the `ALT_SEL` annunciate flag when the absolute deviation exceeds a configurable threshold (default ±200 ft).
- **EFIS-ALTSEL-006:** When the annunciate flag is active, the altitude bug box shall change from white to amber/red to provide a continuous visual deviation alert; the alert shall clear automatically when the aircraft returns within the threshold band.
- **EFIS-ALTSEL-007:** `ALT_SEL` shall be a writable FIX database key; the EFIS display is read-only — it shall not provide a knob or entry interface for setting the selected altitude.
- **EFIS-ALTSEL-008:** `ALT_SEL` shall be settable by any connected FIX client, including an autopilot controller panel or ground-configuration tool; the architecture shall not assume a specific input device.
- **EFIS-ALTSEL-009:** The alerting threshold shall be configurable in fix-gateway config without code changes (default 200 ft).
- **EFIS-ALTSEL-010:** The altitude deviation alert shall be computed and annunciated in fix-gateway so the logic is available to all connected displays and clients, not only the EFIS.

---

## Notes

- Requirements marked as EFIS-SVS are architectural scope definitions; full SVS implementation requires terrain data pipeline design as a prerequisite.
- All configurable parameters shall follow the existing pyEfis preferences YAML pattern.
- FIX database key dependencies (TAS, IAS, pitch, roll, heading, lat, lon, alt) shall be validated at startup with graceful degradation when keys are absent.
