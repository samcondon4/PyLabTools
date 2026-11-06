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
- Driver for the Keysight P9374A VNA (:class:`~pylabtools.instruments.keysight.KeysightP9374a`),
  ported from 0.9, with :meth:`~pylabtools.instruments.keysight.KeysightP9374a.acquire_trace`
  waiting for complete sweeps and averages.
- Packaging, tests and CI.

See :doc:`migrating` for changes from 0.9.

0.9.1
=====

Final release of the configuration-file based 0.9 series (git tag ``v0.9.1``).
