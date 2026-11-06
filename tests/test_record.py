import dataclasses
import datetime

import numpy as np
import pandas as pd
import pytest

from pylabtools import Record
from pylabtools.record import to_dataframe


# - conversion rules ---------------------------------------------------------------------------- #
def test_scalar_gives_single_row_named_after_record():
    df = to_dataframe(3.5, "temp")
    assert list(df.columns) == ["temp"]
    assert df.shape == (1, 1)
    assert df["temp"].iloc[0] == 3.5


def test_string_scalar():
    df = to_dataframe("on", "state")
    assert df["state"].tolist() == ["on"]


@pytest.mark.parametrize("data", [[1, 2, 3], (1, 2, 3), np.array([1, 2, 3])])
def test_1d_sequences_give_single_column(data):
    df = to_dataframe(data, "v")
    assert list(df.columns) == ["v"]
    assert df["v"].tolist() == [1, 2, 3]


def test_2d_array_columns_are_numbered():
    df = to_dataframe(np.arange(6).reshape(3, 2), "img")
    assert list(df.columns) == ["img_0", "img_1"]
    assert df["img_1"].tolist() == [1, 3, 5]


def test_3d_array_is_rejected():
    with pytest.raises(ValueError, match="at most 2"):
        to_dataframe(np.zeros((2, 2, 2)), "cube")


def test_dict_of_scalars_gives_one_row():
    df = to_dataframe({"a": 1, "b": "x"}, "r")
    assert df.to_dict("list") == {"a": [1], "b": ["x"]}


def test_dict_of_arrays_and_2d_values():
    df = to_dataframe({"t": [0, 1], "xy": [[1, 2], [3, 4]]}, "r")
    assert list(df.columns) == ["t", "xy_0", "xy_1"]
    assert df["xy_1"].tolist() == [2, 4]


def test_dict_with_unequal_lengths_is_rejected():
    with pytest.raises(ValueError, match="unequal lengths"):
        to_dataframe({"a": [1, 2], "b": [1, 2, 3]}, "r")


def test_empty_dict_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        to_dataframe({}, "r")


def test_dataframe_is_copied_and_reindexed():
    src = pd.DataFrame({"a": [1, 2]}, index=[10, 11])
    df = to_dataframe(src, "r")
    assert df.index.tolist() == [0, 1]
    src.loc[10, "a"] = 99
    assert df["a"].tolist() == [1, 2]


def test_series_uses_its_name_or_record_name():
    assert list(to_dataframe(pd.Series([1, 2], name="s"), "r").columns) == ["s"]
    assert list(to_dataframe(pd.Series([1, 2]), "r").columns) == ["r"]


# - Record behaviour ---------------------------------------------------------------------------- #
def test_record_fields_and_defaults():
    rec = Record("temp", {"T": [1.0, 2.0]}, proc_params={"setpoint": 4}, meta={"note": "x"},
                 run_id="run-1", index=3)
    assert rec.n_rows == 2
    assert rec.proc_params == {"setpoint": 4}
    assert rec.meta == {"note": "x"}
    assert rec.run_id == "run-1"
    assert rec.index == 3
    assert rec.timestamp.tzinfo is not None


def test_record_is_frozen():
    rec = Record("temp", 1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.data = None


def test_params_and_meta_are_read_only():
    rec = Record("temp", 1.0, proc_params={"a": 1}, meta={"b": 2})
    with pytest.raises(TypeError):
        rec.proc_params["a"] = 5
    with pytest.raises(TypeError):
        rec.meta["c"] = 5


def test_record_is_a_snapshot_of_mutable_inputs():
    """ Regression test for 0.9, where a shared mutable record let later emits overwrite earlier ones. """
    buffer = np.array([1.0, 2.0, 3.0])
    meta = {"calib": [1, 2]}
    params = {"vec": np.array([0.0, 1.0])}
    rec = Record("v", {"x": buffer}, proc_params=params, meta=meta)

    buffer[:] = 0
    meta["calib"].append(3)
    meta["new"] = 1
    params["vec"][0] = 42

    assert rec.data["x"].tolist() == [1.0, 2.0, 3.0]
    assert rec.meta == {"calib": [1, 2]}
    assert rec.proc_params["vec"].tolist() == [0.0, 1.0]


def test_none_params_and_meta_become_empty():
    rec = Record("v", 1, proc_params=None, meta=None)
    assert dict(rec.proc_params) == {} and dict(rec.meta) == {}


@pytest.mark.parametrize("kwargs, match", [
    ({"name": ""}, "non-empty"),
    ({"index": -1}, "non-negative"),
    ({"index": True}, "non-negative"),
    ({"timestamp": datetime.datetime(2026, 1, 1)}, "timezone-aware"),
    ({"meta": [1, 2]}, None),
])
def test_invalid_records_are_rejected(kwargs, match):
    args = {"name": "v", "data": 1, **kwargs}
    with pytest.raises((ValueError, TypeError), match=match):
        Record(**args)


def test_repr_is_compact():
    rec = Record("v", np.zeros((1000, 2)))
    text = repr(rec)
    assert "shape=(1000, 2)" in text and len(text) < 200
