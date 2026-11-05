Concepts
########

The pipeline
============

.. code-block:: text

                                 +--> HDFRecorder  (thread) --> run.h5
    Procedure.execute()          |
      emit("wave", data) --------+--> CSVRecorder  (thread) --> out/wave.csv
      (run worker thread)        |
                                 +--> LineViewer   (thread) --> buffer <-- gui (Qt main thread,
                                                                            polls at fixed fps)

- A **procedure** runs on its own worker thread, created by a :class:`~pylabtools.Run`.
- Each ``emit()`` creates a new, immutable :class:`~pylabtools.Record` holding a *copy* of the data,
  the current parameter values and the metadata, and puts it on the queue of every consumer
  connected to that record name.
- **Consumers** (recorders and viewers) each process their queue on their own thread. A slow
  consumer never corrupts another's data, and a slow plot never slows acquisition.

Because records are copied snapshots, a procedure may reuse its buffers freely after emitting.

Runs and their status
=====================

A run moves through ``QUEUED -> RUNNING -> FINISHED | FAILED | ABORTED``
(:class:`~pylabtools.Status`):

``FINISHED``
    ``execute()`` returned, and every recorder has stored every record of the run.
``FAILED``
    ``startup()``, ``execute()``, ``shutdown()`` or a background task raised, or a recorder failed.
    The exception is in ``run.exception``; ``plab.run()`` and ``plab.wait()`` re-raise it.
``ABORTED``
    :meth:`~pylabtools.Run.stop` was called (or Ctrl-C pressed during ``plab.run``/``plab.wait``).

In every case ``shutdown()`` runs on the worker thread, so it is the place to put instruments in a
safe state. Parameter values are validated *before* the run starts (for a sequence, every step), so
mistakes are reported immediately.

Recorders vs. viewers
---------------------

Recorders are *critical*: if one fails, the run fails, because data would otherwise be lost
silently. Viewers are *non-critical*: a viewer failure is logged and that viewer stops receiving
records, but the run and its recorders continue.

Record indices
==============

Every row PyLabTools writes is identified by three integer indices:

``RecordGroup``
    One per run by default; a whole **sequence** is one run, so all of its steps share a
    RecordGroup. A sequence started with ``group_by`` gets one RecordGroup per value of the
    grouping parameter(s), e.g. one per temperature setpoint (see :doc:`guide/sequences`). All
    records emitted while a group is active share its RecordGroup. Numbering continues from the
    largest group already in the output file.
``RecordGroupInd``
    The emit counter of that record name within the group (0, 1, 2, ...). It keeps counting across
    the steps of a group.
``RecordRow``
    The row within one emit. Emitting a 1601-point trace gives RecordRows 0-1600.

Each record is stored as three tables linked by ``(RecordGroup, RecordGroupInd)``:

``data``
    The emitted data, one row per data row.
``proc_params``
    The procedure parameter values, one row per emit.
``meta``
    The emit ``timestamp`` (UTC) plus metadata, one row per emit.

Example: a two-step sequence over ``power = [-10, 0]`` that emits a 3-point trace twice per step,
written to a file that already holds RecordGroups 0-3, gives

.. code-block:: text

    data                                              proc_params
    RecordGroup  RecordGroupInd  RecordRow  f    S21  RecordGroup  RecordGroupInd  power
    4            0               0          1e9  ...  4            0               -10
    4            0               1          2e9  ...  4            1               -10
    4            0               2          3e9  ...  4            2               0
    4            1               0          1e9  ...  4            3               0
    ...
    4            3               2          3e9  ...

``read_hdf()`` joins the tables back into one frame indexed by all three indices.

What emit() accepts
===================

``emit(name, data, meta=None)`` converts ``data`` to a table (:func:`pylabtools.record.to_dataframe`):

- a **dict** of scalars (one row) or equal-length arrays (one row per element); 2-D values are
  split into columns ``key_0, key_1, ...``;
- a **DataFrame** or **Series**;
- a 1-D array or list (one column named after the record) or a 2-D array (``name_0, name_1, ...``);
- a single scalar.

``meta`` is a dict of extra values for that emit. Values of PyMeasure ``Metadata`` attributes on
the procedure are added automatically, to every record, or only to the records named with
:class:`pylabtools.Metadata` ``records=``. They are evaluated before ``startup()`` and again after
it, so every record of a step (including those emitted during ``startup()`` or by background
tasks) has the same metadata columns.
