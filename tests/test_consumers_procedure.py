import subprocess
import sys
import textwrap
import threading

import pytest
from conftest import ListConsumer
from procedures import Counter

import pylabtools as plab
from pylabtools import ConsumerError, Record


# - Consumer lifecycle ------------------------------------------------------------------------- #
def test_context_manager_starts_and_stops():
    c = ListConsumer()
    with c as started:
        assert started is c and c.running
    assert not c.running
    assert c.events == ["start", "stop"]


def test_hooks_run_on_the_consumer_thread():
    c = ListConsumer()
    with c:
        c.put(Record("r", 1))
        c.join_queue()
    assert len(c.threads) == 1 and threading.get_ident() not in c.threads


def test_put_requires_running_consumer():
    with pytest.raises(ConsumerError, match="not running"):
        ListConsumer().put(Record("r", 1))


def test_stop_drains_the_queue():
    c = ListConsumer(delay=0.001)
    c.start()
    for i in range(200):
        c.put(Record("r", i, index=i))
    c.stop()
    assert [r.index for r in c.records] == list(range(200))


def test_consumer_can_be_restarted():
    c = ListConsumer()
    with c:
        c.put(Record("r", 1))
    with c:
        c.put(Record("r", 2))
    assert len(c.records) == 2
    assert c.events == ["start", "stop", "start", "stop"]


def test_handle_failure_marks_consumer_failed():
    c = ListConsumer(fail_on=0)
    with c:
        c.put(Record("r", 1))
        c.join_queue()
        assert c.failed and isinstance(c.exception, RuntimeError)
        with pytest.raises(ConsumerError, match="has failed"):
            c.put(Record("r", 2))
    assert c.events == ["start", "stop"]  # - on_stop still runs, e.g. to close files - #


def test_on_start_failure_raises_from_start():
    class BadStart(ListConsumer):
        def on_start(self):
            raise OSError("cannot open file")

    c = BadStart()
    with pytest.raises(ConsumerError, match="failed to start"):
        c.start()
    assert not c.running


def test_base_handle_is_abstract():
    c = plab.Consumer()
    with c:
        c.put(Record("r", 1))
        c.join_queue()
    assert isinstance(c.exception, NotImplementedError)


def test_unstopped_consumer_is_drained_at_exit(tmp_path):
    """ A script that never calls stop() still gets every queued record handled at exit. """
    out = tmp_path / "out.txt"
    script = textwrap.dedent(f"""
        import time
        from pylabtools import Consumer, Record

        class Slow(Consumer):
            def on_start(self):
                self.f = open({str(out)!r}, "w")
            def handle(self, record):
                time.sleep(0.001)
                self.f.write(f"{{record.index}}\\n")
            def on_stop(self):
                self.f.close()

        c = Slow()
        c.start()
        for i in range(300):
            c.put(Record("r", i, index=i))
    """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=60)
    assert out.read_text().split() == [str(i) for i in range(300)]


# - Procedure -------------------------------------------------------------------------------- #
def test_unknown_constructor_parameter_is_rejected():
    with pytest.raises(TypeError, match="unknown parameter"):
        Counter(sampels=3)


def test_constructor_parameters_and_defaults():
    proc = Counter(samples=7)
    assert proc.samples == 7 and proc.gain == 1.0
    assert sorted(Counter.parameter_names()) == ["gain", "samples"]


def test_connect_validation_and_routes():
    a, b = ListConsumer(), ListConsumer()
    proc = Counter()
    with pytest.raises(TypeError, match="Expected a Consumer"):
        proc.connect("counts", object())
    with pytest.raises(ValueError):
        proc.connect("", a)
    with pytest.raises(ValueError):
        proc.connect("counts")
    proc.connect("counts", a, b).connect("counts", a).connect("other", b)
    assert proc.routes == {"counts": (a, b), "other": (b,)}
    assert proc.consumers() == [a, b]


def test_disconnect():
    a, b = ListConsumer(), ListConsumer()
    proc = Counter().connect("counts", a, b).connect("other", b)
    proc.disconnect("counts", a)
    assert proc.routes == {"counts": (b,), "other": (b,)}
    proc.disconnect(consumer=b)
    assert proc.routes == {}
    proc.connect("x", a)
    proc.disconnect()
    assert proc.routes == {}


def test_emit_outside_a_run_is_an_error():
    proc = Counter().connect("counts", ListConsumer())
    with pytest.raises(RuntimeError, match="only be called while the procedure is running"):
        proc.emit("counts", 1)
    assert proc.should_stop() is False
