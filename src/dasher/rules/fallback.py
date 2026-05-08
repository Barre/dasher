"""Fallback rule that probes __dask_tokenize__ before raising.

Registered against builtins.object and placed last in the rule order so any
more specific rule wins via MRO + earliest-match-wins tiebreaking.
"""
from __future__ import annotations


def normalize_object_fallback(obj):
    method = getattr(obj, "__dask_tokenize__", None)
    if method is not None and not isinstance(obj, type):
        return method()
    raise ValueError(
        f"No normalizer registered for {type(obj)!r} and no __dask_tokenize__: {obj!r}"
    )


RULES: tuple = (
    ("builtins.object", normalize_object_fallback),
)
