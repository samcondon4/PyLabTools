""" :class:`Dataset` and :class:`RecordView`: navigate, filter and reduce recorded data.

A :class:`Dataset` opens one recorder output (an :class:`~pylabtools.HDFRecorder` file or a
:class:`~pylabtools.CSVRecorder` directory). Indexing it by record name gives a
:class:`RecordView`, which keeps the three PyLabTools tables apart:

``data``
    One row per data row, indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``.
``proc_params``
    One row per emit, indexed by ``(RecordGroup, RecordGroupInd)``.
``meta``
    One row per emit, indexed by ``(RecordGroup, RecordGroupInd)``, including ``timestamp``.

Views are immutable: :meth:`RecordView.where`, :meth:`RecordView.rows`, :meth:`RecordView.group` and
:meth:`RecordView.align` return new views.
"""
import numbers
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from ..recorders.base import DATA_INDEX, EMIT_INDEX, RECORD_GROUP, RECORD_ROW, TIMESTAMP
from ..recorders.csv import _is_record_file, read_csv
from ..recorders.hdf import hdf_records, join_tables, read_hdf, resolve_groups
from .expressions import Names, evaluate

__all__ = ["Dataset", "Emit", "RecordView", "concat"]

_PROC, _META = "proc_", "meta_"


class Dataset:
    """ A recorded dataset: an HDF5 file written by :class:`~pylabtools.HDFRecorder`, or a
    directory written by :class:`~pylabtools.CSVRecorder`.

    .. code-block:: python

        ds = plab.analysis.Dataset("cooldown_12.h5")
        ds.records                  # ['fridge', 's21']
        s21 = ds["s21"]             # RecordView, read once and cached
        latest = ds.record("s21", groups=-1)   # read only some RecordGroups (not cached)

    :param source: Path of the HDF5 file or CSV directory.
    :raises FileNotFoundError: If ``source`` does not exist.
    """

    def __init__(self, source):
        self.path = Path(source)
        if not self.path.exists():
            raise FileNotFoundError(f"No dataset at {self.path}.")
        self.format = "csv" if self.path.is_dir() else "hdf"
        self._cache = {}

    @property
    def records(self):
        """ Names of the records in the dataset, sorted. """
        if self.format == "hdf":
            return hdf_records(self.path)
        return sorted(p.stem for p in self.path.glob("*.csv") if _is_record_file(p))

    def record(self, name, groups=None):
        """ Read one record into a :class:`RecordView`.

        :param name: Record name.
        :param groups: Optional ``RecordGroup`` number or list of numbers to read; negative numbers
            count from the end (``-1`` is the latest group).
        """
        if name not in self.records:
            raise KeyError(f"{self.path} has no record {name!r}; records are {self.records}.")
        if self.format == "hdf":
            tables = read_hdf(self.path, name, join=False, groups=groups)
            return RecordView(name, tables["data"], tables["proc_params"], tables["meta"])
        return _view_from_merged(name, read_csv(self.path, name, groups=groups))

    def __getitem__(self, name):
        if name not in self._cache:
            self._cache[name] = self.record(name)
        return self._cache[name]

    def __contains__(self, name):
        return name in self.records

    def __iter__(self):
        return iter(self.records)

    def __len__(self):
        return len(self.records)

    def __repr__(self):
        return f"Dataset({str(self.path)!r}, records={self.records})"


@dataclass(frozen=True)
class Emit:
    """ One emit of a record, as yielded by :meth:`RecordView.emits`.

    :param group: ``RecordGroup`` number.
    :param index: ``RecordGroupInd``, the emit counter within the group.
    :param params: Procedure parameter values.
    :param meta: Metadata, including ``timestamp``.
    :param data: The emitted rows, indexed by ``RecordRow``.
    """

    group: int
    index: int
    params: Mapping[str, Any]
    meta: Mapping[str, Any]
    data: pd.DataFrame

    @property
    def key(self):
        """ ``(RecordGroup, RecordGroupInd)``. """
        return (self.group, self.index)

    @property
    def timestamp(self):
        """ Time of the emit. """
        return self.meta.get(TIMESTAMP)

    def __repr__(self):
        return f"Emit(group={self.group}, index={self.index}, params={dict(self.params)}, rows={len(self.data)})"


class RecordView:
    """ The recorded data of one record name, or a filtered subset of it.

    Normally obtained from a :class:`Dataset`; it can also be built directly from the three tables
    (``data`` indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``, ``proc_params`` and ``meta``
    indexed by ``(RecordGroup, RecordGroupInd)``), e.g. ``read_hdf(..., join=False)``.

    ``fits`` holds the results of analysis steps that change the data, such as
    :func:`~pylabtools.analysis.resonator.calibrate_cable_delay`: a mapping of step names to tables
    with one row per emit, indexed by ``(RecordGroup, RecordGroupInd)`` like ``proc_params``. Every
    selection carries them along. They live only in memory; they are not part of a recorded file.
    """

    def __init__(self, name, data, proc_params, meta, fits=None):
        self.name = name
        self.data = _with_index(data, DATA_INDEX)
        self.proc_params = _with_index(proc_params, EMIT_INDEX)
        self.meta = _with_index(meta, EMIT_INDEX)
        # - one row per emit of this view, in its order: NaN for emits a step did not cover - #
        self._fits = MappingProxyType({step: _with_index(table, EMIT_INDEX).reindex(self.keys)
                                       for step, table in (fits or {}).items()})

    # - basic properties ----------------------------------------------------------------------- #
    @property
    def fits(self):
        """ Results of the analysis steps applied to this view, e.g. ``fits["cable_delay"]``: a
        read-only mapping of step names to tables with one row per emit (in the order of
        :attr:`keys`), indexed by ``(RecordGroup, RecordGroupInd)``. Emits a step did not cover
        have NaN rows. Empty for a view read from a file. """
        return self._fits

    @property
    def groups(self):
        """ The ``RecordGroup`` numbers in this view, sorted. """
        return sorted(int(g) for g in self.proc_params.index.get_level_values(RECORD_GROUP).unique())

    @property
    def keys(self):
        """ The ``(RecordGroup, RecordGroupInd)`` of every emit, as a MultiIndex. """
        return self.proc_params.index

    @property
    def columns(self):
        """ Names of the data columns. """
        return list(self.data.columns)

    @property
    def params(self):
        """ Names of the procedure parameters. """
        return list(self.proc_params.columns)

    def __len__(self):
        return len(self.proc_params.index)

    def __iter__(self):
        return self.emits()

    def __repr__(self):
        fits = f", fits={list(self.fits)}" if self.fits else ""
        return (f"RecordView({self.name!r}, groups={self.groups}, emits={len(self)}, rows={len(self.data)}, "
                f"columns={self.columns}{fits})")

    def with_data(self, data, step=None, table=None):
        """ A new view with the same emits but new ``data``, optionally recording the per-emit
        ``table`` of an analysis step in :attr:`fits` as ``step``.

        For analysis steps that transform the data, such as calibrations.

        :raises ValueError: If ``step`` is already in :attr:`fits`.
        """
        fits = dict(self.fits)
        if step is not None:
            if step in fits:
                raise ValueError(f"{self.name!r} already has fit results {step!r}; the step was already applied.")
            fits[step] = table
        return RecordView(self.name, data, self.proc_params, self.meta, fits=fits)

    # - tables --------------------------------------------------------------------------------- #
    def emit_table(self):
        """ One row per emit: the procedure parameters and metadata as ``proc_<name>`` and
        ``meta_<name>`` columns, indexed by ``(RecordGroup, RecordGroupInd)``. """
        return pd.concat([_prefixed(self.proc_params, _PROC), _prefixed(self.meta, _META)], axis=1)

    def to_frame(self):
        """ One row per data row with the parameters and metadata joined on, exactly like
        :func:`~pylabtools.read_hdf` with ``join=True``. """
        return join_tables(self.data.reset_index(), self.proc_params.reset_index(), self.meta.reset_index())

    # - selection ------------------------------------------------------------------------------ #
    def group(self, groups):
        """ The emits of one or more ``RecordGroup`` numbers; negative numbers count from the end. """
        wanted = resolve_groups(groups, self.groups)
        missing = sorted(set(wanted) - set(self.groups))
        if missing:
            raise KeyError(f"{self.name!r} has no RecordGroup {missing}; groups are {self.groups}.")
        return self._subset(self.keys[self.keys.get_level_values(RECORD_GROUP).isin(wanted)])

    def where(self, *conditions, **matches):
        """ The emits whose parameters and metadata meet all of the given conditions.

        .. code-block:: python

            s21.where("setpoint < 0.1")                          # an expression
            s21.where("power in [-20, -10] and trace == 0")
            s21.where("proc_power > meta_vna_power - 1")         # prefixed names
            s21.where(power=p)                                   # a value, e.g. a variable
            s21.where(power=[-20, -10], trace=0)                 # any of several values

        Expressions are Python, evaluated for all emits at once with the parameter and metadata
        names and ``np``, as in :mod:`~pylabtools.analysis.plot`. ``a < x < b``, ``and``, ``or``,
        ``not`` and ``in [...]`` work element-wise, and ``==`` compares floats with a relative
        tolerance of 1e-9 (so ``0.15 - 0.05`` matches a stored ``0.1``), as do the keywords. Names
        are looked up among the procedure parameters and then the metadata; prefix them with
        ``proc_`` or ``meta_`` when a name is in both. To select rows of the data within each emit,
        use :meth:`rows`.

        :param conditions: Expression strings, or boolean masks with one value per emit (e.g. built
            from :meth:`reduce`).
        :param matches: ``name=value``: a value, or a list/tuple/set of values to match any of.
        :raises TypeError: For a condition that is neither a string nor a mask.
        """
        table = self.emit_table()
        mask = np.ones(len(table.index), dtype=bool)
        for condition in conditions:
            mask &= self._emit_mask(condition)
        for key, value in matches.items():
            mask &= _matches(table[self._column(table, key)], value, key)
        return self._subset(table.index[mask])

    def rows(self, *conditions):
        """ Keep only the data rows meeting all of the given conditions, within every emit.

        .. code-block:: python

            s21.rows("9e9 < frequency < 10e9")                   # a frequency window
            s21.rows("abs(frequency - f0) < 2e6")                # around each emit's metadata f0
            s21.where(power=-20).rows("frequency > 9e9", "I**2 + Q**2 > 1e-6")

        Each expression is evaluated for every emit with its data columns (as arrays), its
        parameters and metadata (as values) and ``np``, exactly like the expressions of
        :mod:`~pylabtools.analysis.plot`, and must give True or False per row. Comparisons and
        logic work element-wise as in :meth:`where`.

        Every emit is kept, even if none of its rows are, with its parameters and metadata. The kept
        rows keep their ``RecordRow`` numbers, so rows still line up across emits (for
        ``average=True`` plots, say).

        :param conditions: Expression strings.
        :return: A new :class:`RecordView`.
        """
        if not conditions or self.data.empty:
            for condition in conditions:
                _check_expression(condition, "rows()")
            return self
        return RecordView(self.name, self.data[self._row_mask(conditions, "rows()")], self.proc_params,
                          self.meta, fits=self.fits)

    def _row_mask(self, conditions, what):
        """ Boolean array over the rows of :attr:`data`: True where every expression holds, each
        evaluated per emit with its data columns, parameters and metadata. """
        for condition in conditions:
            _check_expression(condition, what)
        keep = np.ones(len(self.data.index), dtype=bool)
        if not conditions or self.data.empty:
            return keep
        shared = set(self.proc_params.columns) & set(self.meta.columns)
        params = self.proc_params.to_dict("index")
        meta = self.meta.to_dict("index")
        for key, positions in self.data.groupby(level=EMIT_INDEX, sort=False).indices.items():
            names = Names(self.data.iloc[positions].droplevel(EMIT_INDEX), params[key], meta[key], shared)
            for condition in conditions:
                keep[positions] &= _boolean(evaluate(condition, names, len(positions), what=what), condition, "row")
        return keep

    def _emit_mask(self, condition):
        if isinstance(condition, str):
            shared = set(self.proc_params.columns) & set(self.meta.columns)
            names = Names(self.data.iloc[:0], _columns_of(self.proc_params), _columns_of(self.meta), shared,
                          with_data=False)
            try:
                result = evaluate(condition, names, len(self), what="where()")
            except NameError as exc:
                hint = "" if not self.columns else f" Data columns {self.columns} are selected with rows()."
                raise NameError(f"{exc}{hint}") from None
            return _boolean(result, condition, "emit")
        if callable(condition):
            raise TypeError("where() takes expression strings, e.g. where(\"setpoint < 0.1\"), not functions.")
        mask = condition.to_numpy() if isinstance(condition, pd.Series) else np.asarray(condition)
        if mask.dtype != bool or mask.shape != (len(self),):
            raise TypeError(f"where() conditions are expression strings or boolean masks with one value per "
                            f"emit ({len(self)}); got {type(condition).__name__} of dtype {mask.dtype} and "
                            f"shape {mask.shape}.")
        return mask

    def values(self, name, dropna=True):
        """ The distinct values of a procedure parameter or metadata item, sorted.

        .. code-block:: python

            s21.values("power")                     # [-20.0, -10.0, 0.0]
            for power in s21.values("power"):
                trace = s21.where(power=power)

        Names are looked up as in :meth:`where`. Float values that :meth:`where` treats as equal
        (relative tolerance 1e-9) are merged into one, so every returned value selects the emits it
        stands for.

        :param name: Parameter or metadata name, optionally prefixed with ``proc_`` or ``meta_``.
        :param dropna: If False, a trailing NaN is included when some emits have no value.
        :return: A list of plain Python values. Values that cannot be ordered keep the order in which
            they first appear.
        """
        table = self.emit_table()
        series = table[self._column(table, name)]
        missing = bool(series.isna().any())
        unique = series.dropna().drop_duplicates()
        try:
            unique = unique.sort_values()
        except TypeError:
            pass
        result = unique.tolist()
        if ptypes.is_float_dtype(series.dtype):
            result = _merge_close(result)
        if missing and not dropna:
            result.append(np.nan)
        return result

    def _column(self, table, key):
        if key in table.columns:
            return key
        found = [p + key for p in (_PROC, _META) if p + key in table.columns]
        if len(found) == 1:
            return found[0]
        if found:
            raise ValueError(f"{key!r} is both a procedure parameter and metadata of {self.name!r}; "
                             f"use {found[0]!r} or {found[1]!r}.")
        raise KeyError(f"{self.name!r} has no parameter or metadata {key!r}; "
                       f"parameters are {self.params}, metadata {list(self.meta.columns)}.")

    def _subset(self, keys):
        if not isinstance(keys, pd.MultiIndex):
            keys = pd.MultiIndex.from_tuples(list(keys), names=EMIT_INDEX) if len(keys) else self.keys[:0]
        rows = self.data.index.droplevel(RECORD_ROW).isin(keys)
        return RecordView(self.name, self.data[rows], self.proc_params.loc[keys], self.meta.loc[keys],
                          fits=self.fits)

    # - iteration and reduction ---------------------------------------------------------------- #
    def emits(self):
        """ Iterate over the emits in order, yielding an :class:`Emit` for each. Emits that had no
        data rows are included, with empty ``data``. """
        data = {key: frame.droplevel(EMIT_INDEX) for key, frame in self.data.groupby(level=EMIT_INDEX)}
        empty = self.data.iloc[:0].droplevel(EMIT_INDEX)
        params = self.proc_params.to_dict("index")
        meta = self.meta.to_dict("index")
        for key in self.keys:
            yield Emit(group=int(key[0]), index=int(key[1]), params=params[key], meta=meta[key],
                       data=data.get(key, empty))

    def reduce(self, func, name=None):
        """ Reduce every emit's data to a few numbers, giving one row per emit.

        .. code-block:: python

            s21.reduce("mean")                                 # mean of every numeric column
            s21.reduce(lambda d: d.s21.min(), name="depth")    # one scalar per emit
            s21.reduce(lambda d: {"f_min": d.f[d.s21.idxmin()], "depth": d.s21.min()})

        :param func: A function of the emit's data (a DataFrame indexed by ``RecordRow``) returning a
            scalar, dict or Series; or the name of a DataFrame reduction such as ``"mean"``,
            ``"std"``, ``"min"`` or ``"max"``, applied to the numeric columns.
        :param name: Column name for a scalar result (default: the function's name, or ``"value"``).
        :return: The :meth:`emit_table` with the results joined on as extra columns.
        """
        if isinstance(func, str):
            method = func
            func = lambda data: getattr(data.select_dtypes("number"), method)()  # noqa: E731
            label = method
        else:
            label = name or getattr(func, "__name__", "value")
            label = "value" if label == "<lambda>" else label

        rows = []
        for emit in self.emits():
            result = func(emit.data)
            if isinstance(result, pd.Series):
                result = result.to_dict()
            elif not isinstance(result, Mapping):
                result = {label: result}
            rows.append(result)
        results = pd.DataFrame(rows, index=self.keys)
        table = self.emit_table()
        clash = sorted(set(results.columns) & set(table.columns))
        if clash:
            raise ValueError(f"reduce() results {clash} clash with emit_table() columns; rename them.")
        return pd.concat([table, results], axis=1)

    # - alignment ------------------------------------------------------------------------------ #
    def align(self, other, by="group", agg="mean", columns=None, window=None, tolerance=None, prefix=None):
        """ Attach statistics of another record to every emit of this one, e.g. the fridge
        temperatures measured while each VNA trace was taken.

        .. code-block:: python

            s21 = ds["s21"].align(ds["fridge"])                          # mean over each RecordGroup
            s21 = ds["s21"].align(ds["fridge"], by="nearest", tolerance="10s")
            s21 = ds["s21"].align(ds["fridge"], by="window", window=("30s", "0s"), agg="std")
            s21 = ds["s21"].align(ds["fridge"], agg=["mean", "std"])     # fridge_T5_mean, fridge_T5_std
            s21.where("fridge_T5 < 0.05").reduce(...)

        The statistics are added to the new view's metadata as ``<prefix><column>`` (by default
        ``<other record>_<column>``), plus ``<prefix>n``, the number of rows aggregated, and, for
        ``by="nearest"``, ``<prefix>dt``, the time of the matched emit minus the time of this emit.
        Times are the emit ``timestamp`` metadata.

        :param other: The :class:`RecordView` to take statistics from.
        :param by: ``"group"``: all rows of ``other`` in the same ``RecordGroup``. ``"nearest"``: the
            rows of the emit of ``other`` nearest in time. ``"window"``: the rows of the emits of
            ``other`` within ``window`` of this emit.
        :param agg: Aggregation applied to each column: a name such as ``"mean"``, ``"median"``,
            ``"std"``, ``"min"``, ``"max"``, or a function of a Series. A list, e.g.
            ``["mean", "std"]``, applies each one and names the columns
            ``<prefix><column>_<agg>`` (``fridge_T5_mean``, ``fridge_T5_std``); functions in a list
            are named by their ``__name__``, so define them with ``def``.
        :param columns: Columns of ``other`` to aggregate (default: all numeric columns).
        :param window: For ``by="window"``: a time span ``w`` (the emits within ``w`` either side) or
            a pair ``(before, after)``. Numbers are seconds; strings such as ``"30s"`` and
            ``Timedelta`` objects work too.
        :param tolerance: For ``by="nearest"``: optional maximum time difference; emits without a
            match within it get NaN.
        :param prefix: Prefix of the new metadata columns.
        :return: A new :class:`RecordView` with the extra metadata.
        """
        if not isinstance(other, RecordView):
            raise TypeError(f"align() needs a RecordView, got {type(other).__name__}.")
        prefix = f"{other.name}_" if prefix is None else prefix
        if columns is None:
            columns = list(other.data.select_dtypes("number").columns)
        else:
            columns = [columns] if isinstance(columns, str) else list(columns)
            unknown = [c for c in columns if c not in other.columns]
            if unknown:
                raise KeyError(f"{other.name!r} has no columns {unknown}; columns are {other.columns}.")
        values = other.data[columns]
        agg = _aggregations(agg)

        if by == "group":
            grouped = values.groupby(level=RECORD_GROUP)
            stats = _aggregate(grouped, agg, columns).assign(n=grouped.size())
            groups = self.keys.get_level_values(RECORD_GROUP)
            stats = stats.reindex(groups).set_axis(self.keys)
        elif by == "nearest":
            stats = _align_nearest(self, other, values, agg, tolerance)
        elif by == "window":
            if window is None:
                raise ValueError('align(by="window") needs a window, e.g. window="30s".')
            stats = _align_window(self, other, values, agg, window)
        else:
            raise ValueError(f'align() by must be "group", "nearest" or "window", not {by!r}.')

        stats["n"] = stats["n"].fillna(0).astype(np.int64)
        stats = stats.rename(columns=lambda c: f"{prefix}{c}")
        clash = sorted(set(stats.columns) & set(self.meta.columns))
        if clash:
            raise ValueError(f"align() columns {clash} are already in the metadata of {self.name!r}; "
                             "pass another prefix=.")
        return RecordView(self.name, self.data, self.proc_params, pd.concat([self.meta, stats], axis=1),
                          fits=self.fits)


def concat(views, label="dataset", name=None):
    """ Combine several views, e.g. the same record from two datasets, into one.

    .. code-block:: python

        both = plab.analysis.concat({"cooldown 1": ds1["s21"], "cooldown 2": ds2["s21"]})
        plot_res_data(both, color_by="dataset")
        both.where("dataset == 'cooldown 2' and power == -10")

        plab.analysis.concat([ds1["s21"], ds2["s21"]])        # without labels

    Emits are numbered by ``(RecordGroup, RecordGroupInd)`` within each view, so the RecordGroups
    of each view are renumbered to follow those of the view before it, keeping their order. Given a
    mapping, every emit gets a metadata item ``label`` (default ``"dataset"``) holding its view's
    key, to select or colour by. Data columns, parameters or metadata that only some views have
    are NaN for the emits of the others, as are the :attr:`RecordView.fits` of views without a step.

    :param views: A mapping of labels to :class:`RecordView`, or a sequence of them (no labels).
    :param label: Name of the metadata item holding the labels of a mapping.
    :param name: Record name of the result; required if the views have different names.
    :return: A new :class:`RecordView`.
    :raises ValueError: If there are no views, their names differ and ``name`` is not given, or
        ``label`` is already metadata of a view.
    """
    labelled = isinstance(views, Mapping)
    items = list(views.items()) if labelled else [(None, v) for v in views]
    if not items:
        raise ValueError("concat() needs at least one RecordView.")
    for _, view in items:
        if not isinstance(view, RecordView):
            raise TypeError(f"concat() combines RecordViews, not {type(view).__name__}.")
    if name is None:
        names = sorted({view.name for _, view in items})
        if len(names) > 1:
            raise ValueError(f"concat() views have different record names {names}; pass name= to combine them.")
        name = names[0]
    if labelled:
        clash = [view.name for _, view in items if label in view.meta.columns]
        if clash:
            raise ValueError(f"concat() label {label!r} is already metadata of the views; pass another label=.")

    data, params, meta, fits, offset = [], [], [], {}, 0
    for key, view in items:
        shift = _group_shift(offset)
        data.append(shift(view.data))
        params.append(shift(view.proc_params))
        meta.append(shift(view.meta) if not labelled else shift(view.meta).assign(**{label: key}))
        for step, table in view.fits.items():
            fits.setdefault(step, []).append(shift(table))
        if len(view):
            offset += max(view.groups) + 1
    return RecordView(name, _concat_frames(data), _concat_frames(params), _concat_frames(meta),
                      fits={step: _concat_frames(tables) for step, tables in fits.items()})


def _group_shift(offset):
    def shift(df):
        return df.rename(index=lambda g: g + offset, level=RECORD_GROUP) if offset else df
    return shift


def _concat_frames(frames):
    """ ``pd.concat`` without the empty frames, whose dtypes pandas no longer lets decide the result. """
    kept = [f for f in frames if len(f.index)]
    if not kept:
        return frames[0]
    return pd.concat(kept) if len(kept) > 1 else kept[0]


# - helpers -------------------------------------------------------------------------------------- #
def _with_index(df, index):
    if list(df.index.names) != index:
        df = df.set_index(index)
    return df.sort_index()


def _prefixed(df, prefix):
    return df.rename(columns=lambda c: f"{prefix}{c}")


def _view_from_merged(name, merged):
    """ Split a merged frame (as written by CSVRecorder) back into the three tables. """
    flat = merged.reset_index()
    proc = [c for c in flat.columns if c.startswith(_PROC)]
    meta = [c for c in flat.columns if c.startswith(_META)]
    data = [c for c in flat.columns if c not in DATA_INDEX and c not in proc and c not in meta]
    emits = flat.drop_duplicates(subset=EMIT_INDEX).set_index(EMIT_INDEX)
    return RecordView(name,
                      flat[DATA_INDEX + data],
                      emits[proc].rename(columns=lambda c: c[len(_PROC):]),
                      emits[meta].rename(columns=lambda c: c[len(_META):]))


def _columns_of(table):
    """ The columns of a per-emit table as Series over 0..n-1, for :class:`Names`. """
    return {c: table[c].reset_index(drop=True) for c in table.columns}


def _check_expression(condition, what):
    if not isinstance(condition, str):
        raise TypeError(f"{what} conditions are expression strings such as \"frequency > 9e9\", "
                        f"not {type(condition).__name__}.")


def _boolean(result, condition, per):
    result = np.asarray(result)
    if result.dtype != bool:
        raise ValueError(f"{condition!r} must give True or False per {per}, not values of dtype {result.dtype}.")
    return result


def _matches(series, condition, key):
    if callable(condition):
        raise TypeError(f"where({key}=...) takes a value or a list of values; write conditions as expression "
                        f"strings, e.g. where(\"{key} < 0.1\").")
    if isinstance(condition, (list, tuple, set, frozenset, range, np.ndarray, pd.Index)):
        mask = np.zeros(len(series.index), dtype=bool)
        for value in condition:
            mask |= _equals(series, value)
        return mask
    return _equals(series, condition)


def _equals(series, value):
    if isinstance(value, float) and np.isnan(value):
        return series.isna().to_numpy()
    if (ptypes.is_float_dtype(series.dtype) and isinstance(value, numbers.Real)
            and not isinstance(value, bool)):
        return np.isclose(series.to_numpy(), value, rtol=1e-9, atol=0.0)
    return (series == value).to_numpy()


def _merge_close(values):
    """ Merge sorted floats that :func:`_equals` treats as equal, keeping the first of each run.

    Each value is compared with the kept value of its run (not with its neighbour), so that
    ``where(name=kept)`` matches every merged value. """
    merged = []
    for value in values:
        if not merged or not np.isclose(value, merged[-1], rtol=1e-9, atol=0.0):
            merged.append(value)
    return merged


def _timedelta(value):
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        return pd.to_timedelta(float(value), unit="s")
    return pd.Timedelta(value)


def _emit_times(view):
    if TIMESTAMP not in view.meta.columns:
        raise ValueError(f"{view.name!r} has no {TIMESTAMP!r} metadata to align by time.")
    return view.meta[TIMESTAMP]


def _aggregations(agg):
    """ ``agg`` as given for a single aggregation, or a list of ``(label, agg)`` pairs for a list. """
    if not isinstance(agg, (list, tuple)):
        return agg
    if not agg:
        raise ValueError("align() agg is an empty list.")
    pairs = []
    for a in agg:
        label = a if isinstance(a, str) else getattr(a, "__name__", None)
        if not label or label == "<lambda>":
            raise ValueError(f"align() cannot name the aggregation {a!r} in a list; use a function "
                             "defined with def, whose name becomes the column suffix.")
        pairs.append((label, a))
    labels = [label for label, _ in pairs]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError(f"align() agg lists {duplicates} more than once.")
    return pairs


def _stat_names(columns, agg):
    """ Column names of the statistics: ``<column>`` or, for a list, ``<column>_<agg>``. """
    if not isinstance(agg, list):
        return list(columns)
    return [f"{c}_{label}" for c in columns for label, _ in agg]


def _aggregate(obj, agg, columns):
    """ Apply ``agg`` (see :func:`_aggregations`) to a DataFrame (-> Series) or a GroupBy (-> DataFrame). """
    if not isinstance(agg, list):
        return obj.agg(agg)
    results = {label: obj.agg(a) for label, a in agg}
    combined = {f"{c}_{label}": results[label][c] for c in columns for label, _ in agg}
    return pd.DataFrame(combined) if isinstance(obj, pd.core.groupby.GroupBy) else pd.Series(combined)


def _agg_rows(frame, agg):
    """ Aggregate rows into one Series of statistics plus the row count ``n``. """
    names = _stat_names(frame.columns, agg)
    stats = _aggregate(frame, agg, frame.columns) if len(frame.index) else pd.Series(np.nan, index=names)
    return pd.concat([pd.Series(stats, index=names), pd.Series({"n": len(frame.index)})])


def _align_nearest(view, other, values, agg, tolerance):
    mine = _emit_times(view).rename("t").reset_index().sort_values("t")
    theirs = _emit_times(other).rename("t_other").reset_index().sort_values("t_other")
    theirs = theirs.rename(columns={c: f"{c}_other" for c in EMIT_INDEX})
    kwargs = {} if tolerance is None else {"tolerance": _timedelta(tolerance)}
    matched = pd.merge_asof(mine, theirs, left_on="t", right_on="t_other", direction="nearest", **kwargs)

    per_emit = {key: frame for key, frame in values.groupby(level=EMIT_INDEX)}
    empty = values.iloc[:0]
    rows, offsets = {}, {}
    for row in matched.itertuples(index=False):
        key = (row.RecordGroup, row.RecordGroupInd)
        if pd.isna(row.t_other):
            rows[key] = _agg_rows(empty, agg)
            offsets[key] = pd.NaT
        else:
            other_key = (int(row.RecordGroup_other), int(row.RecordGroupInd_other))
            rows[key] = _agg_rows(per_emit.get(other_key, empty), agg)
            offsets[key] = row.t_other - row.t
    stats = pd.DataFrame.from_dict(rows, orient="index").reindex(view.keys)
    stats["dt"] = pd.Series(offsets, dtype="timedelta64[ns]").reindex(view.keys)
    return stats


def _align_window(view, other, values, agg, window):
    before, after = window if isinstance(window, (tuple, list)) else (window, window)
    before, after = _timedelta(before), _timedelta(after)
    times = _emit_times(other)
    rows = {}
    emit_of_row = values.index.droplevel(RECORD_ROW)
    for key, t in _emit_times(view).items():
        inside = times.index[(times >= t - before) & (times <= t + after)]
        rows[key] = _agg_rows(values[emit_of_row.isin(inside)], agg)
    return pd.DataFrame.from_dict(rows, orient="index").reindex(view.keys)
