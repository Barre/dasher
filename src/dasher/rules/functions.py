"""Normalizers for Python callables and code objects."""
from __future__ import annotations

import types

from dasher.core import fqn


_CODE_ATTRS = (
    "co_argcount",
    "co_cellvars",
    "co_code",
    "co_consts",
    "co_flags",
    "co_freevars",
    "co_kwonlyargcount",
    "co_name",
    "co_names",
    "co_nlocals",
    "co_stacksize",
    "co_varnames",
)

_FUNCTION_ATTRS = (
    "__closure__",
    "__code__",
    "__defaults__",
    "__dict__",
    "__kwdefaults__",
    "__module__",
    "__name__",
    "__qualname__",
)


def _unwrap(obj):
    while hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__
    return obj


def normalize_function(func):
    func = _unwrap(func)
    return ("function", *(getattr(func, a, None) for a in _FUNCTION_ATTRS))


def normalize_code(code):
    return ("code", *(getattr(code, a, None) for a in _CODE_ATTRS))


def normalize_cell(cell):
    return ("cell", cell.cell_contents)


RULES: tuple = (
    (fqn(types.FunctionType), normalize_function),
    (fqn(types.MethodType),   normalize_function),
    (fqn(types.CodeType),     normalize_code),
    (fqn(types.CellType),     normalize_cell),
    (fqn(classmethod),        normalize_function),
)
