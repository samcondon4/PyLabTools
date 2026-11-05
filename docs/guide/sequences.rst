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
- The whole sequence has one ``run_id`` and is therefore **one RecordGroup** in the output.
  ``RecordGroupInd`` keeps counting across steps; the ``proc_`` columns tell the steps apart.
- If a step fails, the sequence stops and the run is ``FAILED``; ``run.step`` is the index of the
  failing step.
- :meth:`~pylabtools.Run.stop` stops the current step (via ``should_stop()``) and skips the rest.
- Inside a procedure, ``self.is_last()`` is True during the final step, which is useful for
  leaving an instrument on between steps and turning it off only at the very end.

Progress
========

.. code-block:: python

    run = plab.start_sequence(proc, steps)
    run.step, len(run.steps)       # current step index and total
    run.status                     # Status.RUNNING, ...
    plab.wait(run)

With ``plab.log.enable()`` each step is logged as it starts, and ``plab.gui.show(view, run=run)``
shows the step in the window's status line.
