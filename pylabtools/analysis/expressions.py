""" Evaluate the user's column expressions (``"20*np.log10(np.sqrt(I**2 + Q**2))"``,
``"9e9 < frequency < 10e9"``) for one emit.

An expression sees the emit's data columns as numpy arrays, ``np``, and the emit's procedure
parameters and metadata as scalars. Comparisons and logic work element-wise on arrays:
``a < x < b`` means ``(a < x) & (x < b)``, and ``and`` / ``or`` / ``not`` mean ``&`` / ``|`` / ``~``.
Used by :meth:`RecordView.rows() <pylabtools.analysis.RecordView.rows>` and
:mod:`pylabtools.analysis.plot`; it needs only numpy and pandas.
"""
import ast
import copy
from collections.abc import Mapping
from functools import lru_cache, reduce

import numpy as np
import pandas as pd

_PROC, _META = "proc_", "meta_"
RTOL = 1e-9  # - relative tolerance of == between floats, as in RecordView.where(name=value) - #


def _is_float(value):
    return np.issubdtype(np.asarray(value).dtype, np.floating)


def _is_real(value):
    kind = np.asarray(value).dtype.kind
    return kind in "iuf"


def equal(a, b):
    """ Element-wise ``a == b``; floats are compared with a relative tolerance of ``RTOL``. """
    if (_is_float(a) or _is_float(b)) and _is_real(a) and _is_real(b):
        return np.isclose(a, b, rtol=RTOL, atol=0.0)
    return np.asarray(a == b)


def isin(a, values):
    """ Element-wise ``a in values``, with :func:`equal`. """
    if isinstance(values, str):
        raise TypeError(f"'in {values!r}': give a list of values, e.g. in [{values!r}].")
    values = list(values)
    if not values:
        return np.zeros(np.shape(a), dtype=bool)
    return reduce(np.logical_or, [equal(a, v) for v in values])


_AND, _OR, _NOT, _EQ, _IN = "__plab_and", "__plab_or", "__plab_not", "__plab_eq", "__plab_in"
_GLOBALS = {"np": np, "numpy": np,
            _AND: lambda *values: reduce(np.logical_and, values),
            _OR: lambda *values: reduce(np.logical_or, values),
            _NOT: np.logical_not, _EQ: equal, _IN: isin}


class Names(Mapping):
    """ Names available to an expression: data columns, then ``proc_``/``meta_`` prefixed names,
    then parameters and metadata. ``shared`` are the names in both the parameters and metadata,
    which must be prefixed. """

    def __init__(self, data, params, meta, shared, with_data=True):
        self.data, self.params, self.meta, self.shared = data, params, meta, shared
        self.with_data = with_data

    def __getitem__(self, key):
        if self.with_data and key in self.data.columns:
            return self.data[key].to_numpy()
        if key.startswith(_PROC) and key[len(_PROC):] in self.params:
            return self.params[key[len(_PROC):]]
        if key.startswith(_META) and key[len(_META):] in self.meta:
            return self.meta[key[len(_META):]]
        if key in self.shared:
            raise NameError(f"{key!r} is both a procedure parameter and metadata; use 'proc_{key}' or "
                            f"'meta_{key}'.")
        if key in self.params:
            return self.params[key]
        if key in self.meta:
            return self.meta[key]
        raise KeyError(key)

    def __iter__(self):
        columns = list(self.data.columns) if self.with_data else []
        return iter(columns + list(self.params) + list(self.meta))

    def __len__(self):
        return len(list(iter(self)))

    def describe(self):
        columns = f"data columns {list(self.data.columns)}, " if self.with_data else ""
        return f"{columns}parameters {list(self.params)}, metadata {list(self.meta)}"


class _ArrayLogic(ast.NodeTransformer):
    """ Rewrite chained comparisons and ``and``/``or``/``not``, which need single truth values in
    Python, into element-wise numpy calls. """

    def visit_Compare(self, node):
        self.generic_visit(node)
        operands = [node.left, *node.comparators]
        pairs = [_compare(copy.deepcopy(a), op, copy.deepcopy(b))
                 for a, op, b in zip(operands, node.ops, operands[1:])]
        return ast.copy_location(pairs[0] if len(pairs) == 1 else _call(_AND, pairs), node)

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        return ast.copy_location(_call(_AND if isinstance(node.op, ast.And) else _OR, node.values), node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Not):
            return ast.copy_location(_call(_NOT, [node.operand]), node)
        return node


def _compare(a, op, b):
    """ One comparison; ``==``, ``!=``, ``in`` and ``not in`` become tolerant, element-wise calls. """
    if isinstance(op, (ast.Eq, ast.NotEq)):
        call = _call(_EQ, [a, b])
    elif isinstance(op, (ast.In, ast.NotIn)):
        call = _call(_IN, [a, b])
    else:
        return ast.Compare(left=a, ops=[op], comparators=[b])
    return _call(_NOT, [call]) if isinstance(op, (ast.NotEq, ast.NotIn)) else call


def _call(name, args):
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=list(args), keywords=[])


@lru_cache(maxsize=256)
def _compile(expression):
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise SyntaxError(f"{expression!r} is not a valid expression: {exc.msg}.") from None
    tree = ast.fix_missing_locations(_ArrayLogic().visit(tree))
    return compile(tree, "<expression>", "eval")


def run(expression, names, what=None):
    """ Evaluate ``expression`` with ``names``; a NameError lists what is available. """
    try:
        return eval(_compile(expression), _GLOBALS, names)  # noqa: S307  (the user's own expression)
    except NameError as exc:
        label = f"{what} {expression!r}" if what else repr(expression)
        raise NameError(f"{label}: {exc}. Available: {names.describe()}.") from None


def evaluate(expression, names, n_rows, what=None):
    """ Evaluate a column name or expression for one emit, as an array of ``n_rows``; scalars are
    repeated for every row. """
    if names.with_data and expression in names.data.columns:
        return names.data[expression].to_numpy()
    result = run(expression, names, what)
    result = np.asarray(result.to_numpy() if isinstance(result, pd.Series) else result)
    if result.ndim == 0:
        return np.full(n_rows, result.item())
    if result.shape != (n_rows,):
        label = f"{what} {expression!r}" if what else repr(expression)
        raise ValueError(f"{label} gave shape {result.shape}, but the emit has {n_rows} rows.")
    return result
