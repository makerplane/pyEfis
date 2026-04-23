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

## Notes

- Requirements marked as EFIS-SVS are architectural scope definitions; full SVS implementation requires terrain data pipeline design as a prerequisite.
- All configurable parameters shall follow the existing pyEfis preferences YAML pattern.
- FIX database key dependencies (TAS, IAS, pitch, roll, heading, lat, lon, alt) shall be validated at startup with graceful degradation when keys are absent.
