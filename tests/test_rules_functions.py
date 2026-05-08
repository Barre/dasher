import types

import pytest

from dasher import DEFAULT_HASHER
from dasher.rules.fallback import normalize_object_fallback
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
    assert DEFAULT_HASHER.tokenize(wrapped) != DEFAULT_HASHER.tokenize(base)


def test_kwdefaults_affect_token():
    def f(*, k=1):
        return k

    def g(*, k=2):
        return k

    assert DEFAULT_HASHER.tokenize(f) != DEFAULT_HASHER.tokenize(g)


def test_function_dict_affects_token():
    def f(x):
        return x

    def g(x):
        return x

    g.custom_attr = "extra"
    assert DEFAULT_HASHER.tokenize(f) != DEFAULT_HASHER.tokenize(g)


def test_qualname_affects_token():
    def make_inner():
        def f(x):
            return x
        return f

    def f(x):
        return x

    nested = make_inner()
    assert nested.__qualname__ != f.__qualname__
    assert DEFAULT_HASHER.tokenize(nested) != DEFAULT_HASHER.tokenize(f)


def test_different_methods_different_tokens():
    class C:
        def m(self, x):
            return x

        def n(self, x):
            return x + 1

    assert DEFAULT_HASHER.tokenize(C().m) != DEFAULT_HASHER.tokenize(C().n)


def test_multi_cell_closure_second_var_differs():
    def make(a, b):
        def inner():
            return a + b
        return inner

    assert DEFAULT_HASHER.tokenize(make(1, 2)) != DEFAULT_HASHER.tokenize(make(1, 3))
    assert DEFAULT_HASHER.tokenize(make(1, 2)) == DEFAULT_HASHER.tokenize(make(1, 2))


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
    cell = types.CellType()
    result = normalize_cell(cell)
    assert result[0] == "cell"


def test_normalize_cell_empty_stable():
    c1 = types.CellType()
    c2 = types.CellType()
    assert normalize_cell(c1) == normalize_cell(c2)


def test_normalize_cell_empty_differs_from_filled():
    empty = types.CellType()
    def make():
        x = 42
        def inner():
            return x
        return inner
    filled = make().__closure__[0]
    assert normalize_cell(empty) != normalize_cell(filled)


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


def test_classmethod_normalize_function_contains_name():
    class A:
        @classmethod
        def m(cls):
            return 1

    result = normalize_function(A.__dict__["m"])
    assert result[0] == "function"
    assert "m" in result


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


def test_staticmethod_normalize_function_contains_name():
    class A:
        @staticmethod
        def s():
            return 1

    result = normalize_function(A.__dict__["s"])
    assert result[0] == "function"
    assert "s" in result


# --- fallback ---

def test_dask_tokenize_fallback_used():
    class Custom:
        def __init__(self, x):
            self.x = x
        def __dasher_tokenize__(self):
            return ("custom", self.x)

    assert DEFAULT_HASHER.tokenize(Custom(1)) == DEFAULT_HASHER.tokenize(Custom(1))
    assert DEFAULT_HASHER.tokenize(Custom(1)) != DEFAULT_HASHER.tokenize(Custom(2))


def test_no_rule_no_dunder_raises():
    class Bad:
        pass
    with pytest.raises(ValueError, match="No normalizer"):
        DEFAULT_HASHER.tokenize(Bad())


def test_fallback_skips_dask_tokenize_on_classes():
    class WithDunder:
        def __dasher_tokenize__(self):
            return ("instance_method",)

    with pytest.raises(ValueError, match="No normalizer"):
        normalize_object_fallback(WithDunder)


def test_fallback_nonprimitive_return_is_recursively_normalized():
    class Inner:
        def __init__(self, x):
            self.x = x
        def __dasher_tokenize__(self):
            return ("inner", self.x)

    class Outer:
        def __init__(self, inner):
            self.inner = inner
        def __dasher_tokenize__(self):
            return ("outer", self.inner)

    assert DEFAULT_HASHER.tokenize(Outer(Inner(1))) == DEFAULT_HASHER.tokenize(Outer(Inner(1)))
    assert DEFAULT_HASHER.tokenize(Outer(Inner(1))) != DEFAULT_HASHER.tokenize(Outer(Inner(2)))


def test_specific_rule_wins_over_object_fallback():
    # Sanity: an explicit rule for a class beats the builtins.object fallback
    # even though both match via MRO.
    class WithDunder:
        def __dasher_tokenize__(self):
            return ("dunder",)

    from dasher.core import fqn
    h = DEFAULT_HASHER.override((fqn(WithDunder), lambda o: ("specific",)))
    assert h.normalize(WithDunder()) == ("specific",)
