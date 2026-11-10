import asyncio
import pathlib
import sys
import time
import types

import numpy as np
import pandas as pd
import pytest
from procedures import Waiter

import pylabtools as plab
from pylabtools import LineViewer, Record, Viewer

gui = pytest.importorskip("pylabtools.gui", reason="pylabtools[gui] not installed", exc_type=ImportError)


def feed(viewer, *records):
    with viewer:
        for rec in records:
            viewer.put(rec)
        viewer.join_queue()


def test_line_viewer_widget_draws_buffer():
    view = LineViewer(x="t", y=["a", "b"], colors={"a": "r"})
    feed(view, Record("r", pd.DataFrame({"t": np.arange(10.0), "a": np.ones(10), "b": np.zeros(10)})))
    window = gui.show(view, title="test")
    try:
        widget = window.widgets[0]
        widget.refresh()
        assert set(widget.curves) == {"a", "b"}
        x, y = widget.curves["a"].getData()
        assert x.tolist() == list(range(10)) and y.tolist() == [1.0] * 10
        drawn = widget._drawn_version
        widget.refresh()  # - unchanged buffer: nothing to redraw - #
        assert widget._drawn_version == drawn
    finally:
        window.close()
    assert window not in gui._WINDOWS


def test_window_shows_run_status():
    proc = Waiter()
    view = LineViewer(y="v")
    run = plab.start(proc)
    try:
        window = gui.show(view, run=run)
        assert proc.started.wait(5)
        window.update_status()
        assert "running" in window.status.text()
        window.close()
    finally:
        run.stop()
        run.wait(5)


def test_blocking_show_returns_when_window_closed():
    view = LineViewer(y="v")
    app = gui.pg.mkQApp()
    gui.QtCore.QTimer.singleShot(200, app.closeAllWindows)
    window = gui.show(view, block=True)
    assert not window.isVisible()


def test_widget_for_unknown_viewer_type():
    with pytest.raises(TypeError, match="No display widget"):
        gui.widget_for(Viewer())


# - drive="asyncio" --------------------------------------------------------------------------- #
def test_asyncio_drive_processes_qt_events_and_stops_with_last_window(monkeypatch):
    monkeypatch.setattr(gui, "_PUMP", None)
    view = LineViewer(y="v")

    async def main():
        first = gui.show(view, drive="asyncio")
        pump = gui._PUMP
        second = gui.show(view, drive="asyncio")
        assert gui._PUMP is pump  # - one task for every window - #
        fired = []
        timer = gui.QtCore.QTimer()
        timer.timeout.connect(lambda: fired.append(1))
        timer.start(50)
        await asyncio.sleep(0.6)
        timer.stop()
        assert 6 <= len(fired) <= 13
        first.close()
        await asyncio.sleep(0.1)
        assert not pump.done()
        second.close()
        await asyncio.wait_for(pump, 1)

    asyncio.run(main())


def test_asyncio_drive_needs_a_running_loop():
    with pytest.raises(RuntimeError, match="block=True"):
        gui.show(LineViewer(y="v"), drive="asyncio")
    assert gui._WINDOWS == []


@pytest.mark.parametrize("kwargs, match", [
    ({"drive": "qt"}, "drive must be"),
    ({"drive": "asyncio", "block": True}, "not both"),
])
def test_invalid_drive_arguments(kwargs, match):
    with pytest.raises(ValueError, match=match):
        gui.show(LineViewer(y="v"), **kwargs)


def test_asyncio_drive_defers_to_active_gui_magic(monkeypatch):
    kernel = types.SimpleNamespace(eventloop=object())
    fake_ipython = types.SimpleNamespace(get_ipython=lambda: types.SimpleNamespace(kernel=kernel))
    monkeypatch.setitem(sys.modules, "IPython", fake_ipython)
    monkeypatch.setattr(gui, "_PUMP", None)

    async def main():
        with pytest.warns(RuntimeWarning, match="%gui is active"):
            window = gui.show(LineViewer(y="v"), drive="asyncio")
        assert gui._PUMP is None
        window.close()

    asyncio.run(main())


def test_asyncio_drive_keeps_qt_running_in_an_idle_jupyter_kernel():
    """ The case that hung on Windows with %gui qt: Qt must keep running between cells. """
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    pytest.importorskip("ipykernel")
    repo = str(pathlib.Path(__file__).resolve().parents[1])
    nb = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_code_cell(
            f"import sys; sys.path.insert(0, {repo!r})\n"
            "import pylabtools as plab, pylabtools.gui\n"
            "from pyqtgraph.Qt import QtCore\n"
            "window = plab.gui.show(plab.LineViewer(y='v'), drive='asyncio')\n"
            "fired = []\n"
            "timer = QtCore.QTimer()\n"
            "timer.timeout.connect(lambda: fired.append(1))\n"
            "timer.start(100)"),
        nbformat.v4.new_code_cell("timer.stop(); window.close(); print(len(fired))"),
    ])
    client = nbclient.NotebookClient(nb, kernel_name="python3", timeout=60)
    with client.setup_kernel():
        client.execute_cell(nb.cells[0], 0)
        time.sleep(2)  # - kernel idle: only the pump can run Qt now - #
        cell = client.execute_cell(nb.cells[1], 1)
    fired = int(cell.outputs[0]["text"])
    assert 12 <= fired <= 22
