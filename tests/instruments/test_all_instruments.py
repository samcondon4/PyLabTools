""" Generic checks applied to every PyLabTools instrument, following PyMeasure's
``tests/instruments/test_all_instruments.py`` so drivers meet PyMeasure's conventions:

- the constructor takes the adapter first and works with any adapter object, without communicating;
- it accepts a ``name`` keyword argument;
- ``includeSCPI`` is set explicitly (no deprecation warning);
- every property docstring starts with "Control", "Measure", "Set" or "Get".

PyMeasure also checks that a resource *string* is passed to a VISA adapter together with unknown
keyword arguments; that does not apply to network instruments whose first argument is a host name
(e.g. ``BlueforsTC``), so it is not repeated here.
"""
import importlib
import inspect
import pkgutil
from unittest.mock import MagicMock

import pytest
from pymeasure.instruments import Channel, Instrument

import pylabtools.instruments


def _find(base):
    found = set()
    for module in pkgutil.walk_packages(pylabtools.instruments.__path__, "pylabtools.instruments."):
        mod = importlib.import_module(module.name)
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, base) and obj.__module__.startswith("pylabtools.instruments"):
                found.add(obj)
    return sorted(found, key=lambda c: c.__qualname__)


devices = _find(Instrument)
channels = _find(Channel)
properties = [(cls, name, prop) for cls in devices + channels
              for name, prop in inspect.getmembers(cls, lambda o: isinstance(o, property))
              if name not in dir(Instrument) and name not in dir(Channel)]


def test_drivers_are_found():
    assert devices, "no instruments found in pylabtools.instruments"


@pytest.mark.parametrize("cls", devices, ids=lambda c: c.__name__)
def test_adapter_arg(cls):
    cls(adapter=MagicMock())


@pytest.mark.parametrize("cls", devices, ids=lambda c: c.__name__)
def test_name_argument(cls):
    assert cls(adapter=MagicMock(), name="Name_Test").name == "Name_Test"


@pytest.mark.parametrize("cls", devices, ids=lambda c: c.__name__)
@pytest.mark.filterwarnings("error::FutureWarning")
def test_includeSCPI_not_implicit(cls):
    cls(adapter=MagicMock())


@pytest.mark.parametrize("cls, name, prop", properties, ids=[f"{c.__name__}.{n}" for c, n, _ in properties])
def test_property_docstrings(cls, name, prop):
    assert prop.__doc__, f"{cls.__name__}.{name} has no docstring"
    assert prop.__doc__.split(maxsplit=1)[0] in ("Control", "Measure", "Set", "Get"), \
        f"{cls.__name__}.{name}: docstring should start with Control/Measure/Set/Get"
