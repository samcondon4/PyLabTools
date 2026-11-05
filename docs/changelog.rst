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
- Packaging, tests and CI.

See :doc:`migrating` for changes from 0.9.

0.9.1
=====

Final release of the configuration-file based 0.9 series (git tag ``v0.9.1``).
