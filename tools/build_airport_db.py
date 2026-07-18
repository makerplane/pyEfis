#!/usr/bin/env python3
#  SPDX-License-Identifier: GPL-2.0-or-later
"""
Build airports.sqlite from FAA NASR CSV data for the SVS renderer.

NASR (National Airspace System Resource) is the FAA's free public airport
database. We use three of its CSV files:

    APT_BASE.csv     — one row per airport: ICAO/FAA ident, name, location,
                       elevation, magnetic variation
    APT_RWY.csv      — one row per runway: dimensions, surface, lighting
    APT_RWY_END.csv  — two rows per runway (one per end): exact threshold
                       lat/lon, true alignment, marking type, displaced
                       threshold offset, TDZ elevation, approach lighting

Usage:
    python tools/build_airport_db.py [--nasr-dir DIR] [--output PATH]

Defaults:
    --nasr-dir  pyEfis/nasr
    --output    pyEfis/nasr/airports.sqlite

The build joins the three CSVs on (SITE_NO, RWY_ID, RWY_END_ID) and
writes a single SQLite file. SVS loads this at runtime via the
``NASRAirportDB`` class in ``pyefis.instruments.ai.airport_db``.

Total dataset is ~80k rows, completes in a few seconds. Re-run after
each NASR cycle (28-day update from the FAA).
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

# Resolve repo-root relative defaults so this works regardless of CWD.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_NASR = _REPO_ROOT / "nasr"
_DEFAULT_OUT  = _REPO_ROOT / "nasr" / "airports.sqlite"


SCHEMA = """
CREATE TABLE IF NOT EXISTS airports (
    site_no   TEXT PRIMARY KEY,
    icao      TEXT NOT NULL,         -- ARPT_ID, e.g. "KSBA"
    name      TEXT,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL,
    elev_ft   REAL,
    mag_var   REAL,                  -- signed: +E, -W
    state     TEXT,
    city      TEXT
);

CREATE INDEX IF NOT EXISTS idx_airports_lat ON airports(lat);
CREATE INDEX IF NOT EXISTS idx_airports_icao ON airports(icao);

CREATE TABLE IF NOT EXISTS runways (
    site_no    TEXT NOT NULL,
    rwy_id     TEXT NOT NULL,        -- e.g. "07/25"
    length_ft  REAL,
    width_ft   REAL,
    surface    TEXT,                 -- "ASPH", "CONC", "TURF", ...
    lighting   TEXT,                 -- "HIGH", "MED", "LOW", "NSTD", ""
    PRIMARY KEY (site_no, rwy_id)
);

CREATE TABLE IF NOT EXISTS runway_ends (
    site_no              TEXT NOT NULL,
    rwy_id               TEXT NOT NULL,
    end_id               TEXT NOT NULL,   -- e.g. "07" or "25L"
    true_alignment_deg   REAL,
    lat                  REAL,
    lon                  REAL,
    elev_ft              REAL,
    displaced_thr_lat    REAL,
    displaced_thr_lon    REAL,
    displaced_thr_len_ft REAL,
    tdz_elev_ft          REAL,
    marking_type         TEXT,            -- "BSC" / "NPI" / "PIR" / "NSTD" / ""
    apch_lgt_code        TEXT,            -- "P2L", "ALSF1", "MALSR", ...
    end_lgts_flag        TEXT,            -- "Y" / "N"
    cntrln_lgts_flag     TEXT,
    tdz_lgt_flag         TEXT,
    PRIMARY KEY (site_no, rwy_id, end_id)
);
"""


def _f(s: str) -> float | None:
    """Parse a NASR numeric field. Empty string → None."""
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _signed_mag_var(varn_str: str, hemis: str) -> float | None:
    """NASR splits MAG_VARN (degrees, unsigned) from MAG_HEMIS (E/W).
    Return a single signed float: +E, -W."""
    v = _f(varn_str)
    if v is None:
        return None
    return -v if hemis.strip().upper() == "W" else v


def _open_csv(path: Path):
    """NASR CSVs are UTF-8 with double-quoted fields. Open with newline=''
    so csv.reader handles embedded newlines correctly."""
    return open(path, encoding="utf-8", newline="")


def build(nasr_dir: Path, out_path: Path) -> dict:
    apt_base = nasr_dir / "APT_BASE.csv"
    apt_rwy  = nasr_dir / "APT_RWY.csv"
    apt_end  = nasr_dir / "APT_RWY_END.csv"
    for p in (apt_base, apt_rwy, apt_end):
        if not p.is_file():
            raise FileNotFoundError(p)

    # Fresh DB so re-runs are deterministic (cycle data fully replaced).
    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {"airports": 0, "runways": 0, "runway_ends": 0}
    t0 = time.perf_counter()

    con = sqlite3.connect(out_path)
    con.executescript(SCHEMA)

    # --- Airports ----------------------------------------------------------
    with _open_csv(apt_base) as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            lat = _f(r.get("LAT_DECIMAL", ""))
            lon = _f(r.get("LONG_DECIMAL", ""))
            if lat is None or lon is None:
                continue
            rows.append((
                r["SITE_NO"].strip(),
                r["ARPT_ID"].strip(),
                r.get("ARPT_NAME", "").strip(),
                lat, lon,
                _f(r.get("ELEV", "")),
                _signed_mag_var(r.get("MAG_VARN", ""), r.get("MAG_HEMIS", "")),
                r.get("STATE_CODE", "").strip(),
                r.get("CITY", "").strip(),
            ))
        con.executemany(
            "INSERT OR REPLACE INTO airports VALUES (?,?,?,?,?,?,?,?,?)", rows)
        counts["airports"] = len(rows)

    # --- Runways -----------------------------------------------------------
    with _open_csv(apt_rwy) as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append((
                r["SITE_NO"].strip(),
                r["RWY_ID"].strip(),
                _f(r.get("RWY_LEN", "")),
                _f(r.get("RWY_WIDTH", "")),
                r.get("SURFACE_TYPE_CODE", "").strip(),
                r.get("RWY_LGT_CODE", "").strip(),
            ))
        con.executemany(
            "INSERT OR REPLACE INTO runways VALUES (?,?,?,?,?,?)", rows)
        counts["runways"] = len(rows)

    # --- Runway ends -------------------------------------------------------
    with _open_csv(apt_end) as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            lat = _f(r.get("LAT_DECIMAL", ""))
            lon = _f(r.get("LONG_DECIMAL", ""))
            if lat is None or lon is None:
                continue
            rows.append((
                r["SITE_NO"].strip(),
                r["RWY_ID"].strip(),
                r["RWY_END_ID"].strip(),
                _f(r.get("TRUE_ALIGNMENT", "")),
                lat, lon,
                _f(r.get("RWY_END_ELEV", "")),
                _f(r.get("LAT_DISPLACED_THR_DECIMAL", "")),
                _f(r.get("LONG_DISPLACED_THR_DECIMAL", "")),
                _f(r.get("DISPLACED_THR_LEN", "")),
                _f(r.get("TDZ_ELEV", "")),
                r.get("RWY_MARKING_TYPE_CODE", "").strip(),
                r.get("APCH_LGT_SYSTEM_CODE", "").strip(),
                r.get("RWY_END_LGTS_FLAG", "").strip(),
                r.get("CNTRLN_LGTS_AVBL_FLAG", "").strip(),
                r.get("TDZ_LGT_AVBL_FLAG", "").strip(),
            ))
        con.executemany(
            "INSERT OR REPLACE INTO runway_ends VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        counts["runway_ends"] = len(rows)

    con.commit()
    con.close()
    counts["seconds"] = round(time.perf_counter() - t0, 2)
    counts["output"] = str(out_path)
    counts["output_size_mb"] = round(out_path.stat().st_size / (1024 * 1024), 2)
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--nasr-dir", type=Path, default=_DEFAULT_NASR,
                    help=f"Directory with APT_BASE/RWY/RWY_END CSVs (default: {_DEFAULT_NASR})")
    ap.add_argument("--output", type=Path, default=_DEFAULT_OUT,
                    help=f"Output SQLite path (default: {_DEFAULT_OUT})")
    args = ap.parse_args()

    try:
        counts = build(args.nasr_dir, args.output)
    except FileNotFoundError as e:
        print(f"error: required NASR file not found: {e}", file=sys.stderr)
        return 2

    print(f"Built {counts['output']} ({counts['output_size_mb']} MB) in {counts['seconds']} s:")
    print(f"  airports     : {counts['airports']:>6}")
    print(f"  runways      : {counts['runways']:>6}")
    print(f"  runway_ends  : {counts['runway_ends']:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
