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

import pytest

from pymeasure.test import expected_protocol
from pylabtools.instruments.bluefors.bluefors_tc import BlueforsTC

SENSOR_6 = b"mapper.heater_mappings_bftc.device.c6.temperature"
HEATER_1 = b"driver.bftc.data.heaters.heater_1.setpoint"


def test_init():
    with expected_protocol(BlueforsTC, []) as inst:
        assert inst.name == "Bluefors temperature controller"
        assert sorted(inst.channels) == list(range(1, 13))
        assert inst.heaters == {}


def test_init_heaters_without_communication():
    with expected_protocol(BlueforsTC, [], heaters=(1, 2)) as inst:
        assert sorted(inst.heaters) == [1, 2]
        assert inst.heater(1) is inst.heater_1


def test_sensor_temperature():
    with expected_protocol(BlueforsTC, [(SENSOR_6, b"0.0123")]) as inst:
        assert inst.ch_6.temperature == pytest.approx(0.0123)


def test_temperature_by_channel_number():
    with expected_protocol(BlueforsTC, [(SENSOR_6, b"0.0123")]) as inst:
        assert inst.temperature(6) == pytest.approx(0.0123)


def test_temperature_unknown_channel():
    with expected_protocol(BlueforsTC, []) as inst:
        with pytest.raises(ValueError, match="No sensor channel 13"):
            inst.temperature(13)


def test_custom_sensor_path():
    with expected_protocol(BlueforsTC,
                           [(b"mapper.temperature_control.sensors.t2.temperature", b"3.9")],
                           sensor_path="mapper.temperature_control.sensors.t{channel}") as inst:
        assert inst.ch_2.temperature == pytest.approx(3.9)


def test_heater_setpoint():
    with expected_protocol(BlueforsTC, [(HEATER_1, b"0.01")], heaters=(1,)) as inst:
        assert inst.heater_1.setpoint == pytest.approx(0.01)


def test_heater_setpoint_setter():
    with expected_protocol(BlueforsTC,
                           [(HEATER_1 + b"=0.05", None), (HEATER_1, b"0.05")],
                           heaters=(1,)) as inst:
        inst.heater_1.setpoint = 0.05
        assert inst.heater_1.setpoint == pytest.approx(0.05)


def test_heater_setpoint_keeps_full_precision():
    with expected_protocol(BlueforsTC, [(HEATER_1 + b"=0.0123456789", None)], heaters=(1,)) as inst:
        inst.heater_1.setpoint = 0.0123456789


def test_heater_created_on_first_use():
    with expected_protocol(BlueforsTC,
                           [(b"driver.bftc.data.heaters.heater_3.setpoint=0.2", None)]) as inst:
        inst.heater(3).setpoint = 0.2
        assert inst.heater_3 is inst.heaters[3]


def test_custom_heater_path():
    with expected_protocol(BlueforsTC,
                           [(b"mapper.heater_mappings_bftc.device.h1.setpoint", b"0.03")],
                           heaters=(1,), heater_path="mapper.heater_mappings_bftc.device.h{heater}") as inst:
        assert inst.heater_1.setpoint == pytest.approx(0.03)


@pytest.mark.parametrize("value", [0.6, 50, -0.01])
def test_setpoint_out_of_range_is_not_sent(value):
    with expected_protocol(BlueforsTC, [], heaters=(1,)) as inst:
        with pytest.raises(ValueError):
            inst.heater_1.setpoint = value


def test_max_setpoint():
    with expected_protocol(BlueforsTC, [(HEATER_1 + b"=0.8", None)], heaters=(1,), max_setpoint=1.0) as inst:
        inst.heater_1.setpoint = 0.8


def test_setpoint_limit_per_heater():
    with expected_protocol(BlueforsTC, [(b"driver.bftc.data.heaters.heater_2.setpoint=0.8", None)],
                           heaters=(1, 2)) as inst:
        inst.heater_2.setpoint_values = (0, 1.5)
        inst.heater_2.setpoint = 0.8
        with pytest.raises(ValueError):
            inst.heater_1.setpoint = 0.8


@pytest.mark.parametrize("bad", ["sample", "1", 0, -1, True, 1.0])
def test_heater_ids_are_output_numbers(bad):
    with pytest.raises(TypeError, match="output numbers"):
        with expected_protocol(BlueforsTC, [], heaters=(bad,)):
            pass
