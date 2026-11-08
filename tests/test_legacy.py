""" pylabtools.legacy.convert_hdf: 0.9 HDF5 files -> 1.0 files. """
import datetime
import hashlib

import numpy as np
import pandas as pd
import pytest

import pylabtools as plab
from pylabtools.analysis import Dataset
from pylabtools.legacy import convert_hdf


def write_legacy(path, emits, prefix=""):
    """ Write ``emits`` like the 0.9 HDFRecorder: one append per emit to /data, /proc_params, /meta,
    each indexed by a MultiIndex of "%06i" strings. ``emits`` is a list of
    ``(group, index, data dict, proc_params dict, meta dict or None)``. """
    base = f"/{prefix}" if prefix else ""
    with pd.HDFStore(path, mode="a") as store:
        for group, index, data, proc_params, meta in emits:
            data = pd.DataFrame(data)
            rg, rgi = "%06i" % group, "%06i" % index
            data.index = pd.MultiIndex.from_product([[rg], [rgi], ["%06i" % i for i in range(len(data))]],
                                                    names=["RecordGroup", "RecordGroupInd", "RecordRow"])
            emit_index = pd.MultiIndex.from_tuples([(rg, rgi)], names=["RecordGroup", "RecordGroupInd"])
            store.append(f"{base}/data", data)
            store.append(f"{base}/proc_params", pd.DataFrame(proc_params, index=emit_index))
            if meta is not None:
                store.append(f"{base}/meta", pd.DataFrame(meta, index=emit_index))


def sweep_emits(timestamp=lambda g, i: f"20260928_{9 + g:02d}{i}000"):
    """ Two RecordGroups (runs) of three traces each, like a 0.9 VNA temperature sweep. """
    f = np.linspace(5e9, 6e9, 4)
    emits = []
    for group, temp in enumerate([0.02, 0.1]):
        for index in range(3):
            meta = {"power": [20.0], "s_param": ["S21"], "temperature": [temp + 0.001 * index]}
            if timestamp is not None:
                meta["timestamp"] = [timestamp(group, index)]
            emits.append((group, index, {"frequency": f, "I": f * 0 + temp + index, "Q": f * 0 - index},
                          {"power": [20.0], "traces": [3], "average_in_viewer": [True], "s_param": [21]}, meta))
    return emits


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / "legacy_0p9.h5"
    write_legacy(path, sweep_emits())
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# - basic conversion ----------------------------------------------------------------------------- #
def test_convert_top_level_tables(legacy, tmp_path):
    before = digest(legacy)
    assert convert_hdf(legacy, tmp_path / "new") == ["record"]
    assert digest(legacy) == before                                   # - source untouched - #

    out = tmp_path / "new.h5"
    assert plab.hdf_records(out) == ["record"]
    view = Dataset(out)["record"]
    assert view.groups == [0, 1] and len(view) == 6 and len(view.data) == 24
    assert view.keys.tolist() == [(g, i) for g in (0, 1) for i in range(3)]
    assert view.columns == ["frequency", "I", "Q"]
    assert view.params == ["power", "traces", "average_in_viewer", "s_param"]
    assert list(view.meta.columns) == ["power", "s_param", "temperature", "timestamp"]
    assert view.data.loc[(1, 2), "I"].tolist() == pytest.approx([2.1] * 4)
    assert view.where(temperature=0.101).keys.tolist() == [(1, 1)]


def test_indices_are_integers(legacy, tmp_path):
    convert_hdf(legacy, tmp_path / "new.h5")
    with pd.HDFStore(tmp_path / "new.h5", mode="r") as store:
        for kind in ("data", "proc_params", "meta"):
            table = store.select(f"/record/{kind}")
            assert all(str(table[c].dtype) == "int64" for c in ("RecordGroup", "RecordGroupInd"))
        assert str(store.select("/record/data")["RecordRow"].dtype) == "int64"
    assert plab.read_hdf(tmp_path / "new.h5", groups=-1).index.get_level_values(0).unique().tolist() == [1]


def test_record_argument_names_the_output(legacy, tmp_path):
    assert convert_hdf(legacy, tmp_path / "new.h5", record="s21") == ["s21"]
    assert plab.hdf_records(tmp_path / "new.h5") == ["s21"]


# - timestamps ----------------------------------------------------------------------------------- #
def test_string_timestamps_become_utc(legacy, tmp_path):
    convert_hdf(legacy, tmp_path / "new.h5")
    ts = Dataset(tmp_path / "new.h5")["record"].meta["timestamp"]
    assert str(ts.dtype) == "datetime64[ns, UTC]"
    # - 2026-09-28 09:00:00 in Los Angeles is PDT (UTC-7) - #
    assert ts.iloc[0] == pd.Timestamp("2026-09-28 16:00:00", tz="UTC")
    assert ts.iloc[4] == pd.Timestamp("2026-09-28 17:10:00", tz="UTC")


def test_timezone_argument(legacy, tmp_path):
    convert_hdf(legacy, tmp_path / "new.h5", timezone="Europe/Berlin")
    ts = Dataset(tmp_path / "new.h5")["record"].meta["timestamp"]
    assert ts.iloc[0] == pd.Timestamp("2026-09-28 07:00:00", tz="UTC")          # - CEST, UTC+2 - #


def test_naive_datetime_timestamps(tmp_path):
    # - the 0.9 default: meta['timestamp'] = datetime.datetime.now() - #
    start = datetime.datetime(2026, 1, 15, 12, 0, 0)
    write_legacy(tmp_path / "old.h5", sweep_emits(lambda g, i: start + datetime.timedelta(minutes=10 * g + i)))
    convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    ts = Dataset(tmp_path / "new.h5")["record"].meta["timestamp"]
    assert ts.iloc[0] == pd.Timestamp("2026-01-15 20:00:00", tz="UTC")          # - PST, UTC-8 - #


def test_iso_string_timestamps(tmp_path):
    write_legacy(tmp_path / "old.h5", sweep_emits(lambda g, i: f"2026-01-15 12:0{g}:0{i}.250000"))
    convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    ts = Dataset(tmp_path / "new.h5")["record"].meta["timestamp"]
    assert ts.iloc[1] == pd.Timestamp("2026-01-15 20:00:01.25", tz="UTC")


def test_timestamps_across_the_autumn_clock_change(tmp_path):
    # - 01:30 happens twice on 2026-11-01 in Los Angeles; in time order the two are told apart - #
    stamps = ["20261101_005000", "20261101_013000", "20261101_013000", "20261101_020000"]
    emits = [(0, i, {"x": [1.0]}, {"p": [1.0]}, {"timestamp": [s]}) for i, s in enumerate(stamps)]
    write_legacy(tmp_path / "old.h5", emits)
    convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    ts = Dataset(tmp_path / "new.h5")["record"].meta["timestamp"]
    # - 00:50 PDT, 01:30 PDT, 01:30 PST, 02:00 PST - #
    assert ts.diff().dt.total_seconds().tolist()[1:] == [2400.0, 3600.0, 1800.0]


def test_no_timestamp_column(tmp_path):
    write_legacy(tmp_path / "old.h5", sweep_emits(timestamp=None))
    convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    view = Dataset(tmp_path / "new.h5")["record"]
    assert "timestamp" not in view.meta.columns
    assert list(view.meta.columns) == ["power", "s_param", "temperature"]


def test_no_meta_table(tmp_path):
    emits = [(0, i, {"x": [1.0, 2.0]}, {"p": [float(i)]}, None) for i in range(2)]
    write_legacy(tmp_path / "old.h5", emits)
    convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    view = Dataset(tmp_path / "new.h5")["record"]
    assert len(view) == 2 and list(view.meta.columns) == []


def test_unparseable_timestamp_writes_nothing(tmp_path):
    write_legacy(tmp_path / "old.h5", sweep_emits(lambda g, i: "yesterday"))
    with pytest.raises(ValueError, match="cannot parse timestamp 'yesterday'"):
        convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")
    assert not (tmp_path / "new.h5").exists()


# - record_name ---------------------------------------------------------------------------------- #
@pytest.fixture
def processed(tmp_path):
    """ A file whose 0.9 tables were moved under base/, next to other analysis groups. """
    path = tmp_path / "processed.h5"
    write_legacy(path, sweep_emits(), prefix="base")
    write_legacy(path, sweep_emits()[:2], prefix="avg")
    with pd.HDFStore(path, mode="a") as store:
        store.append("/base_fit/res_params", pd.DataFrame({"Qi": [1e4, 2e4]}))
        store.append("/avg/res_params", pd.DataFrame({"Qi": [1e4]}))
    return path


def test_record_name_string(processed, tmp_path):
    assert convert_hdf(processed, tmp_path / "new.h5", record="ignored", record_name="base") == ["base"]
    assert plab.hdf_records(tmp_path / "new.h5") == ["base"]
    with pd.HDFStore(tmp_path / "new.h5", mode="r") as store:
        assert sorted(store.keys()) == ["/base/data", "/base/meta", "/base/proc_params"]
    assert len(Dataset(tmp_path / "new.h5")["base"]) == 6


def test_record_name_list(processed, tmp_path):
    assert convert_hdf(processed, tmp_path / "new.h5", record_name=["base", "/avg/"]) == ["base", "avg"]
    ds = Dataset(tmp_path / "new.h5")
    assert ds.records == ["avg", "base"]
    assert len(ds["avg"]) == 2 and len(ds["base"]) == 6
    with pd.HDFStore(tmp_path / "new.h5", mode="r") as store:
        assert "/avg/res_params" not in store.keys()                # - other tables are ignored - #


def test_record_name_errors(processed, tmp_path):
    with pytest.raises(KeyError, match=r"No 0.9 tables at /nope.*\['/avg', '/base'\]"):
        convert_hdf(processed, tmp_path / "new.h5", record_name="nope")
    with pytest.raises(KeyError, match="the top level"):
        convert_hdf(processed, tmp_path / "new.h5")
    with pytest.raises(ValueError, match="more than once"):
        convert_hdf(processed, tmp_path / "new.h5", record_name=["base", "base"])
    with pytest.raises(ValueError, match="empty list"):
        convert_hdf(processed, tmp_path / "new.h5", record_name=[])
    assert not (tmp_path / "new.h5").exists()


# - files ---------------------------------------------------------------------------------------- #
def test_existing_destination(legacy, tmp_path):
    out = tmp_path / "new.h5"
    out.write_bytes(b"keep me")
    with pytest.raises(FileExistsError, match="overwrite=True"):
        convert_hdf(legacy, out)
    assert out.read_bytes() == b"keep me"
    convert_hdf(legacy, out, overwrite=True)
    assert plab.hdf_records(out) == ["record"]


def test_destination_must_differ_from_source(legacy):
    with pytest.raises(ValueError, match="different file"):
        convert_hdf(legacy, legacy, overwrite=True)


def test_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        convert_hdf(tmp_path / "nope.h5", tmp_path / "new.h5")


def test_not_a_legacy_table(tmp_path):
    with pd.HDFStore(tmp_path / "old.h5", mode="w") as store:
        store.append("/proc_params", pd.DataFrame({"p": [1.0]}))
    with pytest.raises(ValueError, match="not a PyLabTools 0.9 table"):
        convert_hdf(tmp_path / "old.h5", tmp_path / "new.h5")


def test_converted_file_can_be_extended(legacy, tmp_path):
    """ A recorder pointed at a converted file continues its RecordGroup numbering. """
    out = tmp_path / "new.h5"
    convert_hdf(legacy, out)
    recorder = plab.HDFRecorder(out)
    recorder.on_start()
    assert recorder.last_record_group() == 1
    recorder.on_stop()


def test_plab_legacy_is_importable():
    assert plab.legacy.convert_hdf is convert_hdf
