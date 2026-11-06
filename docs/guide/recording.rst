Recording data
##############

HDF5
====

.. code-block:: python

    hdf = plab.HDFRecorder("data/cooldown_12.h5")

Each record name becomes an HDF5 group holding three tables:

.. code-block:: text

    /<record>/data          RecordGroup, RecordGroupInd, RecordRow, <data columns>
    /<record>/proc_params   RecordGroup, RecordGroupInd, <procedure parameters>
    /<record>/meta          RecordGroup, RecordGroupInd, timestamp, <metadata>

Options:

``keep_open=False`` (default)
    The file is opened and closed for every record, so you can open it in another program (or
    notebook) during acquisition. Throughput is roughly 60 emits/s.
``keep_open=True``
    The file stays open (flushed after every record) until the recorder stops. About twice as fast,
    but other programs cannot open the file meanwhile.
``string_width=256``
    Width reserved for string columns when a table is created. Longer strings raise a
    :class:`~pylabtools.SchemaError`.
``complevel``
    Optional compression level 0-9.

Throughput depends on the number of emits, not their size: a 1601-point trace costs about the
same as a single value. Pointing an existing file continues its RecordGroup numbering.

pandas versions
---------------

Datetime columns (including the ``meta`` timestamp) are always written with nanosecond resolution,
and appends convert datetimes to the resolution already in the file, so a file can be extended
from environments with different pandas versions. Note that **pandas 2 cannot read HDF5 tables
written by pandas 3** (a pandas limitation, independent of PyLabTools), while pandas 3 reads files
from either. Use the same pandas major version on the acquisition and analysis computers, or
pandas 3 for reading.

CSV
===

.. code-block:: python

    csv = plab.CSVRecorder("data/cooldown_12_csv")

Writes one file per record name, ``<directory>/<record>.csv``, with the parameters and metadata
repeated on every row as ``proc_<name>`` and ``meta_<name>`` columns. CSV is convenient for quick
looks and other tools; HDF5 is more compact and faster.

You can connect both to the same record; they store identical data.

Schema rules
============

A record name must keep the **same columns, in the same order, with compatible types** across all
of its emits and across runs written to the same file. This is what keeps the three tables (and
CSV columns) aligned. On a mismatch the recorder raises :class:`~pylabtools.SchemaError`, the run
is ``FAILED``, and nothing is written for that record, so the file is never corrupted:

.. code-block:: text

    SchemaError: run.h5:wave/data has columns ['RecordGroup', ..., 'V'], but the new record has
    [..., 'V', 'I'] (missing [], extra ['I']). A record name must keep the same columns; use a new
    record name or a new file for a different layout.

Integers and booleans written into an existing float column are converted automatically. Other
type changes (for example a string into a float column) are errors; emit consistent types, e.g.
``float(x)``.

Parameter and metadata values that are not simple scalars (lists, arrays, dicts) are stored as
their ``repr`` string. ``None`` is stored as NaN.

Record names must be valid HDF5 group names: letters, digits and underscores, not starting with a
digit.

Reading data
============

.. code-block:: python

    plab.hdf_records("run.h5")                     # ['s21', 'temps']
    df = plab.read_hdf("run.h5", "s21")            # everything
    df = plab.read_hdf("run.h5", "s21", groups=-1) # the latest run
    df = plab.read_hdf("run.h5", "s21", groups=[3, 4])

    tables = plab.read_hdf("run.h5", "s21", join=False)
    tables["proc_params"]                          # one row per emit

    df = plab.read_csv("run_csv", "s21", groups=-1)

The joined frame is indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``, so ``df.loc[4]``
selects RecordGroup 4 and ``df.loc[(4, 0)]`` its first emit. Because the files are ordinary pandas
HDF5 tables, ``pandas.read_hdf("run.h5", "s21/data")`` works too.

Custom recorders
================

Subclass :class:`~pylabtools.Recorder` and implement two methods; the base class assigns the
indices and builds the tables:

.. code-block:: python

    class ParquetRecorder(plab.Recorder):
        def __init__(self, directory, **kwargs):
            super().__init__(**kwargs)
            self.directory = Path(directory)

        def last_record_group(self):
            ...  # largest RecordGroup already stored, or -1

        def write(self, record_name, tables):
            ...  # tables.data, tables.proc_params, tables.meta are DataFrames

``on_start()``, ``on_group_end(group)`` and ``on_stop()`` are available for opening and closing
resources; they all run on the recorder's own thread.
