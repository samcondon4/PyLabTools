""" Convert data files written by PyLabTools 0.9 into the 1.0 format.

A 0.9 :class:`HDFRecorder` wrote one record per file as three top-level tables, ``/data``,
``/proc_params`` and ``/meta``, indexed by a pandas MultiIndex of zero-padded strings
(``"000003"``). :func:`convert_hdf` rewrites them as a 1.0 record group, ``/<record>/data`` etc.,
with integer indices and a timezone-aware UTC ``timestamp``:

.. code-block:: python

    plab.legacy.convert_hdf("cooldown_0p9.h5", "cooldown.h5")                       # -> /record/...
    plab.legacy.convert_hdf("cooldown_0p9.h5", "cooldown.h5", record="s21")         # -> /s21/...
    plab.legacy.convert_hdf("processed.h5", "base.h5", record_name="base")          # base/data, ... -> /base/...

The source file is only read, never modified.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from .log import get_logger
from .recorders.base import DATA_INDEX, EMIT_INDEX, TIMESTAMP, RecordTables
from .recorders.hdf import HDFRecorder

logger = get_logger(__name__)

__all__ = ["convert_hdf"]

_TABLES = ("data", "proc_params", "meta")
_LEGACY_TIMESTAMP = "%Y%m%d_%H%M%S"
_DIGITS = re.compile(r"\d+")


def convert_hdf(source, destination, record="record", record_name=None, timezone="America/Los_Angeles",
                overwrite=False, string_width=256):
    """ Convert a PyLabTools 0.9 HDF5 file into a 1.0 file.

    :param source: The 0.9 ``.h5`` file. It is opened read-only.
    :param destination: The 1.0 file to write. ``.h5`` is appended if the path has no suffix.
    :param record: Name of the output record when ``record_name`` is None. 0.9 files do not store
        a record name.
    :param record_name: Where the 0.9 tables are in ``source``. None (default): at the top level
        (``/data``, ``/proc_params``, ``/meta``), as written by 0.9. A string: under that group
        (``/<record_name>/data`` etc.), for files whose 0.9 tables were moved, e.g.
        ``record_name="base"``; the output record keeps that name. A list of strings converts
        several such groups, each to a record of the same name. Other groups in ``source`` are
        ignored.
    :param timezone: Time zone of the 0.9 timestamps, which were local times without a zone
        (``"YYYYMMDD_HHMMSS"`` strings or naive datetimes). They are stored as UTC. Timestamps that
        already carry a zone are converted to UTC unchanged. If the 0.9 ``meta`` table has no
        ``timestamp`` column, the 1.0 file has none either.
    :param overwrite: If False (default), refuse to write over an existing ``destination``.
    :param string_width: Minimum stored width of string columns (see :class:`~pylabtools.HDFRecorder`).
    :return: The names of the records written.
    :raises FileExistsError: If ``destination`` exists and ``overwrite`` is False.
    :raises KeyError: If ``source`` has no 0.9 tables where ``record_name`` says.
    :raises ValueError: If a timestamp cannot be parsed, or the index values are not 0.9 indices.
    """
    source = Path(source)
    destination = Path(destination)
    destination = destination if destination.suffix else destination.with_suffix(".h5")
    if not source.exists():
        raise FileNotFoundError(f"No file at {source}.")
    if destination.resolve() == source.resolve():
        raise ValueError("destination must be a different file from source; the source is never modified.")
    if destination.exists():
        if not overwrite:
            raise FileExistsError(f"{destination} exists; pass overwrite=True to replace it.")
        destination.unlink()

    if record_name is None:
        jobs = [("", record)]
    else:
        names = [record_name] if isinstance(record_name, str) else list(record_name)
        names = [str(n).strip("/") for n in names]
        if not names:
            raise ValueError("record_name is an empty list.")
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"record_name lists {duplicates} more than once.")
        jobs = [(n, n) for n in names]

    with pd.HDFStore(source, mode="r") as store:
        keys = set(store.keys())
        converted = [(prefix, out, _read_legacy(store, keys, prefix, timezone)) for prefix, out in jobs]

    recorder = HDFRecorder(destination, keep_open=True, string_width=string_width)
    recorder.on_start()
    try:
        for prefix, name, tables in converted:
            recorder.write(name, tables)
            logger.info("Converted %s:/%s to %s:/%s (%d emits, %d rows)", source.name, prefix,
                        destination.name, name, len(tables.proc_params), len(tables.data))
    except Exception:
        recorder.on_stop()
        destination.unlink(missing_ok=True)  # - never leave a half-written file - #
        raise
    recorder.on_stop()
    return [name for _, name, _ in converted]


def _read_legacy(store, keys, prefix, timezone):
    """ Read the 0.9 tables under ``prefix`` and return them as 1.0 :class:`RecordTables`. """
    base = f"/{prefix}" if prefix else ""
    where = base or "the top level"
    if f"{base}/proc_params" not in keys:
        found = sorted(k.rsplit("/", 1)[0] or "/" for k in keys if k.endswith("/proc_params"))
        raise KeyError(f"No 0.9 tables at {where} of {store.filename}: there is no {base}/proc_params table. "
                       f"proc_params tables were found under {found}.")

    tables = {kind: _with_integer_index(store[f"{base}/{kind}"], f"{base}/{kind}")
              for kind in _TABLES if f"{base}/{kind}" in keys}
    if "data" not in tables:  # - every emit had zero rows - #
        tables["data"] = pd.DataFrame({c: pd.Series(dtype=np.int64) for c in DATA_INDEX})
    if "meta" not in tables:  # - 1.0 readers need a meta table; give it just the emit keys - #
        tables["meta"] = tables["proc_params"][EMIT_INDEX].copy()
        logger.info("%s has no meta table; writing one without metadata.", where)

    meta = tables["meta"]
    if TIMESTAMP in meta.columns:
        meta[TIMESTAMP] = _utc_timestamps(meta[TIMESTAMP], timezone, f"{base}/meta")

    # - 1.0 order: index columns first, then the 0.9 columns in their stored order - #
    return RecordTables(data=_index_first(tables["data"], DATA_INDEX),
                        proc_params=_index_first(tables["proc_params"], EMIT_INDEX),
                        meta=_index_first(meta, EMIT_INDEX))


def _with_integer_index(df, key):
    """ Turn the 0.9 string MultiIndex into integer index columns. """
    levels = list(df.index.names)
    expected = DATA_INDEX if key.endswith("/data") else EMIT_INDEX
    if levels != expected:
        raise ValueError(f"{key} is indexed by {levels}, not {expected}; it is not a PyLabTools 0.9 table.")
    flat = df.reset_index()
    for column in expected:
        flat[column] = _integers(flat[column], key, column)
    return flat.sort_values(expected, kind="stable").reset_index(drop=True)


def _integers(values, key, column):
    """ ``"000003"`` (or a prefixed ``"rg_000003"``) -> 3, as 0.9 itself read them back. """
    if ptypes.is_integer_dtype(values.dtype):
        return values.astype(np.int64)
    digits = values.astype(str).str.findall(_DIGITS).str.join("")
    bad = digits == ""
    if bad.any():
        raise ValueError(f"{key}: {column} value {values[bad].iloc[0]!r} has no digits.")
    return digits.astype(np.int64)


def _utc_timestamps(values, timezone, key):
    """ Parse 0.9 timestamps (local, usually ``"YYYYMMDD_HHMMSS"``) into UTC datetimes. """
    if ptypes.is_datetime64_any_dtype(values.dtype):
        parsed = values
    else:
        text = values.astype(str)
        parsed = pd.to_datetime(text, format=_LEGACY_TIMESTAMP, errors="coerce").astype("datetime64[ns]")
        if (parsed.isna() & values.notna()).any():  # - other string formats, e.g. str(datetime) - #
            iso = pd.to_datetime(text, format="ISO8601", errors="coerce")
            if getattr(iso.dt, "tz", None) is None:
                parsed = parsed.fillna(iso.astype("datetime64[ns]"))
        unparsed = parsed.isna() & values.notna()
        if unparsed.any():
            raise ValueError(f"{key}: cannot parse timestamp {values[unparsed].iloc[0]!r}; expected "
                             f"'YYYYMMDD_HHMMSS' or an ISO 8601 date and time.")
    if getattr(parsed.dt, "tz", None) is None:
        try:
            parsed = parsed.dt.tz_localize(timezone, ambiguous="infer", nonexistent="raise")
        except Exception as exc:  # - pytz/zoneinfo raise several types around DST changes - #
            raise ValueError(f"{key}: cannot place the timestamps in time zone {timezone!r}: {exc}. Timestamps "
                             "in the repeated hour when clocks go back can only be placed if they are in "
                             "time order.") from exc
    return parsed.dt.tz_convert("UTC")


def _index_first(df, index):
    return df[index + [c for c in df.columns if c not in index]]
