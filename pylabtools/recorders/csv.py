""" :class:`CSVRecorder`: write records to plain-text CSV files, and :func:`read_csv` to read them.

CSV output is *merged*: each record name gets one file, ``<directory>/<record>.csv``, whose rows
are the data rows with the procedure parameters and metadata repeated on every row as
``proc_<name>`` and ``meta_<name>`` columns. The first columns are always
``RecordGroup, RecordGroupInd, RecordRow``.
"""
import csv
from pathlib import Path

import pandas as pd

from ..log import get_logger
from .base import DATA_INDEX, RECORD_GROUP, Recorder, SchemaError
from .hdf import join_tables

logger = get_logger(__name__)

__all__ = ["CSVRecorder", "read_csv"]


class CSVRecorder(Recorder):
    """ Record to one CSV file per record name.

    :param directory: Output directory, created if needed. Existing files are appended to,
        continuing the ``RecordGroup`` numbering.
    :param name: Name used in log messages.
    :param maxsize: Maximum queue length (see :class:`~pylabtools.consumers.Consumer`).
    """

    def __init__(self, directory, name=None, maxsize=0):
        super().__init__(name=name, maxsize=maxsize)
        self.directory = Path(directory)
        self._headers = {}

    def file_for(self, record_name):
        """ Path of the CSV file holding ``record_name``. """
        return self.directory / f"{record_name}.csv"

    def on_start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self._headers = {}
        super().on_start()
        logger.info("%s recording to %s", self.name, self.directory)

    def last_record_group(self):
        groups = [pd.read_csv(path, usecols=[RECORD_GROUP])[RECORD_GROUP].max()
                  for path in self.directory.glob("*.csv") if _is_record_file(path)]
        groups = [g for g in groups if pd.notna(g)]
        return int(max(groups)) if groups else -1

    def write(self, record_name, tables):
        merged = join_tables(tables.data, tables.proc_params, tables.meta).reset_index()
        path = self.file_for(record_name)
        header = self._headers.get(record_name)
        if header is None and path.exists() and path.stat().st_size > 0:
            header = _read_header(path)
            self._headers[record_name] = header
        columns = list(merged.columns)
        if header is not None and header != columns:
            missing = [c for c in header if c not in columns]
            extra = [c for c in columns if c not in header]
            raise SchemaError(f"{path.name} has columns {header}, but the new record has {columns} "
                              f"(missing {missing}, extra {extra}). Use a new record name or directory.")
        merged.to_csv(path, mode="a", header=header is None, index=False)
        self._headers[record_name] = columns


def _read_header(path):
    with open(path, newline="") as f:
        return next(csv.reader(f))


def _is_record_file(path):
    return path.stat().st_size > 0 and _read_header(path)[:3] == DATA_INDEX


def read_csv(directory, record):
    """ Read a record written by :class:`CSVRecorder`.

    :return: DataFrame indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``. The
        ``meta_timestamp`` column is parsed as timezone-aware datetimes.
    """
    path = Path(directory) / f"{record}.csv"
    df = pd.read_csv(path)
    if "meta_timestamp" in df.columns:
        df["meta_timestamp"] = pd.to_datetime(df["meta_timestamp"], utc=True, format="ISO8601")
    return df.set_index(DATA_INDEX)
