"""
Airport / runway database for the SVS renderer.

Two backends, both exposing the same range-based query API:

    db = AirportDB(...)
    for ap in db.airports_in_range(ac_lat, ac_lon, range_nm):
        ap.icao, ap.name, ap.ref_lat, ap.ref_lon, ap.elev_ft
        for rwy in ap.runways:
            rwy.thr1_lat, rwy.thr1_lon, rwy.thr1_elev_ft, ...

* ``NASRAirportDB`` — reads ``airports.sqlite`` built from FAA NASR CSVs
  (see ``tools/build_airport_db.py``). Carries real runway widths,
  displaced-threshold offsets, marking type, TDZ elevation, approach
  lighting — everything needed to render Tier C surface markings.

* ``CIFPAirportDB`` — wraps ``pyavtools.CIFPObjects`` (the same FAA CIFP
  data source used by Virtual VFR). Coarser detail: no width, no marking
  type, but works if a user only has the CIFP download.

``make_airport_db(svs_config)`` picks the best available backend.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

NM_PER_DEG_LAT = 60.0           # 1° of latitude ≈ 60 NM
DEFAULT_RWY_WIDTH_FT = 100.0    # used when source data lacks width

# RWY_MARKING_TYPE_CODE values from FAA NASR (APT_RWY_END):
#   "PIR" — precision instrument runway (full TDZ, side stripes, aim point)
#   "NPI" — non-precision instrument (threshold bars, aim point, no TDZ)
#   "BSC" — basic / visual (designator, centerline only)
#   "NSTD", "" — non-standard or unknown
MARKING_PRECISION = "PIR"
MARKING_NONPRECISION = "NPI"
MARKING_BASIC = "BSC"


@dataclass
class RunwayRecord:
    airport_id : str
    name       : str             # e.g. "07" or "25L"
    thr1_lat   : float
    thr1_lon   : float
    thr1_elev_ft : float
    thr2_lat   : float
    thr2_lon   : float
    thr2_elev_ft : float
    length_ft  : float
    bearing_deg: float           # true bearing thr1 → thr2
    width_ft   : float = DEFAULT_RWY_WIDTH_FT
    # Optional Tier C fields — populated by NASR backend; empty/zero from CIFP.
    thr1_designator : str = ""   # e.g. "07" or "25L"
    thr2_designator : str = ""
    thr1_marking    : str = ""   # PIR / NPI / BSC / ""
    thr2_marking    : str = ""
    thr1_displaced_ft : float = 0.0
    thr2_displaced_ft : float = 0.0
    thr1_tdz_elev_ft  : float = 0.0
    thr2_tdz_elev_ft  : float = 0.0
    thr1_apch_lgt   : str = ""   # "MALSR", "ALSF1", "P2L", ...
    thr2_apch_lgt   : str = ""


@dataclass
class AirportRecord:
    icao    : str
    name    : str
    ref_lat : float
    ref_lon : float
    elev_ft : float
    runways : list[RunwayRecord] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NASR sqlite backend
# ---------------------------------------------------------------------------
class NASRAirportDB:
    """SVS airport/runway data source backed by ``airports.sqlite`` —
    built once by ``tools/build_airport_db.py`` from the FAA NASR CSVs."""

    def __init__(self, sqlite_path: str | Path | None, paved_only=True):
        # Filter to paved runways (ASPH/CONC/PEM
        # substrings); airports left with no
        # runways drop entirely — flight-tested
        # declutter (DFW turf strips).
        self._paved_only = bool(paved_only)
        self._path = Path(sqlite_path) if sqlite_path else None
        self._con: sqlite3.Connection | None = None
        if self._path is None or not self._path.is_file():
            log.info("NASRAirportDB: %s not found — falling back", self._path)
            return
        try:
            self._con = sqlite3.connect(str(self._path),
                                        check_same_thread=False)
            self._con.row_factory = sqlite3.Row
        except Exception as e:
            log.warning("NASRAirportDB: cannot open %s: %s", self._path, e)
            self._con = None

    @property
    def ready(self) -> bool:
        return self._con is not None

    def airports_in_range(self, ac_lat: float, ac_lon: float,
                          range_nm: float):
        if not self.ready:
            return
        lat_cos = math.cos(math.radians(ac_lat))
        range_deg_lat = range_nm / NM_PER_DEG_LAT
        range_deg_lon = range_deg_lat / max(lat_cos, 1e-6)
        lat_lo = ac_lat - range_deg_lat
        lat_hi = ac_lat + range_deg_lat
        lon_lo = ac_lon - range_deg_lon
        lon_hi = ac_lon + range_deg_lon

        # First pass: airports within the bounding box.
        cur = self._con.execute(
            "SELECT site_no, icao, name, lat, lon, elev_ft "
            "FROM airports "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (lat_lo, lat_hi, lon_lo, lon_hi))
        airport_rows = cur.fetchall()
        if not airport_rows:
            return

        range_nm_sq = range_nm * range_nm
        for ar in airport_rows:
            d_lat = (ar["lat"] - ac_lat) * NM_PER_DEG_LAT
            d_lon = (ar["lon"] - ac_lon) * NM_PER_DEG_LAT * lat_cos
            if d_lat * d_lat + d_lon * d_lon > range_nm_sq:
                continue
            runways = list(self._runways_for(ar["site_no"]))
            if not runways:
                continue
            icao = ar["icao"]
            # NASR's ARPT_ID is FAA-style (no leading K for CONUS); add it
            # so labels and lookup keys match how pilots refer to airports.
            if icao and len(icao) == 3 and icao.isalpha():
                icao = "K" + icao
            yield AirportRecord(
                icao=icao,
                name=(ar["name"] or "").title(),
                ref_lat=ar["lat"], ref_lon=ar["lon"],
                elev_ft=ar["elev_ft"] or 0.0,
                runways=runways)

    def _runways_for(self, site_no: str):
        # Fetch all runways and ends for this site, then pair each end pair
        # into a single RunwayRecord.
        rwys = self._con.execute(
            "SELECT rwy_id, length_ft, width_ft, surface FROM runways "
            "WHERE site_no = ?", (site_no,)).fetchall()
        if self._paved_only:
            rwys = [r for r in rwys
                    if any(t in (r["surface"] or "").upper()
                           for t in ("ASPH", "CONC", "PEM"))]
        ends_by_rwy: dict[str, list] = {}
        for e in self._con.execute(
            "SELECT * FROM runway_ends WHERE site_no = ?", (site_no,)):
            ends_by_rwy.setdefault(e["rwy_id"], []).append(e)

        for r in rwys:
            ends = ends_by_rwy.get(r["rwy_id"], [])
            if len(ends) < 2:
                continue   # need both ends to draw a quad
            # Sort by numeric designator so "07/25" yields end "07" first.
            ends.sort(key=lambda x: _designator_sort_key(x["end_id"]))
            a, b = ends[0], ends[1]
            if a["lat"] is None or b["lat"] is None:
                continue
            yield RunwayRecord(
                airport_id=site_no, name=r["rwy_id"],
                thr1_lat=a["lat"], thr1_lon=a["lon"],
                thr1_elev_ft=a["elev_ft"] or 0.0,
                thr2_lat=b["lat"], thr2_lon=b["lon"],
                thr2_elev_ft=b["elev_ft"] or 0.0,
                length_ft=r["length_ft"] or 0.0,
                bearing_deg=a["true_alignment_deg"] or 0.0,
                width_ft=r["width_ft"] or DEFAULT_RWY_WIDTH_FT,
                thr1_designator=a["end_id"] or "",
                thr2_designator=b["end_id"] or "",
                thr1_marking=(a["marking_type"] or "").strip(),
                thr2_marking=(b["marking_type"] or "").strip(),
                thr1_displaced_ft=a["displaced_thr_len_ft"] or 0.0,
                thr2_displaced_ft=b["displaced_thr_len_ft"] or 0.0,
                thr1_tdz_elev_ft=a["tdz_elev_ft"] or 0.0,
                thr2_tdz_elev_ft=b["tdz_elev_ft"] or 0.0,
                thr1_apch_lgt=(a["apch_lgt_code"] or "").strip(),
                thr2_apch_lgt=(b["apch_lgt_code"] or "").strip(),
            )


def _designator_sort_key(end_id: str):
    """Sort key so '07' < '25' and 'L'/'C'/'R' suffixes stay grouped."""
    s = (end_id or "").strip()
    digits = "".join(c for c in s if c.isdigit())
    suffix = "".join(c for c in s if not c.isdigit())
    try:
        n = int(digits) if digits else 99
    except ValueError:
        n = 99
    return (n, suffix)


# ---------------------------------------------------------------------------
# CIFP backend (existing behaviour — kept for users without NASR)
# ---------------------------------------------------------------------------
class CIFPAirportDB:
    """Range-queryable airport/runway database backed by FAA CIFP data.

    Construction never raises — if the CIFP files are missing or the import
    fails, ``ready`` stays False and ``airports_in_range`` yields nothing.
    """

    def __init__(self, cifp_path: str | Path | None,
                 index_path: str | Path | None):
        self._cifp_path  = Path(cifp_path)  if cifp_path  else None
        self._index_path = Path(index_path) if index_path else None
        # Block cache: { (int_lat, int_lng): [CIFPObjects.Airport | Runway | Navaid, ...] }
        self._block_cache: dict[tuple[int, int], list] = {}
        self._cifp_module = None

        if self._cifp_path is None or self._index_path is None:
            return
        if not self._cifp_path.is_file() or not self._index_path.is_file():
            log.info("AirportDB: CIFP not found at %s / %s — runways disabled",
                     self._cifp_path, self._index_path)
            return
        try:
            import pyavtools.CIFPObjects as _cifp
        except Exception as e:
            log.warning("AirportDB: failed to import pyavtools.CIFPObjects: %s", e)
            return
        self._cifp_module = _cifp

    @property
    def ready(self) -> bool:
        return self._cifp_module is not None

    # ------------------------------------------------------------------
    # Public query
    # ------------------------------------------------------------------
    def airports_in_range(self, ac_lat: float, ac_lon: float,
                          range_nm: float):
        """Yield AirportRecord for each airport within *range_nm* of the
        aircraft. Skips airports with no matched runway pairs (which would
        produce nothing drawable anyway)."""
        if not self.ready:
            return
        lat_cos = math.cos(math.radians(ac_lat))
        range_deg_lat = range_nm / NM_PER_DEG_LAT

        # Load enough blocks to cover ±range_nm in both axes. CIFP blocks
        # are keyed by the degree-part of the latitude/longitude string
        # ("N34..."→34, "W119..."→-119), which Python's int() recovers via
        # truncation toward zero. (math.floor is wrong for negative
        # longitudes — floor(-119.84)=-120 but the index uses -119.)
        range_deg_lon = range_deg_lat / max(lat_cos, 1e-6)
        lat_min = int(ac_lat - range_deg_lat)
        lat_max = int(ac_lat + range_deg_lat)
        lon_min = int(ac_lon - range_deg_lon)
        lon_max = int(ac_lon + range_deg_lon)

        # Collect all objects from the covered blocks, matching runways
        # across block boundaries as we go.
        airports: dict[str, AirportRecord] = {}
        unmatched_rwys: dict[str, list] = {}
        for block_lat in range(lat_min, lat_max + 1):
            for block_lon in range(lon_min, lon_max + 1):
                for obj in self._block(block_lat, block_lon):
                    cls_name = obj.__class__.__name__
                    if cls_name == "Airport":
                        if obj.id not in airports:
                            airports[obj.id] = AirportRecord(
                                icao=obj.id, name=obj.name,
                                ref_lat=obj.lat, ref_lon=obj.lng,
                                elev_ft=0.0)
                    elif cls_name == "Runway":
                        unmatched_rwys.setdefault(obj.airport_id, []).append(obj)

        # Pair runways within each airport. CIFP runways come as one record
        # per threshold ("RW07" and "RW25" are the same physical strip).
        for icao, runways in unmatched_rwys.items():
            consumed = set()
            for i, a in enumerate(runways):
                if i in consumed:
                    continue
                # Find the matching opposing runway.
                partner_idx = None
                for j in range(i + 1, len(runways)):
                    if j in consumed:
                        continue
                    if self._runways_match(a, runways[j]):
                        partner_idx = j
                        break
                if partner_idx is None:
                    continue
                b = runways[partner_idx]
                consumed.add(i); consumed.add(partner_idx)

                # Establish bearing thr1→thr2. CIFP carries each runway's
                # own bearing; use the lower-numbered end as thr1 so the
                # name "07" reads naturally.
                if (b.name or "").lstrip("RW") < (a.name or "").lstrip("RW"):
                    a, b = b, a
                rec = RunwayRecord(
                    airport_id=icao, name=(a.name or "").lstrip("RW"),
                    thr1_lat=a.lat, thr1_lon=a.lng,
                    thr1_elev_ft=float(a.elevation),
                    thr2_lat=b.lat, thr2_lon=b.lng,
                    thr2_elev_ft=float(b.elevation),
                    length_ft=float(getattr(a, "length", 0) or 0),
                    bearing_deg=float(getattr(a, "bearing", 0.0) or 0.0),
                )
                ap = airports.get(icao)
                if ap is None:
                    # CIFP sometimes has runways in a block whose airport
                    # record is in a neighbouring block we haven't loaded.
                    # Fabricate a minimal airport entry so the runway still
                    # renders.
                    ap = AirportRecord(
                        icao=icao, name=icao,
                        ref_lat=(a.lat + b.lat) * 0.5,
                        ref_lon=(a.lng + b.lng) * 0.5,
                        elev_ft=float(a.elevation))
                    airports[icao] = ap
                ap.runways.append(rec)

        # Yield airports that ended up with at least one drawable runway and
        # whose reference point is actually within range_nm of the aircraft.
        range_nm_sq = range_nm * range_nm
        for ap in airports.values():
            if not ap.runways:
                continue
            d_lat = (ap.ref_lat - ac_lat) * NM_PER_DEG_LAT
            d_lon = (ap.ref_lon - ac_lon) * NM_PER_DEG_LAT * lat_cos
            if d_lat * d_lat + d_lon * d_lon > range_nm_sq:
                continue
            # Use the first runway's threshold elevation as the field elev.
            ap.elev_ft = ap.runways[0].thr1_elev_ft
            yield ap

    # ------------------------------------------------------------------
    # Internal block loader (cached)
    # ------------------------------------------------------------------
    def _block(self, block_lat: int, block_lon: int) -> list:
        key = (block_lat, block_lon)
        cached = self._block_cache.get(key)
        if cached is not None:
            return cached
        try:
            objs = self._cifp_module.find_objects(
                str(self._cifp_path), str(self._index_path),
                float(block_lat), float(block_lon))
        except Exception as e:
            log.warning("AirportDB: find_objects failed at (%d, %d): %s",
                        block_lat, block_lon, e)
            objs = []
        self._block_cache[key] = objs
        return objs

    # ------------------------------------------------------------------
    # CIFP runway pairing
    # ------------------------------------------------------------------
    @staticmethod
    def _runways_match(a, b) -> bool:
        """Loose pair test that mirrors CIFPObjects.Runway.match() without
        raising on the empty-name records VVfr's loop catches with try/except.
        Two runways pair when they share an airport and their numbers
        differ by ~18 (180° apart). Letter suffixes (L/R/C) and the W/G
        helipad suffixes must agree."""
        if a.airport_id != b.airport_id:
            return False
        na = (a.name or "").lstrip("RW")
        nb = (b.name or "").lstrip("RW")
        if not na or not nb:
            return False
        # Trailing letter suffix must match.
        def split(s):
            i = len(s)
            while i and not s[i-1].isdigit():
                i -= 1
            return s[:i], s[i:]
        num_a, suf_a = split(na)
        num_b, suf_b = split(nb)
        if suf_a != suf_b:
            return False
        try:
            ia, ib = int(num_a), int(num_b)
        except ValueError:
            return False
        diff = abs(ia - ib)
        return diff == 18


# Back-compat alias — earlier code imports ``AirportDB``.
AirportDB = CIFPAirportDB


# ---------------------------------------------------------------------------
# Backend selector
# ---------------------------------------------------------------------------
class _MultiAirportDB:
    """Merge several airport providers into one queryable DB.

    Airport data comes from independent provider packs on their own update
    cadences — the US FAA NASR pack (primary, rich Tier-C data) plus optional
    supplemental packs (e.g. Canada from OurAirports). Each provider is a
    ``NASRAirportDB`` over its own sqlite. ``airports_in_range`` chains them and
    de-dups by ICAO so an airport that two providers both carry appears once
    (earlier providers — NASR first — win)."""

    def __init__(self, dbs):
        self._dbs = [d for d in dbs if getattr(d, "ready", False)]

    @property
    def ready(self) -> bool:
        return bool(self._dbs)

    def airports_in_range(self, ac_lat, ac_lon, range_nm):
        seen = set()
        for db in self._dbs:
            for ap in db.airports_in_range(ac_lat, ac_lon, range_nm):
                key = (ap.icao or "").upper() or (round(ap.ref_lat, 4),
                                                  round(ap.ref_lon, 4))
                if key in seen:
                    continue
                seen.add(key)
                yield ap


def make_airport_db(config: dict):
    """Pick the best available airport DB backend for an SVS config.

    Preference order:
      1. NASR primary (``nasr_db_path``) + any provider packs discovered under
         ``airport_provider_dir`` (``<dir>/*/current/airports.sqlite``), merged.
      2. CIFP if ``cifp_path`` and the index resolve.
      3. A no-op stub (``ready == False``).

    Provider packs auto-discover: dropping a new airports-<x> pack into the
    provider dir makes its airports appear with no config change.
    """
    paved = bool(config.get("paved_only", True))
    dbs = []
    nasr_path = config.get("nasr_db_path", "")
    if nasr_path:
        dbs.append(NASRAirportDB(nasr_path, paved_only=paved))

    provider_dir = config.get("airport_provider_dir", "")
    if provider_dir:
        import glob
        pat = str(Path(provider_dir) / "*" / "current" / "airports.sqlite")
        for p in sorted(glob.glob(pat)):
            dbs.append(NASRAirportDB(p, paved_only=paved))

    dbs = [d for d in dbs if getattr(d, "ready", False)]
    if len(dbs) == 1:
        return dbs[0]
    if dbs:
        return _MultiAirportDB(dbs)

    cifp_path  = config.get("cifp_path", "")
    index_path = config.get("cifp_index_path", "")
    if cifp_path and not index_path:
        index_path = str(Path(cifp_path).with_name("index.bin"))
    if cifp_path:
        db = CIFPAirportDB(cifp_path or None, index_path or None)
        if db.ready:
            return db

    # No data — return an empty stub so callers can rely on .ready.
    class _Empty:
        ready = False
        def airports_in_range(self, *a, **kw):
            return iter(())
    return _Empty()
