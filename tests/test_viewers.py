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


# - expressions in x and y ---------------------------------------------------------------------- #
def test_line_viewer_evaluates_expressions():
    I, Q = np.array([1.0, 3.0]), np.array([0.0, 4.0])
    view = LineViewer(x="frequency / 1e9", y=["20*np.log10(np.sqrt(I**2 + Q**2))", "I"],
                      colors={"I": "r"})
    feed(view, Record("vna", {"frequency": [1e9, 2e9], "I": I, "Q": Q}))
    data = view.plot_data()
    assert list(data) == ["20*np.log10(np.sqrt(I**2 + Q**2))", "I"]
    x, mag = data["20*np.log10(np.sqrt(I**2 + Q**2))"]
    assert x.tolist() == [1.0, 2.0]
    assert np.allclose(mag, [0.0, 20 * np.log10(5.0)])


def test_line_viewer_expressions_see_parameters_and_metadata():
    view = LineViewer(x="t", y=["v - proc_offset", "power", "meta_gain * v"])
    feed(view, Record("r", {"t": [0.0, 1.0], "v": [5.0, 6.0]},
                      proc_params={"offset": 1.0, "power": -20.0}, meta={"gain": 2.0, "offset": 9.0}))
    data = view.plot_data()
    assert data["v - proc_offset"][1].tolist() == [4.0, 5.0]
    assert data["power"][1].tolist() == [-20.0, -20.0]  # - scalars repeat for every row - #
    assert data["meta_gain * v"][1].tolist() == [10.0, 12.0]


def test_line_viewer_buffers_evaluated_values_across_records():
    view = LineViewer(y="2 * v", max_rows=3)
    feed(view, *[Record("r", {"v": [float(k)]}) for k in range(5)])
    assert view.snapshot()["2 * v"].tolist() == [4.0, 6.0, 8.0]


def test_line_viewer_column_names_that_are_not_expressions():
    view = LineViewer(x="f (Hz)", y="S21 (dB)")
    feed(view, Record("r", {"f (Hz)": [1.0, 2.0], "S21 (dB)": [-3.0, -4.0]}))
    assert view.plot_data()["S21 (dB)"][1].tolist() == [-3.0, -4.0]


@pytest.mark.parametrize("y, error, match", [
    ("np.log10(nope)", NameError, "nope"),
    ("v *", SyntaxError, "not a valid expression"),
    ("v[:1]", ValueError, "shape"),
    ("offset", NameError, "both a procedure parameter and metadata"),
])
def test_bad_expressions_fail_the_viewer_only(y, error, match):
    view = LineViewer(y=y)
    feed(view, Record("r", {"v": [1.0, 2.0]}, proc_params={"offset": 1}, meta={"offset": 2}))
    assert view.failed and isinstance(view.exception, error)
    assert match in str(view.exception)


def test_line_viewer_rejects_non_string_columns():
    with pytest.raises(TypeError, match="column names or expressions"):
        LineViewer(y=[1])
