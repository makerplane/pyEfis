"""Terrain mip pyramid downsample (tools/build_terrain_mips.py)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_terrain_mips as bm                       # noqa: E402
from pyefis.instruments.ai.svs import SRTM3_VOID      # noqa: E402


def _flat(n=65, fill=0):
    return np.full((n, n), fill, dtype=">i2")


def test_sizes_and_dtype():
    nat = _flat(65)
    for factor, side in ((2, 33), (4, 17), (16, 5), (64, 2)):
        out = bm.downsample(nat, factor)
        assert out.shape == (side, side)
        assert out.dtype == np.dtype(">i2")


def test_constant_is_preserved():
    out = bm.downsample(_flat(65, 500), 4)
    assert np.all(out == 500)


def test_row_ramp_registration_and_orientation():
    n = 65
    nat = (np.arange(n)[:, None] * 10 * np.ones((1, n))).astype(">i2")   # row i -> i*10
    out = bm.downsample(nat, 2).astype(np.float64)                       # (33, 33)
    assert np.all(np.diff(out[:, 0]) > 0)               # increases DOWN rows
    assert out[:, 0] == pytest.approx(out[:, -1], abs=1.0)   # ~constant across cols
    assert out[0, 0] == pytest.approx(0.0, abs=15)      # NW corner registered
    assert out[-1, 0] == pytest.approx(640.0, abs=15)   # SW corner registered


def test_col_ramp_orientation():
    n = 65
    nat = (np.ones((n, 1)) * np.arange(n)[None, :] * 10).astype(">i2")   # col j -> j*10
    out = bm.downsample(nat, 2).astype(np.float64)
    assert np.all(np.diff(out[0, :]) > 0)               # increases ACROSS cols
    assert out[0, :] == pytest.approx(out[-1, :], abs=1.0)


def test_void_excluded_not_averaged_in():
    n = 65
    nat = _flat(n, 300)
    nat[:12, :12] = SRTM3_VOID                          # a void block in the NW
    out = bm.downsample(nat, 4).astype(np.float64)
    assert out[0, 0] == float(SRTM3_VOID)               # all-void box stays void
    assert out[-1, -1] == pytest.approx(300.0, abs=1e-6)  # valid area unaffected
    # a node straddling the void edge still averages only valid samples (all 300)
    assert np.all(out[(out != SRTM3_VOID)] == pytest.approx(300.0, abs=1e-6))
