""" Viewers: consumers that keep a rolling buffer of recent data for live display.

Viewers are headless. They only buffer data; drawing is done by the optional
:mod:`pylabtools.gui`, which polls :meth:`Viewer.snapshot` at a fixed frame rate. The plot refresh
rate is therefore independent of how fast a procedure emits, and a slow display never slows down
acquisition.

Viewers are *non-critical* consumers: if one fails (for example because a plotted column is
missing), the error is logged and the run continues; recorders keep receiving every record.
"""
import collections
import threading

import pandas as pd

from .analysis.expressions import Names, evaluate
from .consumers import Consumer
from .log import get_logger

logger = get_logger(__name__)

__all__ = ["Viewer", "LineViewer"]


class Viewer(Consumer):
    """ Base viewer: buffers the most recent ``max_rows`` data rows of the records it receives.

    :param max_rows: Number of data rows to keep.
    :param clear_on_new_run: If True, empty the buffer when records of a new run arrive.
    :param name: Name used in log messages and window titles.
    :param maxsize: Maximum queue length (see :class:`~pylabtools.consumers.Consumer`).
    """

    critical = False

    def __init__(self, max_rows=1000, clear_on_new_run=False, name=None, maxsize=0):
        super().__init__(name=name, maxsize=maxsize)
        if max_rows < 1:
            raise ValueError("max_rows must be at least 1.")
        self.max_rows = int(max_rows)
        self.clear_on_new_run = clear_on_new_run
        self._frames = collections.deque()
        self._n_rows = 0
        self._buffer_lock = threading.Lock()
        self._version = 0
        self._run_id = None
        self._cache = (None, None)  # - (version, DataFrame) - #

    def handle(self, record):
        frame = self.select(record)
        with self._buffer_lock:
            if self.clear_on_new_run and record.run_id != self._run_id:
                self._frames.clear()
                self._n_rows = 0
            self._run_id = record.run_id
            self._frames.append(frame)
            self._n_rows += len(frame.index)
            # - drop whole frames that are entirely outside the newest max_rows rows - #
            while self._frames and self._n_rows - len(self._frames[0].index) >= self.max_rows:
                self._n_rows -= len(self._frames.popleft().index)
            self._version += 1

    def select(self, record):
        """ Return the part of ``record.data`` to buffer. Subclasses may restrict the columns. """
        return record.data

    @property
    def version(self):
        """ Counter incremented on every buffer change; displays redraw only when it changes. """
        return self._version

    def snapshot(self):
        """ Return a copy of the buffered rows (at most ``max_rows``) as one DataFrame. Thread-safe. """
        with self._buffer_lock:
            version, cached = self._cache
            if version == self._version and cached is not None:
                return cached.copy()
            if not self._frames:
                frame = pd.DataFrame()
            else:
                frame = pd.concat(list(self._frames), ignore_index=True).tail(self.max_rows)
                frame = frame.reset_index(drop=True)
            self._cache = (self._version, frame)
            return frame.copy()

    def clear(self):
        """ Empty the buffer. """
        with self._buffer_lock:
            self._frames.clear()
            self._n_rows = 0
            self._version += 1


class LineViewer(Viewer):
    """ Buffer data for a line plot of one or more ``y`` columns against an ``x`` column.

    ``x`` and ``y`` can be column names or expressions, as in
    :func:`~pylabtools.analysis.plot.lineplot`::

        LineViewer(x="frequency / 1e9", y="20*np.log10(np.sqrt(I**2 + Q**2))")

    An expression sees the record's data columns as numpy arrays, ``np``, and the record's
    procedure parameters and metadata as scalars (prefix with ``proc_`` / ``meta_`` when a name is
    in both); scalars are repeated for every row. Expressions are evaluated once per record as it
    arrives, on the viewer's thread, and the results are buffered under the expression string.

    :param y: Column name or expression, or a list of them, to plot. Defaults to every numeric
        column except ``x``, taken from the first record received.
    :param x: Column name or expression for the horizontal axis. If None, points are plotted
        against their position in the buffer.
    :param max_rows: Number of points to keep.
    :param colors: Optional ``{y: color}`` (any pyqtgraph color, e.g. ``"r"`` or ``"#1f77b4"``),
        keyed by the ``y`` strings as given.
    :param title: Plot title; defaults to the viewer name.
    :param kwargs: Further :class:`Viewer` arguments.
    """

    def __init__(self, y=None, x=None, max_rows=1000, colors=None, title=None, **kwargs):
        super().__init__(max_rows=max_rows, **kwargs)
        self.y = [y] if isinstance(y, str) else (None if y is None else list(y))
        self.x = x
        for expression in ([] if x is None else [x]) + (self.y or []):
            if not isinstance(expression, str):
                raise TypeError(f"x and y must be column names or expressions, not {expression!r}.")
        self.colors = dict(colors or {})
        self.title = title if title is not None else self.name

    def select(self, record):
        data = record.data
        if self.y is None:
            self.y = [c for c in data.columns
                      if c != self.x and pd.api.types.is_numeric_dtype(data[c])
                      and not pd.api.types.is_bool_dtype(data[c])]
        columns = ([self.x] if self.x is not None else []) + self.y
        params, meta = record.proc_params, record.meta
        names = Names(data, params, meta, set(params) & set(meta))
        missing = [c for c in columns if c.isidentifier() and c not in names]
        if missing:
            raise KeyError(f"{self.name}: record {record.name!r} has no column(s) {missing}; "
                           f"its columns are {list(data.columns)}.")
        n_rows = len(data.index)
        return pd.DataFrame({c: evaluate(c, names, n_rows, what=f"{self.name}:") for c in columns})

    def plot_data(self):
        """ Return ``{y column: (x values or None, y values)}`` for the buffered data. """
        frame = self.snapshot()
        if frame.empty or self.y is None:
            return {}
        x = None if self.x is None else frame[self.x].to_numpy(dtype=float)
        return {col: (x, frame[col].to_numpy(dtype=float)) for col in self.y}
