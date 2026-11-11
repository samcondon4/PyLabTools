""" Optional Qt display for PyLabTools viewers (``pip install pylabtools[gui]``).

In a script, show the viewers and block until the window is closed::

    with hdf, view:
        run = plab.start(proc)
        plab.gui.show(view, run=run, block=True)  # Ctrl-C stops the run and closes the window
        plab.wait(run)

In Jupyter, let the kernel's asyncio loop drive the window; it updates while the notebook stays
usable::

    window = plab.gui.show(view, run=run, drive="asyncio")

Alternatively run ``%gui qt`` once per kernel and call ``plab.gui.show(view)``.
"""
import asyncio
import itertools
import signal
import sys
import threading
import warnings

try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtCore, QtWidgets
except ImportError as exc:  # pragma: no cover - exercised only without the gui extra
    raise ImportError("pylabtools.gui needs pyqtgraph and a Qt binding; "
                      "install them with: pip install 'pylabtools[gui]'") from exc

from ..log import get_logger
from ..viewers import LineViewer

logger = get_logger(__name__)

__all__ = ["LineViewerWidget", "ViewerWindow", "show", "widget_for"]

# - shown windows are kept here so they are not garbage collected - #
_WINDOWS = []

# - drive="asyncio": seconds between Qt event processing, and the single running pump task - #
PUMP_INTERVAL = 0.02
_PUMP = None


class LineViewerWidget(QtWidgets.QWidget):
    """ Plot of a :class:`~pylabtools.viewers.LineViewer`, redrawn at most ``fps`` times a second.

    :param viewer: The LineViewer to display.
    :param fps: Maximum redraw rate.
    """

    def __init__(self, viewer, fps=20, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.plot = pg.PlotWidget(title=viewer.title)
        self.plot.addLegend()
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        if viewer.x is not None:
            self.plot.setLabel("bottom", viewer.x)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.curves = {}
        self._palette = (pg.intColor(i, hues=9) for i in itertools.count())
        self._drawn_version = None
        self._shown_failure = False
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1, int(1000 / fps)))

    def refresh(self):
        """ Redraw if the viewer's buffer changed since the last draw. """
        if self.viewer.failed and not self._shown_failure:
            self.plot.setTitle(f"{self.viewer.title} — viewer failed: {self.viewer.exception}")
            self._shown_failure = True
        version = self.viewer.version
        if version == self._drawn_version:
            return
        self._drawn_version = version
        for column, (x, y) in self.viewer.plot_data().items():
            curve = self.curves.get(column)
            if curve is None:
                color = self.viewer.colors.get(column) or next(self._palette)
                curve = self.plot.plot(name=column, pen=pg.mkPen(color, width=1.5))
                self.curves[column] = curve
            if x is None:
                curve.setData(y)
            else:
                curve.setData(x, y)

    def stop(self):
        self.timer.stop()


def widget_for(viewer, fps=20):
    """ Return the display widget for a viewer. """
    if isinstance(viewer, LineViewer):
        return LineViewerWidget(viewer, fps=fps)
    raise TypeError(f"No display widget for {type(viewer).__name__}.")


class ViewerWindow(QtWidgets.QWidget):
    """ A window holding one widget per viewer, with an optional run-status line.

    :param viewers: Viewers to display.
    :param title: Window title.
    :param fps: Maximum redraw rate of each plot.
    :param columns: Number of plot columns in the grid.
    :param run: Optional :class:`~pylabtools.runner.Run` (or list of runs) whose status is shown.
    """

    def __init__(self, viewers, title="PyLabTools", fps=20, columns=1, run=None):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(900, 300 + 250 * ((len(viewers) - 1) // columns))
        grid = QtWidgets.QGridLayout(self)
        self.widgets = [widget_for(v, fps=fps) for v in viewers]
        for i, widget in enumerate(self.widgets):
            grid.addWidget(widget, i // columns, i % columns)
        self.runs = [] if run is None else (list(run) if isinstance(run, (list, tuple)) else [run])
        self.status = QtWidgets.QLabel()
        grid.addWidget(self.status, grid.rowCount(), 0, 1, columns)
        self.status.setVisible(bool(self.runs))
        self._status_timer = QtCore.QTimer(self)
        self._status_timer.timeout.connect(self.update_status)
        self._status_timer.start(250)
        self.update_status()

    def update_status(self):
        text = []
        for active in self.runs:
            step = "" if active.step is None or len(active.steps) == 1 else f" step {active.step + 1}/{len(active.steps)}"
            group = "" if not active.group_by or active.group is None else f", group {active.group}"
            text.append(f"{type(active.procedure).__name__} [{active.run_id[:8]}]: {active.status.value}{step}{group}")
        self.status.setText("    ".join(text))

    def closeEvent(self, event):
        for widget in self.widgets:
            widget.stop()
        self._status_timer.stop()
        if self in _WINDOWS:
            _WINDOWS.remove(self)
        super().closeEvent(event)


def show(*viewers, title="PyLabTools", fps=20, columns=1, run=None, block=False, drive=None):
    """ Open a window displaying ``viewers``.

    :param viewers: Viewers to display.
    :param title: Window title.
    :param fps: Maximum redraw rate of each plot.
    :param columns: Number of plot columns.
    :param run: Optional run (or list of runs) whose status is shown in the window. With
        ``block=True``, Ctrl-C stops these runs and waits for their ``shutdown()``.
    :param block: If True, run the Qt event loop until every window is closed (for scripts).
    :param drive: ``"asyncio"`` to process Qt events from a task on the running asyncio loop,
        such as a Jupyter kernel's, so the window updates without ``%gui qt``. One task serves
        every window and ends when the last one is closed. If ``%gui qt`` is active, it already
        drives the window and no task is started. Cannot be combined with ``block=True``.
    :return: The :class:`ViewerWindow`.
    :raises KeyboardInterrupt: If Ctrl-C is pressed while blocking.
    :raises RuntimeError: With ``drive="asyncio"`` when no asyncio loop is running (in a script,
        use ``block=True``).
    """
    if not viewers:
        raise ValueError("show() needs at least one viewer.")
    if drive not in (None, "asyncio"):
        raise ValueError(f"drive must be None or 'asyncio', not {drive!r}.")
    if drive and block:
        raise ValueError("show(): use either block=True (scripts) or drive='asyncio' (notebooks), not both.")
    if drive:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            raise RuntimeError(
                "show(drive='asyncio') needs a running asyncio loop, as in Jupyter. "
                "In a script, use show(..., block=True) instead.") from None
    app = pg.mkQApp("PyLabTools")
    window = ViewerWindow(list(viewers), title=title, fps=fps, columns=columns, run=run)
    window.show()
    _WINDOWS.append(window)
    if block:
        _exec(app, window.runs)
    elif drive:
        _start_pump(app, loop)
    return window


def _kernel_eventloop():
    """ The GUI event loop enabled with IPython's ``%gui``, or None (also outside IPython). """
    ipython = sys.modules.get("IPython")
    shell = ipython.get_ipython() if ipython is not None else None
    return getattr(getattr(shell, "kernel", None), "eventloop", None)


def _start_pump(app, loop):
    """ Start the task that processes Qt events, unless it or ``%gui`` is already running. """
    global _PUMP
    if _kernel_eventloop() is not None:
        warnings.warn("%gui is active and drives the window, so drive='asyncio' starts no task. "
                      "If the window hangs, run %gui (without an argument) to disable it and call "
                      "show(..., drive='asyncio') again.", RuntimeWarning, stacklevel=3)
        return
    if _PUMP is not None and not _PUMP.done():
        return
    _PUMP = loop.create_task(_pump(app))


async def _pump(app):
    """ Process Qt events every PUMP_INTERVAL seconds while a window is open. """
    while _WINDOWS:
        try:
            app.processEvents()
        except KeyboardInterrupt:
            # - an interrupt while the kernel is idle lands here; ending the task would freeze the window - #
            logger.info("KeyboardInterrupt ignored by the Qt pump; close the window to stop it.")
        await asyncio.sleep(PUMP_INTERVAL)
    app.processEvents()  # - let the last window finish closing - #


def _exec(app, runs):
    """ Run the Qt event loop, turning Ctrl-C into a clean stop of ``runs``. """
    interrupted = []
    in_main = threading.current_thread() is threading.main_thread()

    def on_sigint(signum, frame):
        interrupted.append(True)
        app.quit()

    previous = signal.signal(signal.SIGINT, on_sigint) if in_main else None
    # - Qt holds the interpreter inside exec(); wake it regularly so the signal handler can run - #
    wake = QtCore.QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(200)
    try:
        app.exec()
    finally:
        wake.stop()
        if in_main:
            signal.signal(signal.SIGINT, previous)

    if interrupted:
        for active in runs:
            logger.warning("KeyboardInterrupt: stopping run %s", active.run_id[:8])
            active.stop()
        for active in runs:
            active.wait()
        raise KeyboardInterrupt
