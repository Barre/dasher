"""Normalizers for common types: builtins, numpy, pyarrow, pandas, sklearn."""
from __future__ import annotations

import dask.base
import types


def normalize_type(typ):
    return (typ.__name__, typ.__module__)


def normalize_dict(dct):
    return ("dict", tuple(sorted(dct.items())))


def normalize_module(module):
    return ("module", module.__name__, module.__package__)


def _make_lazy_rules():
    """Return rules that depend on optional imports. Call once at Hasher build time."""
    rules = []

    try:
        import numpy as np

        def normalize_numpy_random_state(random_state):
            return ("numpy.RandomState", random_state.get_state())

        def normalize_numpy_array_function_dispatcher(func):
            return ("numpy.ufunc", func.__name__, func.__module__)

        rules += [
            (np.random.RandomState, normalize_numpy_random_state),
            (type(np.mean), normalize_numpy_array_function_dispatcher),
        ]
    except ImportError:
        pass

    try:
        import pandas as pd

        def normalize_interval(interval):
            return ("pd.Interval", interval.left, interval.right, interval.closed)

        def normalize_timestamp(timestamp):
            return ("pd.Timestamp", str(timestamp))

        rules += [
            (pd._libs.interval.Interval, normalize_interval),
            (pd._libs.tslibs.timestamps.Timestamp, normalize_timestamp),
        ]
    except ImportError:
        pass

    try:
        import pyarrow as pa

        def normalize_pyarrow_table(table):
            return ("pa.Table", tuple(
                dask.base.tokenize(el.serialize().to_pybytes())
                for el in table.to_batches()
            ))

        def normalize_pyarrow_schema(schema):
            return ("pa.Schema", str(schema))

        rules += [
            (pa.Table, normalize_pyarrow_table),
            (pa.Schema, normalize_pyarrow_schema),
        ]
    except ImportError:
        pass

    try:
        from sklearn.base import BaseEstimator

        def normalize_sklearn_estimator(estimator):
            params = tuple(sorted(estimator.get_params(deep=True).items()))
            return (
                "sklearn.estimator",
                type(estimator).__name__,
                type(estimator).__module__,
                params,
            )

        rules += [(BaseEstimator, normalize_sklearn_estimator)]
    except ImportError:
        pass

    return rules


EAGER_RULES: list[tuple] = [
    (type, normalize_type),
    (dict, normalize_dict),
    (types.ModuleType, normalize_module),
]
