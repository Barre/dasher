# ADR 004: xxhash over hashlib

## Status

Accepted

## Context

After encoding the normalized structure to bytes, a hash function is applied to
produce the final token. The initial implementation used `hashlib.md5`. The
question is whether a faster non-cryptographic alternative is worth the
additional dependency.

## Benchmark

10,000 iterations over an ~80KB pickle blob:

| Hash function | Time | Relative |
|---|---|---|
| `hashlib.md5` | 342ms | 1.0x |
| `xxhash.xxh64` | 21ms | 16.7x faster |
| `xxhash.xxh128` | 13ms | 27.3x faster |

## Decision

Use `xxhash.xxh128`. It is ~27x faster than MD5 and produces a 128-bit
(32 hex character) digest, matching MD5's output length.

Cryptographic strength is not required — the hash is used only for cache
keying and deduplication, not for security.

## Consequences

- `xxhash` is added as a required dependency
- Tokens are not compatible with MD5-based tokens (different algorithm,
  different values for the same input)
- `xxh128` output is 32 hex characters, same length as MD5, making it a
  drop-in replacement in any system that treats the token as an opaque string
