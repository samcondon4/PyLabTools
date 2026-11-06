Changelog
#########

1.0.0.dev0 (unreleased)
=======================

Ground-up rewrite. First milestone: the procedure -> emit -> record -> recorder/viewer pipeline.

- :class:`~pylabtools.Procedure` built on upstream PyMeasure, with ``connect()`` and ``emit()``.
- :class:`~pylabtools.Run` state machine; ``run``/``start``, sequences and ``sweep``.
- Immutable :class:`~pylabtools.Record` snapshots.
- :class:`~pylabtools.HDFRecorder` and :class:`~pylabtools.CSVRecorder` with the
  RecordGroup / RecordGroupInd / RecordRow indices; ``read_hdf`` and ``read_csv``.
- :class:`~pylabtools.LineViewer` and the optional :mod:`pylabtools.gui`.
- Background tasks with :func:`~pylabtools.every`, ``group_by`` record groups for sequences, and
  :meth:`Procedure.sleep() <pylabtools.Procedure.sleep>`. Consumer hook ``on_run_end`` is now
  ``on_group_end``. Metadata is also evaluated before ``startup()``.
- :class:`pylabtools.Metadata` with ``records=`` limits metadata to specific records.
- :mod:`pylabtools.instruments`, laid out like :mod:`pymeasure.instruments`, with a driver for the
  Bluefors temperature controller (:class:`~pylabtools.instruments.bluefors.BlueforsTC`).
- :mod:`pylabtools.analysis`: :class:`~pylabtools.analysis.Dataset` and
  :class:`~pylabtools.analysis.RecordView` for selecting, iterating, reducing and time-aligning
  recorded emits, and :func:`~pylabtools.analysis.plot.lineplot` /
  :func:`~pylabtools.analysis.plot.scatterplot` for matplotlib plots of column expressions, coloured
  by a parameter (colour bar or legend) and optionally averaged (``pip install pylabtools[analysis]``).
- Packaging, tests and CI.

See :doc:`migrating` for changes from 0.9.

0.9.1
=====

Final release of the configuration-file based 0.9 series (git tag ``v0.9.1``).
