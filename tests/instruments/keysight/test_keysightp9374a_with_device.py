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

""" Read-only tests against a connected Keysight P9374A.

Run with::

    pytest tests/instruments/keysight/test_keysightp9374a_with_device.py \
        --device-address="TCPIP::localhost::hislip0::INSTR"

These tests only query the analyzer; they do not trigger sweeps or change settings.
"""
import numpy as np
import pytest

from pylabtools.instruments.keysight.keysightp9374a import KeysightP9374a


@pytest.fixture(scope="module")
def vna(connected_device_address):
    return KeysightP9374a(connected_device_address)


def test_identity(vna):
    assert "P937" in vna.id


def test_sweep_settings(vna):
    assert 300e3 <= vna.start <= vna.stop <= 20e9
    assert 1 <= vna.points <= 100001
    assert vna.sweep_time > 0
    assert vna.sweep_mode in ("HOLD", "CONT", "GRO", "SING")


def test_current_trace(vna):
    trace = vna.trace_data
    assert trace.shape == (vna.points,)
    assert np.isfinite(trace).all()
    assert vna.frequency_axis.shape == trace.shape
