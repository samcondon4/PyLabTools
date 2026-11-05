Quickstart
##########

This walk-through uses PyMeasure's ``SwissArmyFake`` instrument, so it runs without hardware. The
complete script is ``examples/quickstart.py``; run it with ``python examples/quickstart.py`` (add
``--no-gui`` to skip the plot).

1. Write a procedure
====================

A procedure is a :class:`pylabtools.Procedure` subclass. Parameters are PyMeasure parameter objects
declared on the class; instruments are ordinary constructor arguments.

.. code-block:: python

    import time
    from pymeasure.experiment import FloatParameter, IntegerParameter
    import pylabtools as plab

    class WaveLog(plab.Procedure):
        amplitude = FloatParameter("Amplitude", units="V", default=1.0, minimum=0, maximum=10)
        samples = IntegerParameter("Samples", default=300, minimum=1)
        interval = FloatParameter("Interval", units="s", default=0.02, minimum=0)

        def __init__(self, inst, **kwargs):
            super().__init__(**kwargs)
            self.inst = inst

        def startup(self):
            self.inst.output_voltage = self.amplitude

        def execute(self):
            for _ in range(self.samples):
                if self.should_stop():
                    break
                self.emit("wave", {"t": self.inst.time,
                                   "V": self.inst.output_voltage * self.inst.wave})
                time.sleep(self.interval)

        def shutdown(self):
            self.inst.output_voltage = 0   # always runs, even after an error

2. Connect recorders and viewers
================================

``connect()`` routes a record name to any number of consumers:

.. code-block:: python

    from pymeasure.instruments.fakes import SwissArmyFake

    proc = WaveLog(SwissArmyFake(wait=0))
    hdf = plab.HDFRecorder("quickstart.h5")
    view = plab.LineViewer(x="t", y="V", max_rows=500)
    proc.connect("wave", hdf, view)

3. Run it
=========

Consumers must be running while the procedure emits; :func:`pylabtools.running` starts them and
stops them (after writing everything still queued) at the end of the block.

.. code-block:: python

    plab.log.enable()                 # print progress messages

    with plab.running(hdf, view):
        run = plab.start(proc, amplitude=2.5)          # returns immediately
        plab.gui.show(view, run=run, block=True)       # live plot until the window is closed
        plab.wait(run)                                 # Ctrl-C stops the run cleanly

    print(run.status)                 # Status.FINISHED

Without a plot, ``plab.run(proc, amplitude=2.5)`` starts the run and waits for it in one call.

4. Read the data
================

.. code-block:: python

    df = plab.read_hdf("quickstart.h5", "wave", groups=-1)   # -1: the latest run
    df.head()

The result has one row per data point, indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``,
with the procedure parameters (``proc_amplitude``, ...) and metadata (``meta_timestamp``, ...)
joined on. See :doc:`concepts` for what the indices mean.

In Jupyter
==========

The same code works in a notebook. Enable Qt integration once, then show the plot without blocking:

.. code-block:: python

    %gui qt
    plab.gui.show(view)
    hdf.start(); view.start()
    run = plab.start(proc)      # the notebook stays usable; run.stop() to stop early

    # ... later, when you are done with this recorder and viewer:
    hdf.stop(); view.stop()
