""" :class:`HDFRecorder`: write records to an HDF5 file, and :func:`read_hdf` to read them back.

File layout, with one HDF5 group per record name::

    /<record>/data          RecordGroup, RecordGroupInd, RecordRow, <data columns>
    /<record>/proc_params   RecordGroup, RecordGroupInd, <procedure parameters>
    /<record>/meta          RecordGroup, RecordGroupInd, timestamp, <metadata>

Tables are pandas ``HDFStore`` tables (PyTables), so they can be appended to and queried by
``RecordGroup``/``RecordGroupInd``. A record name must keep the same columns and column types
across emits and runs; a mismatch raises :class:`~pylabtools.recorders.base.SchemaError` instead of
corrupting the file.

Datetime columns (such as the ``meta`` timestamp) are written with nanosecond resolution, which
every pandas version reads. pandas 3 would otherwise store microseconds, and pandas 2 cannot read
or append to such tables. When appending to an existing file, datetimes are converted to the
resolution already stored, so files written by either pandas version can be extended by the other.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from ..log import get_logger
from .base import DATA_INDEX, EMIT_INDEX, RECORD_GROUP, Recorder, SchemaError

logger = get_logger(__name__)

__all__ = ["HDFRecorder", "read_hdf", "hdf_records"]

_TABLES = ("data", "proc_params", "meta")
_NATURAL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class HDFRecorder(Recorder):
    """ Record to an HDF5 file.

    :param path: Output file. ``.h5`` is appended if the path has no suffix; parent directories
        are created. An existing file is appended to, continuing the ``RecordGroup`` numbering.
    :param keep_open: If False (default), the file is opened and closed for every record, so other
        programs can read it during acquisition. If True, it stays open (and is flushed after every
        record) until the recorder stops, which is much faster for high emit rates.
    :param string_width: Minimum stored width of string columns, fixed when a table is created.
    :param complevel: Optional compression level 0-9 (blosc).
    :param name: Name used in log messages.
    :param maxsize: Maximum queue length (see :class:`~pylabtools.consumers.Consumer`).
    """

    def __init__(self, path, keep_open=False, string_width=256, complevel=None, name=None, maxsize=0):
        super().__init__(name=name, maxsize=maxsize)
        path = Path(path)
        self.path = path if path.suffix else path.with_suffix(".h5")
        self.keep_open = keep_open
        self.string_width = string_width
        self.complevel = complevel
        self._store = None
        self._schemas = {}

    # - recorder interface --------------------------------------------------------------------- #
    def on_start(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._schemas = {}
        super().on_start()
        if self.keep_open:
            self._open()
        logger.info("%s recording to %s", self.name, self.path)

    def on_stop(self):
        self._close()

    def last_record_group(self):
        if not self.path.exists():
            return -1
        with pd.HDFStore(self.path, mode="r") as store:
            groups = [store.select_column(key, RECORD_GROUP).max()
                      for key in store.keys() if key.endswith("/proc_params")]
        return int(max(groups)) if groups else -1

    def write(self, record_name, tables):
        if not _NATURAL_NAME.match(record_name):
            raise ValueError(f"Record name {record_name!r} cannot be used as an HDF5 group name; use "
                             "letters, digits and underscores, not starting with a digit.")
        store = self._open()
        try:
            # - check all three tables before appending any, so a mismatch writes nothing - #
            conformed = [(f"{record_name}/{kind}",
                          self._conform(store, f"{record_name}/{kind}", _datetimes_as_ns(df)))
                         for kind, df in tables.items()]
            for key, df in conformed:
                if len(df.index) == 0:
                    continue
                self._append(store, key, df)
            if self.keep_open:
                store.flush()
        finally:
            if not self.keep_open:
                self._close()

    # - helpers -------------------------------------------------------------------------------- #
    def _open(self):
        if self._store is None:
            kwargs = {} if self.complevel is None else {"complevel": self.complevel, "complib": "blosc"}
            self._store = pd.HDFStore(self.path, mode="a", **kwargs)
        return self._store

    def _close(self):
        if self._store is not None:
            self._store.close()
            self._store = None

    def _append(self, store, key, df):
        kwargs = {}
        if key not in store:
            strings = [c for c in df.columns if _kind(df[c].dtype) == "string"]
            kwargs["min_itemsize"] = {c: max(self.string_width, int(df[c].astype(str).str.len().max()))
                                      for c in strings}
        try:
            store.append(key, df, format="table", data_columns=EMIT_INDEX, index=False, **kwargs)
        except ValueError as exc:
            if "Trying to store a string with len" in str(exc):
                raise SchemaError(f"{key}: {exc} Increase HDFRecorder(string_width=...) for new files.") from exc
            raise
        self._schemas[key] = df.dtypes

    def _conform(self, store, key, df):
        """ Check ``df`` against the stored table, casting ints/bools into stored float columns. """
        stored = self._schemas.get(key)
        if stored is None:
            if key not in store:
                return df
            stored = store.select(key, stop=0).dtypes
            self._schemas[key] = stored

        if list(stored.index) != list(df.columns):
            missing = [c for c in stored.index if c not in df.columns]
            extra = [c for c in df.columns if c not in stored.index]
            raise SchemaError(
                f"{self.path.name}:{key} has columns {list(stored.index)}, but the new record has "
                f"{list(df.columns)} (missing {missing}, extra {extra}). A record name must keep the same "
                "columns; use a new record name or a new file for a different layout.")

        casts = {}
        for col in df.columns:
            have, want = _kind(df[col].dtype), _kind(stored[col])
            if have == want == "datetime":
                if df[col].dtype != stored[col]:
                    casts[col] = stored[col]  # - e.g. us -> ns resolution, from another pandas version - #
                continue
            if have == want:
                continue
            if want == "float" and have in ("int", "bool"):
                casts[col] = stored[col]
                continue
            raise SchemaError(f"{self.path.name}:{key} column {col!r} is stored as {stored[col]} but the new "
                              f"record has {df[col].dtype}. Emit a consistent type (e.g. float(x)).")
        return df.astype(casts) if casts else df


def _datetimes_as_ns(df):
    """ Store datetimes with nanosecond resolution, readable by pandas 2 and 3. """
    casts = {}
    for col in df.columns:
        dtype = df[col].dtype
        if ptypes.is_datetime64_any_dtype(dtype):
            tz = getattr(dtype, "tz", None)
            target = f"datetime64[ns, {tz}]" if tz is not None else "datetime64[ns]"
            if str(dtype) != target:
                casts[col] = target
    return df.astype(casts) if casts else df


def _kind(dtype):
    if ptypes.is_bool_dtype(dtype):
        return "bool"
    if ptypes.is_integer_dtype(dtype):
        return "int"
    if ptypes.is_float_dtype(dtype):
        return "float"
    if ptypes.is_complex_dtype(dtype):
        return "complex"
    if ptypes.is_datetime64_any_dtype(dtype):
        return "datetime"
    if ptypes.is_string_dtype(dtype) or ptypes.is_object_dtype(dtype):
        return "string"
    return str(dtype)


def hdf_records(path):
    """ Names of the records stored in a PyLabTools HDF5 file. """
    with pd.HDFStore(path, mode="r") as store:
        keys = set(store.keys())
    names = {key.strip("/").rsplit("/", 1)[0] for key in keys if key.endswith("/proc_params")}
    return sorted(n for n in names if all(f"/{n}/{t}" in keys for t in ("proc_params", "meta")))


def read_hdf(path, record=None, join=True, groups=None):
    """ Read a record from a PyLabTools HDF5 file.

    :param path: The HDF5 file.
    :param record: Record name. May be omitted if the file holds a single record.
    :param join: If True (default), return one DataFrame indexed by
        ``(RecordGroup, RecordGroupInd, RecordRow)``, with procedure parameters and metadata joined
        onto every data row as ``proc_<name>`` and ``meta_<name>`` columns. If False, return a dict
        with the separate ``data``, ``proc_params`` and ``meta`` tables.
    :param groups: Optional ``RecordGroup`` number, or list of numbers, to read. Negative numbers
        count from the end: ``-1`` is the most recent run in the file.
    """
    names = hdf_records(path)
    if record is None:
        if len(names) != 1:
            raise ValueError(f"{path} holds records {names}; pass record=<name>.")
        record = names[0]
    elif record not in names:
        raise KeyError(f"{path} has no record {record!r}; records are {names}.")

    with pd.HDFStore(path, mode="r") as store:
        keys = set(store.keys())
        where = None
        if groups is not None:
            stored = sorted(set(store.select_column(f"/{record}/proc_params", RECORD_GROUP)))
            where = f"{RECORD_GROUP} = {resolve_groups(groups, stored)}"
        tables = {}
        for kind in _TABLES:
            key = f"/{record}/{kind}"
            if key in keys:
                tables[kind] = store.select(key, where=where).reset_index(drop=True)
            else:  # - a record whose emits all had zero data rows - #
                tables[kind] = pd.DataFrame(columns=DATA_INDEX)

    if not join:
        return {"data": tables["data"].set_index(DATA_INDEX),
                "proc_params": tables["proc_params"].set_index(EMIT_INDEX),
                "meta": tables["meta"].set_index(EMIT_INDEX)}
    return join_tables(tables["data"], tables["proc_params"], tables["meta"])


def resolve_groups(groups, stored):
    """ Turn ``groups`` (an int or list, negatives counting from the end of ``stored``) into a list. """
    groups = [groups] if isinstance(groups, (int, np.integer)) else list(groups)
    resolved = []
    for group in groups:
        if group < 0:
            if -group > len(stored):
                raise IndexError(f"RecordGroup {group} is out of range; the file holds {len(stored)} groups.")
            group = stored[group]
        resolved.append(int(group))
    return resolved


def join_tables(data, proc_params, meta):
    """ Join the three tables of a record into one DataFrame (see :func:`read_hdf`). """
    def prefixed(df, prefix):
        return df.rename(columns={c: f"{prefix}{c}" for c in df.columns if c not in EMIT_INDEX})

    joined = (data.merge(prefixed(proc_params, "proc_"), on=EMIT_INDEX, how="left")
                  .merge(prefixed(meta, "meta_"), on=EMIT_INDEX, how="left"))
    return joined.set_index(DATA_INDEX).sort_index()
