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
    "co_posonlyargcount",
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


def normalize_function(func):
    return ("function", *(getattr(func, a, None) for a in _FUNCTION_ATTRS))


def normalize_code(code):
    return ("code", *(getattr(code, a, None) for a in _CODE_ATTRS))


_EMPTY_CELL = object()


def normalize_cell(cell):
    try:
        contents = cell.cell_contents
    except ValueError:
        contents = _EMPTY_CELL
    return ("cell", contents)


RULES: tuple = (
    (fqn(types.FunctionType), normalize_function),
    (fqn(types.MethodType),   normalize_function),
    (fqn(types.CodeType),     normalize_code),
    (fqn(types.CellType),     normalize_cell),
    (fqn(classmethod),        normalize_function),
    (fqn(staticmethod),       normalize_function),
)
