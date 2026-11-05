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

Behaviour fixes
===============

- Records are immutable snapshots; in 0.9 a recorder could write the same (latest) data several
  times and lose earlier records when a procedure emitted quickly.
- A procedure that raises ends ``FAILED`` with ``shutdown()`` still run on the worker thread; in
  0.9 the status stayed "running" and a sequence could hang.
- Importing the package no longer creates a Qt application or a log file.
