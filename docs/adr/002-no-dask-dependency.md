# ADR 002: No dask dependency

## Status

Accepted

## Context

xorq uses `dask.base.tokenize` and `dask.base.normalize_token.register` as
its hashing infrastructure. Normalizers are registered as side effects of
importing modules, and overrides are applied by temporarily patching
`dask.base.normalize_token._lookup` via context managers
(`patch_normalize_token`).

This library is intended as a declarative replacement for that system. The
question is whether to build on top of dask's tokenization machinery or to own
the full pipeline.

## Decision

Do not depend on dask. Implement tokenization entirely within this library.

## Consequences

**Benefits:**
- No risk of interference with dask's global registry
- No need to patch or monkey-patch dask internals
- `Hasher.tokenize()` is self-contained and deterministic regardless of what
  else is imported in the process
- Removes a heavy dependency (dask pulls in cloudpickle, click, etc.) from
  what is conceptually a small utility library

**Drawbacks:**
- Cannot interoperate directly with code that calls `dask.base.tokenize()`
  on objects — callers must use `Hasher.tokenize()` explicitly
- Must re-implement and maintain our own encoding and hashing pipeline
