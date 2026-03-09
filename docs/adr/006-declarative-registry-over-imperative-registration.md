# ADR 006: Declarative registry over imperative registration

## Status

Accepted

## Context

xorq registers normalizers imperatively as side effects of importing modules:

```python
# dask_normalize_expr.py
@dask.base.normalize_token.register(ir.DatabaseTable)
def normalize_databasetable(dt):
    ...

# dask_normalize_other.py
@dask.base.normalize_token.register(pa.Table)
def normalize_pyarrow_table(table):
    ...
```

These registrations mutate a global dispatch table in dask. Import order
determines what is registered; if a file is not imported, its normalizers are
absent with no error at definition time — only a failure at tokenization time.
Overriding a normalizer for a specific context (e.g. `SnapshotStrategy`)
requires patching the global table with a context manager and restoring it
afterwards.

## Decision

Represent the normalizer registry as an immutable value — a `Hasher` instance
— rather than as global mutable state.

```python
@frozen
class Hasher:
    rules: tuple  # tuple[tuple[str, Callable], ...]

DEFAULT_HASHER = Hasher(rules=(
    ("builtins.dict",                  normalize_dict),
    ("numpy.random.mtrand.RandomState", normalize_numpy_random_state),
    ("pyarrow.lib.Table",              normalize_pyarrow_table),
    ...
))

snapshot_hasher = DEFAULT_HASHER.override(
    ("xorq.vendor.ibis.backends.BaseBackend", snapshot_normalize_backend),
)
```

## Consequences

**Benefits:**
- The full set of registered normalizers is visible in one place (`RULES` in
  each rules module) with no need to trace import side effects
- Import order does not affect correctness — `DEFAULT_HASHER` is constructed
  explicitly, not accumulated across imports
- Overrides are first-class: `Hasher.override()` returns a new `Hasher`
  without mutating anything, making it safe to create context-specific hashers
  (e.g. per-strategy) without risk of leaking state
- `Hasher` instances are `attrs` frozen dataclasses — immutable, comparable,
  and inspectable
- Missing normalizers fail loudly at `normalize()` call time with a clear
  error, rather than silently falling through to a wrong result

**Drawbacks:**
- Callers must use `Hasher.tokenize()` rather than `dask.base.tokenize()`,
  requiring adoption at call sites
- Third-party code that registers normalizers via `normalize_token.register`
  (e.g. dask itself, other libraries) is not automatically incorporated;
  those normalizers must be explicitly added to `RULES`
