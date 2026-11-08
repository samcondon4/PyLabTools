""" PyLabTools: laboratory measurement automation built on PyMeasure.

The core package is headless: importing it never imports Qt, creates windows, or writes files.
The optional GUI lives in :mod:`pylabtools.gui` (``pip install pylabtools[gui]``) and is only
imported when first accessed as ``pylabtools.gui``.
"""

__version__ = "1.0.0.dev0"

from . import analysis, legacy, log
from .consumers import Consumer, ConsumerError, running
from .procedure import Metadata, Procedure, every
from .record import Record
from .recorders import CSVRecorder, HDFRecorder, Recorder, SchemaError, hdf_records, read_csv, read_hdf
from .runner import Run, Status, run, run_sequence, start, start_sequence, sweep, wait
from .viewers import LineViewer, Viewer

__all__ = [
    "CSVRecorder", "Consumer", "ConsumerError", "HDFRecorder", "LineViewer", "Metadata", "Procedure",
    "Record", "Recorder", "Run", "SchemaError", "Status", "Viewer", "analysis", "every", "hdf_records",
    "legacy", "log", "read_csv", "read_hdf", "run", "run_sequence", "running", "start", "start_sequence",
    "sweep", "wait", "__version__",
]


def __getattr__(name):
    # - import the Qt-dependent GUI lazily so the core never requires Qt - #
    if name == "gui":
        import importlib
        return importlib.import_module(".gui", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
