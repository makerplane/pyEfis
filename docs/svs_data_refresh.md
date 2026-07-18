# SVS Data Refresh Workflow

Three external FAA datasets feed the SVS. All three are public-domain
and on regular cycles. This doc captures the current manual refresh
process — download, drop, build, verify.

| Source | Cycle | Size on disk | Built into |
|--------|-------|--------------|-------------|
| FAA NASR | 28 days | ~180 MB raw / 5.6 MB sqlite | `nasr/airports.sqlite` |
| FAA CIFP | 28 days | ~53 MB raw / 1.8 MB index | `cifp/index.bin` |
| FAA DOF  | 56 days | ~96 MB raw / 71 MB sqlite | `dof/obstacles.sqlite` |

None of the raw data or derived sqlite files are tracked in git
(see `.gitignore`). They live entirely in the working tree on whatever
machine SVS is running on.

If you've gone a full cycle without refreshing: the SVS still runs,
but airports newly added or relocated won't appear, runway designators
that have flipped magnetic alignment (rare, but it happens — e.g.
KSAN renumbered in 2026) will be wrong, and obstacle data may miss
recently-erected towers.

---

## 1. NASR — airports & runways

NASR (National Airspace System Resource) covers airports, runways,
airspace boundaries, navaids, comm frequencies, and a lot more. SVS
uses three of its CSVs.

### Download

Visit https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/

Click the current effective cycle (e.g. *"14 May 2026 - 11 June 2026"*)
and download the **CSV** bundle. The file is named like
`<DD>_<Mon>_<YYYY>_CSV.zip` — about 180 MB.

### Drop & extract

Place the zip in `pyEfis/nasr/` and extract it. You should end up
with (at minimum):

```
pyEfis/nasr/
  APT_BASE.csv       (~6 MB)
  APT_RWY.csv        (~3 MB)
  APT_RWY_END.csv    (~10 MB)
  <DD>_<Mon>_<YYYY>_CSV/    (full extracted dir; SVS only needs the three APT_*.csv files above)
```

Only the three `APT_*.csv` files are read by the build tool. The rest
of the bundle is fine to leave in place but isn't used.

### Build

```bash
cd pyEfis
python tools/build_airport_db.py
```

Expected output (~1.3 s):

```
Built nasr/airports.sqlite (~5.6 MB) in 1.3 s:
  airports     :  19410
  runways      :  23185
  runway_ends  :  23611
```

Row counts shift by a few dozen each cycle; large drops (more than a
few hundred) suggest a download problem.

### Verify

Pick an airport you know and check it round-trips:

```bash
python -c "
import sqlite3
con = sqlite3.connect('nasr/airports.sqlite')
con.row_factory = sqlite3.Row
for r in con.execute(\"SELECT icao, name, lat, lon, elev_ft FROM airports WHERE icao = 'SBA'\"):
    print(dict(r))
"
```

---

## 2. CIFP — fallback airport data (also used by Virtual VFR)

CIFP (Coded Instrument Flight Procedures) is the airline-grade IFR
procedure database. SVS uses it as a fallback when NASR isn't built,
but the Virtual VFR feature in pyEfis depends on it directly — so
keep it current regardless.

### Download

Visit https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/download/

Download the current cycle. The file is `cifp_<YYMMDD>.zip` — ~50 MB.

### Drop & extract

Extract so the main data file lands at `pyEfis/cifp/FAACIFP18`.
Naming is fixed — that's the filename `pyavtools.CIFPObjects`
expects, even though the cycle date is in the zip filename.

### Build the index

```bash
cd pyEfis/cifp
PYTHONPATH="C:/pylib" python C:/pylib/pyavtools/utils/MakeCIFPIndex.py FAACIFP18 -o index.bin
```

This is *not* a tool we own — it ships with `pyavtools`. The index
build takes ~10 s and shows a spinner. End state:

```
pyEfis/cifp/
  FAACIFP18    (~53 MB)
  index.bin    (~1.8 MB)
```

### Verify

```bash
python -c "
import pyavtools.CIFPObjects as cifp
objs = cifp.find_objects('cifp/FAACIFP18', 'cifp/index.bin', 34.0, -120.0)
print(sum(1 for o in objs if o.__class__.__name__ == 'Airport'), 'airports in (34, -120)')
"
```

(Should be a small positive number — 5 for the Santa Barbara block in
the current cycle.)

---

## 3. DOF — obstacles

DOF (Digital Obstacle File) is the FAA's master list of every charted
obstacle in US airspace — towers, antennas, tall buildings, stacks,
oil rigs, wind turbines, cranes.

### Download

The current daily DOF is at a stable URL:

```
https://aeronav.faa.gov/Obst_Data/DAILY_DOF_CSV.ZIP
```

You can also use `curl` from inside `pyEfis/dof/`:

```bash
cd pyEfis/dof
curl -O https://aeronav.faa.gov/Obst_Data/DAILY_DOF_CSV.ZIP
```

The file is ~20 MB compressed.

### Drop & extract

Extract so the CSV lands at `pyEfis/dof/DOF.CSV` (~96 MB).

### Build

```bash
cd pyEfis
python tools/build_obstacle_db.py
```

Expected output (~9 s):

```
Built dof/obstacles.sqlite (~71 MB) in 9.3 s:
  obstacles            :  636581
  dropped (no position):       0
```

If the dropped count grows beyond a few hundred, FAA may have changed
the CSV format — open the CSV and check the column headers against
`tools/build_obstacle_db.py`.

### Verify

```bash
python -c "
import sqlite3
con = sqlite3.connect('dof/obstacles.sqlite')
# Towers above 1000 ft AGL — there should be a few hundred nationwide.
n = con.execute('SELECT count(*) FROM obstacles WHERE agl_ft >= 1000').fetchone()[0]
print(n, 'obstacles >= 1000 ft AGL nationwide')
"
```

---

## Cadence at a glance

If you fly often, refresh on this cadence:

- **NASR**: every 28 days when the cycle changes (next dates published on the FAA page)
- **CIFP**: same — same FAA cycle dates
- **DOF**: every 56 days when the new daily file rotates (FAA describes it as "daily" but the underlying data updates every 56 days)

If you fly occasionally, refresh **before each trip**, especially if
the trip touches unfamiliar terrain. The biggest practical risk of
stale data is a new tower near an approach corridor that the SVS
won't show.

---

## Troubleshooting

**Build tool says "file not found"** — check the CSV is in the right
directory and that the filename casing matches. The build tools look
for `APT_BASE.csv`, `APT_RWY.csv`, `APT_RWY_END.csv`, and `DOF.CSV`
(or `DOF.csv` for DOF) at the configured paths.

**SVS doesn't show airports or obstacles after a refresh** — confirm
the sqlite file exists and is newer than the source CSVs:

```bash
ls -la nasr/airports.sqlite dof/obstacles.sqlite
```

If the timestamps are old, the build didn't run. If they're new but
SVS still doesn't show data, restart the SVS process — the sqlite
connection is opened once at startup.

**Row counts dropped sharply** — most likely a partial download.
Re-download and rebuild.

**Latin-1 / UTF-8 decode errors during build** — the DOF importer
already handles this; airports importer might choke on a non-ASCII
city name in a new cycle. Fix by adding `encoding="latin-1"` to the
relevant `open()` call in the build tool.
