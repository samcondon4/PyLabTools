#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2026 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import logging
from contextlib import contextmanager

import numpy as np

from pymeasure.instruments import Instrument, SCPIMixin
from pymeasure.instruments.validators import strict_discrete_set, strict_range

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def _normalize(choices):
    """ Return a get_process mapping instrument replies (long or short SCPI form) to ``choices``. """
    def process(value):
        value = str(value).strip().strip('"').upper()
        for short in choices:
            if value.startswith(short):
                return short
        return value
    return process


class KeysightP9374a(SCPIMixin, Instrument):
    """ Represents the Keysight P9374A Streamline USB vector network analyzer (300 kHz to 20 GHz)
    and provides a high-level interface for single-channel measurements.

    The analyzer measures one *measurement* (by default ``"CH1_S11_1"``, which exists after a
    preset). Use :meth:`acquire_trace` to take a complete, freshly triggered (and, if enabled,
    fully averaged) trace:

    .. code-block:: python

        vna = KeysightP9374a("TCPIP::localhost::hislip0::INSTR")
        vna.s_param = "S22"
        vna.center, vna.span, vna.points = 11.635e9, 90e6, 10001
        vna.power, vna.if_bandwidth = -20, 100
        vna.averages_enabled, vna.averages = True, 5
        vna.output_enabled = True

        trace = vna.acquire_trace()     # waits for all 5 averaging sweeps to finish
        f = vna.frequency_axis

    :meth:`acquire_trace` (and :meth:`acquire`) leave the channel in HOLD; set
    ``vna.sweep_mode = "continuous"`` to resume free-running sweeps.

    :param adapter: VISA resource name or adapter instance.
    :param name: Instrument name.
    :param measurement: Name of the measurement that traces are read from.
    :param kwargs: Further arguments for the adapter.
    """

    def __init__(self, adapter, name="Keysight P9374A Vector Network Analyzer",
                 measurement="CH1_S11_1", **kwargs):
        super().__init__(adapter, name, **kwargs)
        self.measurement = measurement

    # - stimulus ------------------------------------------------------------------------------ #
    output_enabled = Instrument.control(
        "OUTP?", "OUTP %d",
        """Control whether the RF output is on (bool).""",
        validator=strict_discrete_set,
        values={True: 1, False: 0},
        map_values=True,
    )

    power = Instrument.control(
        "SOUR:POW?", "SOUR:POW %g",
        """Control the RF output power in dBm (float).""",
        validator=strict_range,
        values=[-40, 20],
    )

    start = Instrument.control(
        "SENS:FREQ:STAR?", "SENS:FREQ:STAR %.12g",
        """Control the start frequency of the sweep in Hz (float).""",
        validator=strict_range,
        values=[300e3, 20e9],
    )

    stop = Instrument.control(
        "SENS:FREQ:STOP?", "SENS:FREQ:STOP %.12g",
        """Control the stop frequency of the sweep in Hz (float).""",
        validator=strict_range,
        values=[300e3, 20e9],
    )

    center = Instrument.control(
        "SENS:FREQ:CENT?", "SENS:FREQ:CENT %.12g",
        """Control the center frequency of the sweep in Hz (float).""",
        validator=strict_range,
        values=[300e3, 20e9],
    )

    span = Instrument.control(
        "SENS:FREQ:SPAN?", "SENS:FREQ:SPAN %.12g",
        """Control the frequency span of the sweep in Hz (float).""",
        validator=strict_range,
        values=[0, 20e9],
    )

    points = Instrument.control(
        "SENS:SWE:POIN?", "SENS:SWE:POIN %d",
        """Control the number of points in a sweep (int).""",
        validator=strict_range,
        values=[1, 100001],
        cast=int,
    )

    if_bandwidth = Instrument.control(
        "SENS:BAND?", "SENS:BAND %g",
        """Control the IF bandwidth in Hz (float).""",
        validator=strict_range,
        values=[10, 1.2e6],
    )

    sweep_time = Instrument.measurement(
        "SENS:SWE:TIME?",
        """Measure the time one sweep takes, in seconds (float).""",
    )

    # - averaging ----------------------------------------------------------------------------- #
    averages_enabled = Instrument.control(
        "SENS:AVER?", "SENS:AVER %d",
        """Control whether averaging is on (bool).""",
        validator=strict_discrete_set,
        values={True: 1, False: 0},
        map_values=True,
    )

    averages = Instrument.control(
        "SENS:AVER:COUN?", "SENS:AVER:COUN %d",
        """Control the number of sweeps (or points, in point averaging) to average (int).""",
        validator=strict_range,
        values=[1, 65536],
        cast=int,
    )

    averaging_mode = Instrument.control(
        "SENS:AVER:MODE?", "SENS:AVER:MODE %s",
        """Control the averaging mode (str): ``"SWE"`` averages over successive sweeps,
        ``"POIN"`` averages each point before moving to the next.""",
        validator=strict_discrete_set,
        values=["SWE", "POIN"],
        get_process=_normalize(("SWE", "POIN")),
    )

    # - triggering ---------------------------------------------------------------------------- #
    sweep_mode = Instrument.control(
        "SENS:SWE:MODE?", "SENS:SWE:MODE %s",
        """Control the sweep (trigger) mode of the channel (str): ``"HOLD"``, ``"CONT"``
        (continuous), ``"GRO"`` (the number of sweeps set by ``SENS:SWE:GRO:COUN``) or
        ``"SING"`` (one sweep, then HOLD). Use :meth:`acquire` to take sweeps and wait for them.""",
        validator=strict_discrete_set,
        values=["HOLD", "CONT", "GRO", "SING"],
        get_process=_normalize(("HOLD", "CONT", "GRO", "SING")),
    )

    # - measurement --------------------------------------------------------------------------- #
    s_param = Instrument.control(
        "CALC:PAR:CAT:EXT?", "CALC:PAR:MOD:EXT %s",
        """Control the S-parameter of the selected measurement (str), e.g. ``"S22"`` for a
        reflection measurement on port 2. Reading assumes a single measurement in the channel.""",
        validator=strict_discrete_set,
        values=["S11", "S12", "S21", "S22"],
        get_process=lambda v: str(v).strip().strip('"'),
        # - the reply is '"<measurement name>,<parameter>"', split at the comma - #
        get_process_list=lambda v: str(v[-1]).strip().strip('"'),
    )

    trace_format = Instrument.control(
        "CALC:FORM?", "CALC:FORM %s",
        """Control the display format of the selected measurement (str), which is the format
        of the trace data, e.g. ``"MLOG"`` (dB) or ``"PHAS"``.""",
        validator=strict_discrete_set,
        values=["MLIN", "MLOG", "PHAS", "UPH", "IMAG", "REAL", "POL"],
        get_process=_normalize(("MLIN", "MLOG", "PHAS", "UPH", "IMAG", "REAL", "POL")),
    )

    electrical_delay = Instrument.control(
        "CALC:CORR:EDEL:TIME?", "CALC:CORR:EDEL:TIME %.12g",
        """Control the electrical delay of the selected measurement in seconds (float).""",
        validator=strict_range,
        values=[0, 1e5],
    )

    @property
    def frequency_axis(self):
        """Get the stimulus frequencies of the sweep in Hz (numpy array)."""
        return np.linspace(self.start, self.stop, self.points)

    @property
    def trace_data(self):
        """Get the formatted data of the selected measurement as it currently is (numpy array).

        This does not trigger a sweep: after changing settings it may hold stale or partially
        averaged data. Use :meth:`acquire_trace` for a complete, fresh trace."""
        self.select_measurement()
        self.write("FORM:DATA REAL,32")
        self.write("FORM:BORD NORM")
        self.write("CALC:DATA? FDATA")
        return np.frombuffer(self._read_block(), dtype=">f4").astype(np.float64)

    # - methods ------------------------------------------------------------------------------- #
    def select_measurement(self, measurement=None):
        """Select the measurement that settings such as :attr:`s_param` and the trace data
        refer to.

        :param measurement: Measurement name; defaults to the ``measurement`` given at
            construction (``"CH1_S11_1"``, which exists after a preset).
        """
        if measurement is not None:
            self.measurement = measurement
        self.write(f"CALC:PAR:SEL {self.measurement}")

    def acquire(self, timeout=None):
        """Trigger a complete measurement and wait until it has finished.

        With sweep averaging on, averaging is restarted and as many sweeps as ``averages`` are
        taken (``SENS:SWE:MODE GRO`` with the group count set to the average count); otherwise a
        single sweep is taken (``SENS:SWE:MODE SING``). The method waits with ``*OPC?``, which
        only returns once the sweeps are complete. Afterwards the channel is in HOLD.

        :param timeout: Seconds to allow for the measurement. By default, 1.5 times the expected
            duration (sweep time times the number of sweeps) plus 10 s. For a VISA connection the
            timeout is raised to this value while waiting.
        """
        sweeps = 1
        averaging = self.averages_enabled
        if averaging and self.averaging_mode == "SWE":
            sweeps = self.averages
        if timeout is None:
            timeout = 1.5 * sweeps * self.sweep_time + 10
        if averaging:
            self.write("SENS:AVER:CLE")
        with self._connection_timeout(timeout):
            if sweeps > 1:
                self.write(f"SENS:SWE:GRO:COUN {sweeps}")
                self.ask("SENS:SWE:MODE GRO;*OPC?")
            else:
                self.ask("SENS:SWE:MODE SING;*OPC?")

    def acquire_trace(self, timeout=None):
        """Trigger a complete (fully averaged, if averaging is on) measurement, wait for it, and
        return the formatted trace data (numpy array). See :meth:`acquire`."""
        self.acquire(timeout=timeout)
        return self.trace_data

    # - helpers ------------------------------------------------------------------------------- #
    def _read_block(self):
        """Read an IEEE 488.2 definite-length binary block (``#<n><length><data>``) and the
        terminating line feed."""
        header = self.read_bytes(2)
        if header[:1] != b"#" or not header[1:2].isdigit() or header[1:2] == b"0":
            raise ValueError(f"Expected a definite-length binary block, got header {header!r}.")
        length = int(self.read_bytes(int(header[1:2])))
        data = self.read_bytes(length)
        self.read_bytes(1)  # - line feed after the block - #
        return data

    @contextmanager
    def _connection_timeout(self, seconds):
        """Raise the VISA timeout (in ms) to ``seconds`` while waiting, if the adapter has one."""
        connection = getattr(self.adapter, "connection", None)
        previous = getattr(connection, "timeout", None)
        if not isinstance(previous, (int, float)) or isinstance(previous, bool):
            yield
            return
        connection.timeout = max(previous, seconds * 1000)
        try:
            yield
        finally:
            connection.timeout = previous
