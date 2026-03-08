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


def _encode(obj) -> bytes:
    """Encode a normalized primitive structure to bytes deterministically."""
    out = []
    _write(obj, out)
    return b''.join(out)


def _write(obj, out: list) -> None:
    if obj is None:
        out.append(_TAG_NONE)
    elif isinstance(obj, bool):
        out.append(_TAG_BOOL)
        out.append(b'\x01' if obj else b'\x00')
    elif isinstance(obj, int):
        out.append(_TAG_INT)
        sign = b'\x01' if obj < 0 else b'\x00'
        magnitude = abs(obj).to_bytes((abs(obj).bit_length() + 7) // 8 or 1, 'little')
        out.append(sign)
        out.append(struct.pack('<I', len(magnitude)))
        out.append(magnitude)
    elif isinstance(obj, float):
        out.append(_TAG_FLOAT)
        out.append(struct.pack('<d', obj))
    elif isinstance(obj, str):
        encoded = obj.encode('utf-8')
        out.append(_TAG_STR)
        out.append(struct.pack('<I', len(encoded)))
        out.append(encoded)
    elif isinstance(obj, bytes):
        out.append(_TAG_BYTES)
        out.append(struct.pack('<I', len(obj)))
        out.append(obj)
    elif isinstance(obj, (tuple, list)):
        out.append(_TAG_SEQ)
        out.append(struct.pack('<I', len(obj)))
        for el in obj:
            _write(el, out)
    else:
        raise TypeError(
            f"Cannot encode type {type(obj).__name__!r} in normalized structure; "
            "normalizers must return nested tuples/lists of str, int, float, bool, bytes, or None"
        )


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
        return xxhash.xxh128(_encode(normalized)).hexdigest()

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
