""" pylabtools.analysis: Dataset, RecordView and Emit, on files written by the real recorders. """
import datetime

import numpy as np
import pandas as pd
import pytest
from pymeasure.experiment import FloatParameter, IntegerParameter

import pylabtools as plab
from pylabtools import CSVRecorder, HDFRecorder, Record
from pylabtools.analysis import Dataset, Emit, RecordView
from pylabtools.recorders import DATA_INDEX, EMIT_INDEX, make_tables

T0 = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=datetime.timezone.utc)


def at(seconds):
    return T0 + datetime.timedelta(seconds=seconds)


def write(recorder, records):
    """ Write ``(group, Record)`` pairs straight through a recorder, with controlled timestamps. """
    recorder.on_start()
    try:
        for group, record in records:
            recorder.write(record.name, make_tables(record, group))
    finally:
        recorder.on_stop()


def sweep_records():
    """ Two setpoint groups. Per group: fridge samples every 10 s, and two powers x two traces. """
    records = []
    t = 0
    for group, setpoint in enumerate([0.05, 0.1]):
        fridge_i = trace_i = 0
        for power in [-20.0, -10.0]:
            for trace in range(2):
                records.append((group, Record("fridge", {"T5": setpoint + 0.001 * fridge_i, "T1": 45.0},
                                              proc_params={"setpoint": setpoint, "power": power},
                                              index=fridge_i, timestamp=at(t))))
                fridge_i += 1
                f = np.linspace(5.99e9, 6.01e9, 5)
                s21 = -np.abs(power) / 10 * np.array([0, 1, 3, 1, 0]) - trace
                records.append((group, Record("s21", {"f": f, "s21": s21},
                                              proc_params={"setpoint": setpoint, "power": power},
                                              meta={"trace": trace, "power": power + 0.5},
                                              index=trace_i, timestamp=at(t + 2))))
                trace_i += 1
                t += 10
    return records


@pytest.fixture(params=["hdf", "csv"])
def ds(request, tmp_path):
    if request.param == "hdf":
        recorder, source = HDFRecorder(tmp_path / "sweep.h5"), tmp_path / "sweep.h5"
    else:
        recorder, source = CSVRecorder(tmp_path / "sweep_csv"), tmp_path / "sweep_csv"
    write(recorder, sweep_records())
    return Dataset(source)


# - Dataset ---------------------------------------------------------------------------------------- #
def test_dataset_lists_and_reads_records(ds):
    assert ds.records == ["fridge", "s21"]
    assert "s21" in ds and "nope" not in ds
    assert list(ds) == ["fridge", "s21"] and len(ds) == 2
    assert ds["s21"] is ds["s21"]                      # - cached - #
    assert "records=['fridge', 's21']" in repr(ds)


def test_dataset_errors(tmp_path, ds):
    with pytest.raises(FileNotFoundError):
        Dataset(tmp_path / "missing.h5")
    with pytest.raises(KeyError, match="no record 'nope'"):
        ds["nope"]


def test_dataset_reads_selected_groups(ds):
    latest = ds.record("s21", groups=-1)
    assert latest.groups == [1]
    assert len(latest) == 4


def test_plab_analysis_is_importable():
    assert plab.analysis.Dataset is Dataset


# - RecordView tables ---------------------------------------------------------------------------- #
def test_view_tables(ds):
    s21 = ds["s21"]
    assert s21.groups == [0, 1]
    assert len(s21) == 8 and len(s21.data) == 40
    assert s21.columns == ["f", "s21"]
    assert s21.params == ["setpoint", "power"]
    assert s21.data.index.names == DATA_INDEX
    assert s21.proc_params.index.names == EMIT_INDEX
    assert list(s21.meta.columns) == ["timestamp", "trace", "power"]
    assert "emits=8" in repr(s21)


def test_emit_table_and_to_frame(ds):
    s21 = ds["s21"]
    table = s21.emit_table()
    assert table.index.names == EMIT_INDEX
    assert list(table.columns) == ["proc_setpoint", "proc_power", "meta_timestamp", "meta_trace", "meta_power"]
    frame = s21.to_frame()
    assert frame.index.names == DATA_INDEX
    assert len(frame) == 40
    assert set(table.columns) <= set(frame.columns)


def test_to_frame_matches_read_hdf(tmp_path):
    write(HDFRecorder(tmp_path / "a.h5"), sweep_records())
    pd.testing.assert_frame_equal(Dataset(tmp_path / "a.h5")["s21"].to_frame(),
                                  plab.read_hdf(tmp_path / "a.h5", "s21"))


# - selection ------------------------------------------------------------------------------------ #
def test_group(ds):
    s21 = ds["s21"]
    assert s21.group(1).groups == [1]
    assert s21.group(-1).groups == [1]
    assert s21.group([0, 1]).groups == [0, 1]
    assert len(s21.group(0).data) == 20
    with pytest.raises(KeyError, match="no RecordGroup"):
        s21.group(5)


def test_where_values_and_lists(ds):
    s21 = ds["s21"]
    assert len(s21.where(setpoint=0.1)) == 4
    assert len(s21.where(setpoint=0.1, trace=0)) == 2
    assert len(s21.where(trace=[0, 1], proc_power=-20)) == 4
    assert len(s21.where(setpoint=0.3)) == 0


def test_where_expressions(ds):
    s21 = ds["s21"]
    assert len(s21.where("setpoint < 0.07")) == 4
    assert len(s21.where("setpoint > 0.07", trace=1)) == 2              # - with keywords - #
    assert len(s21.where("setpoint > 0.07", "trace == 1")) == 2         # - all must hold - #
    assert len(s21.where("0.01 < setpoint < 0.07 and trace == 0")) == 2
    assert len(s21.where("trace in [0, 1] and not proc_power == -10")) == 4
    assert len(s21.where("proc_power > meta_power - 1")) == 8
    assert len(s21.where("trace != 0 or setpoint == 0.1")) == 6
    assert len(s21.where("np.abs(proc_power) > 15")) == 4


def test_where_floats_use_isclose(ds):
    assert len(ds["s21"].where(setpoint=0.15 - 0.05)) == 4   # - 0.09999999999999999 - #
    assert len(ds["s21"].where("setpoint == 0.15 - 0.05")) == 4
    assert len(ds["s21"].where("setpoint in [0.15 - 0.05]")) == 4
    assert len(ds["s21"].where("setpoint != 0.15 - 0.05")) == 4


def test_where_masks(ds):
    s21 = ds["s21"]
    depth = s21.reduce(lambda d: d.s21.min(), name="depth")["depth"]
    assert len(s21.where(depth < -4.5)) == 4                            # - a Series, one value per emit - #
    assert len(s21.where((depth < -4.5).to_numpy(), trace=0)) == 2


def test_where_errors(ds):
    s21 = ds["s21"]
    with pytest.raises(TypeError, match="not functions"):
        s21.where(lambda t: t.proc_setpoint > 0.07)
    with pytest.raises(TypeError, match="expression strings"):
        s21.where(setpoint=lambda s: s < 0.07)
    with pytest.raises(TypeError, match="one value per emit"):
        s21.where(np.ones(3, dtype=bool))
    with pytest.raises(NameError, match="'f'.*selected with rows"):
        s21.where("f > 6e9")
    with pytest.raises(NameError, match="both a procedure parameter and metadata"):
        s21.where("power > -15")
    with pytest.raises(ValueError, match="True or False per emit"):
        s21.where("setpoint * 2")
    with pytest.raises(SyntaxError, match="not a valid expression"):
        s21.where("setpoint <")


# - rows ----------------------------------------------------------------------------------------- #
def test_rows_selects_data_within_every_emit(ds):
    s21 = ds["s21"]
    window = s21.rows("5.995e9 <= f < 6.01e9")
    assert len(window) == len(s21) == 8                                 # - every emit kept - #
    assert len(window.data) == 8 * 3
    assert window.data.index.get_level_values("RecordRow").unique().tolist() == [1, 2, 3]
    pd.testing.assert_frame_equal(window.proc_params, s21.proc_params)
    pd.testing.assert_frame_equal(window.meta, s21.meta)
    assert len(s21.rows("f > 6e9", "s21 < -0.5").data) == 12             # - all must hold - #
    assert len(s21.rows("f > 6e9 and s21 < -0.5").data) == 12


def test_rows_use_params_and_meta_per_emit(ds):
    s21 = ds["s21"]
    # - the dip (row 2) is 0.3 * |power| + trace deep; only it is deeper than half of that - #
    deep = s21.rows("s21 < -0.15 * np.abs(proc_power) - trace")
    assert len(deep.data) == 8
    assert deep.data.index.get_level_values("RecordRow").unique().tolist() == [2]
    assert len(s21.rows("trace == 1").data) == 4 * 5                     # - scalars are repeated - #
    for emit in s21.rows("trace == 1"):
        assert len(emit.data) == (5 if emit.meta["trace"] == 1 else 0)  # - emptied emits stay - #


def test_rows_chain_with_where_and_reduce(ds):
    sel = ds["s21"].where(proc_power=[-20]).rows("f >= 6e9")
    assert len(sel) == 4 and len(sel.data) == 4 * 3
    assert sel.reduce("min")["f"].tolist() == pytest.approx([6e9] * 4)
    assert ds["s21"].rows() is ds["s21"]


def test_rows_errors(ds):
    s21 = ds["s21"]
    with pytest.raises(TypeError, match="expression strings"):
        s21.rows(lambda d: d.f > 6e9)
    with pytest.raises(NameError, match="'nope'.*Available: data columns"):
        s21.rows("nope > 1")
    with pytest.raises(ValueError, match="True or False per row"):
        s21.rows("f * 2")


def test_where_subsets_the_data_too(ds):
    sel = ds["s21"].where(setpoint=0.05, trace=1)
    assert len(sel.data) == 10
    assert set(sel.data.index.droplevel("RecordRow")) == set(sel.keys)


def test_where_name_lookup_errors(ds):
    with pytest.raises(ValueError, match="both a procedure parameter and metadata"):
        ds["s21"].where(power=-20)
    with pytest.raises(KeyError, match="no parameter or metadata 'nope'"):
        ds["s21"].where(nope=1)
    assert len(ds["s21"].where(meta_power=-19.5)) == 4


def test_empty_selection_is_usable(ds):
    empty = ds["s21"].where(setpoint=0.3)
    assert empty.groups == [] and len(empty.data) == 0
    assert list(empty.emits()) == []
    assert len(empty.reduce("mean")) == 0
    assert empty.values("setpoint") == []


# - values --------------------------------------------------------------------------------------- #
def test_values(ds):
    s21 = ds["s21"]
    assert s21.values("setpoint") == [0.05, 0.1]
    assert s21.values("proc_power") == [-20.0, -10.0]
    assert s21.values("meta_power") == [-19.5, -9.5]
    assert s21.values("trace") == [0, 1]
    assert all(type(v) is int for v in s21.values("trace"))        # - plain Python values - #
    assert s21.where(setpoint=0.1).values("setpoint") == [0.1]
    assert len(s21.values("timestamp")) == 8


def test_values_name_lookup_errors(ds):
    with pytest.raises(ValueError, match="both a procedure parameter and metadata"):
        ds["s21"].values("power")
    with pytest.raises(KeyError, match="no parameter or metadata"):
        ds["s21"].values("nope")


def values_view(params, meta=None):
    """ A view with one single-row emit per entry of ``params``. """
    meta = meta or [{}] * len(params)
    keys = pd.MultiIndex.from_tuples([(0, i) for i in range(len(params))], names=EMIT_INDEX)
    data = pd.DataFrame({"x": np.zeros(len(params))},
                        index=pd.MultiIndex.from_tuples([(0, i, 0) for i in range(len(params))], names=DATA_INDEX))
    return RecordView("r", data, pd.DataFrame(params, index=keys), pd.DataFrame(meta, index=keys))


def test_values_are_sorted_and_merge_floats_like_where():
    view = values_view([{"p": 0.3}, {"p": 0.1 + 1e-12}, {"p": 0.1}, {"p": 0.2}, {"p": 0.1 + 1e-15}])
    values = view.values("p")
    assert values == [0.1, 0.2, 0.3]
    assert sum(len(view.where(p=v)) for v in values) == len(view)


def test_values_missing_and_strings():
    view = values_view([{"p": 1.0, "mode": "b"}, {"p": None, "mode": "a"}, {"p": 1.0, "mode": "b"}])
    assert view.values("p") == [1.0]
    with_nan = view.values("p", dropna=False)
    assert with_nan[0] == 1.0 and np.isnan(with_nan[1])
    assert view.values("mode") == ["a", "b"]


def test_values_unorderable_keep_first_seen_order():
    view = values_view([{"p": "x"}, {"p": 2}, {"p": "x"}])
    assert view.values("p") == ["x", 2]


# - emits and reduce ----------------------------------------------------------------------------- #
def test_emits(ds):
    emits = list(ds["s21"].group(1))
    assert len(emits) == 4
    first = emits[0]
    assert isinstance(first, Emit)
    assert first.key == (1, 0)
    assert first.params == {"setpoint": 0.1, "power": -20.0}
    assert first.meta["trace"] == 0
    assert first.timestamp == pd.Timestamp(at(42))
    assert first.data.index.name == "RecordRow"
    assert list(first.data.columns) == ["f", "s21"]
    assert len(first.data) == 5


def test_emits_include_emits_without_rows(tmp_path):
    write(HDFRecorder(tmp_path / "a.h5"), [(0, Record("r", {"x": [1.0, 2.0]}, index=0)),
                                           (0, Record("r", {"x": np.zeros(0)}, index=1))])
    emits = list(Dataset(tmp_path / "a.h5")["r"].emits())
    assert [len(e.data) for e in emits] == [2, 0]


def test_reduce_named_reduction(ds):
    table = ds["s21"].reduce("min")
    assert table.index.names == EMIT_INDEX
    assert table.loc[(0, 0), "s21"] == pytest.approx(-6.0)
    assert table.loc[(0, 1), "s21"] == pytest.approx(-7.0)
    assert "proc_setpoint" in table.columns


def test_reduce_scalar_and_dict(ds):
    s21 = ds["s21"]
    assert list(s21.reduce(lambda d: d.s21.min()).columns)[-1] == "value"
    assert list(s21.reduce(lambda d: d.s21.min(), name="depth").columns)[-1] == "depth"

    def depth(data):
        return data.s21.min()
    assert "depth" in s21.reduce(depth).columns

    table = s21.reduce(lambda d: {"f_min": d.f[d.s21.idxmin()], "depth": d.s21.min()})
    assert table["f_min"].tolist() == pytest.approx([6.0e9] * 8)
    with pytest.raises(ValueError, match="clash"):
        s21.reduce(lambda d: {"proc_power": 1})


# - align ---------------------------------------------------------------------------------------- #
def test_align_by_group(ds):
    s21 = ds["s21"].align(ds["fridge"])
    assert {"fridge_T5", "fridge_T1", "fridge_n"} <= set(s21.meta.columns)
    assert s21.meta.loc[(0, 3), "fridge_T5"] == pytest.approx(0.05 + 0.0015)
    assert s21.meta.loc[(1, 0), "fridge_T5"] == pytest.approx(0.1 + 0.0015)
    assert s21.meta["fridge_n"].tolist() == [4] * 8
    # - the aligned values work with where() and are passed to emits - #
    assert len(s21.where("fridge_T5 < 0.07")) == 4
    assert "fridge_T5" in next(s21.emits()).meta


def test_align_by_nearest(ds):
    s21 = ds["s21"].align(ds["fridge"], by="nearest", columns="T5", agg="mean")
    assert s21.meta.loc[(0, 2), "fridge_T5"] == pytest.approx(0.052)
    assert s21.meta["fridge_dt"].tolist() == [pd.Timedelta(seconds=-2)] * 8
    assert s21.meta["fridge_n"].tolist() == [1] * 8
    assert "fridge_T1" not in s21.meta.columns


def test_align_by_nearest_with_tolerance(ds):
    s21 = ds["s21"].align(ds["fridge"], by="nearest", tolerance=1)
    assert s21.meta["fridge_T5"].isna().all()
    assert s21.meta["fridge_n"].tolist() == [0] * 8


def test_align_by_window(ds):
    # - samples at t = 0, 10, ...; traces at t + 2. A window of 15 s before and none after - #
    s21 = ds["s21"].align(ds["fridge"], by="window", window=("15s", 0), agg="max", prefix="T_")
    assert s21.meta.loc[(0, 0), "T_n"] == 1
    assert s21.meta.loc[(0, 1), "T_n"] == 2
    assert s21.meta.loc[(0, 1), "T_T5"] == pytest.approx(0.051)
    # - symmetric window crossing into the next group - #
    s21 = ds["s21"].align(ds["fridge"], by="window", window=9)
    assert s21.meta.loc[(0, 3), "fridge_n"] == 2


@pytest.mark.parametrize("by, kwargs", [("group", {}), ("nearest", {}), ("window", {"window": 9})])
def test_align_with_a_list_of_aggregations(ds, by, kwargs):
    s21, fridge = ds["s21"], ds["fridge"]

    def spread(values):
        return values.max() - values.min()

    out = s21.align(fridge, by=by, agg=["mean", "std", spread], columns=["T5", "T1"], **kwargs)
    new = [c for c in out.meta.columns if c not in s21.meta.columns]
    expected = [f"fridge_{c}_{a}" for c in ["T5", "T1"] for a in ["mean", "std", "spread"]] + ["fridge_n"]
    if by == "nearest":
        expected.append("fridge_dt")
    assert new == expected
    # - the same numbers as one aggregation at a time - #
    for name, agg in [("mean", "mean"), ("std", "std"), ("spread", spread)]:
        single = s21.align(fridge, by=by, agg=agg, columns=["T5", "T1"], **kwargs).meta
        for column in ["T5", "T1"]:
            pd.testing.assert_series_equal(out.meta[f"fridge_{column}_{name}"], single[f"fridge_{column}"],
                                           check_names=False)
    assert out.meta["fridge_n"].dtype == np.int64


def test_align_list_without_matches(ds):
    s21 = ds["s21"].align(ds["fridge"], by="nearest", tolerance=1, agg=["mean", "max"], columns="T5")
    assert s21.meta[["fridge_T5_mean", "fridge_T5_max"]].isna().all().all()
    assert s21.meta["fridge_n"].tolist() == [0] * 8


def test_align_list_errors(ds):
    s21, fridge = ds["s21"], ds["fridge"]
    with pytest.raises(ValueError, match="cannot name"):
        s21.align(fridge, agg=["mean", lambda v: v.max()])
    with pytest.raises(ValueError, match="more than once"):
        s21.align(fridge, agg=["mean", "mean"])
    with pytest.raises(ValueError, match="empty list"):
        s21.align(fridge, agg=[])


def test_align_errors(ds):
    s21, fridge = ds["s21"], ds["fridge"]
    with pytest.raises(ValueError, match="needs a window"):
        s21.align(fridge, by="window")
    with pytest.raises(ValueError, match="by must be"):
        s21.align(fridge, by="time")
    with pytest.raises(KeyError, match="no columns"):
        s21.align(fridge, columns=["T9"])
    with pytest.raises(TypeError):
        s21.align(fridge.data)
    with pytest.raises(ValueError, match="already in the metadata"):
        s21.align(fridge).align(fridge)


def test_align_leaves_original_view_unchanged(ds):
    s21 = ds["s21"]
    s21.align(ds["fridge"])
    assert "fridge_T5" not in s21.meta.columns


# - end to end with a real sequence ---------------------------------------------------------------- #
class Sweep(plab.Procedure):
    setpoint = FloatParameter("Setpoint", units="K")
    power = FloatParameter("Power", units="dBm")
    n = IntegerParameter("Traces", default=2)

    def execute(self):
        self.emit("fridge", {"T": self.setpoint})
        for i in range(self.n):
            self.emit("trace", {"f": np.arange(3.0), "s": np.arange(3.0) * self.power}, meta={"i": i})


def test_end_to_end_sequence(tmp_path):
    proc = Sweep()
    hdf = HDFRecorder(tmp_path / "run.h5")
    proc.connect("fridge", hdf)
    proc.connect("trace", hdf)
    with hdf:
        run = plab.run_sequence(proc, plab.sweep(setpoint=[0.05, 0.1], power=[-20, -10]), group_by="setpoint")
    assert run.status is plab.Status.FINISHED

    ds = Dataset(tmp_path / "run.h5")
    traces = ds["trace"].align(ds["fridge"])
    assert traces.groups == [0, 1]
    table = traces.where(power=-10).reduce(lambda d: d.s.min(), name="smin")
    assert table["smin"].tolist() == [-20.0] * 4
    assert table["meta_fridge_T"].tolist() == pytest.approx([0.05, 0.05, 0.1, 0.1])


def test_record_view_from_read_hdf_tables(tmp_path):
    write(HDFRecorder(tmp_path / "a.h5"), sweep_records())
    tables = plab.read_hdf(tmp_path / "a.h5", "s21", join=False)
    view = RecordView("s21", tables["data"], tables["proc_params"], tables["meta"])
    assert len(view) == 8
