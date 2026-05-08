import types

import pytest

from dasher import DEFAULT_HASHER
from dasher.rules.functions import normalize_cell, normalize_code, normalize_function


def test_same_function_same_token():
    def f(x):
        return x + 1
    assert DEFAULT_HASHER.tokenize(f) == DEFAULT_HASHER.tokenize(f)


def test_different_bodies_different_tokens():
    def f(x):
        return x + 1
    def g(x):
        return x + 2
    assert DEFAULT_HASHER.tokenize(f) != DEFAULT_HASHER.tokenize(g)


def test_closure_captured_value_affects_token():
    def make(n):
        def inner(x):
            return x + n
        return inner

    assert DEFAULT_HASHER.tokenize(make(1)) != DEFAULT_HASHER.tokenize(make(2))
    assert DEFAULT_HASHER.tokenize(make(1)) == DEFAULT_HASHER.tokenize(make(1))


def test_method_normalization():
    class C:
        def m(self, x):
            return x

    assert DEFAULT_HASHER.tokenize(C().m) == DEFAULT_HASHER.tokenize(C().m)


def test_lambda_default_value_affects_token():
    f = lambda x, y=1: x + y
    g = lambda x, y=2: x + y
    assert DEFAULT_HASHER.tokenize(f) != DEFAULT_HASHER.tokenize(g)


def test_decorator_changes_token():
    import functools

    def deco(f):
        @functools.wraps(f)
        def inner(*a, **k):
            return f(*a, **k) + 1000
        return inner

    def base(x):
        return x

    wrapped = deco(base)
    # Decorators that change behavior produce different tokens, even with functools.wraps
    assert DEFAULT_HASHER.tokenize(wrapped) != DEFAULT_HASHER.tokenize(base)


# --- normalize_code ---

def test_normalize_code_returns_all_attrs():
    def f(x):
        return x
    result = normalize_code(f.__code__)
    assert result[0] == "code"
    assert f.__code__.co_name in result


def test_normalize_code_different_bodies():
    def f(x):
        return x + 1
    def g(x):
        return x + 2
    assert normalize_code(f.__code__) != normalize_code(g.__code__)


def test_normalize_code_posonlyargcount_distinguishes():
    # Without co_posonlyargcount, these two functions would collide:
    # same name, same arg names, same body — only the positional-only
    # separator differs.
    src_pos = "def f(x, /): return x + 1"
    src_reg = "def f(x): return x + 1"
    ns_pos, ns_reg = {}, {}
    exec(compile(src_pos, "<pos>", "exec"), ns_pos)
    exec(compile(src_reg, "<reg>", "exec"), ns_reg)
    assert normalize_code(ns_pos["f"].__code__) != normalize_code(ns_reg["f"].__code__)


# --- normalize_cell ---

def test_normalize_cell_returns_contents():
    def make():
        x = 42
        def inner():
            return x
        return inner
    cell = make().__closure__[0]
    assert normalize_cell(cell) == ("cell", 42)


def test_normalize_cell_different_values():
    def make(n):
        def inner():
            return n
        return inner
    c1 = make(1).__closure__[0]
    c2 = make(2).__closure__[0]
    assert normalize_cell(c1) != normalize_cell(c2)


def test_normalize_cell_empty():
    # An empty cell (variable declared but not yet assigned) should not crash
    cell = types.CellType()
    result = normalize_cell(cell)
    assert result[0] == "cell"


# --- normalize_function direct ---

def test_normalize_function_includes_name():
    def my_func(x):
        return x
    result = normalize_function(my_func)
    assert result[0] == "function"
    assert "my_func" in result


# --- classmethod / staticmethod ---

def test_classmethod_normalization():
    class A:
        @classmethod
        def m(cls):
            return 1

    class B:
        @classmethod
        def m(cls):
            return 2

    assert DEFAULT_HASHER.tokenize(A.__dict__["m"]) == DEFAULT_HASHER.tokenize(A.__dict__["m"])
    assert DEFAULT_HASHER.tokenize(A.__dict__["m"]) != DEFAULT_HASHER.tokenize(B.__dict__["m"])


def test_staticmethod_normalization():
    class A:
        @staticmethod
        def s():
            return 1

    class B:
        @staticmethod
        def s():
            return 2

    assert DEFAULT_HASHER.tokenize(A.__dict__["s"]) == DEFAULT_HASHER.tokenize(A.__dict__["s"])
    assert DEFAULT_HASHER.tokenize(A.__dict__["s"]) != DEFAULT_HASHER.tokenize(B.__dict__["s"])


# --- fallback ---

def test_dask_tokenize_fallback_used():
    class Custom:
        def __init__(self, x):
            self.x = x
        def __dask_tokenize__(self):
            return ("custom", self.x)

    assert DEFAULT_HASHER.tokenize(Custom(1)) == DEFAULT_HASHER.tokenize(Custom(1))
    assert DEFAULT_HASHER.tokenize(Custom(1)) != DEFAULT_HASHER.tokenize(Custom(2))


def test_no_rule_no_dunder_raises():
    class Bad:
        pass
    with pytest.raises(ValueError, match="No normalizer"):
        DEFAULT_HASHER.tokenize(Bad())


def test_specific_rule_wins_over_object_fallback():
    # Sanity: an explicit rule for a class beats the builtins.object fallback
    # even though both match via MRO.
    class WithDunder:
        def __dask_tokenize__(self):
            return ("dunder",)

    from dasher.core import fqn
    h = DEFAULT_HASHER.override((fqn(WithDunder), lambda o: ("specific",)))
    assert h.normalize(WithDunder()) == ("specific",)
