Instruments
###########

Instrument drivers live in :mod:`pylabtools.instruments`, organised by manufacturer exactly like
:mod:`pymeasure.instruments`, with one subpackage per manufacturer. They are ordinary PyMeasure
instruments, so they work with PyLabTools procedures and with PyMeasure alike, and are written to be
contributed to PyMeasure.

.. code-block:: python

    from pylabtools.instruments.bluefors import BlueforsTC

.. toctree::
    :maxdepth: 2

    bluefors/index

Adding a driver
===============

Follow PyMeasure's layout and conventions, so the driver can later move to PyMeasure unchanged:

- ``pylabtools/instruments/<manufacturer>/<module>.py`` with the PyMeasure license header, and
  ``pylabtools/instruments/<manufacturer>/__init__.py`` importing the driver classes.
- The constructor takes the adapter first, and a ``name`` keyword argument, without communicating
  with the instrument; ``includeSCPI`` is set explicitly (or ``SCPIMixin`` is inherited).
- Property docstrings start with "Control", "Measure", "Set" or "Get".
- Protocol tests in ``tests/instruments/<manufacturer>/test_<module>.py`` using
  :func:`pymeasure.test.expected_protocol`; optional read-only device tests in
  ``test_<module>_with_device.py``, run with ``pytest --device-address=<address>``.
- A page in ``docs/api/instruments/<manufacturer>/``.

``tests/instruments/test_all_instruments.py`` applies PyMeasure's generic instrument checks to every
driver in the package.
