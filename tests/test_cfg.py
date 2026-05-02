import pytest
from unittest.mock import patch
import pyefis.cfg as cfg
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
            "tests/data/cfg/sub/test_preference_file_not_found.yaml",
            preferences={"includes": {"NOT_FOUND": "preference_not_found.yaml"}},
        )

def test_preference_file_not_found_list():
    with pytest.raises(FileNotFoundError):
        e = from_yaml(
            "tests/data/cfg/sub/test_preference_file_not_found_list.yaml",
            preferences={"includes": {"NOT_FOUND": "preference_not_found.yaml"}},
        )

def test_preference_file_not_found_list_no_includes():
    with pytest.raises(FileNotFoundError):
        e = from_yaml(
            "tests/data/cfg/sub/test_preference_file_not_found_list.yaml",
            preferences={"includes_typo": {"NOT_FOUND": "preference_not_found.yaml"}},
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


def test_scalar_yaml_returns_empty_config(tmp_path):
    config = tmp_path / "scalar.yaml"
    config.write_text("just-a-string\n")

    assert from_yaml(str(config)) == {}


def test_top_level_preference_include_can_resolve_from_base_path(tmp_path):
    subdir = tmp_path / "sub"
    subdir.mkdir()
    config = subdir / "config.yaml"
    preferred = tmp_path / "preferred.yaml"
    config.write_text("include: SELECTED\n")
    preferred.write_text("chosen: true\n")

    result = from_yaml(
        str(config),
        bpath=str(tmp_path),
        preferences={"includes": {"SELECTED": "preferred.yaml"}},
    )

    assert result == {"chosen": True}


def test_top_level_preference_include_without_mapping_raises(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("include: MISSING\n")

    with pytest.raises(FileNotFoundError):
        from_yaml(str(config), preferences={"includes": {}})


def test_list_preference_include_without_mapping_raises(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("items:\n  - include: MISSING\n")

    with pytest.raises(FileNotFoundError):
        from_yaml(str(config), preferences={"includes": {}})


def test_list_include_with_null_items_adds_nothing(tmp_path):
    config = tmp_path / "config.yaml"
    included = tmp_path / "included.yaml"
    config.write_text("items:\n  - include: included.yaml\n")
    included.write_text("items:\n")

    assert from_yaml(str(config), preferences={}) == {"items": []}


def test_top_level_include_ignores_non_mapping_recursive_result(tmp_path):
    config = tmp_path / "config.yaml"
    included = tmp_path / "included.yaml"
    included.write_text("ignored: true\n")
    original_from_yaml = cfg.from_yaml

    def recursive_from_yaml(*args, **kwargs):
        return "not-a-mapping"

    with patch("pyefis.cfg.from_yaml", side_effect=recursive_from_yaml):
        result = original_from_yaml(
            str(config),
            bpath=str(tmp_path),
            cfg={"include": "included.yaml"},
            bc=[],
            preferences={},
        )

    assert result == {}
