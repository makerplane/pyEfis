#  SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for tools/build_airport_db.py -- NASR APT CSVs -> sqlite.

Focused on NASR 26-01 DPN robustness (effective 03 Sep 2026): APT_RWY.csv gains
a PAVEMENT CLASSIFICATION column and its PCN number widens from 3 to 4 chars.
The builder reads by column name and never reads pavement fields, so the built
database must be byte-for-byte unchanged. This proves the "none structurally"
claim in makerplane-data docs/nasr_2601_dpn_prep.md section 3 rather than
asserting it. Plain pytest + tmp_path.
"""

import csv
import importlib.util
import sqlite3
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_OPEN = []


@pytest.fixture(autouse=True)
def _close_connections():
    yield
    while _OPEN:
        _OPEN.pop().close()


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ba = _load("build_airport_db")


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


APT_BASE_HEADER = ["SITE_NO", "ARPT_ID", "ARPT_NAME", "LAT_DECIMAL",
                   "LONG_DECIMAL", "ELEV", "MAG_VARN", "MAG_HEMIS",
                   "STATE_CODE", "CITY"]
APT_BASE_ROWS = [
    ("0001", "KAAA", "ALPHA FIELD", "34.0", "-119.0", "100", "13", "E", "CA", "ALPHATOWN"),
    ("0002", "KBBB", "BRAVO FIELD", "35.0", "-118.0", "250", "12", "E", "CA", "BRAVOCITY"),
]

RWY_END_HEADER = ["SITE_NO", "RWY_ID", "RWY_END_ID", "TRUE_ALIGNMENT",
                  "LAT_DECIMAL", "LONG_DECIMAL", "RWY_END_ELEV",
                  "LAT_DISPLACED_THR_DECIMAL", "LONG_DISPLACED_THR_DECIMAL",
                  "DISPLACED_THR_LEN", "TDZ_ELEV", "RWY_MARKING_TYPE_CODE",
                  "APCH_LGT_SYSTEM_CODE", "RWY_END_LGTS_FLAG",
                  "CNTRLN_LGTS_AVBL_FLAG", "TDZ_LGT_AVBL_FLAG"]
RWY_END_ROWS = [
    ("0001", "07/25", "07", "70", "34.00", "-119.00", "100", "", "", "", "", "PIR", "MALSR", "Y", "Y", "Y"),
    ("0001", "07/25", "25", "250", "34.01", "-119.01", "101", "", "", "", "", "PIR", "", "N", "N", "N"),
]

# Pre-DPN vs post-DPN APT_RWY: post adds the PAVEMENT CLASSIFICATION column and
# a 4-char PCN. The builder reads only SITE_NO/RWY_ID/RWY_LEN/RWY_WIDTH/
# SURFACE_TYPE_CODE/RWY_LGT_CODE, none of them pavement, so output is unchanged.
RWY_PRE_HEADER = ["SITE_NO", "RWY_ID", "RWY_LEN", "RWY_WIDTH",
                  "SURFACE_TYPE_CODE", "PCN", "RWY_LGT_CODE"]
RWY_PRE_ROWS = [("0001", "07/25", "5000", "100", "ASPH", "45", "HIGH")]

RWY_POST_HEADER = ["SITE_NO", "RWY_ID", "RWY_LEN", "RWY_WIDTH",
                   "SURFACE_TYPE_CODE", "PCN", "PAVEMENT CLASSIFICATION",
                   "RWY_LGT_CODE"]
RWY_POST_ROWS = [("0001", "07/25", "5000", "100", "ASPH", "1234", "PCR", "HIGH")]


def _build(dir_, rwy_header, rwy_rows):
    dir_.mkdir(parents=True)
    _write(dir_ / "APT_BASE.csv", APT_BASE_HEADER, APT_BASE_ROWS)
    _write(dir_ / "APT_RWY.csv", rwy_header, rwy_rows)
    _write(dir_ / "APT_RWY_END.csv", RWY_END_HEADER, RWY_END_ROWS)
    out = dir_ / "airports.sqlite"
    ba.build(dir_, out)
    con = sqlite3.connect(out)
    _OPEN.append(con)
    return con


def _dump(con):
    return {t: con.execute(f"SELECT * FROM {t} ORDER BY 1, 2, 3").fetchall()
            for t in ("airports", "runways", "runway_ends")}


def test_pavement_classification_column_does_not_change_output(tmp_path):
    pre = _build(tmp_path / "pre", RWY_PRE_HEADER, RWY_PRE_ROWS)
    post = _build(tmp_path / "post", RWY_POST_HEADER, RWY_POST_ROWS)
    assert _dump(pre) == _dump(post)


def test_build_reads_expected_rows(tmp_path):
    """Sanity: the fixture actually populates all three tables (so the identity
    test above is comparing real data, not two empty databases)."""
    con = _build(tmp_path / "x", RWY_PRE_HEADER, RWY_PRE_ROWS)
    d = _dump(con)
    assert len(d["airports"]) == 2
    assert len(d["runways"]) == 1
    assert len(d["runway_ends"]) == 2
