""" Instrument drivers for PyLabTools, laid out like :mod:`pymeasure.instruments`.

Drivers are organised by manufacturer, one subpackage each, and are written as ordinary PyMeasure
instruments so that they can be contributed to PyMeasure::

    pylabtools/instruments/<manufacturer>/__init__.py      imports the driver classes
    pylabtools/instruments/<manufacturer>/<model>.py       one module per instrument family

Import drivers from their manufacturer package, e.g.
``from pylabtools.instruments.bluefors import BlueforsTC``. As in PyMeasure, this package does not
import the manufacturer subpackages itself, so a driver's optional dependencies are only needed
when that driver is used.
"""
