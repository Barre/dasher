import pytest
from dasher import Hasher, DEFAULT_HASHER, fqn
from dasher.core import _encode


def normalize_int(x):
    return ("int", x)


def normalize_str(x):
    return ("str", x)


# --- _encode ---

def test_encode_none():
    assert _encode(None) == b'\x00'


def test_encode_bool():
    assert _encode(True) != _encode(False)
    assert _encode(True) != _encode(1)   # bool and int must be distinct


def test_encode_int_zero():
    assert _encode(0) == _encode(0)


def test_encode_int_positive_negative_distinct():
    assert _encode(1) != _encode(-1)


def test_encode_large_int():
    big = 2 ** 128 + 1
    assert _encode(big) != _encode(big - 1)


def test_encode_float():
    assert _encode(1.0) != _encode(1)   # float and int must be distinct
    assert _encode(1.5) == _encode(1.5)


def test_encode_str():
    assert _encode("hello") != _encode(b"hello")  # str and bytes must be distinct
    assert _encode("a") != _encode("b")


def test_encode_bytes():
    assert _encode(b"x") == _encode(b"x")
    assert _encode(b"x") != _encode(b"y")


def test_encode_seq_order_matters():
    assert _encode(("a", "b")) != _encode(("b", "a"))


def test_encode_seq_length_matters():
    assert _encode(("a",)) != _encode(("a", "a"))


def test_encode_nested():
    assert _encode((("a", 1), (True, None))) == _encode((("a", 1), (True, None)))


def test_encode_rejects_unknown_type():
    with pytest.raises(TypeError, match="Cannot encode"):
        _encode(object())


# --- Hasher.normalize ---

def test_normalize_exact_type():
    h = Hasher(rules=((fqn(int), normalize_int),))
    assert h.normalize(42) == ("int", 42)


def test_normalize_subclass():
    class MyInt(int):
        pass

    h = Hasher(rules=((fqn(int), normalize_int),))
    assert h.normalize(MyInt(5)) == ("int", 5)


def test_normalize_first_match_wins():
    class Base:
        pass

    class Sub(Base):
        pass

    h = Hasher(rules=(
        (fqn(Sub), lambda x: "sub"),
        (fqn(Base), lambda x: "base"),
    ))
    assert h.normalize(Sub()) == "sub"


def test_normalize_base_rule_matches_subclass_when_no_specific_rule():
    class Base:
        pass

    class Sub(Base):
        pass

    h = Hasher(rules=((fqn(Base), lambda x: "base"),))
    assert h.normalize(Sub()) == "base"


def test_normalize_missing_raises():
    h = Hasher(rules=())
    with pytest.raises(ValueError, match="No normalizer"):
        h.normalize(42)


def test_normalize_string_key_no_import_needed():
    # rules can be registered using a hardcoded fqn string
    h = Hasher(rules=(("builtins.int", normalize_int),))
    assert h.normalize(42) == ("int", 42)


def test_override_replaces_rule():
    h = Hasher(rules=((fqn(int), normalize_int),))
    h2 = h.override((fqn(int), lambda x: ("custom", x)))
    assert h2.normalize(42) == ("custom", 42)
    assert h.normalize(42) == ("int", 42)  # original unchanged


def test_override_adds_rule():
    h = Hasher(rules=((fqn(int), normalize_int),))
    h2 = h.override((fqn(str), normalize_str))
    assert h2.normalize(42) == ("int", 42)
    assert h2.normalize("hi") == ("str", "hi")


def test_override_new_rule_takes_priority_over_base():
    # Sub has no rule; Base does. Adding a Sub rule via override should
    # take priority over the existing Base rule (not be buried at the end).
    class Base:
        pass

    class Sub(Base):
        pass

    h = Hasher(rules=((fqn(Base), lambda x: "base"),))
    h2 = h.override((fqn(Sub), lambda x: "sub"))
    assert h2.normalize(Sub()) == "sub"


def test_override_existing_rule_preserves_position():
    # Overriding an existing rule should keep it in the same position,
    # not move it to the front or back.
    class A: pass
    class B: pass
    class C: pass

    h = Hasher(rules=(
        (fqn(A), lambda x: "a"),
        (fqn(B), lambda x: "b"),
        (fqn(C), lambda x: "c"),
    ))
    h2 = h.override((fqn(B), lambda x: "b2"))
    assert [k for k, _ in h2.rules] == [fqn(A), fqn(B), fqn(C)]
    assert h2.normalize(B()) == "b2"


def test_without_removes_rule():
    h = Hasher(rules=((fqn(int), normalize_int), (fqn(str), normalize_str)))
    h2 = h.without(fqn(int))
    with pytest.raises(ValueError):
        h2.normalize(42)
    assert h2.normalize("hi") == ("str", "hi")


# --- Hasher.tokenize ---

def test_tokenize_same_value_same_token():
    h = Hasher(rules=((fqn(int), normalize_int),))
    assert h.tokenize(42) == h.tokenize(42)


def test_tokenize_different_values_different_tokens():
    h = Hasher(rules=((fqn(int), normalize_int),))
    assert h.tokenize(42) != h.tokenize(43)


def test_tokenize_returns_hex_string():
    h = Hasher(rules=((fqn(int), normalize_int),))
    token = h.tokenize(42)
    assert isinstance(token, str)
    assert len(token) == 32  # xxh128 = 128 bits = 32 hex chars
    int(token, 16)  # valid hex


def test_default_dasher_handles_dict():
    t = DEFAULT_HASHER.tokenize({"a": 1, "b": 2})
    assert isinstance(t, str)


def test_default_dasher_dict_order_invariant():
    h = DEFAULT_HASHER
    assert h.tokenize({"a": 1, "b": 2}) == h.tokenize({"b": 2, "a": 1})


def test_immutability():
    h = Hasher(rules=((fqn(int), normalize_int),))
    with pytest.raises(Exception):
        h.rules = ()
