""" Background tasks (@plab.every), record groups (group_by) and Procedure.sleep(). """
import threading
import time

import numpy as np
import pytest
from conftest import ListConsumer
from pymeasure.experiment import FloatParameter, IntegerParameter, Metadata

import pylabtools as plab
from pylabtools import HDFRecorder, Run, Status


class Sweep(plab.Procedure):
    """ A miniature temperature/power sweep with a background polling task. """

    setpoint = FloatParameter("Setpoint", units="K", default=0.01)
    power = FloatParameter("Power", units="dBm", default=-20)
    traces = IntegerParameter("Traces", default=2)
    step_time = FloatParameter("Step time", units="s", default=0.05)
    poll_interval = FloatParameter("Poll interval", units="s", default=0.01)

    def __init__(self, fail_task_after=None, task_delay=0.0, **kwargs):
        super().__init__(**kwargs)
        self.fail_task_after = fail_task_after
        self.task_delay = task_delay
        self.ticks = []
        self.calls = []

    @plab.every("poll_interval")
    def poll(self):
        self.ticks.append(time.monotonic())
        if self.fail_task_after is not None and len(self.ticks) > self.fail_task_after:
            raise RuntimeError("fridge read failed")
        if self.task_delay:
            time.sleep(self.task_delay)
        self.emit("fridge", {"T": self.setpoint + 0.001 * len(self.ticks)})

    def startup(self):
        self.calls.append("startup")

    def execute(self):
        self.calls.append("execute")
        for i in range(self.traces):
            self.emit("s21", {"f": np.arange(3.0), "s21": np.full(3, self.power)})
        self.sleep(self.step_time)

    def shutdown(self):
        self.calls.append("shutdown")


@pytest.fixture
def recs():
    s21, fridge = ListConsumer(), ListConsumer()
    with plab.running(s21, fridge):
        yield s21, fridge


def connect(proc, recs):
    s21, fridge = recs
    return proc.connect("s21", s21).connect("fridge", fridge)


# - @every ------------------------------------------------------------------------------------- #
def test_every_validation_and_discovery():
    with pytest.raises(TypeError, match="needs an interval"):
        @plab.every
        def f(self):
            pass
    for bad in (0, -1, True):
        with pytest.raises(ValueError):
            plab.every(bad)
    with pytest.raises(TypeError):
        plab.every([1])
    assert Sweep.tasks() == {"poll": "poll_interval"}


def test_task_interval_must_name_a_parameter():
    class Bad(plab.Procedure):
        @plab.every("not_a_parameter")
        def poll(self):
            pass

    with pytest.raises(NameError, match="not a parameter"):
        Run(Bad())


def test_task_runs_continuously_across_sequence_steps(recs):
    proc = connect(Sweep(step_time=0.1, poll_interval=0.01), recs)
    run = plab.run_sequence(proc, plab.sweep(power=[-30, -20, -10]))
    assert run.status is Status.FINISHED
    gaps = np.diff(proc.ticks)
    assert len(proc.ticks) >= 15
    assert gaps.max() < 0.08  # - never restarted between steps - #
    # - task records carry the parameters of the step active when they were emitted - #
    _, fridge = recs
    assert {r.proc_params["power"] for r in fridge.records} == {-30, -20, -10}


def test_task_starts_after_parameters_are_set_and_stops_after_last_shutdown(recs):
    proc = connect(Sweep(poll_interval=0.005), recs)
    run = plab.run(proc, power=-5.0)
    n_ticks = len(proc.ticks)
    time.sleep(0.05)
    assert len(proc.ticks) == n_ticks  # - stopped - #
    _, fridge = recs
    assert dict(fridge.records[0].proc_params)["power"] == -5.0
    assert all(r.timestamp <= run.finished_at for r in fridge.records)


def test_failing_task_stops_and_fails_the_run(recs):
    proc = connect(Sweep(fail_task_after=3, step_time=30, poll_interval=0.01), recs)
    t = time.monotonic()
    run = plab.start(proc)
    run.wait(10)
    assert time.monotonic() - t < 5  # - sleep() was interrupted - #
    assert run.status is Status.FAILED
    assert "fridge read failed" in str(run.exception)
    assert proc.calls[-1] == "shutdown"


def test_task_emitting_unconnected_record_fails_run(recs):
    s21, _ = recs
    proc = Sweep(step_time=5).connect("s21", s21)
    run = plab.start(proc)
    run.wait(10)
    assert run.status is Status.FAILED
    assert isinstance(run.exception, KeyError)


def test_non_positive_interval_parameter_fails_run(recs):
    proc = connect(Sweep(poll_interval=0), recs)
    run = plab.start(proc)
    run.wait(10)
    assert run.status is Status.FAILED
    assert "positive number of seconds" in str(run.exception)


def test_slow_task_skips_ticks_instead_of_bunching(recs):
    proc = connect(Sweep(task_delay=0.05, poll_interval=0.02, step_time=0.4), recs)
    plab.run(proc)
    gaps = np.diff(proc.ticks)
    assert gaps.min() >= 0.045  # - no back-to-back catch-up calls - #


def test_run_without_tasks_starts_no_threads(consumer):
    from procedures import Counter
    before = threading.active_count()
    plab.run(Counter().connect("counts", consumer))
    assert threading.active_count() == before


# - sleep() -------------------------------------------------------------------------------------- #
def test_sleep_waits_and_returns_true(recs):
    result = {}

    class Sleeper(Sweep):
        def execute(self):
            t = time.monotonic()
            result["ok"] = self.sleep(0.1)
            result["dt"] = time.monotonic() - t

    plab.run(connect(Sleeper(), recs))
    assert result["ok"] is True and result["dt"] >= 0.09


def test_sleep_returns_false_promptly_on_stop(recs):
    result = {}

    class Sleeper(Sweep):
        def execute(self):
            t = time.monotonic()
            result["ok"] = self.sleep(30)
            result["dt"] = time.monotonic() - t

    run = plab.start(connect(Sleeper(), recs))
    time.sleep(0.1)
    run.stop()
    run.wait(5)
    assert run.status is Status.ABORTED
    assert result["ok"] is False and result["dt"] < 2


def test_sleep_outside_a_run():
    assert Sweep().sleep(0.01) is True


# - group_by ------------------------------------------------------------------------------------- #
def test_default_is_one_group_per_run(recs):
    run = plab.run_sequence(connect(Sweep(), recs), plab.sweep(setpoint=[0.01, 0.02]))
    s21, _ = recs
    assert {r.group for r in s21.records} == {run.run_id}
    assert [r.index for r in s21.records] == [0, 1, 2, 3]


def test_group_by_starts_a_group_per_setpoint_and_resets_index(recs):
    proc = connect(Sweep(traces=2), recs)
    steps = plab.sweep(setpoint=[0.01, 0.02], power=[-30, -20, -10])
    run = plab.run_sequence(proc, steps, group_by="setpoint")
    s21, fridge = recs
    assert run.status is Status.FINISHED and run.group == 1

    groups = sorted({r.group for r in s21.records})
    assert len(groups) == 2
    for group, setpoint in zip(groups, (0.01, 0.02)):
        traces = [r for r in s21.records if r.group == group]
        assert {r.proc_params["setpoint"] for r in traces} == {setpoint}
        assert [r.index for r in traces] == list(range(6))  # - 3 powers x 2 traces - #
        temps = [r for r in fridge.records if r.group == group]
        assert temps and {r.proc_params["setpoint"] for r in temps} == {setpoint}
        assert [r.index for r in temps] == list(range(len(temps)))
    assert [g for g, _ in s21.group_ends] == groups


def test_group_by_several_parameters(recs):
    steps = plab.sweep(setpoint=[0.01, 0.02], power=[-30, -20], traces=[1, 2])
    plab.run_sequence(connect(Sweep(), recs), steps, group_by=["setpoint", "power"])
    s21, _ = recs
    assert len({r.group for r in s21.records}) == 4


def test_returning_to_an_earlier_value_starts_a_new_group(recs):
    steps = [{"setpoint": 0.01}, {"setpoint": 0.02}, {"setpoint": 0.01}]
    plab.run_sequence(connect(Sweep(), recs), steps, group_by="setpoint")
    s21, _ = recs
    assert len({r.group for r in s21.records}) == 3


def test_group_by_unknown_parameter():
    with pytest.raises(NameError, match="group_by: unknown parameter"):
        plab.start_sequence(Sweep(), [{}], group_by="temperature")


def test_temperature_power_sweep_into_hdf(tmp_path):
    """ The motivating experiment: traces and fridge samples share RecordGroup per setpoint. """
    hdf = HDFRecorder(tmp_path / "sweep.h5")
    proc = Sweep(traces=2, step_time=0.05, poll_interval=0.01).connect("s21", hdf).connect("fridge", hdf)
    setpoints = [0.01, 0.02, 0.05]
    with plab.running(hdf):
        plab.run_sequence(proc, plab.sweep(setpoint=setpoints, power=[-30, -20]), group_by="setpoint")
        plab.run(proc, setpoint=0.1)  # - a later run in the same file continues the numbering - #

    s21 = plab.read_hdf(hdf.path, "s21")
    fridge = plab.read_hdf(hdf.path, "fridge")
    for group, setpoint in enumerate(setpoints + [0.1]):
        assert set(s21.loc[group]["proc_setpoint"]) == {setpoint}
        assert set(fridge.loc[group]["proc_setpoint"]) == {setpoint}
        assert s21.loc[group].index.get_level_values("RecordGroupInd").min() == 0
    assert sorted(set(s21.index.get_level_values("RecordGroup"))) == [0, 1, 2, 3]


# - metadata during startup -------------------------------------------------------------------- #
def test_records_emitted_during_startup_include_metadata_columns(tmp_path):
    """ Regression: emits before metadata evaluation lacked its columns -> SchemaError in HDF. """
    class EarlyEmit(plab.Procedure):
        level = FloatParameter("Level", default=1.0)
        reading = Metadata("Reading", fget="read")

        def read(self):
            return 4.2

        def startup(self):
            self.emit("r", {"x": 1.0})

        def execute(self):
            self.emit("r", {"x": 2.0})

    hdf = HDFRecorder(tmp_path / "early.h5")
    proc = EarlyEmit().connect("r", hdf)
    with plab.running(hdf):
        run = plab.run(proc)
    assert run.status is Status.FINISHED
    assert plab.read_hdf(hdf.path)["meta_reading"].tolist() == [4.2, 4.2]
