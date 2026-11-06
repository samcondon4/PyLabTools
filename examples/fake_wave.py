""" Example procedure shared by the PyLabTools examples, using PyMeasure's SwissArmyFake instrument.

Replace ``SwissArmyFake`` with any PyMeasure instrument driver to run against real hardware.
"""
import time

from pymeasure.experiment import FloatParameter, IntegerParameter

import pylabtools as plab


class WaveLog(plab.Procedure):
    """ Sets an output amplitude, then logs ``amplitude * sin(t)`` from the instrument. """

    amplitude = FloatParameter("Amplitude", units="V", default=1.0, minimum=0, maximum=10)
    samples = IntegerParameter("Samples", default=300, minimum=1)
    interval = FloatParameter("Interval", units="s", default=0.02, minimum=0)

    def __init__(self, inst, **kwargs):
        super().__init__(**kwargs)
        self.inst = inst

    def startup(self):
        self.inst.output_voltage = self.amplitude

    def execute(self):
        for _ in range(self.samples):
            if self.should_stop():
                break
            self.emit("wave", {"t": self.inst.time, "V": self.inst.output_voltage * self.inst.wave},
                      meta={"instrument": self.inst.name})
            time.sleep(self.interval)

    def shutdown(self):
        # - always leave the instrument in a safe state, even after an error or a stop - #
        self.inst.output_voltage = 0
