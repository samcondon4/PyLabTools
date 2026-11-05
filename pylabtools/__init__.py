""" PyLabTools: laboratory measurement automation built on PyMeasure.

The core package is headless: importing it never imports Qt, creates windows, or writes files.
"""

__version__ = "1.0.0.dev0"

from . import log
from .record import Record

__all__ = ["Record", "log", "__version__"]
