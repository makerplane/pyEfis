import pytest
import os
from unittest.mock import MagicMock, patch
from pyefis.cfg import from_yaml


def test_missing_path():
    with pytest.raises(SyntaxError):
        d = from_yaml(fname="missing_path.yaml")


def test_sub_parent_includes():
    a = from_yaml("tests/data/cfg/test_sub_parent_includesA.yaml")
    assert a == {"a": {"b": {"c": {"done": True}}, "b2": {"d": {"end": True}}}}


def test_array_and_preferences():
    b = from_yaml(
        "tests/data/cfg/test_array_and_preferences.yaml",
        preferences={
            "includes": {
                "PREFERENCEA": "test_array_and_preferencesA.yaml",
                "PREFERENCEB": "test_array_and_preferencesB.yaml",
            }
        },
    )
    assert b == {"ARRAYS": {"includeC": True, "includeA": True, "includeB": True}}


def test_data_type():
    with pytest.raises(SyntaxError):
        c = from_yaml("tests/data/cfg/test_data_type.yaml")


def test_loop_detection_exception():
    with pytest.raises(RecursionError):
        d = from_yaml("tests/data/cfg/test_loop_detection_exception.yaml")


def test_preference_file_not_found():
    with pytest.raises(FileNotFoundError):
        e = from_yaml(
            "tests/data/cfg/test_preference_file_not_found.yaml",
            preferences={"includes": {"NOT_FOUND": "preference_not_found.yaml"}},
        )


def test_no_preferences():
    with pytest.raises(FileNotFoundError):
        e = from_yaml("tests/data/cfg/test_no_preferences.yaml")


def test_list_include_missing_items():
    with pytest.raises(SyntaxError):
        e = from_yaml("tests/data/cfg/test_list_include_missing_items.yaml")


def test_list_include_missing_items_via_preferences():
    with pytest.raises(SyntaxError):
        e = from_yaml(
            "tests/data/cfg/test_list_include_missing_items_pref.yaml",
            preferences={
                "includes": {
                    "PREFERENCED": "test_list_include_missing_items_via_preferencesD.yaml",
                    "PREFERENCEE": "preferencee.yaml",
                }
            },
        )


def test_list_include_missing_items_via_preferences_nested():
    with pytest.raises(SyntaxError):
        e = from_yaml(
            "tests/data/cfg/test_list_include_missing_items_pref_nested.yaml",
            preferences={
                "includes": {
                    "PREFERENCEF": "test_list_include_missing_items_via_preferences_nestedF.yaml",
                    "PREFERENCEG": "test_list_include_missing_items_via_preferences_nestedG.yaml",
                }
            },
        )


def test_list_bpath_preference():
    e = from_yaml(
        "tests/data/cfg/test_list_bpath_preference.yaml",
        preferences={
            "includes": {
                "A": "sub/sub2/test_list_bpath_preferenceA.yaml",
                "B": "test_list_bpath_preferenceB.yaml",
                "C": "test_list_bpath_preferenceC.yaml",
            }
        },
    )
    assert e == {"test": [{"b_id": 5}, {"c_id_is": 5}, 5, "Ten"]}
