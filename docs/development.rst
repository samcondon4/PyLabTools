Development
###########

Setup
=====

.. code-block:: bash

    git clone -b dev/1.0 https://github.com/samcondon4/PyLabTools.git
    cd PyLabTools
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev,gui,docs]"

Tests
=====

.. code-block:: bash

    pytest

The suite runs headless (``QT_QPA_PLATFORM=offscreen`` is set by ``tests/conftest.py``); GUI tests
are skipped if the ``gui`` extra is not installed. Warnings are errors. Every test has a 60 s
timeout so a hung thread fails instead of stalling CI.

What the suite protects:

``test_record.py``
    Conversion rules of ``emit()`` data, and that records are immutable snapshots.
``test_runner.py``
    The run state machine, ``shutdown()`` always running on the worker thread, validation before
    start, sequences, routing errors, consumer failure policy, and data integrity under load
    (10,000 fast emits into a slow consumer must arrive exactly once, in order).
``test_consumers_procedure.py``
    Consumer lifecycle, queue draining (including at interpreter exit) and ``connect()``.
``test_recorders.py``
    The output format: table columns, RecordGroup numbering across runs and files, schema checks,
    and HDF5 / CSV equivalence.
``test_viewers.py``, ``test_gui.py``
    Viewer buffering and offscreen rendering.
``test_examples.py``
    The scripts in ``examples/`` run end to end.
``test_package.py``
    Importing ``pylabtools`` imports no Qt and writes no files.
``instruments/``
    Instrument drivers, as in PyMeasure: protocol tests per driver
    (``instruments/<manufacturer>/test_<module>.py``), PyMeasure's generic checks for every driver
    (``instruments/test_all_instruments.py``), and read-only device tests
    (``*_with_device.py``) that only run with ``pytest --device-address=<address>``.

When changing behaviour, add a test that fails before the change. Changes to the output format
should update ``test_recorders.py`` and :doc:`guide/recording`.

Docs
====

.. code-block:: bash

    sphinx-build -W -b html docs docs/_build/html

Warnings are errors here too, so broken references fail the build.

Adding a recorder or viewer
===========================

Subclass :class:`~pylabtools.Recorder` (implement ``last_record_group`` and ``write``) or
:class:`~pylabtools.Viewer` (override ``select``). All hooks run on the consumer's thread. Use the
``ListConsumer`` helper in ``tests/conftest.py`` and the procedures in ``tests/procedures.py`` for
tests.
