import pytest
import os
from unittest.mock import MagicMock, patch
from pyefis.cfg import from_yaml



def test_sub_parent_includes():
    d = from_yaml('tests/data/cfg/a.yaml')
    assert d == {'a': {'b': {'c': {'done': True}}, 'b2': {'d': {'end': True}}}}

def test_array_and_preferences():
    e = from_yaml('tests/data/cfg/array_of_includes.yaml', preferences={"includes": {"PREFERENCEA": "PREFERENCEA.yaml"}})
    assert e == {'ARRAYS': {'includea': True, 'PREFERENCEA': True}}

def test_data_type():
    with pytest.raises(Exception):
        d = from_yaml('tests/data/cfg/not_string.yaml')

def test_loop_detection_exception():
    with pytest.raises(Exception):
        d = from_yaml('tests/data/cfg/loop1.yaml')

# We want to test:
# Various loop exceptions
#
# include: filename
# include:
# - filename1:
# - filename2:
# include: PREFERENCE_NAME
# various uses of 'item'
# include from root or from same sub-folder
# include from another folder

