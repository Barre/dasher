# ADR 003: FQN strings as rule keys

## Status

Accepted

## Context

`Hasher` maintains an ordered list of `(key, normalize_fn)` pairs. The key
identifies which types the rule applies to. The initial implementation used
class objects as keys (as dask does), requiring the class to be imported at
the point of rule registration:

```python
import numpy as np

Hasher(rules=(
    (np.random.RandomState, normalize_numpy_random_state),
))
```

## Decision

Use fully qualified type name strings (`'{module}.{qualname}'`) as rule keys.
A `fqn(typ)` helper is provided to compute the string from a class object.
Lookup walks the MRO so subclasses match base class rules; among multiple
matches the earliest rule wins.

```python
Hasher(rules=(
    ("numpy.random.mtrand.RandomState", normalize_numpy_random_state),
))
```

## Consequences

**Benefits:**
- Rules can be registered without importing the type — the string can be
  hardcoded, making the full rule set visible in one place with no hidden
  import-time side effects
- Optional dependencies (numpy, pandas, pyarrow, sklearn, xorq) do not need
  to be imported at `Hasher` construction time; their normalizer functions are
  only called when an object of that type is actually encountered
- The rule list is inspectable as plain data (a tuple of strings and callables)

**Drawbacks:**
- FQN strings can change between library versions (e.g. numpy's array function
  dispatcher moved from `numpy.core` to `numpy._core` in 2.0); both must be
  registered explicitly
- Hardcoded strings require knowing the internal module path of a type, which
  may not be obvious from the public API
- MRO-based subclass matching requires walking `type(obj).__mro__` at normalize
  time rather than a single dict lookup, though this cost is negligible in
  practice
