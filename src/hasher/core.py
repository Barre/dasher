from __future__ import annotations

import struct

import xxhash
from attr import frozen, field


_PRIMITIVES = (str, int, float, bool, bytes, type(None))

_TAG_NONE  = b'\x00'
_TAG_BOOL  = b'\x01'
_TAG_INT   = b'\x02'
_TAG_FLOAT = b'\x03'
_TAG_STR   = b'\x04'
_TAG_BYTES = b'\x05'
_TAG_SEQ   = b'\x06'


def fqn(typ: type) -> str:
    """Return the fully qualified name of a type: '{module}.{qualname}'."""
    return f"{typ.__module__}.{typ.__qualname__}"


def _encode(obj) -> bytes:
    """Encode a normalized primitive structure to bytes deterministically."""
    out = []
    _write(obj, out)
    return b''.join(out)


def _write(obj, out: list) -> None:
    match obj:
        case None:
            out.append(_TAG_NONE)
        case bool():
            out.append(_TAG_BOOL)
            out.append(b'\x01' if obj else b'\x00')
        case int():
            out.append(_TAG_INT)
            sign = b'\x01' if obj < 0 else b'\x00'
            magnitude = abs(obj).to_bytes((abs(obj).bit_length() + 7) // 8 or 1, 'little')
            out.append(sign)
            out.append(struct.pack('<I', len(magnitude)))
            out.append(magnitude)
        case float():
            out.append(_TAG_FLOAT)
            out.append(struct.pack('<d', obj))
        case str():
            encoded = obj.encode('utf-8')
            out.append(_TAG_STR)
            out.append(struct.pack('<I', len(encoded)))
            out.append(encoded)
        case bytes():
            out.append(_TAG_BYTES)
            out.append(struct.pack('<I', len(obj)))
            out.append(obj)
        case tuple() | list():
            out.append(_TAG_SEQ)
            out.append(struct.pack('<I', len(obj)))
            for el in obj:
                _write(el, out)
        case _:
            raise TypeError(
                f"Cannot encode type {type(obj).__name__!r} in normalized structure; "
                "normalizers must return nested tuples/lists of str, int, float, bool, bytes, or None"
            )


@frozen
class Hasher:
    """An immutable, inspectable registry of (fqn, normalize_fn) rules.

    Rules are keyed by fully qualified type name ('{module}.{qualname}').
    Lookup walks the MRO so subclasses match base class rules; among
    multiple matches, the rule listed earliest wins.

    Normalizers must return primitive structures: nested tuples/lists of
    str, int, float, bool, bytes, or None. Objects within those structures
    that are not primitives will be recursively normalized using this hasher.
    """

    rules: tuple = field(factory=tuple)  # tuple[tuple[str, Callable], ...]

    def normalize(self, obj):
        """Normalize obj to a primitive structure using registered rules."""
        lookup = {name: (i, f) for i, (name, f) in enumerate(self.rules)}
        best_idx, best_fn = None, None
        for typ in type(obj).__mro__:
            name = fqn(typ)
            if name in lookup:
                idx, f = lookup[name]
                if best_idx is None or idx < best_idx:
                    best_idx = idx
                    best_fn = f
        if best_fn is not None:
            return best_fn(obj)
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
        return xxhash.xxh128(_encode(normalized)).hexdigest()

    def override(self, *rules: tuple) -> Hasher:
        """Return a new Hasher with the given (fqn, fn) rules added or replacing existing ones.

        Existing rules are updated in-place (position preserved). New rules are
        prepended so they take priority over any existing base-class rules.
        """
        overrides = dict(rules)
        updated = tuple((k, overrides.pop(k, f)) for k, f in self.rules)
        new = tuple(overrides.items())
        return Hasher(rules=tuple(new + updated))

    def without(self, *fqns: str) -> Hasher:
        """Return a new Hasher with rules for the given fqns removed."""
        return Hasher(rules=tuple((name, f) for name, f in self.rules if name not in fqns))

    def __repr__(self):
        names = [name for name, _ in self.rules]
        return f"Hasher(rules=[{', '.join(names)}])"
