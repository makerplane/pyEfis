import pytest
from pyefis.common import bounds

def test_bounds_below_min():
    assert bounds(0, 10, -5) == 0

def test_bounds_above_max():
    assert bounds(0, 10, 15) == 10

def test_bounds_within_range():
    assert bounds(0, 10, 5) == 5

def test_bounds_on_min():
    assert bounds(0, 10, 0) == 0

def test_bounds_on_max():
    assert bounds(0, 10, 10) == 10

if __name__ == "__main__":
    pytest.main()

