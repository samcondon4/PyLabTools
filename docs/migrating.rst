Migrating from 0.9
##################

PyLabTools 1.0 keeps the ideas of 0.9 (procedures emitting records to recorders and viewers, the
RecordGroup / RecordGroupInd / RecordRow indices, logging procedure parameters and metadata with
the data) but replaces the configuration-package interface with plain Python objects.

The 0.9 code is preserved at the ``v0.9.1`` tag.

Concept map
===========

.. list-table::
    :header-rows: 1
    :widths: 40 60

    * - 0.9
      - 1.0
    * - Experiment control package with ``INSTRUMENT_SUITE``, ``PROCEDURES``, ``RECORDERS``,
        ``VIEWERS``, ``CONTROLLERS`` lists
      - Create the objects directly in a script or notebook.
    * - ``create_experiment(config).start()``
      - ``plab.run(proc)`` / ``plab.start(proc)``; ``plab.gui.show(...)`` for plots.
    * - Instrument dicts (``manufacturer``, ``instrument``, ``resource_name``)
      - Instantiate the PyMeasure driver yourself and pass it to the procedure's constructor.
    * - ``"hw"`` key of a procedure config
      - Constructor arguments of the procedure.
    * - ``"records": {"name": {"viewer": ..., "recorder": ...}}``
      - ``proc.connect("name", recorder, viewer, ...)``; any number of consumers per record.
    * - ``self.emit(name, data, meta=...)``
      - Unchanged.
    * - PyLabTools' vendored parameter classes (``pylabtools.parameters``)
      - Upstream ``pymeasure.experiment`` parameters.
    * - ``ProcedureSequence`` and the sequencer widget / sequence files
      - ``plab.run_sequence(proc, plab.sweep(...))``. A sequence is still one RecordGroup.
    * - ``HDFRecorder``, ``CSVRecorder``
      - Same names; see the output format changes below.
    * - ``LineViewer`` with a ``lines`` dict
      - ``LineViewer(x=..., y=[...], colors={...})``.
    * - ``slt.log`` written to the working directory
      - Nothing is written unless you call ``plab.log.enable(file=...)``.

Not (yet) in 1.0: ``InstrumentController`` / ``ProcedureController`` panels, ``CompoundInstrument``,
``SQLRecorder``, ``ImageViewer``, ``LoggingProcedure``, ``AlertProcedure``. Generated control
panels are planned for a later milestone.

Output format changes
=====================

- The indices are **integer columns**, not zero-padded strings like ``"000003"``.
- HDF5 files hold one group per record name (``/<record>/data`` etc.) instead of top-level
  ``data`` / ``proc_params`` / ``meta`` tables, so several records can share a file.
- ``timestamp`` is a column of the ``meta`` table, stored as timezone-aware UTC.
- CSV output is one file per record name in a directory, rather than a single file.
- Schema mismatches raise :class:`~pylabtools.SchemaError` instead of silently misaligning
  columns.

Converting 0.9 data files
=========================

:func:`plab.legacy.convert_hdf <pylabtools.legacy.convert_hdf>` rewrites an HDF5 file written by the
0.9 ``HDFRecorder`` as a 1.0 file. The source file is only read, never modified, and an existing
destination is only replaced with ``overwrite=True``.

.. code-block:: python

    import pylabtools as plab

    plab.legacy.convert_hdf("cooldown_0p9.h5", "cooldown.h5")                  # -> record "record"
    plab.legacy.convert_hdf("cooldown_0p9.h5", "cooldown.h5", record="s21")    # -> record "s21"

    ds = plab.analysis.Dataset("cooldown.h5")

What changes:

- The top-level ``/data``, ``/proc_params`` and ``/meta`` tables become one record,
  ``/<record>/data`` etc. 0.9 files do not store a record name, so it is given by ``record``
  (default ``"record"``). A 0.9 file is assumed to hold one record.
- The zero-padded string indices (``"000003"``) become the integers 0.9 itself read them as.
  RecordGroup and RecordGroupInd numbering is kept.
- ``timestamp`` metadata, stored by 0.9 as local time without a time zone (``"YYYYMMDD_HHMMSS"``
  strings or naive datetimes), is interpreted in ``timezone`` (default ``"America/Los_Angeles"``)
  and stored as UTC. Around the autumn clock change, the repeated hour is resolved from the time
  order of the emits. If the 0.9 file has no ``timestamp``, the 1.0 file has none either; only the
  time-based modes of :meth:`~pylabtools.analysis.RecordView.align` need one.
- All other columns, values and types are copied unchanged.

Files whose 0.9 tables have been moved into a group, e.g. by later processing, are converted with
``record_name``: a string names the group holding ``data``, ``proc_params`` and ``meta``, and a list
converts several groups. Each output record keeps its group's name, and other groups in the file are
ignored:

.. code-block:: python

    plab.legacy.convert_hdf("processed.h5", "base.h5", record_name="base")       # base/... -> /base/...
    plab.legacy.convert_hdf("processed.h5", "both.h5", record_name=["base", "temp_avg_s21"])

0.9 CSV files are not converted yet.

Behaviour fixes
===============

- Records are immutable snapshots; in 0.9 a recorder could write the same (latest) data several
  times and lose earlier records when a procedure emitted quickly.
- A procedure that raises ends ``FAILED`` with ``shutdown()`` still run on the worker thread; in
  0.9 the status stayed "running" and a sequence could hang.
- Importing the package no longer creates a Qt application or a log file.
