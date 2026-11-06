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

""" Read-only tests against a real Bluefors control software instance.

Run with::

    BLUEFORS_KEY=<API key> pytest tests/instruments/bluefors/test_bluefors_tc_with_device.py \
        --device-address=<host>

Optional environment variables: ``BLUEFORS_PORT`` (default 49098), ``BLUEFORS_CHANNEL`` (sensor
channel to read, default 6) and ``BLUEFORS_HEATER`` (heater output to read, default 1). These tests
only read values; they never change a setpoint.
"""
import math
import os

import pytest

from pylabtools.instruments.bluefors.bluefors_tc import BlueforsTC


@pytest.fixture(scope="module")
def tc(connected_device_address):
    key = os.environ.get("BLUEFORS_KEY")
    if not key:
        pytest.skip("Set BLUEFORS_KEY to the control software API key.")
    heater = int(os.environ.get("BLUEFORS_HEATER", 1))
    return BlueforsTC(connected_device_address, key=key, port=int(os.environ.get("BLUEFORS_PORT", 49098)),
                      heaters=(heater,))


def test_sensor_temperature(tc):
    temperature = tc.temperature(int(os.environ.get("BLUEFORS_CHANNEL", 6)))
    assert math.isfinite(temperature) and 0 < temperature < 400


def test_heater_setpoint(tc):
    heater = next(iter(tc.heaters.values()))
    setpoint = heater.setpoint
    assert math.isfinite(setpoint) and setpoint >= 0
