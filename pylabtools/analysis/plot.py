""" Line and scatter plots of :class:`~pylabtools.analysis.RecordView` data with matplotlib.

Needs matplotlib (``pip install pylabtools[analysis]``). Everything is drawn through the
object-oriented interface onto one :class:`~matplotlib.axes.Axes`; pyplot is only used to create a
figure when no ``ax`` is given.

.. code-block:: python

    from pylabtools.analysis.plot import lineplot, scatterplot

    fig, ax = lineplot(vna, x="frequency", y="20*np.log10(np.sqrt(I**2 + Q**2))",
                       color_by="setpoint", ylabel="|S21| (dB)")
"""
import numbers
import warnings

import numpy as np
import pandas as pd

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.cm import ScalarMappable

from ..recorders.base import RECORD_ROW
from .expressions import Names as _Names
from .expressions import evaluate as _evaluate
from .expressions import run as _run

__all__ = ["AveragingWarning", "lineplot", "scatterplot"]

_COLOR_KWARGS = ("color", "c", "colors")


class AveragingWarning(UserWarning):
    """ Issued when ``average=True`` averages emits whose ``x`` values differ. """


def lineplot(view, x, y, color_by=None, average=False, xaverage_silent=False, ax=None, xlabel=None,
             ylabel=None, title=None, cmap="viridis", norm=None, colorbar=True, clabel=None, legend=True,
             **kwargs):
    """ Plot one line per emit of a view, with ``ax.plot``.

    .. code-block:: python

        lineplot(vna, x="frequency", y="20*np.log10(np.sqrt(I**2 + Q**2))")
        lineplot(vna, x="frequency", y="I", color_by="setpoint")            # colour bar
        lineplot(vna, x="frequency", y="I", color_by="mode")                # legend
        lineplot(vna, x="frequency", y="I", color_by="setpoint", average=True, lw=2)

    :param view: The :class:`~pylabtools.analysis.RecordView` to plot.
    :param x: Data column name, or an expression evaluated for every emit. Expressions can use the
        data columns, ``np``, and the emit's procedure parameters and metadata (looked up as in
        :meth:`~pylabtools.analysis.RecordView.where`; prefix with ``proc_`` / ``meta_`` when a name
        is in both). Scalars are repeated for every row.
    :param y: Column name or expression, as ``x``.
    :param color_by: Optional parameter or metadata name, or an expression of them, giving one value
        per emit. Numbers colour the lines on ``cmap`` with a colour bar; other values (e.g. strings)
        get one colour per distinct value and a legend.
    :param average: If True, average the emits that share a ``color_by`` value (all emits when
        ``color_by`` is None) into one line. The numeric data columns are averaged row by row
        before ``x`` and ``y`` are evaluated, so ``y`` sees the averaged columns. The emits of a
        group must have the same number of rows. If their ``x`` values differ (e.g. different
        frequency grids, or ``x="I"`` for an I-Q circle) they are still averaged, with an
        :class:`AveragingWarning`. Parameters that differ within a group cannot be used in ``x``
        or ``y``.
    :param xaverage_silent: If True, do not warn when ``average=True`` averages emits whose ``x``
        values differ.
    :param ax: Axes to draw on. By default a new figure and axes are created.
    :param xlabel: x-axis label (default: ``x``).
    :param ylabel: y-axis label (default: ``y``).
    :param title: Optional axes title (default: none).
    :param cmap: Colormap for numeric ``color_by`` values.
    :param norm: Optional :class:`matplotlib.colors.Normalize` (e.g. ``LogNorm()``) for numeric
        ``color_by`` values; limits left unset are taken from the data.
    :param colorbar: Whether to add a colour bar for numeric ``color_by`` values.
    :param clabel: Colour bar or legend title (default: ``color_by``).
    :param legend: Whether to add a legend for non-numeric ``color_by`` values.
    :param kwargs: Passed to :meth:`matplotlib.axes.Axes.plot` (``lw``, ``ls``, ``marker``, ``alpha``, ...).
    :return: ``(fig, ax)``.
    """
    return _plot("plot", view, x, y, color_by, average, xaverage_silent, ax, xlabel, ylabel, title, cmap,
                 norm, colorbar, clabel, legend, kwargs)


def scatterplot(view, x, y, color_by=None, average=False, xaverage_silent=False, ax=None, xlabel=None,
                ylabel=None, title=None, cmap="viridis", norm=None, colorbar=True, clabel=None, legend=True,
                **kwargs):
    """ Scatter plot of every emit of a view, with ``ax.scatter``.

    Takes the same arguments as :func:`lineplot`; ``kwargs`` go to
    :meth:`matplotlib.axes.Axes.scatter` (``s``, ``marker``, ``alpha``, ...). Points are coloured
    per emit by ``color_by``. With ``average=True``, averaging I-Q circles (``x="I", y="Q"``)
    warns that ``x`` differs between emits; pass ``xaverage_silent=True`` to silence it.

    :return: ``(fig, ax)``.
    """
    return _plot("scatter", view, x, y, color_by, average, xaverage_silent, ax, xlabel, ylabel, title, cmap,
                 norm, colorbar, clabel, legend, kwargs)


# - implementation ------------------------------------------------------------------------------- #
def _plot(kind, view, x, y, color_by, average, xaverage_silent, ax, xlabel, ylabel, title, cmap, norm,
          colorbar, clabel, legend, kwargs):
    if len(view) == 0:
        raise ValueError(f"{view.name!r}: the view has no emits to plot.")
    if color_by is not None:
        clash = [k for k in _COLOR_KWARGS if k in kwargs]
        if clash:
            raise ValueError(f"{clash[0]}= cannot be combined with color_by=; the colours come from color_by.")

    emits = list(view.emits())
    shared = _shared(view)
    cvalues = _color_values(emits, color_by, shared)
    traces, differing = _traces(emits, x, y, cvalues, average, shared)
    if differing and not xaverage_silent:
        which = f"color_by values {differing}" if color_by is not None else "all emits"
        warnings.warn(f"average=True averaged emits whose x ({x!r}) differs, for {which}. Pass "
                      "xaverage_silent=True if this is intended (e.g. averaging I-Q circles).",
                      AveragingWarning, stacklevel=3)

    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.figure
    draw = ax.plot if kind == "plot" else ax.scatter
    clabel = color_by if clabel is None else clabel

    if cvalues is None:
        for xs, ys, _ in traces:
            draw(xs, ys, **kwargs)
    elif all(_is_number(v) for v in cvalues):
        cmap = matplotlib.colormaps[cmap] if isinstance(cmap, str) else cmap
        norm = mcolors.Normalize() if norm is None else norm
        norm.autoscale_None(np.ma.masked_invalid(np.asarray(cvalues, dtype=float)))
        for xs, ys, value in traces:
            draw(xs, ys, color=cmap(norm(float(value))), **kwargs)
        if colorbar:
            fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=ax, label=clabel)
    else:
        palette = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])
        order = _distinct(cvalues)
        color_of = {value: palette[i % len(palette)] for i, value in enumerate(order)}
        labelled = set()
        for xs, ys, value in sorted(traces, key=lambda t: order.index(_hashable(t[2]))):
            key = _hashable(value)
            draw(xs, ys, color=color_of[key], label=None if key in labelled else str(value), **kwargs)
            labelled.add(key)
        if legend:
            ax.legend(title=clabel)

    ax.set_xlabel(x if xlabel is None else xlabel)
    ax.set_ylabel(y if ylabel is None else ylabel)
    if title is not None:
        ax.set_title(title)
    return fig, ax


def _traces(emits, x, y, cvalues, average, shared):
    """ ``[(x array, y array, colour value)]``, one per emit or per averaged group, and the colour
    values of the averaged groups whose emits have differing ``x``. """
    if not average:
        traces = []
        for i, emit in enumerate(emits):
            names = _Names(emit.data, emit.params, emit.meta, shared)
            traces.append((_evaluate(x, names, len(emit.data)), _evaluate(y, names, len(emit.data)),
                           None if cvalues is None else cvalues[i]))
        return traces, []

    groups = {}
    for i, emit in enumerate(emits):
        value = None if cvalues is None else cvalues[i]
        groups.setdefault(_hashable(value), (value, []))[1].append(emit)
    traces, differing = [], []
    for value, members in groups.values():
        xs, ys, same_x = _average(members, x, y, value, shared)
        traces.append((xs, ys, value))
        if not same_x:
            differing.append(value)
    return traces, differing


def _average(emits, x, y, value, shared):
    lengths = {len(e.data) for e in emits}
    if len(lengths) > 1:
        raise ValueError(f"average=True: the emits with color_by value {value!r} have different numbers of "
                         f"rows {sorted(lengths)}; they cannot be averaged row by row.")
    n = lengths.pop()
    first = _evaluate(x, _Names(emits[0].data, emits[0].params, emits[0].meta, shared), n)
    same_x = all(_same(first, _evaluate(x, _Names(e.data, e.params, e.meta, shared), n)) for e in emits[1:])
    data = (pd.concat([e.data.select_dtypes("number") for e in emits])
              .groupby(level=RECORD_ROW).mean())
    params = _common([e.params for e in emits])
    meta = _common([e.meta for e in emits])
    names = _Names(data, params, meta, shared & set(params) & set(meta))
    return _evaluate(x, names, n), _evaluate(y, names, n), same_x


def _shared(view):
    """ Names that are both procedure parameters and metadata, which must be prefixed. """
    return set(view.proc_params.columns) & set(view.meta.columns)


def _color_values(emits, color_by, shared):
    """ The ``color_by`` value of every emit, or None without ``color_by``. """
    return None if color_by is None else [_color_value(e, color_by, shared) for e in emits]


def _numeric_colors(view, color_by):
    """ True if ``color_by`` gives numbers (colour bar), False for other values (legend), None
    without ``color_by``. """
    values = _color_values(list(view.emits()), color_by, _shared(view))
    return None if values is None else all(_is_number(v) for v in values)


def _color_value(emit, color_by, shared):
    names = _Names(emit.data, emit.params, emit.meta, shared, with_data=False)
    try:
        return names[color_by]
    except KeyError:
        pass
    value = np.asarray(_run(color_by, names, what="color_by"))
    if value.ndim != 0:
        raise ValueError(f"color_by {color_by!r} must give one value per emit, not shape {value.shape}.")
    return value.item()


def _is_number(value):
    """ Numbers (NaN included, drawn in the colormap's "bad" colour) get a colour bar. """
    return isinstance(value, numbers.Real) and not isinstance(value, (bool, np.bool_))


def _distinct(values):
    unique = list(dict.fromkeys(_hashable(v) for v in values))
    try:
        return sorted(unique)
    except TypeError:
        return unique


def _hashable(value):
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def _same(a, b):
    if a.shape != b.shape:
        return False
    if np.issubdtype(a.dtype, np.number) and np.issubdtype(b.dtype, np.number):
        return bool(np.allclose(a, b, rtol=1e-9, atol=0.0, equal_nan=True))
    return bool(np.array_equal(a, b))


def _common(mappings):
    """ The items with the same value in every mapping. """
    common = {}
    for key, value in mappings[0].items():
        if all(key in m and _equal(m[key], value) for m in mappings[1:]):
            common[key] = value
    return common


def _equal(a, b):
    try:
        if pd.isna(a) and pd.isna(b):
            return True
    except (TypeError, ValueError):
        pass
    try:
        return bool(a == b)
    except (TypeError, ValueError):
        return False
