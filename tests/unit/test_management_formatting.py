from bots.management.formatting import flatten_leaves, parse_new_value, set_nested


def test_flatten_produces_stable_paths():
    value = {"per_person": {"hall": 39000}, "catering_per_person": 39000}
    paths = [p for p, _ in flatten_leaves(value)]
    assert paths == [("catering_per_person",), ("per_person", "hall")]


def test_set_nested_does_not_mutate_original():
    original = {"a": {"b": 1}}
    updated = set_nested(original, ("a", "b"), 2)
    assert original["a"]["b"] == 1
    assert updated["a"]["b"] == 2


def test_parse_persian_digits_for_integer_setting():
    assert parse_new_value("۳۹۰۰۰۰", 1) == 390000


def test_parse_strips_thousand_separators():
    assert parse_new_value("390,000", 1) == 390000


def test_string_setting_keeps_text():
    assert parse_new_value("07:30", "23:30") == "07:30"


def test_non_editable_type_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        parse_new_value("true", True)
