"""Normalizers for common types: builtins, numpy, pyarrow, pandas, sklearn."""
from __future__ import annotations

import types
import xxhash

from hasher.core import fqn


def normalize_type(typ):
    return (typ.__name__, typ.__module__)


def normalize_dict(dct):
    return ("dict", tuple(sorted(dct.items())))


def normalize_module(module):
    return ("module", module.__name__, module.__package__)


def normalize_numpy_random_state(random_state):
    return ("numpy.RandomState", random_state.get_state())


def normalize_numpy_array_function_dispatcher(func):
    return ("numpy.ufunc", func.__name__, func.__module__)


def normalize_interval(interval):
    return ("pd.Interval", interval.left, interval.right, interval.closed)


def normalize_timestamp(timestamp):
    return ("pd.Timestamp", str(timestamp))


def normalize_pyarrow_table(table):
    return ("pa.Table", tuple(
        xxhash.xxh128(el.serialize().to_pybytes()).hexdigest()
        for el in table.to_batches()
    ))


def normalize_pyarrow_schema(schema):
    return ("pa.Schema", str(schema))


def normalize_sklearn_estimator(estimator):
    params = tuple(sorted(estimator.get_params(deep=True).items()))
    return (
        "sklearn.estimator",
        type(estimator).__name__,
        type(estimator).__module__,
        params,
    )


RULES: list[tuple] = [
    (fqn(type),             normalize_type),
    (fqn(dict),             normalize_dict),
    (fqn(types.ModuleType), normalize_module),
    # numpy
    ("numpy.random.mtrand.RandomState",                          normalize_numpy_random_state),
    ("numpy.core._multiarray_umath._ArrayFunctionDispatcher",    normalize_numpy_array_function_dispatcher),  # numpy <2.0
    ("numpy._core._multiarray_umath._ArrayFunctionDispatcher",   normalize_numpy_array_function_dispatcher),  # numpy >=2.0
    # pandas
    ("pandas._libs.interval.Interval",              normalize_interval),
    ("pandas._libs.tslibs.timestamps.Timestamp",    normalize_timestamp),
    # pyarrow
    ("pyarrow.lib.Table",   normalize_pyarrow_table),
    ("pyarrow.lib.Schema",  normalize_pyarrow_schema),
    # sklearn
    ("sklearn.base.BaseEstimator", normalize_sklearn_estimator),
]
