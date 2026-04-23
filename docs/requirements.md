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
- **EFIS-SVS-004:** Terrain data shall be sourced from a configurable external database (e.g., SRTM 30m or similar open-source elevation dataset); the SVS module shall define the required data format and loading interface.
- **EFIS-SVS-005:** SVS terrain rendering shall apply color coding to distinguish terrain clearance zones relative to current aircraft altitude (e.g., green = safe, yellow = caution, red = terrain conflict).
- **EFIS-SVS-006:** When SVS terrain data is unavailable or outside the loaded tile area, the display shall fall back to the standard sky/ground gradient without error annunciation.
- **EFIS-SVS-007:** SVS rendering shall not degrade the PFD attitude indicator update rate below 20 Hz on the reference hardware platform.
- **EFIS-SVS-008:** SVS shall be independently enable/disable-able via the preferences system; the standard AI shall remain fully functional when SVS is disabled.
- **EFIS-SVS-009:** The SVS implementation shall define a terrain data provider interface so alternative terrain backends can be substituted without changes to the rendering layer.
- **EFIS-SVS-010:** SVS shall include configurable display of terrain-referenced obstacles (towers, terrain peaks) when obstacle database data is provided.

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
