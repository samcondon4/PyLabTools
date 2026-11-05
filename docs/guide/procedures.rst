Writing procedures
##################

:class:`pylabtools.Procedure` is a subclass of the upstream PyMeasure
:class:`pymeasure.experiment.Procedure`, so everything about PyMeasure parameters applies.

Structure
=========

.. code-block:: python

    from pymeasure.experiment import FloatParameter, IntegerParameter, ListParameter, Metadata
    import pylabtools as plab

    class S21Sweep(plab.Procedure):
        power = FloatParameter("Power", units="dBm", default=-10, minimum=-40, maximum=20)
        points = IntegerParameter("Points", default=1601)
        fmt = ListParameter("Format", choices=["MLOG", "PHAS"], default="MLOG")
        averages = IntegerParameter("Averages", default=10)

        # - read from the instrument after startup() and stored with every emit - #
        if_bandwidth = Metadata("IF bandwidth", fget="vna.if_bandwidth")

        def __init__(self, vna, **kwargs):
            super().__init__(**kwargs)
            self.vna = vna

        def startup(self):
            self.vna.power = self.power
            self.vna.points = self.points
            self.vna.trace_format = self.fmt

        def execute(self):
            f = self.vna.frequency_axis
            for i in range(self.averages):
                if self.should_stop():
                    break
                self.emit("s21", {"f": f, "s21": self.vna.trace_data}, meta={"average": i})

        def shutdown(self):
            self.vna.output_enabled = 0

    proc = S21Sweep(vna, points=801)      # parameters can be set in the constructor ...
    plab.run(proc, power=-20)             # ... or per run

Rules of thumb
==============

- **Check** ``self.should_stop()`` **in every loop**; :meth:`~pylabtools.Run.stop` and Ctrl-C only
  request a stop.
- **Put safety in** ``shutdown()``. It runs after ``startup()``/``execute()`` no matter how they
  end. If ``shutdown()`` itself raises after an earlier error, the original error is kept and the
  second one is logged.
- **Parameters are referred to by attribute name** (``power``, not ``"Power"``) everywhere:
  constructor, ``plab.run(proc, power=...)``, sequence steps, and the ``proc_`` output columns.
  Unknown names raise immediately.
- **Every parameter needs a value** before a run starts: give it a ``default`` or pass it in.
- **Keep a record's columns consistent.** All emits of one record name should have the same
  columns and types (recorders enforce this, see :doc:`recording`). Use a different record name
  for differently shaped data, e.g. ``"trace"`` and ``"summary"``.
- **Batch fast data.** Each emit costs a few milliseconds in a recorder. For kHz acquisition, emit
  arrays of many samples rather than one emit per sample.

Several records
===============

A procedure can emit any number of record names, each routed to its own consumers:

.. code-block:: python

    proc.connect("s21", hdf, trace_view)
    proc.connect("temps", hdf, temp_view)

Emitting a name that is not connected fails the run with a ``KeyError`` naming the connected
records, which catches typos early.

Instruments and threads
=======================

The procedure's methods run on the run's worker thread; instruments are used from that thread.
PyLabTools 1.0 does not add locking around instruments, so do not use the same instrument object
from another thread (for example your notebook) while a run that uses it is active.

Reusing a procedure
===================

A procedure object can be run many times (one at a time). Parameters keep the values of the last
run unless overridden, and the routes set with ``connect()`` stay in place. ``disconnect()`` removes
routes; routes cannot be changed while the procedure is running.
