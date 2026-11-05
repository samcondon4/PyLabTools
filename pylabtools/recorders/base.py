""" The :class:`Recorder` base class: turns records into the three PyLabTools output tables.

Every record is written as three tables, linked by the ``RecordGroup`` and ``RecordGroupInd``
columns:

``data``
    ``RecordGroup, RecordGroupInd, RecordRow`` followed by the emitted data columns, one row per
    data row.
``proc_params``
    ``RecordGroup, RecordGroupInd`` followed by the procedure parameter values, one row per emit.
``meta``
    ``RecordGroup, RecordGroupInd, timestamp`` followed by the metadata, one row per emit.

``RecordGroup`` numbers record groups within one output file, continuing from the largest group
already stored. By default a group is one run (a whole sequence is one run); a sequence started
with ``group_by`` gets one group per value of the grouping parameters. ``RecordGroupInd`` is the
emit counter of the record within the group, and ``RecordRow`` the row within one emit.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..consumers import Consumer
from ..log import get_logger

logger = get_logger(__name__)

RECORD_GROUP = "RecordGroup"
RECORD_GROUP_IND = "RecordGroupInd"
RECORD_ROW = "RecordRow"
TIMESTAMP = "timestamp"

#: Columns that identify one emit, shared by all three tables.
EMIT_INDEX = [RECORD_GROUP, RECORD_GROUP_IND]
#: Columns that identify one data row.
DATA_INDEX = [RECORD_GROUP, RECORD_GROUP_IND, RECORD_ROW]


class SchemaError(ValueError):
    """ Raised when a record does not match the columns or types already stored for its name. """


@dataclass(frozen=True)
class RecordTables:
    """ The three output tables of one record. """

    data: pd.DataFrame
    proc_params: pd.DataFrame
    meta: pd.DataFrame

    def items(self):
        return (("data", self.data), ("proc_params", self.proc_params), ("meta", self.meta))


class Recorder(Consumer):
    """ Base class for recorders. Subclasses implement :meth:`last_record_group` and :meth:`write`.

    :param name: Name used in log messages.
    :param maxsize: Maximum queue length (see :class:`~pylabtools.consumers.Consumer`).
    """

    critical = True

    def __init__(self, name=None, maxsize=0):
        super().__init__(name=name, maxsize=maxsize)
        self._groups = {}
        self._next_group = 0

    def on_start(self):
        self._groups = {}
        self._next_group = self.last_record_group() + 1

    def handle(self, record):
        group = self._record_group(record.group)
        self.write(record.name, make_tables(record, group))

    def on_group_end(self, group):
        self._groups.pop(group, None)

    def _record_group(self, group):
        if group not in self._groups:
            self._groups[group] = self._next_group
            logger.info("%s: group %s is RecordGroup %d", self.name, group[:10], self._next_group)
            self._next_group += 1
        return self._groups[group]

    # - for subclasses ------------------------------------------------------------------------- #
    def last_record_group(self):
        """ Return the largest ``RecordGroup`` already stored, or -1 if there is none. """
        raise NotImplementedError("Recorder subclasses must implement last_record_group().")

    def write(self, record_name, tables):
        """ Store the :class:`RecordTables` of one record. """
        raise NotImplementedError("Recorder subclasses must implement write().")


def make_tables(record, group):
    """ Build the ``data``, ``proc_params`` and ``meta`` tables of a record.

    :param record: The :class:`~pylabtools.record.Record` to convert.
    :param group: The ``RecordGroup`` number assigned to the record's run.
    :raises ValueError: If the record uses a reserved column name.
    """
    _check_reserved(record.data.columns, DATA_INDEX, record.name, "data column")
    _check_reserved(record.proc_params, EMIT_INDEX, record.name, "procedure parameter")
    _check_reserved(record.meta, EMIT_INDEX + [TIMESTAMP], record.name, "meta key")

    n_rows = record.n_rows
    data = record.data.copy()
    data.insert(0, RECORD_ROW, np.arange(n_rows, dtype=np.int64))
    data.insert(0, RECORD_GROUP_IND, np.full(n_rows, record.index, dtype=np.int64))
    data.insert(0, RECORD_GROUP, np.full(n_rows, group, dtype=np.int64))

    emit = {RECORD_GROUP: np.int64(group), RECORD_GROUP_IND: np.int64(record.index)}
    proc_params = _one_row({**emit, **{k: _scalar(v) for k, v in record.proc_params.items()}})
    meta = _one_row({**emit, TIMESTAMP: record.timestamp,
                     **{k: _scalar(v) for k, v in record.meta.items()}})
    return RecordTables(data=data, proc_params=proc_params, meta=meta)


def _one_row(values):
    return pd.DataFrame({key: [val] for key, val in values.items()})


def _scalar(value):
    """ Make a parameter or metadata value storable in a table cell. """
    if value is None:
        return np.nan
    if isinstance(value, (str, bytes, bool, int, float, np.generic, pd.Timestamp)):
        return value
    if hasattr(value, "isoformat"):  # - datetime, date - #
        return value
    return repr(value.tolist() if isinstance(value, np.ndarray) else value)


def _check_reserved(names, reserved, record_name, what):
    clash = sorted(set(names) & set(reserved))
    if clash:
        raise ValueError(f"Record {record_name!r}: {what} name(s) {clash} are reserved by PyLabTools.")
