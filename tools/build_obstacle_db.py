#!/usr/bin/env python3
"""
Build obstacles.sqlite from the FAA Digital Obstacle File (DOF) CSV.

Source data:
    DOF.CSV from https://aeronav.faa.gov/Obst_Data/DAILY_DOF_CSV.ZIP
    (~96 MB extracted, ~636k records nationwide, 56-day update cycle)

The DOF carries every charted obstacle in US airspace: towers, antennas,
tall buildings, stacks, water tanks, oil rigs, wind turbines, cranes...
Each row has lat/lon, AGL height, AMSL elevation, lighting and marking.

Usage:
    python tools/build_obstacle_db.py [--dof-dir DIR] [--output PATH]

Defaults:
    --dof-dir  pyEfis/dof
    --output   pyEfis/dof/obstacles.sqlite

No height filtering is applied at import time — that's a runtime config
on the SVS renderer. Storing everything lets the user change min-AGL
thresholds without rebuilding.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

_REPO_ROOT     = Path(__file__).resolve().parent.parent
_DEFAULT_DOF   = _REPO_ROOT / "dof"
_DEFAULT_OUT   = _REPO_ROOT / "dof" / "obstacles.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS obstacles (
    oas_no    TEXT PRIMARY KEY,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL,
    amsl_ft   REAL NOT NULL,        -- tip elevation, ft MSL
    agl_ft    REAL NOT NULL,        -- height above ground, ft
    type      TEXT,                 -- "TOWER", "ANTENNA", "BLDG", "STACK", "WIND TURB", ...
    quantity  INTEGER,              -- number of objects at this site (usually 1)
    lighting  TEXT,                 -- R=red, W=white, D=dual, M=marked, N=none, U=unknown
    marking   TEXT,
    state     TEXT,
    city      TEXT
);

-- Range queries scan by lat first; (lat, lon) index lets the lon WHERE
-- clause filter against the same row set without extra IO.
CREATE INDEX IF NOT EXISTS idx_obstacles_lat ON obstacles(lat);
CREATE INDEX IF NOT EXISTS idx_obstacles_agl ON obstacles(agl_ft);
"""


def _f(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _i(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def build(dof_dir: Path, out_path: Path) -> dict:
    dof_csv = dof_dir / "DOF.CSV"
    if not dof_csv.is_file():
        # Try lowercase too — naming on FAA's site has shifted.
        alt = dof_dir / "DOF.csv"
        if alt.is_file():
            dof_csv = alt
        else:
            raise FileNotFoundError(dof_csv)

    if out_path.exists():
        out_path.unlink()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {"obstacles": 0, "dropped_no_position": 0}
    t0 = time.perf_counter()

    con = sqlite3.connect(out_path)
    con.executescript(SCHEMA)

    rows = []
    # FAA's DOF.CSV is Latin-1 (windows-1252 compatible) — there are accented
    # city names that aren't valid UTF-8.
    with open(dof_csv, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            lat = _f(r.get("LATDEC", ""))
            lon = _f(r.get("LONDEC", ""))
            amsl = _f(r.get("AMSL", ""))
            agl  = _f(r.get("AGL", ""))
            if lat is None or lon is None or amsl is None or agl is None:
                counts["dropped_no_position"] += 1
                continue
            rows.append((
                r["OAS"].strip(),
                lat, lon, amsl, agl,
                (r.get("TYPE", "") or "").strip(),
                _i(r.get("QUANTITY", "")) or 1,
                (r.get("LIGHTING", "") or "").strip(),
                (r.get("MARKING",  "") or "").strip(),
                (r.get("STATE", "") or "").strip(),
                (r.get("CITY",  "") or "").strip(),
            ))
            if len(rows) >= 10000:
                con.executemany(
                    "INSERT OR REPLACE INTO obstacles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    rows)
                counts["obstacles"] += len(rows)
                rows = []
    if rows:
        con.executemany(
            "INSERT OR REPLACE INTO obstacles VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        counts["obstacles"] += len(rows)

    con.commit()
    con.close()
    counts["seconds"] = round(time.perf_counter() - t0, 2)
    counts["output"] = str(out_path)
    counts["output_size_mb"] = round(out_path.stat().st_size / (1024 * 1024), 2)
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dof-dir", type=Path, default=_DEFAULT_DOF,
                    help=f"Directory containing DOF.CSV (default: {_DEFAULT_DOF})")
    ap.add_argument("--output", type=Path, default=_DEFAULT_OUT,
                    help=f"Output SQLite path (default: {_DEFAULT_OUT})")
    args = ap.parse_args()

    try:
        counts = build(args.dof_dir, args.output)
    except FileNotFoundError as e:
        print(f"error: required DOF file not found: {e}", file=sys.stderr)
        return 2

    print(f"Built {counts['output']} ({counts['output_size_mb']} MB) in {counts['seconds']} s:")
    print(f"  obstacles            : {counts['obstacles']:>7}")
    print(f"  dropped (no position): {counts['dropped_no_position']:>7}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
