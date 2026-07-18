"""Airport DB backend selection + multi-provider merge.

Airport data is provider-based: a US FAA NASR primary plus optional
supplemental packs (e.g. Canada) auto-discovered under a provider directory and
merged at query time."""
import sqlite3
from pathlib import Path

from pyefis.instruments.ai.airport_db import (
    make_airport_db, NASRAirportDB, _MultiAirportDB)

SCHEMA = """
CREATE TABLE airports (site_no TEXT PRIMARY KEY, icao TEXT NOT NULL, name TEXT,
  lat REAL NOT NULL, lon REAL NOT NULL, elev_ft REAL, mag_var REAL, state TEXT, city TEXT);
CREATE TABLE runways (site_no TEXT, rwy_id TEXT, length_ft REAL, width_ft REAL,
  surface TEXT, lighting TEXT, PRIMARY KEY (site_no, rwy_id));
CREATE TABLE runway_ends (site_no TEXT, rwy_id TEXT, end_id TEXT, true_alignment_deg REAL,
  lat REAL, lon REAL, elev_ft REAL, displaced_thr_lat REAL, displaced_thr_lon REAL,
  displaced_thr_len_ft REAL, tdz_elev_ft REAL, marking_type TEXT, apch_lgt_code TEXT,
  end_lgts_flag TEXT, cntrln_lgts_flag TEXT, tdz_lgt_flag TEXT,
  PRIMARY KEY (site_no, rwy_id, end_id));
"""


def _mkdb(path, rows):
    """rows: (site_no, icao, lat, lon). Each gets one paved runway w/ 2 ends so
    airports_in_range yields it (it skips runway-less airports)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for site, icao, lat, lon in rows:
        con.execute("INSERT INTO airports VALUES (?,?,?,?,?,?,?,?,?)",
                    (site, icao, icao, lat, lon, 100, 0, "ST", "City"))
        con.execute("INSERT INTO runways VALUES (?,?,?,?,?,?)",
                    (site, "09/27", 5000, 100, "ASPH", "HIGH"))
        for end, dlon in (("09", -0.005), ("27", 0.005)):
            con.execute("INSERT INTO runway_ends VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (site, "09/27", end, 90, lat, lon + dlon, 100,
                         None, None, 0, None, "", "", "", "", ""))
    con.commit()
    con.close()


def test_single_nasr_returns_plain_db(tmp_path):
    p = tmp_path / "navdata/current/airports.sqlite"
    _mkdb(p, [("1", "KABC", 42.3, -83.0)])
    db = make_airport_db({"nasr_db_path": str(p)})
    assert isinstance(db, NASRAirportDB)        # no provider dir -> single backend


def test_provider_dir_merges_us_and_canada(tmp_path):
    us = tmp_path / "navdata/current/airports.sqlite"
    _mkdb(us, [("1", "KABC", 42.30, -83.00)])
    prov = tmp_path / "airports"
    _mkdb(prov / "airports-canada/current/airports.sqlite", [("CYQG", "CYQG", 42.28, -82.96)])

    db = make_airport_db({"nasr_db_path": str(us),
                          "airport_provider_dir": str(prov)})
    assert isinstance(db, _MultiAirportDB) and db.ready
    got = {a.icao for a in db.airports_in_range(42.29, -82.98, 30)}
    assert "KABC" in got and "CYQG" in got      # US + CA merged


def test_provider_only_no_primary(tmp_path):
    """Provider packs work even with no US primary configured."""
    prov = tmp_path / "airports"
    _mkdb(prov / "airports-canada/current/airports.sqlite", [("CYQG", "CYQG", 42.28, -82.96)])
    db = make_airport_db({"airport_provider_dir": str(prov)})
    assert db.ready
    got = {a.icao for a in db.airports_in_range(42.28, -82.96, 20)}
    assert got == {"CYQG"}


def test_multi_dedups_by_icao(tmp_path):
    """An airport carried by two providers appears once (primary wins)."""
    a = tmp_path / "a/airports.sqlite"
    b = tmp_path / "b/airports.sqlite"
    _mkdb(a, [("1", "CYQG", 42.28, -82.96)])
    _mkdb(b, [("CYQG", "CYQG", 42.28, -82.96)])
    multi = _MultiAirportDB([NASRAirportDB(str(a)), NASRAirportDB(str(b))])
    got = [ap for ap in multi.airports_in_range(42.28, -82.96, 20)]
    assert len(got) == 1 and got[0].icao == "CYQG"


def test_no_data_is_empty_stub():
    db = make_airport_db({})
    assert db.ready is False
    assert list(db.airports_in_range(0, 0, 50)) == []
