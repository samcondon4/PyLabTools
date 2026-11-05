""" PyLabTools: laboratory measurement automation built on PyMeasure.

The core package is headless: importing it never imports Qt, creates windows, or writes files.
The optional GUI lives in :mod:`pylabtools.gui` (``pip install pylabtools[gui]``) and is only
imported when first accessed as ``pylabtools.gui``.
"""

__version__ = "1.0.0.dev0"

from . import log
from .consumers import Consumer, ConsumerError
from .procedure import Procedure
from .record import Record
from .runner import Run, Status, run, run_sequence, start, start_sequence, sweep

__all__ = [
    "Consumer", "ConsumerError", "Procedure", "Record", "Run", "Status",
    "log", "run", "run_sequence", "start", "start_sequence", "sweep", "__version__",
]


def __getattr__(name):
    # - import the Qt-dependent GUI lazily so the core never requires Qt - #
    if name == "gui":
        import importlib
        return importlib.import_module(".gui", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
