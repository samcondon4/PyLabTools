import threading
import time

import pytest
from conftest import ListConsumer
from procedures import BufferReuse, Counter, NoDefault, Waiter, WithMetadata
from pymeasure.experiment import Procedure as PyMeasureProcedure

import pylabtools as plab
from pylabtools import ConsumerError, Run, Status


# - basic runs ---------------------------------------------------------------------------------- #
def test_run_emits_records_with_params_run_id_and_index(consumer):
    proc = Counter(samples=3, gain=2.0).connect("counts", consumer)
    run = plab.run(proc)
    consumer.join_queue()

    assert run.status is Status.FINISHED and run.done
    assert proc.calls == ["startup", "execute", "shutdown"]
    assert [r.index for r in consumer.records] == [0, 1, 2]
    assert {r.run_id for r in consumer.records} == {run.run_id}
    assert [r.data["v"].iloc[0] for r in consumer.records] == [0.0, 2.0, 4.0]
    assert dict(consumer.records[0].proc_params) == {"samples": 3, "gain": 2.0}


def test_status_transitions_and_pymeasure_status(consumer):
    proc = Waiter()
    run = Run(proc)
    assert run.status is Status.QUEUED and not run.done
    run.start()
    assert proc.started.wait(5)
    assert run.status is Status.RUNNING
    assert proc.status == PyMeasureProcedure.RUNNING
    run.stop()
    assert run.wait(5)
    assert run.status is Status.ABORTED
    assert proc.status == PyMeasureProcedure.ABORTED
    assert proc.calls == ["execute", "shutdown"]
    assert run.duration > 0


def test_start_overrides_parameters(consumer):
    proc = Counter().connect("counts", consumer)
    plab.run(proc, samples=5, gain=0.5)
    consumer.join_queue()
    assert len(consumer.records) == 5
    assert consumer.records[0].proc_params["gain"] == 0.5


def test_record_indices_count_per_record_name():
    a, b = ListConsumer(), ListConsumer()

    class TwoRecords(Counter):
        def execute(self):
            for i in range(3):
                self.emit("a", i)
                self.emit("b", i)
                self.emit("b", i)

    proc = TwoRecords().connect("a", a).connect("b", b)
    with a, b:
        plab.run(proc)
    assert [r.index for r in a.records] == [0, 1, 2]
    assert [r.index for r in b.records] == list(range(6))


def test_run_end_is_notified_after_all_records(consumer):
    proc = Counter(samples=50, delay=0).connect("counts", consumer)
    run = plab.run(proc)
    consumer.join_queue()
    assert consumer.run_ends == [(run.run_id, 50)]


# - failures always run shutdown() on the worker thread ---------------------------------------- #
@pytest.mark.parametrize("where", ["startup", "execute"])
def test_failure_ends_run_failed_and_shutdown_runs_on_worker(consumer, where):
    proc = Counter(fail_in=where).connect("counts", consumer)
    run = plab.start(proc)
    run.wait(5)
    assert run.status is Status.FAILED
    assert isinstance(run.exception, RuntimeError)
    assert proc.calls[-1] == "shutdown"
    assert proc.threads["shutdown"] == proc.threads["startup"] != threading.get_ident()
    with pytest.raises(RuntimeError, match=f"failure in {where}"):
        run.raise_for_status()


def test_blocking_run_reraises_the_procedure_exception(consumer):
    proc = Counter(fail_in="execute").connect("counts", consumer)
    with pytest.raises(RuntimeError, match="failure in execute"):
        plab.run(proc)
    assert proc._run is None  # - the procedure can run again - #
    proc.fail_in = None
    assert plab.run(proc).status is Status.FINISHED


def test_shutdown_failure_fails_run(consumer):
    proc = Counter(fail_in="shutdown").connect("counts", consumer)
    run = plab.start(proc)
    run.wait(5)
    assert run.status is Status.FAILED
    assert "shutdown" in str(run.exception)


def test_shutdown_failure_does_not_mask_original_error(consumer):
    class DoubleFailure(Counter):
        def shutdown(self):
            raise ValueError("shutdown failure")

    proc = DoubleFailure(fail_in="execute").connect("counts", consumer)
    run = plab.start(proc)
    run.wait(5)
    assert "failure in execute" in str(run.exception)


def test_stop_before_start_aborts_without_running():
    proc = Counter()
    run = Run(proc)
    run.stop()
    run.start().wait(5)
    assert run.status is Status.ABORTED
    assert proc.calls == []


def test_ctrl_c_in_blocking_run_stops_and_waits_for_shutdown(monkeypatch):
    proc = Waiter()
    original_wait = Run.wait
    calls = {"n": 0}

    def wait(self, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            assert proc.started.wait(5)
            raise KeyboardInterrupt
        return original_wait(self, timeout)

    monkeypatch.setattr(Run, "wait", wait)
    with pytest.raises(KeyboardInterrupt):
        plab.run(proc)
    assert proc.calls == ["execute", "shutdown"]
    assert proc._run is None


# - validation happens before the run starts ---------------------------------------------------- #
def test_unknown_parameter_rejected_before_start():
    proc = Counter()
    with pytest.raises(NameError, match="unknown parameter"):
        plab.start(proc, sample=3)
    assert proc.calls == []


def test_invalid_value_rejected_before_start():
    with pytest.raises(ValueError, match="invalid value 20"):
        plab.start(Counter(), gain=20)


def test_missing_value_rejected_before_start():
    with pytest.raises(ValueError, match="has no value"):
        plab.start(NoDefault())
    assert plab.run(NoDefault(), level=1.0).status is Status.FINISHED


def test_invalid_constructor_value_rejected_at_start():
    with pytest.raises(ValueError, match="invalid value"):
        plab.start(Counter(gain=-1))


def test_bad_sequence_step_rejected_before_any_step_runs():
    proc = Counter()
    with pytest.raises(ValueError, match="Step 2: invalid value"):
        plab.start_sequence(proc, [{"gain": 1}, {"gain": 2}, {"gain": 99}])
    assert proc.calls == []


def test_cannot_start_twice():
    proc = Waiter()
    run = plab.start(proc)
    try:
        with pytest.raises(RuntimeError, match="already been started"):
            run.start()
        with pytest.raises(RuntimeError, match="already running"):
            plab.start(proc)
        with pytest.raises(RuntimeError, match="while the procedure is running"):
            proc.connect("x", ListConsumer())
    finally:
        run.stop()
        run.wait(5)


# - sequences ------------------------------------------------------------------------------------ #
def test_sequence_shares_run_id_and_continues_index(consumer):
    proc = Counter(samples=2).connect("counts", consumer)
    run = plab.run_sequence(proc, plab.sweep(gain=[1.0, 2.0, 3.0]))
    consumer.join_queue()
    assert run.status is Status.FINISHED
    assert {r.run_id for r in consumer.records} == {run.run_id}
    assert [r.index for r in consumer.records] == list(range(6))
    assert [r.proc_params["gain"] for r in consumer.records] == [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    assert proc.calls == ["startup", "execute", "shutdown"] * 3
    assert consumer.run_ends == [(run.run_id, 6)]


def test_sequence_values_carry_over_and_common_params(consumer):
    proc = Counter().connect("counts", consumer)
    plab.run_sequence(proc, [{"samples": 1}, {"gain": 3.0}], gain=2.0)
    consumer.join_queue()
    # - step 1: samples=1, gain=2 (common); step 2: samples carries over, gain=3 overrides - #
    assert [dict(r.proc_params) for r in consumer.records] == [
        {"samples": 1, "gain": 2.0}, {"samples": 1, "gain": 3.0}]


def test_failing_step_ends_sequence(consumer):
    class FailSecond(Counter):
        def execute(self):
            if self.gain == 2.0:
                raise RuntimeError("bad step")
            super().execute()

    proc = FailSecond(samples=1).connect("counts", consumer)
    run = plab.start_sequence(proc, plab.sweep(gain=[1.0, 2.0, 3.0]))
    run.wait(5)
    consumer.join_queue()
    assert run.status is Status.FAILED
    assert run.step == 1
    assert len(consumer.records) == 1


def test_is_last_tracks_sequence_steps(consumer):
    seen = []

    class LastCheck(Counter):
        def execute(self):
            seen.append(self.is_last())

    plab.run_sequence(LastCheck(), plab.sweep(gain=[1.0, 2.0, 3.0]))
    assert seen == [False, False, True]


def test_sweep_cartesian_order():
    assert plab.sweep(a=[1, 2], b=["x", "y"], c=0) == [
        {"a": 1, "b": "x", "c": 0}, {"a": 1, "b": "y", "c": 0},
        {"a": 2, "b": "x", "c": 0}, {"a": 2, "b": "y", "c": 0}]
    assert plab.sweep(name="abc") == [{"name": "abc"}]


# - routing and consumer failures --------------------------------------------------------------- #
def test_emitting_unconnected_record_fails_run(consumer):
    proc = Counter(record="typo").connect("counts", consumer)
    run = plab.start(proc)
    run.wait(5)
    assert run.status is Status.FAILED
    assert isinstance(run.exception, KeyError)
    assert "procedure.connect('typo'" in str(run.exception)


def test_consumer_not_started_fails_run():
    proc = Counter().connect("counts", ListConsumer(name="hdf"))
    with pytest.raises(ConsumerError, match="hdf is not running"):
        plab.run(proc)


def test_critical_consumer_failure_fails_run():
    failing = ListConsumer(fail_on=2, delay=0.001)
    proc = Counter(samples=1000).connect("counts", failing)
    with failing:
        run = plab.start(proc)
        run.wait(10)
    assert run.status is Status.FAILED
    assert isinstance(run.exception, ConsumerError)


def test_finished_means_every_record_was_handled():
    slow = ListConsumer(delay=0.002)
    with slow:
        plab.run(Counter(samples=100).connect("counts", slow))
        assert len(slow.records) == 100  # - no join_queue() needed - #


def test_recorder_failing_on_last_record_fails_run():
    last = ListConsumer(fail_on=2)
    with last:
        run = plab.start(Counter(samples=3).connect("counts", last))
        run.wait(5)
    assert run.status is Status.FAILED


def test_non_critical_consumer_failure_does_not_stop_run():
    viewer = ListConsumer(fail_on=2, critical=False, delay=0.001)
    recorder = ListConsumer()
    proc = Counter(samples=200).connect("counts", viewer, recorder)
    with viewer, recorder:
        run = plab.run(proc)
        recorder.join_queue()
    assert run.status is Status.FINISHED
    assert viewer.failed
    assert len(recorder.records) == 200


# - data integrity: the 0.9 shared-record bug ----------------------------------------------------- #
def test_fast_emits_into_slow_consumer_arrive_exactly_once_in_order():
    slow = ListConsumer()
    original = slow.handle

    def handle(record):
        if record.index % 500 == 0:
            time.sleep(0.01)  # - fall behind the producer - #
        original(record)

    slow.handle = handle
    proc = BufferReuse(samples=10_000).connect("buf", slow)
    with slow:
        plab.run(proc)
    assert [r.index for r in slow.records] == list(range(10_000))
    assert [r.data["x"].iloc[0] for r in slow.records] == list(range(10_000))


def test_bounded_queue_applies_backpressure_without_loss():
    bounded = ListConsumer(maxsize=5, delay=0.0005)
    proc = BufferReuse(samples=500).connect("buf", bounded)
    with bounded:
        plab.run(proc)
    assert [r.data["x"].iloc[0] for r in bounded.records] == list(range(500))


def test_emits_from_several_threads_get_unique_indices(consumer):
    class Threaded(Counter):
        def execute(self):
            workers = [threading.Thread(target=lambda: [self.emit("counts", 1) for _ in range(250)])
                       for _ in range(4)]
            for w in workers:
                w.start()
            for w in workers:
                w.join()

    plab.run(Threaded().connect("counts", consumer))
    consumer.join_queue()
    assert sorted(r.index for r in consumer.records) == list(range(1000))


# - metadata ------------------------------------------------------------------------------------- #
def test_metadata_is_added_to_meta_and_reevaluated_each_run(consumer):
    proc = WithMetadata().connect("m", consumer)
    plab.run(proc)
    plab.run(proc)
    consumer.join_queue()
    assert [r.meta["reading"] for r in consumer.records] == [1, 2]


def test_metadata_can_read_an_instrument_attribute(consumer):
    from pymeasure.experiment import Metadata
    from pymeasure.instruments.fakes import SwissArmyFake

    class InstrumentMeta(plab.Procedure):
        output = Metadata("Output voltage", fget="inst.output_voltage")

        def __init__(self, inst, **kwargs):
            super().__init__(**kwargs)
            self.inst = inst

        def execute(self):
            self.emit("m", 1.0)

    inst = SwissArmyFake(wait=0)
    inst.output_voltage = 3.0
    plab.run(InstrumentMeta(inst).connect("m", consumer))
    consumer.join_queue()
    assert consumer.records[0].meta["output"] == 3.0
