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

import numpy as np
import pytest

from pymeasure.test import expected_protocol
from pylabtools.instruments.keysight.keysightp9374a import KeysightP9374a


def block(values):
    """ IEEE 488.2 definite-length block of big-endian float32 values, with the line feed. """
    data = np.asarray(values, dtype=">f4").tobytes()
    length = str(len(data)).encode()
    return b"#" + str(len(length)).encode() + length + data + b"\n"


TRACE_READ = [(b"CALC:PAR:SEL CH1_S11_1", None), (b"FORM:DATA REAL,32", None),
              (b"FORM:BORD NORM", None)]


def test_init():
    with expected_protocol(KeysightP9374a, []) as inst:
        assert inst.measurement == "CH1_S11_1"


# - stimulus -------------------------------------------------------------------------------------- #
def test_output_enabled():
    with expected_protocol(KeysightP9374a, [(b"OUTP 1", None), (b"OUTP?", b"1"), (b"OUTP 0", None)]) as inst:
        inst.output_enabled = True
        assert inst.output_enabled is True
        inst.output_enabled = False


def test_power():
    with expected_protocol(KeysightP9374a, [(b"SOUR:POW -20", None), (b"SOUR:POW?", b"-20")]) as inst:
        inst.power = -20
        assert inst.power == -20


@pytest.mark.parametrize("value", [-41, 21])
def test_power_out_of_range(value):
    with expected_protocol(KeysightP9374a, []) as inst:
        with pytest.raises(ValueError):
            inst.power = value


@pytest.mark.parametrize("prop, command", [
    ("start", b"SENS:FREQ:STAR"), ("stop", b"SENS:FREQ:STOP"), ("center", b"SENS:FREQ:CENT")])
def test_frequencies_keep_full_precision(prop, command):
    with expected_protocol(KeysightP9374a, [(command + b" 11635123456", None),
                                            (command + b"?", b"1.1635123456E+10")]) as inst:
        setattr(inst, prop, 11_635_123_456)
        assert getattr(inst, prop) == 11_635_123_456


def test_frequency_out_of_range():
    with expected_protocol(KeysightP9374a, []) as inst:
        with pytest.raises(ValueError):
            inst.center = 25e9


def test_span():
    with expected_protocol(KeysightP9374a, [(b"SENS:FREQ:SPAN 90000000", None), (b"SENS:FREQ:SPAN?", b"9E+07")]) as inst:
        inst.span = 90e6
        assert inst.span == 90e6


def test_points():
    with expected_protocol(KeysightP9374a, [(b"SENS:SWE:POIN 10001", None), (b"SENS:SWE:POIN?", b"10001")]) as inst:
        inst.points = 10001
        points = inst.points
        assert points == 10001 and isinstance(points, int)


def test_if_bandwidth():
    with expected_protocol(KeysightP9374a, [(b"SENS:BAND 100", None), (b"SENS:BAND?", b"100")]) as inst:
        inst.if_bandwidth = 100
        assert inst.if_bandwidth == 100


def test_sweep_time():
    with expected_protocol(KeysightP9374a, [(b"SENS:SWE:TIME?", b"0.0123")]) as inst:
        assert inst.sweep_time == pytest.approx(0.0123)


def test_frequency_axis():
    with expected_protocol(KeysightP9374a, [(b"SENS:FREQ:STAR?", b"1E9"), (b"SENS:FREQ:STOP?", b"2E9"),
                                            (b"SENS:SWE:POIN?", b"3")]) as inst:
        assert inst.frequency_axis.tolist() == [1e9, 1.5e9, 2e9]


# - averaging ------------------------------------------------------------------------------------- #
def test_averages_enabled():
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER 1", None), (b"SENS:AVER?", b"0")]) as inst:
        inst.averages_enabled = True
        assert inst.averages_enabled is False


def test_averages():
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER:COUN 5", None), (b"SENS:AVER:COUN?", b"5")]) as inst:
        inst.averages = 5
        assert inst.averages == 5


@pytest.mark.parametrize("reply, value", [(b"SWE", "SWE"), (b"SWEEP", "SWE"), (b"POIN", "POIN"), (b"POINT", "POIN")])
def test_averaging_mode(reply, value):
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER:MODE?", reply)]) as inst:
        assert inst.averaging_mode == value


def test_averaging_mode_setter():
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER:MODE POIN", None)]) as inst:
        inst.averaging_mode = "POIN"


# - triggering and measurement ------------------------------------------------------------------- #
@pytest.mark.parametrize("reply, value", [(b"HOLD", "HOLD"), (b"CONT", "CONT"), (b"CONTINUOUS", "CONT"),
                                          (b"GRO", "GRO"), (b"SING", "SING")])
def test_sweep_mode(reply, value):
    with expected_protocol(KeysightP9374a, [(b"SENS:SWE:MODE?", reply)]) as inst:
        assert inst.sweep_mode == value


def test_sweep_mode_setter():
    with expected_protocol(KeysightP9374a, [(b"SENS:SWE:MODE CONT", None)]) as inst:
        inst.sweep_mode = "CONT"


def test_s_param():
    with expected_protocol(KeysightP9374a, [(b"CALC:PAR:MOD:EXT S22", None),
                                            (b"CALC:PAR:CAT:EXT?", b'"CH1_S11_1,S22"')]) as inst:
        inst.s_param = "S22"
        assert inst.s_param == "S22"


def test_trace_format():
    with expected_protocol(KeysightP9374a, [(b"CALC:FORM MLOG", None), (b"CALC:FORM?", b"MLOG")]) as inst:
        inst.trace_format = "MLOG"
        assert inst.trace_format == "MLOG"


def test_electrical_delay():
    with expected_protocol(KeysightP9374a, [(b"CALC:CORR:EDEL:TIME 1.5e-09", None),
                                            (b"CALC:CORR:EDEL:TIME?", b"1.5E-09")]) as inst:
        inst.electrical_delay = 1.5e-9
        assert inst.electrical_delay == pytest.approx(1.5e-9)


def test_select_measurement():
    with expected_protocol(KeysightP9374a, [(b"CALC:PAR:SEL CH1_S22_2", None)], measurement="CH1_S22_2") as inst:
        inst.select_measurement()


def test_trace_data():
    values = [-1.5, -2.25, -30.0]
    with expected_protocol(KeysightP9374a, TRACE_READ + [(b"CALC:DATA? FDATA", block(values))]) as inst:
        data = inst.trace_data
        assert data.tolist() == values and data.dtype == np.float64


def test_trace_data_large_block():
    values = np.linspace(-40, 0, 10001)
    with expected_protocol(KeysightP9374a, TRACE_READ + [(b"CALC:DATA? FDATA", block(values))]) as inst:
        np.testing.assert_allclose(inst.trace_data, values, rtol=1e-6)


def test_trace_data_rejects_non_block_reply():
    with expected_protocol(KeysightP9374a, TRACE_READ + [(b"CALC:DATA? FDATA", b"-1")]) as inst:
        with pytest.raises(ValueError, match="definite-length binary block"):
            inst.trace_data


# - acquisition ---------------------------------------------------------------------------------- #
def test_acquire_without_averaging_takes_one_sweep():
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER?", b"0"), (b"SENS:SWE:TIME?", b"0.5"),
                                            (b"SENS:SWE:MODE SING;*OPC?", b"1")]) as inst:
        inst.acquire()


def test_acquire_with_sweep_averaging_takes_all_averaging_sweeps():
    with expected_protocol(KeysightP9374a, [
            (b"SENS:AVER?", b"1"), (b"SENS:AVER:MODE?", b"SWE"), (b"SENS:AVER:COUN?", b"5"),
            (b"SENS:SWE:TIME?", b"2.0"),
            (b"SENS:AVER:CLE", None), (b"SENS:SWE:GRO:COUN 5", None),
            (b"SENS:SWE:MODE GRO;*OPC?", b"1")]) as inst:
        inst.acquire()


def test_acquire_with_point_averaging_takes_one_sweep():
    with expected_protocol(KeysightP9374a, [
            (b"SENS:AVER?", b"1"), (b"SENS:AVER:MODE?", b"POIN"), (b"SENS:SWE:TIME?", b"0.5"),
            (b"SENS:AVER:CLE", None), (b"SENS:SWE:MODE SING;*OPC?", b"1")]) as inst:
        inst.acquire()


def test_acquire_with_explicit_timeout_skips_sweep_time_query():
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER?", b"0"),
                                            (b"SENS:SWE:MODE SING;*OPC?", b"1")]) as inst:
        inst.acquire(timeout=60)


def test_acquire_raises_and_restores_the_connection_timeout():
    seen = []
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER?", b"1"), (b"SENS:AVER:MODE?", b"SWE"),
                                            (b"SENS:AVER:COUN?", b"5"), (b"SENS:SWE:TIME?", b"100"),
                                            (b"SENS:AVER:CLE", None), (b"SENS:SWE:GRO:COUN 5", None),
                                            (b"SENS:SWE:MODE GRO;*OPC?", b"1")],
                           connection_attributes={"timeout": 2000}) as inst:
        original_ask = inst.ask

        def ask(command, **kwargs):
            seen.append(inst.adapter.connection.timeout)
            return original_ask(command, **kwargs)

        inst.ask = ask
        inst.acquire()
        assert seen[-1] == pytest.approx((1.5 * 5 * 100 + 10) * 1000)  # - during the *OPC? wait - #
        assert inst.adapter.connection.timeout == 2000                 # - restored afterwards - #


def test_acquire_trace():
    values = [-3.0, -4.0]
    with expected_protocol(KeysightP9374a, [(b"SENS:AVER?", b"0"), (b"SENS:SWE:MODE SING;*OPC?", b"1")]
                           + TRACE_READ + [(b"CALC:DATA? FDATA", block(values))]) as inst:
        assert inst.acquire_trace(timeout=30).tolist() == values
