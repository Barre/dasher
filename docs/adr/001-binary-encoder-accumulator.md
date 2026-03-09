# ADR 001: Binary encoder accumulator strategy

## Status

Accepted

## Context

`_encode` serializes a normalized primitive structure (nested tuples/lists of
`str`, `int`, `float`, `bool`, `bytes`, `None`) to a flat `bytes` object that
is then passed to `xxhash.xxh128`. The implementation recurses over the
structure via `_write`, and the core question is how `_write` accumulates its
output chunks.

Three strategies were considered:

**1. Mutable list passed by reference (current)**
```python
def _write(obj, out: list) -> None:
    match obj:
        case str():
            enc = obj.encode('utf-8')
            out.append(_TAG_STR)
            out.append(struct.pack('<I', len(enc)))
            out.append(enc)
        case tuple() | list():
            out.append(_TAG_SEQ)
            out.append(struct.pack('<I', len(obj)))
            for el in obj:
                _write(el, out)
        ...

def _encode(obj) -> bytes:
    out = []
    _write(obj, out)
    return b''.join(out)
```

**2. Flat tuple concatenation**
```python
def _write(obj) -> tuple:
    match obj:
        case str():
            enc = obj.encode('utf-8')
            return (_TAG_STR, struct.pack('<I', len(enc)), enc)
        case tuple() | list():
            chunks = (_TAG_SEQ, struct.pack('<I', len(obj)))
            for el in obj:
                chunks += _write(el)   # copies entire accumulated tuple each time
            return chunks
        ...

def _encode(obj) -> bytes:
    return b''.join(_write(obj))
```

**3. Nested tuples of tuples**
```python
def _write(obj) -> object:
    match obj:
        case str():
            enc = obj.encode('utf-8')
            return (_TAG_STR, struct.pack('<I', len(enc)), enc)
        case tuple() | list():
            return (_TAG_SEQ, struct.pack('<I', len(obj)), tuple(_write(el) for el in obj))
        ...

def _flatten(obj, out: list) -> None:
    if isinstance(obj, bytes):
        out.append(obj)
    else:
        for el in obj:
            _flatten(el, out)

def _encode(obj) -> bytes:
    out = []
    _flatten(_write(obj), out)
    return b''.join(out)
```

## Benchmarks

Tested on the normalized output of a real xorq expression
(`DatabaseTable → Filter → Project` over an in-memory DuckDB table):

| Strategy | Time (10k iters) | Relative |
|---|---|---|
| Mutable list | 159ms | 1.0x (baseline) |
| Flat tuple concat | 196ms | 1.23x slower |
| Nested tuples + flatten | 309ms | 1.94x slower |

Concat overhead within the tuple strategies:

| | Tuple concat | Nested tuples |
|---|---|---|
| Build only | ~91ms | ~195ms |
| Concat/flatten overhead | ~101ms (53%) | ~114ms |

## Analysis

**Flat tuple concat** is O(n²) in accumulated chunk count. Each `chunks +=
_write(el)` copies the entire tuple built so far into a new one. On a shallow
3-node expr, this already accounts for 53% of the tuple approach's total cost.
The overhead grows with expression depth.

**Nested tuples** avoid the O(n²) copy by building one allocation per node,
but the allocation cost per node is similar to the concat approach. A second
O(n) flatten pass is then required, adding ~114ms on top. Net result is ~2x
slower than the mutable list.

**Mutable list** is O(n) appends with amortized O(1) each. A single `b''.join`
at the end costs ~8% of total encode time. No intermediate copies. The list
grows monotonically and is discarded after joining.

## Decision

Use the mutable list strategy (option 1). It is the fastest, simplest, and
most memory-efficient of the three. Passing `out` by reference is idiomatic
Python for accumulator patterns and avoids any intermediate allocation overhead.

## Consequences

- `_write` is not a pure function — it mutates `out` as a side effect
- `_encode` owns the list and is the only caller of `_write`, so the mutation
  is fully contained
- Deeper or wider expressions will continue to favour this approach since the
  mutable list scales linearly while alternatives do not
