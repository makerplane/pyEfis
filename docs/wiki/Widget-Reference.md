# Widget Reference

Every widget you can place on a pyEFIS screen, by its YAML `type:` string. This
is the master index; click through to the family page for full option tables.
**Read [Concepts](Concepts) first** — it defines the shared model (FIX keys,
color states, fonts/masks, layout, encoder) that the family pages build on.

The authoritative registry is `INSTRUMENT_FACTORIES` in
`src/pyefis/screens/screenbuilder_factory.py`. There are 27 widget types; the
four gauges also have `ganged_` variants.

## Primary flight instruments — [Widgets-Flight-Instruments](Widgets-Flight-Instruments)

| `type:` | Class | Default FIX key(s) | Description |
|---------|-------|--------------------|-------------|
| `airspeed_dial` | `airspeed.Airspeed` | `IAS` | Round analog airspeed dial |
| `airspeed_box` | `airspeed.Airspeed_Box` | `IAS` / `GS` / `TAS` | Digital airspeed box, switchable IAS/GS/TAS |
| `airspeed_tape` | `airspeed.Airspeed_Tape` | `IAS` (+`TAS`) | Vertical airspeed tape w/ V-speed bands, TAS box, trend |
| `airspeed_trend_tape` | `vsi.AS_Trend_Tape` | `IAS` | Airspeed trend bar |
| `altimeter_dial` | `altimeter.Altimeter` | `ALT` | Round analog altimeter |
| `altimeter_tape` | `altimeter.Altimeter_Tape` | `ALT` | Vertical altitude tape (honors `dbkey:`) |
| `altimeter_trend_tape` | `vsi.Alt_Trend_Tape` | `VS`¹ | Vertical-speed trend bar + VSI number |
| `vsi_dial` | `vsi.VSI_Dial` | `VS` | Round analog VSI |
| `vsi_pfd` | `vsi.VSI_PFD` | `VS` | PFD-style vertical-speed indicator |
| `heading_display` | `hsi.HeadingDisplay` | `HEAD` | Digital heading readout |
| `heading_tape` | `hsi.DG_Tape` | `HEAD` | Horizontal heading tape |
| `horizontal_situation_indicator` | `hsi.HSI` | `COURSE`,`CDI`,`GSI`,`HEAD` | HSI with CDI/glideslope |
| `turn_coordinator` | `tc.TurnCoordinator` | `ROT`,`ALAT` | Turn & slip |
| `wind_display` | `wind.WindDisplay` | `HWIND`,`XWIND` | Headwind/crosswind components |

## Attitude & Synthetic Vision — [Widgets-Attitude-and-SVS](Widgets-Attitude-and-SVS)

| `type:` | Class | Default FIX key(s) | Description |
|---------|-------|--------------------|-------------|
| `atitude_indicator` | `ai.AI` | `PITCH`,`ROLL`,`ALAT`,`TAS` | Attitude indicator (+ optional FPM, SVS). Note the one-`t` spelling. |
| `virtual_vfr` | `ai.VirtualVfr.VirtualVfr` | `PITCH`,`ROLL`,`ALAT`,`LAT`,`LONG`,`ALT`,`COURSE`¹ | AI + airport/runway overlay + Synthetic Vision terrain |

## Engine & data gauges — [Widgets-Engine-Gauges](Widgets-Engine-Gauges)

| `type:` | Class | Default FIX key(s) | Description |
|---------|-------|--------------------|-------------|
| `arc_gauge` | `gauges.ArcGauge` | *(set `dbkey`)* | 180° analog arc + value |
| `vertical_bar_gauge` | `gauges.VerticalBar` | *(set `dbkey`)* | Vertical bar (EGT/CHT strips, peak/normalize) |
| `horizontal_bar_gauge` | `gauges.HorizontalBar` | *(set `dbkey`)* | Horizontal bar |
| `numeric_display` | `gauges.NumericDisplay` | *(set `dbkey`)* | Color-aware numeric readout |

Each also exists as `ganged_<type>` for grouped strips.

## Text & interactive — [Widgets-Text-and-Interactive](Widgets-Text-and-Interactive)

| `type:` | Class | Default FIX key(s) | Description |
|---------|-------|--------------------|-------------|
| `static_text` | `misc.StaticText` | — | Fixed label |
| `value_text` | `misc.ValueDisplay` | *(set `dbkey`)* | Plain value readout (no gauge colors) |
| `button` | `button.Button` | *(button config)* | Interactive button: state, conditions, actions |
| `listbox` | `listbox.ListBox` | *(per list)* | Selectable list (radio freqs, waypoints) |

## System & status — [Widgets-System](Widgets-System)

| `type:` | Class | Default FIX key(s) | Description |
|---------|-------|--------------------|-------------|
| `data_status` | `data_status.DataStatus` | — | Full-screen navdata currency / updater |
| `data_annunciation` | `data_status.DataAnnunciation` | — | Small "DATA" flag, hidden when healthy |
| `weston` | `weston.Weston` | — | Embeds an Android app (Weston/waydroid) |

---

¹ **Default-key discrepancies** (verified in source): `altimeter_trend_tape`'s
entry in `INSTRUMENT_DEFAULTS` lists `ALT`, but `Alt_Trend_Tape` subscribes to
**`VS`** and renders a vertical-speed trend. `virtual_vfr` lists `HEAD`, but the
widget binds its heading source to **`COURSE`** (`head_item = get_item("COURSE")`).
These are documented on the respective family pages.

See [FIX Database Keys](FIX-Database-Keys) for what each key means.
