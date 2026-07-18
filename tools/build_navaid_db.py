#!/usr/bin/env python3
#  SPDX-License-Identifier: GPL-2.0-or-later
"""Build navaids.sqlite from FAA NASR NAV / FIX / AWY CSVs.

Feeds the moving map's navaid, fix and airway layers
(docs/moving_map_spec.md 5.3). Mirrors tools/build_airport_db.py:
plain stdlib, produces a self-contained sqlite consumed on-device.

    python tools/build_navaid_db.py \
        --nav NAV_BASE.csv --fix FIX_BASE.csv --awy AWY_BASE.csv \
        -o navaids.sqlite

    # or point at a directory holding the extracted NAV/FIX/AWY CSV zips
    # (the makerplane-data pack pipeline calls it this way):
    python tools/build_navaid_db.py --nasr-dir extracted/ -o navaids.sqlite

Tables:
  navaids(id, type, name, freq, elev_ft, lat, lon)
  fixes(id, use_code, lat, lon)
  awy_segments(awy_id, seq, p1, lat1, lon1, p2, lat2, lon2)

Airway geometry comes from AWY_BASE.AIRWAY_STRING (ordered point
names) joined against the fix/navaid coordinates. Points whose name
is ambiguous (duplicate id with different coordinates) or unknown are
skipped; the polyline connects across the gap.
"""

import argparse
import csv
import sqlite3
from pathlib import Path

# SP = SPECIAL ROUTE (NASR 26-01 DPN, effective 03 Sep 2026): non-regulatory
# ZK helicopter-air-ambulance RNAV routes. Per the FAA they are "not included
# on public charts" and may not be filed or flown without Flight Standards
# approval -- so they must never be drawn on the moving map. Filter them out at
# build time by their AWY_DESIGNATION. See makerplane-data
# docs/nasr_2601_dpn_prep.md section 4. No SP rows exist before the 03 Sep
# cycle, so this is a no-op on every current pack.
EXCLUDE_AWY_DESIGNATIONS = frozenset({"SP"})


def _find_csv(root, name):
    hits = sorted(Path(root).rglob(name))
    if not hits:
        raise SystemExit(f"{name} not found under {root}")
    return str(hits[0])


def _f(row, key):
    v = (row.get(key) or "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def load_navaids(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            lat, lon = _f(r, "LAT_DECIMAL"), _f(r, "LONG_DECIMAL")
            if lat is None or lon is None:
                continue
            out.append(((r.get("NAV_ID") or "").strip(),
                        (r.get("NAV_TYPE") or "").strip(),
                        (r.get("NAME") or "").strip().title(),
                        (r.get("FREQ") or "").strip(),
                        _f(r, "ELEV"), lat, lon))
    return out


def load_fixes(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            lat, lon = _f(r, "LAT_DECIMAL"), _f(r, "LONG_DECIMAL")
            if lat is None or lon is None:
                continue
            out.append(((r.get("FIX_ID") or "").strip(),
                        (r.get("FIX_USE_CODE") or "").strip(), lat, lon))
    return out


def point_lookup(navaids, fixes):
    """name -> (lat, lon); ambiguous names (conflicting coords beyond
    ~1 NM) are dropped so airways never jump continents."""
    pts, dead = {}, set()
    for name, _t, _n, _f2, _e, lat, lon in navaids:
        _add(pts, dead, name, lat, lon)
    for name, _u, lat, lon in fixes:
        _add(pts, dead, name, lat, lon)
    for name in dead:
        pts.pop(name, None)
    return pts


def _add(pts, dead, name, lat, lon):
    if not name or name in dead:
        return
    old = pts.get(name)
    if old is None:
        pts[name] = (lat, lon)
    elif abs(old[0] - lat) + abs(old[1] - lon) > 0.02:
        dead.add(name)


def load_airways(path, pts):
    segs = []
    skipped = 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if (r.get("AWY_DESIGNATION") or "").strip() in EXCLUDE_AWY_DESIGNATIONS:
                skipped += 1          # SP special routes -- never charted
                continue
            awy = (r.get("AWY_ID") or "").strip()
            chain = [(n, pts[n]) for n in
                     (r.get("AIRWAY_STRING") or "").split()
                     if n in pts]
            for i, ((n1, c1), (n2, c2)) in enumerate(
                    zip(chain, chain[1:])):
                segs.append((awy, i, n1, c1[0], c1[1], n2, c2[0], c2[1]))
    return segs, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nav")
    ap.add_argument("--fix")
    ap.add_argument("--awy")
    ap.add_argument("--nasr-dir",
                    help="directory holding extracted NAV/FIX/AWY CSVs; "
                         "stands in for any of --nav/--fix/--awy")
    ap.add_argument("-o", "--output", default="navaids.sqlite")
    args = ap.parse_args(argv)

    if args.nasr_dir:
        args.nav = args.nav or _find_csv(args.nasr_dir, "NAV_BASE.csv")
        args.fix = args.fix or _find_csv(args.nasr_dir, "FIX_BASE.csv")
        args.awy = args.awy or _find_csv(args.nasr_dir, "AWY_BASE.csv")
    if not (args.nav and args.fix and args.awy):
        ap.error("provide --nav/--fix/--awy or --nasr-dir")

    navaids = load_navaids(args.nav)
    fixes = load_fixes(args.fix)
    pts = point_lookup(navaids, fixes)
    segs, skipped_awy = load_airways(args.awy, pts)

    con = sqlite3.connect(args.output)
    cur = con.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS navaids;
        DROP TABLE IF EXISTS fixes;
        DROP TABLE IF EXISTS awy_segments;
        CREATE TABLE navaids (id TEXT, type TEXT, name TEXT, freq TEXT,
                              elev_ft REAL, lat REAL, lon REAL);
        CREATE TABLE fixes (id TEXT, use_code TEXT, lat REAL, lon REAL);
        CREATE TABLE awy_segments (awy_id TEXT, seq INTEGER,
                                   p1 TEXT, lat1 REAL, lon1 REAL,
                                   p2 TEXT, lat2 REAL, lon2 REAL);
    """)
    cur.executemany("INSERT INTO navaids VALUES (?,?,?,?,?,?,?)", navaids)
    cur.executemany("INSERT INTO fixes VALUES (?,?,?,?)", fixes)
    cur.executemany("INSERT INTO awy_segments VALUES (?,?,?,?,?,?,?,?)",
                    segs)
    cur.executescript("""
        CREATE INDEX idx_nav_ll ON navaids(lat, lon);
        CREATE INDEX idx_fix_ll ON fixes(lat, lon);
        CREATE INDEX idx_seg_ll ON awy_segments(lat1, lon1);
    """)
    con.commit()
    con.close()
    # The "skipped N special routes" count always prints (even at 0) so a CI log
    # reader can see the SP filter ran, per docs/nasr_2601_dpn_prep.md section 4.
    print("wrote %s: %d navaids, %d fixes, %d airway segments "
          "(skipped %d special routes)"
          % (args.output, len(navaids), len(fixes), len(segs), skipped_awy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
