""" Procedures shared by the tests. """
import threading
import time

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter, Metadata, Parameter

from pylabtools import Procedure


class Counter(Procedure):
    """ Emits ``samples`` rows of a counter, recording which hooks ran and on which thread. """

    samples = IntegerParameter("Samples", default=3, minimum=0, maximum=100_000)
    gain = FloatParameter("Gain", units="V", default=1.0, minimum=0, maximum=10)

    def __init__(self, fail_in=None, delay=0.0, record="counts", **kwargs):
        super().__init__(**kwargs)
        self.fail_in = fail_in
        self.delay = delay
        self.record = record
        self.calls = []
        self.threads = {}

    def _hook(self, name):
        self.calls.append(name)
        self.threads[name] = threading.get_ident()
        if self.fail_in == name:
            raise RuntimeError(f"failure in {name}")

    def startup(self):
        self._hook("startup")

    def execute(self):
        self._hook("execute")
        for i in range(self.samples):
            if self.should_stop():
                break
            self.emit(self.record, {"i": i, "v": i * self.gain})
            if self.delay:
                time.sleep(self.delay)

    def shutdown(self):
        self._hook("shutdown")


class BufferReuse(Procedure):
    """ Reuses one numpy buffer for every emit, as fast acquisition code often does. """

    samples = IntegerParameter("Samples", default=10_000, maximum=1_000_000)

    def execute(self):
        buffer = np.zeros(4)
        for i in range(self.samples):
            buffer[:] = i
            self.emit("buf", {"x": buffer})


class Waiter(Procedure):
    """ Runs until stopped. """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.started = threading.Event()
        self.calls = []

    def execute(self):
        self.calls.append("execute")
        self.started.set()
        while not self.should_stop():
            time.sleep(0.01)

    def shutdown(self):
        self.calls.append("shutdown")


class NoDefault(Procedure):
    level = FloatParameter("Level")  # - no default: must be given - #

    def execute(self):
        pass


class WithMetadata(Procedure):
    """ Metadata with an fget is re-read on every run (upstream raises on re-evaluation). """

    note = Parameter("Note", default="x")
    reading = Metadata("Reading", fget="read_value")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.value = 0

    def read_value(self):
        self.value += 1
        return self.value

    def execute(self):
        self.emit("m", 1.0)
