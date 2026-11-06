import numpy as np
import pandas as pd
import pytest
from procedures import Counter
from pymeasure.experiment import Parameter

import pylabtools as plab
from pylabtools import CSVRecorder, HDFRecorder, Procedure, Record, SchemaError, Status
from pylabtools.recorders import DATA_INDEX, make_tables


class Emitter(Procedure):
    """ Emits each item of ``self.items`` (set before the run) to record ``self.record``. """

    label = Parameter("Label", default="a")

    def __init__(self, items=(), record="r", meta=None, **kwargs):
        super().__init__(**kwargs)
        self.items, self.record, self.extra_meta = list(items), record, meta

    def execute(self):
        for item in self.items:
            self.emit(self.record, item, meta=self.extra_meta)


def record_with(recorder, proc, **params):
    """ Run ``proc`` once into ``recorder`` and return the run. """
    with recorder:
        run = plab.start(proc, **params)
        run.wait(20)
    return run


# - table construction --------------------------------------------------------------------------- #
def test_make_tables_columns_and_indices():
    rec = Record("v", {"x": [1.0, 2.0]}, proc_params={"gain": 2.0}, meta={"note": "n"}, index=4)
    tables = make_tables(rec, group=7)
    assert list(tables.data.columns) == DATA_INDEX + ["x"]
    assert tables.data[DATA_INDEX].values.tolist() == [[7, 4, 0], [7, 4, 1]]
    assert list(tables.proc_params.columns) == ["RecordGroup", "RecordGroupInd", "gain"]
    assert list(tables.meta.columns) == ["RecordGroup", "RecordGroupInd", "timestamp", "note"]
    assert tables.meta["timestamp"].iloc[0] == rec.timestamp


def test_make_tables_stores_odd_values():
    rec = Record("v", 1.0, meta={"none": None, "arr": np.array([1, 2]), "d": {"a": 1}})
    meta = make_tables(rec, 0).meta
    assert np.isnan(meta["none"].iloc[0])
    assert meta["arr"].iloc[0] == "[1, 2]"
    assert meta["d"].iloc[0] == "{'a': 1}"


@pytest.mark.parametrize("kwargs", [
    {"data": {"RecordRow": [1]}},
    {"data": 1, "proc_params": {"RecordGroup": 1}},
    {"data": 1, "meta": {"timestamp": 1}},
])
def test_reserved_names_are_rejected(kwargs):
    with pytest.raises(ValueError, match="reserved"):
        make_tables(Record("v", **kwargs), 0)


# - HDF5 ------------------------------------------------------------------------------------------- #
@pytest.mark.parametrize("keep_open", [False, True])
def test_hdf_round_trip(tmp_path, keep_open):
    path = tmp_path / "run.h5"
    proc = Counter(samples=3, gain=2.0)
    hdf = HDFRecorder(path, keep_open=keep_open)
    proc.connect("counts", hdf)
    run = record_with(hdf, proc)
    assert run.status is Status.FINISHED

    df = plab.read_hdf(path)
    assert df.index.names == DATA_INDEX
    assert df.index.tolist() == [(0, 0, 0), (0, 1, 0), (0, 2, 0)]
    assert df["v"].tolist() == [0.0, 2.0, 4.0]
    assert df["proc_gain"].tolist() == [2.0] * 3
    assert df["proc_samples"].tolist() == [3] * 3
    assert str(df["meta_timestamp"].dtype).endswith("UTC]")

    tables = plab.read_hdf(path, join=False)
    assert set(tables) == {"data", "proc_params", "meta"}
    assert tables["proc_params"].index.names == ["RecordGroup", "RecordGroupInd"]


def test_hdf_record_groups_continue_across_runs_and_recorders(tmp_path):
    path = tmp_path / "run.h5"
    proc = Counter(samples=2)
    hdf = HDFRecorder(path)
    proc.connect("counts", hdf)
    with hdf:
        plab.run(proc)
        plab.run(proc, gain=3.0)
    # - a new recorder on the same file continues the numbering - #
    hdf2 = HDFRecorder(path)
    proc.disconnect()
    proc.connect("counts", hdf2)
    record_with(hdf2, proc)

    df = plab.read_hdf(path)
    assert sorted(set(df.index.get_level_values("RecordGroup"))) == [0, 1, 2]
    assert plab.read_hdf(path, groups=1)["proc_gain"].unique().tolist() == [3.0]
    assert sorted(set(plab.read_hdf(path, groups=[0, 2]).index.get_level_values(0))) == [0, 2]


def test_hdf_sequence_is_one_record_group(tmp_path):
    path = tmp_path / "seq.h5"
    hdf = HDFRecorder(path)
    proc = Counter(samples=2).connect("counts", hdf)
    with hdf:
        plab.run_sequence(proc, plab.sweep(gain=[1.0, 2.0]))
    df = plab.read_hdf(path)
    assert set(df.index.get_level_values("RecordGroup")) == {0}
    assert df.index.get_level_values("RecordGroupInd").tolist() == [0, 1, 2, 3]
    assert df["proc_gain"].tolist() == [1.0, 1.0, 2.0, 2.0]


def test_hdf_file_is_readable_while_recording(tmp_path):
    path = tmp_path / "live.h5"
    hdf = HDFRecorder(path)
    proc = Counter(samples=2).connect("counts", hdf)
    with hdf:
        plab.run(proc)
        hdf.join_queue()
        assert len(plab.read_hdf(path)) == 2  # - closed after each write by default - #


def test_hdf_multiple_records_and_data_shapes(tmp_path):
    class Mixed(Procedure):
        def execute(self):
            self.emit("trace", {"f": np.arange(5.0), "s21": np.ones((5, 2))})
            self.emit("status", {"state": "locked", "ok": True})
            self.emit("empty", pd.DataFrame({"x": pd.Series([], dtype=float)}))

    path = tmp_path / "mixed.h5"
    hdf = HDFRecorder(path)
    proc = Mixed().connect("trace", hdf).connect("status", hdf).connect("empty", hdf)
    assert record_with(hdf, proc).status is Status.FINISHED

    assert plab.hdf_records(path) == ["empty", "status", "trace"]
    with pytest.raises(ValueError, match="pass record="):
        plab.read_hdf(path)
    trace = plab.read_hdf(path, "trace")
    assert list(trace.columns[:3]) == ["f", "s21_0", "s21_1"]
    assert len(trace) == 5
    status = plab.read_hdf(path, "status")
    assert status["state"].tolist() == ["locked"] and status["ok"].tolist() == [True]
    assert len(plab.read_hdf(path, "empty")) == 0
    assert len(plab.read_hdf(path, "empty", join=False)["meta"]) == 1
    with pytest.raises(KeyError, match="no record 'missing'"):
        plab.read_hdf(path, "missing")


def test_hdf_path_suffix_and_parent_dirs(tmp_path):
    hdf = HDFRecorder(tmp_path / "a" / "b" / "run")
    assert hdf.path.name == "run.h5"
    record_with(hdf, Counter(samples=1).connect("counts", hdf))
    assert hdf.path.exists()


def test_hdf_schema_mismatch_fails_run_and_preserves_file(tmp_path):
    path = tmp_path / "s.h5"
    hdf = HDFRecorder(path)
    proc = Emitter(items=[{"x": 1.0}]).connect("r", hdf)
    record_with(hdf, proc)

    proc.items = [{"x": 1.0, "y": 2.0}]
    run = record_with(hdf, proc)
    assert run.status is Status.FAILED
    assert isinstance(run.exception.__cause__, SchemaError)
    assert "extra ['y']" in str(run.exception.__cause__)
    df = plab.read_hdf(path)
    assert len(df) == 1 and list(df.columns) == ["x", "proc_label", "meta_timestamp"]


def test_hdf_int_into_float_column_is_widened(tmp_path):
    path = tmp_path / "w.h5"
    hdf = HDFRecorder(path)
    proc = Emitter(items=[{"x": 1.5}, {"x": 2}, {"x": True}]).connect("r", hdf)
    assert record_with(hdf, proc).status is Status.FINISHED
    assert plab.read_hdf(path)["x"].tolist() == [1.5, 2.0, 1.0]


def test_hdf_incompatible_type_is_reported(tmp_path):
    hdf = HDFRecorder(tmp_path / "t.h5")
    proc = Emitter(items=[{"x": 1.5}, {"x": "high"}]).connect("r", hdf)
    run = record_with(hdf, proc)
    assert run.status is Status.FAILED
    assert "stored as float64" in str(run.exception.__cause__)


def test_hdf_string_width(tmp_path):
    hdf = HDFRecorder(tmp_path / "narrow.h5", string_width=4)
    proc = Emitter(items=[{"s": "ab"}, {"s": "much longer"}]).connect("r", hdf)
    run = record_with(hdf, proc)
    assert run.status is Status.FAILED
    assert "string_width" in str(run.exception.__cause__)

    wide = HDFRecorder(tmp_path / "wide.h5", string_width=32)
    proc.disconnect()
    proc.connect("r", wide)
    assert record_with(wide, proc).status is Status.FINISHED


def test_hdf_invalid_record_name(tmp_path):
    hdf = HDFRecorder(tmp_path / "n.h5")
    run = record_with(hdf, Emitter(items=[1], record="bad name").connect("bad name", hdf))
    assert run.status is Status.FAILED
    assert "cannot be used as an HDF5 group name" in str(run.exception.__cause__)


# - CSV --------------------------------------------------------------------------------------------- #
def test_csv_round_trip_and_groups(tmp_path):
    out = tmp_path / "csv_out"
    csv_rec = CSVRecorder(out)
    proc = Counter(samples=2).connect("counts", csv_rec)
    with csv_rec:
        plab.run(proc)
        plab.run(proc, gain=4.0)
    csv2 = CSVRecorder(out)
    proc.disconnect()
    proc.connect("counts", csv2)
    record_with(csv2, proc)

    df = plab.read_csv(out, "counts")
    assert df.index.names == DATA_INDEX
    assert sorted(set(df.index.get_level_values(0))) == [0, 1, 2]
    assert df.loc[1]["proc_gain"].unique().tolist() == [4.0]
    assert str(df["meta_timestamp"].dtype).endswith("UTC]")


def test_csv_header_mismatch_is_reported(tmp_path):
    rec = CSVRecorder(tmp_path)
    proc = Emitter(items=[{"x": 1}]).connect("r", rec)
    record_with(rec, proc)
    proc.items = [{"z": 1}]
    run = record_with(rec, proc)
    assert run.status is Status.FAILED
    assert isinstance(run.exception.__cause__, SchemaError)
    assert len(plab.read_csv(tmp_path, "r")) == 1


def test_hdf_and_csv_store_the_same_data(tmp_path):
    hdf, csv_rec = HDFRecorder(tmp_path / "d.h5"), CSVRecorder(tmp_path / "csv")
    proc = Emitter(items=[{"x": [1.0, 2.0], "n": [1, 2]}, {"x": [3.0, 4.0], "n": [3, 4]}],
                   meta={"note": "hello"}).connect("r", hdf, csv_rec)
    with hdf, csv_rec:
        plab.run_sequence(proc, plab.sweep(label=["a", "b"]))
    from_hdf = plab.read_hdf(hdf.path, "r")
    from_csv = plab.read_csv(csv_rec.directory, "r")
    pd.testing.assert_frame_equal(from_hdf, from_csv, check_dtype=False)


def test_negative_groups_count_from_the_latest_run(tmp_path):
    hdf, csv_rec = HDFRecorder(tmp_path / "g.h5"), CSVRecorder(tmp_path / "csv")
    proc = Counter(samples=1).connect("counts", hdf, csv_rec)
    with hdf, csv_rec:
        for gain in (1.0, 2.0, 3.0):
            plab.run(proc, gain=gain)
    assert plab.read_hdf(hdf.path, groups=-1)["proc_gain"].tolist() == [3.0]
    assert plab.read_hdf(hdf.path, groups=[-3, -1])["proc_gain"].tolist() == [1.0, 3.0]
    assert plab.read_csv(csv_rec.directory, "counts", groups=-2)["proc_gain"].tolist() == [2.0]
    with pytest.raises(IndexError, match="out of range"):
        plab.read_hdf(hdf.path, groups=-4)


def test_hdf_stores_datetimes_with_nanosecond_resolution(tmp_path):
    """ pandas 3 would store microseconds, which pandas 2 cannot append to; always write ns. """
    hdf = HDFRecorder(tmp_path / "ns.h5")
    when = pd.Timestamp("2026-11-05 12:00:00.123456", tz="UTC").to_pydatetime()
    proc = Emitter(items=[{"x": 1.0}], meta={"started": when}).connect("r", hdf)
    record_with(hdf, proc)
    with pd.HDFStore(hdf.path, mode="r") as store:
        meta = store.select("r/meta")
    assert str(meta["timestamp"].dtype) == "datetime64[ns, UTC]"
    assert str(meta["started"].dtype) == "datetime64[ns, UTC]"


@pytest.mark.skipif(int(pd.__version__.split(".")[0]) < 3,
                    reason="non-nanosecond datetime tables come from pandas 3, which pandas 2 cannot read "
                           "at all; pandas 2 also cannot write them to set up this test")
@pytest.mark.parametrize("unit", ["us", "ms", "s"])
def test_hdf_appends_to_files_with_other_datetime_resolution(tmp_path, unit):
    """ Regression: a file written with another pandas version (different datetime resolution)
    failed with "Cannot serialize the column [timestamp] ..." on append. """
    path = tmp_path / "other.h5"
    hdf = HDFRecorder(path)
    proc = Emitter(items=[{"x": 1.0}]).connect("r", hdf)
    record_with(hdf, proc)

    # - rewrite the meta table as another pandas version would have stored it - #
    with pd.HDFStore(path, mode="a") as store:
        meta = store.select("r/meta")
        meta["timestamp"] = meta["timestamp"].astype(f"datetime64[{unit}, UTC]")
        store.remove("r/meta")
        store.append("r/meta", meta, format="table", data_columns=["RecordGroup", "RecordGroupInd"], index=False)

    hdf2 = HDFRecorder(path)
    proc.disconnect()
    proc.connect("r", hdf2)
    assert record_with(hdf2, proc).status is Status.FINISHED
    df = plab.read_hdf(path)
    assert len(df) == 2 and df["meta_timestamp"].notna().all()
