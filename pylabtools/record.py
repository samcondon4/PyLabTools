""" The :class:`Record`: an immutable snapshot of one ``emit()`` call from a procedure.

Every emit creates a new Record, which is then placed on the queue of each connected recorder and
viewer. Because the inputs are copied when the Record is created, a procedure is free to reuse or
mutate its own buffers after emitting, and consumers on other threads always see exactly the data
that was emitted.

Consumers must treat ``Record.data`` as read-only: the same Record object is shared by every
consumer it is routed to. Copy the frame before modifying it.
"""
import copy
import datetime
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import pandas as pd


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


@dataclass(frozen=True, eq=False)
class Record:
    """ An immutable snapshot of data emitted by a procedure.

    The three PyLabTools output indices are derived from a Record as follows:

    - ``RecordGroup``: assigned by a recorder from :attr:`group` (by default the whole run or
      sequence; see ``group_by`` in :func:`pylabtools.start_sequence`).
    - ``RecordGroupInd``: :attr:`index`, the emit counter for this record name within the group.
    - ``RecordRow``: the row number within :attr:`data`.

    :param name: Name of the record, e.g. ``"temperature"``.
    :param data: The emitted data. Converted to a :class:`pandas.DataFrame` by :func:`to_dataframe`.
    :param proc_params: Procedure parameter values at the time of the emit.
    :param meta: Additional metadata to store alongside the data.
    :param run_id: Identifier of the run (or sequence) that produced this record.
    :param index: Emit counter for this record name within the group.
    :param timestamp: Time of the emit (timezone-aware, UTC by default).
    :param group: Identifier of the record group; defaults to ``run_id``.
    """

    name: str
    data: Any
    proc_params: Mapping[str, Any] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)
    run_id: str = ""
    index: int = 0
    timestamp: datetime.datetime = field(default_factory=_utc_now)
    group: str = ""

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Record name must be a non-empty string.")
        if not isinstance(self.index, (int, np.integer)) or isinstance(self.index, bool) or self.index < 0:
            raise ValueError(f"Record index must be a non-negative integer, got {self.index!r}.")
        if self.timestamp.tzinfo is None:
            raise ValueError("Record timestamp must be timezone-aware.")
        # - frozen dataclass: assign the converted values with object.__setattr__ - #
        object.__setattr__(self, "data", to_dataframe(self.data, self.name))
        object.__setattr__(self, "proc_params", _frozen_mapping(self.proc_params, "proc_params"))
        object.__setattr__(self, "meta", _frozen_mapping(self.meta, "meta"))
        object.__setattr__(self, "index", int(self.index))
        if not self.group:
            object.__setattr__(self, "group", self.run_id)

    @property
    def n_rows(self):
        """ Number of rows in :attr:`data`, i.e. the number of ``RecordRow`` values. """
        return len(self.data.index)

    def __repr__(self):
        return (f"Record(name={self.name!r}, run_id={self.run_id!r}, index={self.index}, "
                f"shape={self.data.shape}, columns={list(self.data.columns)})")


def _frozen_mapping(obj, label):
    """ Copy a mapping of parameters or metadata and wrap it in a read-only view. """
    if obj is None:
        obj = {}
    if not isinstance(obj, Mapping):
        raise TypeError(f"Record {label} must be a mapping, got {type(obj).__name__}.")
    return MappingProxyType({str(key): _copy_value(val) for key, val in obj.items()})


def _copy_value(val):
    """ Copy containers so later mutation by the procedure cannot change the record. """
    if isinstance(val, np.ndarray):
        return val.copy()
    if isinstance(val, (list, tuple, dict, set)):
        return copy.deepcopy(val)
    return val


def to_dataframe(data, name):
    """ Convert emitted data into a new :class:`pandas.DataFrame`, copying the input.

    Conversion rules:

    - ``DataFrame``: copied, with its index reset to ``0..n-1``.
    - ``Series``: one column, named after the series (or ``name`` if it is unnamed).
    - ``dict``: one column per key. Scalar values give one row; 1-D values give one row per element;
      2-D values with ``m`` columns are split into columns ``key_0 .. key_{m-1}``. All values must
      have the same number of rows.
    - 0-D or 1-D ``ndarray``, ``list`` or ``tuple``: a single column named ``name``.
    - 2-D ``ndarray``: columns ``name_0 .. name_{m-1}``.
    - Any other scalar: a single row and column named ``name``.

    :param data: The data to convert.
    :param name: Record name used to label unnamed columns.
    :raises ValueError: For arrays with more than 2 dimensions or dict values of unequal length.
    """
    if isinstance(data, pd.DataFrame):
        df = data.copy(deep=True).reset_index(drop=True)
        df.columns = [str(c) for c in df.columns]
        return df

    if isinstance(data, pd.Series):
        col = name if data.name is None else str(data.name)
        return pd.DataFrame({col: data.to_numpy(copy=True)})

    if isinstance(data, Mapping):
        if len(data) == 0:
            raise ValueError(f"Record {name!r}: cannot emit an empty dict.")
        columns = {}
        for key, val in data.items():
            columns.update(_columns_from_value(str(key), val, name))
        lengths = {col: len(vals) for col, vals in columns.items()}
        if len(set(lengths.values())) > 1:
            raise ValueError(f"Record {name!r}: dict values have unequal lengths {lengths}.")
        return pd.DataFrame(columns)

    if isinstance(data, (np.ndarray, list, tuple)):
        return pd.DataFrame(_columns_from_value(name, data, name))

    return pd.DataFrame({name: [data]})


def _columns_from_value(key, val, name):
    """ Return ``{column name: 1-D array}`` for a single dict value or top-level array. """
    if isinstance(val, (str, bytes)) or np.isscalar(val) or val is None:
        return {key: np.array([val])}
    arr = np.array(val, copy=True)
    if arr.ndim == 0:
        return {key: arr.reshape(1)}
    if arr.ndim == 1:
        return {key: arr}
    if arr.ndim == 2:
        return {f"{key}_{i}": arr[:, i].copy() for i in range(arr.shape[1])}
    raise ValueError(f"Record {name!r}: {key!r} has {arr.ndim} dimensions; at most 2 are supported.")
