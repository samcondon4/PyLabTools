Installation
############

PyLabTools needs Python 3.10 or newer.

Until 1.0 is released, install it from the ``dev/1.0`` branch:

.. code-block:: bash

    pip install "pylabtools[gui] @ git+https://github.com/samcondon4/PyLabTools.git@dev/1.0"

or, from a clone, in editable mode:

.. code-block:: bash

    git clone -b dev/1.0 https://github.com/samcondon4/PyLabTools.git
    cd PyLabTools
    pip install -e ".[gui]"

Dependencies
============

The core installs ``numpy``, ``pandas``, ``pymeasure>=0.14`` and ``tables`` (PyTables, for HDF5).

Optional extras:

``gui``
    ``pyqtgraph`` and ``PyQt5`` for live plots (:mod:`pylabtools.gui`). Any Qt binding supported by
    pyqtgraph (PyQt5, PyQt6, PySide6) works; the extra installs PyQt5.
``dev``
    ``pytest`` and ``pytest-timeout`` to run the test suite.
``docs``
    Sphinx and the documentation theme.

Instrument drivers come from PyMeasure. Some drivers need extra packages (for example ``pyvisa-py``
or a vendor VISA library); see the PyMeasure documentation for your instrument.

Legacy 0.9
==========

The configuration-file based 0.9 series is preserved at the ``v0.9.1`` tag:

.. code-block:: bash

    pip install "git+https://github.com/samcondon4/PyLabTools.git@v0.9.1"
