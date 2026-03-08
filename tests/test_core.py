import pytest
from hasher import Hasher, DEFAULT_HASHER


def normalize_int(x):
    return ("int", x)


def normalize_str(x):
    return ("str", x)


def test_normalize_exact_type():
    h = Hasher(rules=((int, normalize_int),))
    assert h.normalize(42) == ("int", 42)


def test_normalize_subclass():
    class MyInt(int):
        pass

    h = Hasher(rules=((int, normalize_int),))
    assert h.normalize(MyInt(5)) == ("int", 5)


def test_normalize_first_match_wins():
    class Base:
        pass

    class Sub(Base):
        pass

    h = Hasher(rules=(
        (Sub, lambda x: "sub"),
        (Base, lambda x: "base"),
    ))
    assert h.normalize(Sub()) == "sub"


def test_normalize_missing_raises():
    h = Hasher(rules=())
    with pytest.raises(ValueError, match="No normalizer"):
        h.normalize(42)


def test_override_replaces_rule():
    h = Hasher(rules=((int, normalize_int),))
    h2 = h.override((int, lambda x: ("custom", x)))
    assert h2.normalize(42) == ("custom", 42)
    assert h.normalize(42) == ("int", 42)  # original unchanged


def test_override_adds_rule():
    h = Hasher(rules=((int, normalize_int),))
    h2 = h.override((str, normalize_str))
    assert h2.normalize(42) == ("int", 42)
    assert h2.normalize("hi") == ("str", "hi")


def test_without_removes_rule():
    h = Hasher(rules=((int, normalize_int), (str, normalize_str)))
    h2 = h.without(int)
    with pytest.raises(ValueError):
        h2.normalize(42)
    assert h2.normalize("hi") == ("str", "hi")


def test_tokenize_same_value_same_token():
    h = Hasher(rules=((int, normalize_int),))
    assert h.tokenize(42) == h.tokenize(42)


def test_tokenize_different_values_different_tokens():
    h = Hasher(rules=((int, normalize_int),))
    assert h.tokenize(42) != h.tokenize(43)


def test_default_hasher_handles_dict():
    t = DEFAULT_HASHER.tokenize({"a": 1, "b": 2})
    assert isinstance(t, str)


def test_default_hasher_dict_order_invariant():
    h = DEFAULT_HASHER
    assert h.tokenize({"a": 1, "b": 2}) == h.tokenize({"b": 2, "a": 1})


def test_immutability():
    h = Hasher(rules=((int, normalize_int),))
    with pytest.raises(Exception):
        h.rules = ()
