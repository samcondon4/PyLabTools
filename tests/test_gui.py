import numpy as np
import pandas as pd
import pytest
from procedures import Waiter

import pylabtools as plab
from pylabtools import LineViewer, Record, Viewer

gui = pytest.importorskip("pylabtools.gui", reason="pylabtools[gui] not installed")


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
