from __future__ import annotations

import dask.base
from attr import frozen, field


@frozen
class Hasher:
    """An immutable, inspectable registry of (type, normalize_fn) rules.

    Rules are evaluated in order; the first matching type wins.
    Subclass resolution walks the MRO so you can register a base class and
    have it apply to subclasses unless a more specific rule is listed first.
    """

    rules: tuple = field(factory=tuple)  # tuple[tuple[type, Callable], ...]

    def normalize(self, obj):
        for typ, f in self.rules:
            if isinstance(obj, typ):
                return f(obj)
        raise ValueError(f"No normalizer registered for {type(obj)!r}: {obj!r}")

    def tokenize(self, *objs):
        """Tokenize objects using this hasher's rules, not the global dask registry."""
        import unittest.mock as mock

        lookup = {typ: f for typ, f in self.rules}

        with mock.patch.dict(dask.base.normalize_token._lookup, lookup):
            return dask.base.tokenize(*objs)

    def override(self, *rules: tuple) -> Hasher:
        """Return a new Hasher with the given (type, fn) rules added or replacing existing ones."""
        base = dict(self.rules)
        base.update(rules)
        return Hasher(rules=tuple(base.items()))

    def without(self, *types) -> Hasher:
        """Return a new Hasher with rules for the given types removed."""
        return Hasher(rules=tuple((t, f) for t, f in self.rules if t not in types))

    def __repr__(self):
        type_names = [t.__name__ for t, _ in self.rules]
        return f"Hasher(rules=[{', '.join(type_names)}])"
