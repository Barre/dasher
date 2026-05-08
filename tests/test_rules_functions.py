import pytest

from dasher import DEFAULT_HASHER


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


def test_unwraps_functools_wraps():
    import functools

    def deco(f):
        @functools.wraps(f)
        def inner(*a, **k):
            return f(*a, **k) + 1000
        return inner

    def base(x):
        return x

    wrapped = deco(base)
    # __wrapped__ unwrapping means the wrapped function tokenizes as its inner
    assert DEFAULT_HASHER.tokenize(wrapped) == DEFAULT_HASHER.tokenize(base)


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

    h = DEFAULT_HASHER.override(
        ("__main__.WithDunder", lambda o: ("specific",)),
    )
    # The override fqn won't match (class qualname differs at test time),
    # so we instead verify via a direct rule registration on the actual fqn:
    from dasher.core import fqn
    h2 = DEFAULT_HASHER.override((fqn(WithDunder), lambda o: ("specific",)))
    assert h2.normalize(WithDunder()) == ("specific",)
