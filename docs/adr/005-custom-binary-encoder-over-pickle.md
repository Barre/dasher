# ADR 005: Custom binary encoder over pickle

## Status

Accepted

## Context

`Hasher.tokenize()` needs to convert a normalized primitive structure (nested
tuples/lists of `str`, `int`, `float`, `bool`, `bytes`, `None`) to bytes
before hashing. The initial implementation used `pickle.dumps(normalized,
protocol=5)`.

## Decision

Replace `pickle.dumps` with a custom type-tagged binary encoder (`_encode` /
`_write` in `dasher/core.py`).

The encoder uses single-byte type tags and length-prefixed payloads:

| Type | Encoding |
|---|---|
| `None` | `\x00` |
| `bool` | `\x01` + `\x01`/`\x00` |
| `int` | `\x02` + sign byte + 4-byte length + magnitude (little-endian, variable length) |
| `float` | `\x03` + 8-byte IEEE 754 little-endian |
| `str` | `\x04` + 4-byte length + UTF-8 bytes |
| `bytes` | `\x05` + 4-byte length + raw bytes |
| `tuple`/`list` | `\x06` + 4-byte element count + encoded elements |

## Consequences

**Benefits:**
- Output is stable across Python versions — pickle's wire format can change
  between minor versions even with a fixed protocol number
- No dependency on pickle's object graph machinery; the encoder only handles
  the primitive types that normalizers are contracted to return
- `bool` and `int` are encoded with distinct tags, preventing `True == 1`
  collisions that pickle would also avoid but which are worth making explicit
- Slightly faster than pickle for the primitive structures produced by
  normalizers (pickle carries overhead for arbitrary object graphs)

**Drawbacks:**
- Custom format must be maintained; any new primitive type requires a new tag
  and corresponding decoder if one is ever needed
- No decoder is implemented — the format is write-only (sufficient for hashing,
  but not for round-tripping)
