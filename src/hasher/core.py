from __future__ import annotations

import hashlib
import pickle
from attr import frozen, field


_PRIMITIVES = (str, int, float, bool, bytes, type(None))


@frozen
class Hasher:
    """An immutable, inspectable registry of (type, normalize_fn) rules.

    Rules are evaluated in order; the first matching type wins.
    Subclass resolution walks the MRO so you can register a base class and
    have it apply to subclasses unless a more specific rule is listed first.

    Normalizers must return primitive structures: nested tuples/lists of
    str, int, float, bool, bytes, or None. Objects within those structures
    that are not primitives will be recursively normalized using this hasher.
    """

    rules: tuple = field(factory=tuple)  # tuple[tuple[type, Callable], ...]

    def normalize(self, obj):
        """Normalize obj to a primitive structure using registered rules."""
        for typ, f in self.rules:
            if isinstance(obj, typ):
                return f(obj)
        raise ValueError(f"No normalizer registered for {type(obj)!r}: {obj!r}")

    def _normalize_recursive(self, obj):
        """Recursively reduce obj to a fully primitive structure."""
        if isinstance(obj, _PRIMITIVES):
            return obj
        if isinstance(obj, (tuple, list)):
            return tuple(self._normalize_recursive(el) for el in obj)
        return self._normalize_recursive(self.normalize(obj))

    def tokenize(self, *objs):
        """Return a deterministic hex digest for the given objects."""
        normalized = tuple(self._normalize_recursive(obj) for obj in objs)
        return hashlib.md5(pickle.dumps(normalized, protocol=5)).hexdigest()

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
