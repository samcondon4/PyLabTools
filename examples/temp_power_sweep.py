""" Temperature / VNA-power sweep with continuous fridge polling.

At each fridge setpoint: set the PID setpoint, wait for the fridge to settle, then take VNA traces
at several output powers. The fridge temperatures are polled at a fixed cadence for the whole
experiment by a background task. ``group_by="setpoint"`` makes each setpoint one RecordGroup, so the
traces and the fridge samples taken at a setpoint share a RecordGroup in the HDF5 file.

The fake instruments below mimic ``BlueforsTC`` (``tc.heater_sample.setpoint``,
``tc.temperature(ch)``) and a VNA driver (``power``, ``output_enabled``, ``frequency_axis``,
``trace_data``); swap in the real drivers for the experiment.

    python examples/temp_power_sweep.py            # with live plots (needs pylabtools[gui])
    python examples/temp_power_sweep.py --no-gui --fast
"""
import argparse
import threading
import time

import numpy as np
from pymeasure.experiment import FloatParameter, IntegerParameter

import pylabtools as plab


class TempPowerSweep(plab.Procedure):
    setpoint = FloatParameter("Setpoint", units="K", minimum=0, maximum=0.5)
    power = FloatParameter("VNA power", units="dBm", minimum=-40, maximum=20)
    n_traces = IntegerParameter("Traces", default=10, minimum=1)
    settle_time = FloatParameter("Settle time", units="s", default=600, minimum=0)
    poll_interval = FloatParameter("Poll interval", units="s", default=5, minimum=0.01)

    def __init__(self, vna, tc, channels=(1, 2, 5, 6), **kwargs):
        super().__init__(**kwargs)
        self.vna, self.tc, self.channels = vna, tc, channels
        self.phase = "settling"
        self._applied_setpoint = None

    @plab.every("poll_interval")
    def poll_fridge(self):
        self.emit("fridge", {f"T{ch}": self.tc.temperature(ch) for ch in self.channels},
                  meta={"phase": self.phase})

    def startup(self):
        if self.setpoint != self._applied_setpoint:          # - settle only when T changes - #
            self.phase = "settling"
            self.tc.heater_sample.setpoint = self.setpoint
            self._applied_setpoint = self.setpoint
            self.sleep(self.settle_time)                      # - returns early on stop - #
        self.phase = "measuring"

    def execute(self):
        self.vna.power = self.power
        self.vna.output_enabled = 1
        f = self.vna.frequency_axis
        for i in range(self.n_traces):
            if self.should_stop():
                break
            self.emit("s21", {"f": f, "s21": self.vna.trace_data}, meta={"trace": i})

    def shutdown(self):
        if self.is_last() or self.should_stop():
            self.vna.output_enabled = 0


# - fake instruments ------------------------------------------------------------------------------ #
class FakeHeater:
    def __init__(self, fridge):
        self._fridge = fridge

    @property
    def setpoint(self):
        return self._fridge.target

    @setpoint.setter
    def setpoint(self, value):
        with self._fridge.lock:
            self._fridge.start_T, self._fridge.t0 = self._fridge.mxc(), time.monotonic()
            self._fridge.target = float(value)


class FakeFridge:
    """ Mixing chamber relaxes exponentially towards the setpoint; other stages are fixed. """

    STAGES = {1: 45.0, 2: 3.5, 5: None, 6: None}

    def __init__(self, tau=60.0):
        self.tau, self.lock = tau, threading.Lock()
        self.target, self.start_T, self.t0 = 0.010, 0.010, time.monotonic()
        self.heater_sample = FakeHeater(self)

    def mxc(self):
        dt = time.monotonic() - self.t0
        return self.target + (self.start_T - self.target) * np.exp(-dt / self.tau)

    def temperature(self, channel):
        with self.lock:
            fixed = self.STAGES.get(channel)
            return float(fixed if fixed is not None else self.mxc() * (1.02 if channel == 5 else 1.0))


class FakeVNA:
    """ A resonance whose depth depends on power and whose frequency depends on temperature. """

    def __init__(self, fridge, points=401, sweep_time=0.5):
        self.fridge, self.points, self.sweep_time = fridge, points, sweep_time
        self.power, self.output_enabled = -20.0, 0

    @property
    def frequency_axis(self):
        return np.linspace(5.99e9, 6.01e9, self.points)

    @property
    def trace_data(self):
        time.sleep(self.sweep_time)  # - a real VNA sweep takes time - #
        f = self.frequency_axis
        f0 = 6.0e9 * (1 - 1e-5 * self.fridge.mxc())
        depth = 20 / (1 + 10 ** ((self.power + 20) / 10))
        noise = np.random.normal(0, 0.05, f.size)
        return -depth / (1 + ((f - f0) / 3e5) ** 2) + noise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="temp_power_sweep.h5")
    parser.add_argument("--fast", action="store_true", help="short settle and poll times")
    parser.add_argument("--no-gui", action="store_true")
    args = parser.parse_args(argv)

    plab.log.enable()
    fridge = FakeFridge(tau=0.2 if args.fast else 20)
    vna = FakeVNA(fridge, sweep_time=0.05 if args.fast else 0.5)
    proc = TempPowerSweep(vna, fridge, n_traces=3 if args.fast else 10,
                          settle_time=0.5 if args.fast else 60,
                          poll_interval=0.05 if args.fast else 2)

    hdf = plab.HDFRecorder(args.out, keep_open=True)
    fridge_view = plab.LineViewer(y=["T5", "T6"], max_rows=5000, title="Mixing chamber (K)")
    trace_view = plab.LineViewer(x="f", y="s21", max_rows=vna.points, title="S21")
    proc.connect("s21", hdf, trace_view).connect("fridge", hdf, fridge_view)

    steps = plab.sweep(setpoint=[0.020, 0.050, 0.100], power=[-30, -20, -10])
    with plab.running(hdf, fridge_view, trace_view):
        run = plab.start_sequence(proc, steps, group_by="setpoint")
        if not args.no_gui:
            plab.gui.show(fridge_view, trace_view, run=run, columns=2, block=True)
        plab.wait(run)
    print(run)

    # - link the two records through RecordGroup: one group per setpoint - #
    s21 = plab.read_hdf(args.out, "s21")
    temps = plab.read_hdf(args.out, "fridge")
    for group in s21.index.get_level_values("RecordGroup").unique()[-3:]:
        traces, t = s21.loc[group], temps.loc[group]
        settled = t[t["meta_phase"] == "measuring"]
        print(f"RecordGroup {group}: setpoint {traces['proc_setpoint'].iloc[0] * 1e3:.0f} mK, "
              f"{traces.index.get_level_values('RecordGroupInd').nunique()} traces, "
              f"{len(t)} fridge samples, MXC while measuring {settled['T6'].mean() * 1e3:.2f} mK")
    return run


if __name__ == "__main__":
    main()
