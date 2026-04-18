# pyEfis — Electronic Flight Instrument System

**Status:** Open Source — Experimental Amateur-Built Category  
**License:** GPL v2  
**Language:** Python 3 / PyQt6  
**Snap:** `pyefis` on snapcraft.io

[![snapcraft.io](https://snapcraft.io/pyefis/badge.svg)](https://snapcraft.io/pyefis)
[![Coverage](https://raw.githubusercontent.com/makerplane/pyEfis/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

---

## What This Is

pyEfis is an open-source **Electronic Flight Instrument System (EFIS)** display application. It renders a configurable set of flight instruments — attitude indicator, airspeed tape, altimeter tape, HSI, VSI, turn coordinator, engine gauges, annunciators, and a moving map — on any screen from a 5-inch Raspberry Pi display to a desktop monitor.

pyEfis does **not** read hardware directly. All flight data is sourced from [FIX-Gateway](../fix-gateway), the avionics data broker that aggregates sensors, GPS, CAN-FIX bus, autopilot data, and simulator connections into a single named-parameter database. This separation makes pyEfis hardware-agnostic: the same display software runs against real sensors, a flight simulator, or recorded flight data without modification.

## Instrument Suite

| Instrument | Module |
|---|---|
| Attitude Indicator (AI) | `instruments/ai/` |
| Airspeed Indicator (tape or round) | `instruments/airspeed/` |
| Altimeter (tape or round) | `instruments/altimeter/` |
| Horizontal Situation Indicator (HSI) | `instruments/hsi/` |
| Vertical Speed Indicator | `instruments/vsi/` |
| Turn Coordinator | `instruments/tc/` |
| Engine gauges (RPM, MAP, EGT, CHT, fuel, oil) | `instruments/gauges/` |
| Numerical displays | `instruments/NumericalDisplay/` |
| Annunciator panel | `instruments/pa/` |
| Moving map (via pyAvMap) | integrated via `pyAvMap` |
| Button controls | `instruments/button/` |

All instruments are configurable in size, position, color scheme, and data source key via YAML screen definition files.

## Virtual VFR / Moving Map

pyEfis supports rendering FAA aeronautical charts beneath the ownship position marker using:
- **[pyAvMap](../pyAvMap)** for chart tile rendering
- **[faa-cifp-data](../faa-cifp-data)** for waypoint, fix, airway, and procedure overlays
- GPS position and heading from FIX-Gateway `LAT`, `LONG`, `HEAD` keys

To enable:
1. Download current FAA CIFP data: https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/download/
2. Extract `FAACIFP18` into the `pyEfis/CIFP/` directory
3. Build the spatial index: `./MakeCIFPIndex.py CIFP/FAACIFP18`
4. Or use the `faa-cifp-data` snap for automatic cycle management

## Installation

### Snap (Recommended for Deployment)

```bash
sudo snap install pyefis
```

The snap automatically connects to the `faa-cifp-data` snap for navigation data and the `fixgateway` snap for flight data.

### From Source (Development)

```bash
git clone https://github.com/makerplane/pyEfis.git
cd pyEfis
make venv
source venv/bin/activate
make init

# Install FIX-Gateway (required):
# See fix-gateway/README.md

python pyEfis.py
```

See [INSTALLING.md](INSTALLING.md) for detailed platform-specific instructions.

## Screen Configuration

Screens are defined in YAML files that specify the layout, instrument types, sizes, positions, and FIX-Gateway keys. Multiple screen layouts can be defined and cycled with the `a` / `s` keys.

Example configuration reference is in the [MakerPlane Documentation](../makerplanedocuments/) PDF.

## Controls

| Key | Function |
|---|---|
| `a` / `s` | Cycle between screen layouts |
| `[` / `]` | Adjust altimeter setting (baro) |
| `m` | Toggle airspeed mode: IAS → TAS → GS |

## Data Flow

```
[FIX-Gateway] ──NetFIX TCP──→ [pyEfis client] ──→ instrument rendering
                              ↑
                         named parameters:
                         PITCH, ROLL, HEAD, IAS, ALT,
                         LAT, LONG, RPM1, EGT11..., etc.
```

Parameter staleness is tracked: if FIX-Gateway stops updating a key within its tolerance window, pyEfis flags that instrument as failed (red X or similar), giving the pilot explicit awareness of data loss.

## Role in the MAOS Ecosystem

pyEfis is the **cockpit display application** for a MAOS-equipped aircraft. It is the piece the pilot looks at.

Integration path for MAOS:
1. **MAOS-FCS** publishes attitude, airspeed, altitude, and surface positions via MAVLink
2. **FIX-Gateway** MAVLink plugin receives FCS data and maps it to FIX parameter keys
3. **pyEfis** renders the flight instruments from those keys in real time
4. **pyAvMap + CIFP data** provide moving map and IFR procedure context
5. **CAN-FIX bus** (via Arduino nodes) feeds engine data and system status

For MAOS specifically, custom screen layouts can be designed to expose FCS mode state, propulsion system parameters, and fault annunciations — all driven through FIX-Gateway custom keys.

## Platform Support

- Raspberry Pi (primary embedded target, Snap distribution)
- BeagleBone Black (via [7-inch hardware](../efis-hardware-7-inch))
- Any Linux desktop with PyQt6 (development and simulation)
- Android (experimental — see [ANDROID.md](ANDROID.md))

## Important Disclaimer

> pyEfis is developed for Experimental Amateur-Built aircraft use only.  
> It is not FAA-approved avionics software. This system must not be used as a sole-source primary instrument without independent backup instrumentation.  
> Aircraft builders are responsible for all integration, installation, and safety decisions.
