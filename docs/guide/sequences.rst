Sequences
#########

A sequence runs a procedure once per **step**, where each step is a dict of parameter values.

.. code-block:: python

    steps = plab.sweep(power=[-20, -10, 0], averages=[5, 20])
    # [{'power': -20, 'averages': 5}, {'power': -20, 'averages': 20},
    #  {'power': -10, 'averages': 5}, ...]          (the first keyword is the outer loop)

    with plab.running(hdf, view):
        run = plab.run_sequence(proc, steps, points=801)   # points applies to every step

- :func:`~pylabtools.sweep` builds the Cartesian product of the given values; scalars are held
  constant. Any list of dicts works as ``steps``, so non-grid sequences are just a list.
- Keyword arguments to :func:`~pylabtools.start_sequence` / :func:`~pylabtools.run_sequence` apply to
  every step; a step's own values override them.
- Values **carry over**: a parameter not mentioned in a step keeps its value from the previous
  step.
- **Every step is validated before the first one starts.** An out-of-range value in the last step
  of an overnight sweep raises immediately.

Behaviour
=========

- Each step runs ``startup()``, ``execute()`` and ``shutdown()``.
- By default the whole sequence is **one RecordGroup** in the output. ``RecordGroupInd`` keeps
  counting across steps; the ``proc_`` columns tell the steps apart. Use ``group_by`` (below) to
  split a sequence into several RecordGroups.
- If a step fails, the sequence stops and the run is ``FAILED``; ``run.step`` is the index of the
  failing step.
- :meth:`~pylabtools.Run.stop` stops the current step (via ``should_stop()``) and skips the rest.
- Inside a procedure, ``self.is_last()`` is True during the final step, which is useful for
  leaving an instrument on between steps and turning it off only at the very end.

Record groups: ``group_by``
===========================

``group_by`` starts a new RecordGroup whenever the named parameter(s) change value from one step to
the next. In a temperature/power sweep, ``group_by="setpoint"`` makes every setpoint one
RecordGroup, so *all* records emitted at that setpoint (VNA traces, fridge samples from a
:ref:`background task <guide/procedures:Background tasks>`, ...) share it:

.. code-block:: python

    steps = plab.sweep(setpoint=[0.02, 0.05, 0.1], power=[-30, -20, -10])   # setpoint outermost
    run = plab.start_sequence(proc, steps, group_by="setpoint")

    s21 = plab.read_hdf("sweep.h5", "s21")
    fridge = plab.read_hdf("sweep.h5", "fridge")
    s21.loc[4], fridge.loc[4]        # the traces and the temperatures of RecordGroup 4

- ``RecordGroupInd`` restarts at 0 in every group and counts each record name separately, so the
  traces of a group are numbered 0..N-1 and its fridge samples 0..M-1.
- Groups follow the step order: put the grouping parameter in the **outer loop** (first keyword of
  :func:`~pylabtools.sweep`). Returning to an earlier value later in the sequence starts another
  group.
- ``group_by`` accepts a list, e.g. ``group_by=["setpoint", "field"]`` for one group per
  combination.
- ``run.group`` is the index of the current group within the run; it is shown in the plot window's
  status line.

``examples/temp_power_sweep.py`` is a complete, runnable version of this experiment with fake
instruments.

Progress
========

.. code-block:: python

    run = plab.start_sequence(proc, steps)
    run.step, len(run.steps)       # current step index and total
    run.status                     # Status.RUNNING, ...
    plab.wait(run)

With ``plab.log.enable()`` each step is logged as it starts, and ``plab.gui.show(view, run=run)``
shows the step in the window's status line.
