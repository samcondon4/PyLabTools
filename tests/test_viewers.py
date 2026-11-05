import threading

import numpy as np
import pandas as pd
import pytest
from procedures import Counter

import pylabtools as plab
from pylabtools import LineViewer, Record, Status, Viewer


def feed(viewer, *records):
    with viewer:
        for rec in records:
            viewer.put(rec)
        viewer.join_queue()


# - headless viewers ---------------------------------------------------------------------------- #
def test_viewer_buffer_keeps_newest_rows():
    view = Viewer(max_rows=5)
    feed(view, *[Record("r", {"i": [3 * k, 3 * k + 1, 3 * k + 2]}) for k in range(4)])
    assert view.snapshot()["i"].tolist() == [7, 8, 9, 10, 11]
    assert len(view._frames) <= 3  # - old frames are dropped, not just hidden - #


def test_snapshot_is_a_copy_and_version_changes():
    view = Viewer()
    assert view.snapshot().empty
    v0 = view.version
    feed(view, Record("r", {"i": [1]}))
    snap = view.snapshot()
    snap.loc[0, "i"] = 99
    assert view.snapshot()["i"].tolist() == [1]
    assert view.version > v0
    view.clear()
    assert view.snapshot().empty


def test_clear_on_new_run():
    view = Viewer(clear_on_new_run=True)
    feed(view, Record("r", 1, run_id="a"), Record("r", 2, run_id="a"), Record("r", 3, run_id="b"))
    assert view.snapshot()["r"].tolist() == [3]


def test_line_viewer_plot_data_and_default_columns():
    view = LineViewer(x="t")
    feed(view, Record("r", {"t": [0.0, 1.0], "a": [1, 2], "b": [3.0, 4.0], "flag": [True, False],
                            "name": ["x", "y"]}))
    assert view.y == ["a", "b"]
    data = view.plot_data()
    assert set(data) == {"a", "b"}
    x, y = data["b"]
    assert x.tolist() == [0.0, 1.0] and y.tolist() == [3.0, 4.0]


def test_line_viewer_without_x():
    view = LineViewer(y="v")
    feed(view, Record("r", {"v": [5.0, 6.0]}))
    assert view.plot_data()["v"][0] is None


def test_line_viewer_missing_column_fails_viewer_but_not_run():
    view = LineViewer(y="nope")
    proc = Counter(samples=5).connect("counts", view)
    with view:
        run = plab.run(proc)
        view.join_queue()
    assert run.status is Status.FINISHED
    assert view.failed and "no column(s) ['nope']" in str(view.exception)


def test_viewer_does_not_delay_run_end():
    """ Viewers are non-critical: a slow viewer must not hold the run open. """
    class Slow(Viewer):
        def handle(self, record):
            threading.Event().wait(0.05)
            super().handle(record)

    view = Slow()
    with view:
        run = plab.run(Counter(samples=20).connect("counts", view))
        assert run.duration < 0.5
