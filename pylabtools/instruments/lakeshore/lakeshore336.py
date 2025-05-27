#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2022 PyMeasure Developers
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
import threading
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import *
from .ls336_prop_helpers import Lakeshore336PropHelpers

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class LakeShore336(Instrument):

    # lock for multiple threads accessing the lakeshore #
    lock = threading.Lock()
    lock_initialized = True

    # manual output properties #
    mout1 = Lakeshore336PropHelpers.get_mout_prop(1)
    mout2 = Lakeshore336PropHelpers.get_mout_prop(2)
    mout3 = Lakeshore336PropHelpers.get_mout_prop(3)
    mout4 = Lakeshore336PropHelpers.get_mout_prop(4)

    # output range properties #
    range1 = Lakeshore336PropHelpers.get_12_range_prop(1)
    range2 = Lakeshore336PropHelpers.get_12_range_prop(2)
    range3 = Lakeshore336PropHelpers.get_34_range_prop(3)
    range4 = Lakeshore336PropHelpers.get_34_range_prop(4)

    # setpoint properties #
    setpoint1 = Lakeshore336PropHelpers.get_setpoint_prop(1)
    setpoint2 = Lakeshore336PropHelpers.get_setpoint_prop(2)
    setpoint3 = Lakeshore336PropHelpers.get_setpoint_prop(3)
    setpoint4 = Lakeshore336PropHelpers.get_setpoint_prop(4)

    # pid properties #
    pid1 = Lakeshore336PropHelpers.get_pid_prop(1)
    pid2 = Lakeshore336PropHelpers.get_pid_prop(2)
    pid3 = Lakeshore336PropHelpers.get_pid_prop(3)
    pid4 = Lakeshore336PropHelpers.get_pid_prop(4)

    # output mode properties #
    outmode1 = Lakeshore336PropHelpers.get_outmode_prop(1)
    outmode2 = Lakeshore336PropHelpers.get_outmode_prop(2)
    outmode3 = Lakeshore336PropHelpers.get_outmode_prop(3)
    outmode4 = Lakeshore336PropHelpers.get_outmode_prop(4)

    # sensor outputs #
    sensorA = Instrument.measurement(
        "SRDG? A", """ Query sensor units reading of channel A sensor. """
    )

    sensorB = Instrument.measurement(
        "SRDG? B", """ Query sensor units reading of channel B sensor. """
    )

    sensorC = Instrument.measurement(
        "SRDG? C", """ Query sensor units reading of channel C sensor. """
    )

    sensorD = Instrument.measurement(
        "SRDG? D", """ Query sensor units reading of channel D sensor. """
    )

    outmode_map = {
        "Off": 0, "Closed Loop PID": 1, "Zone": 2, "Open Loop": 3, "Monitor Out": 4, "Warmup Supply": 5
    }

    input_map = {
        "None": 0, "A": 1, "B": 2, "C": 3, "D": 4
    }

    def __init__(self, adapter, **kwargs):
        super().__init__(
            adapter,
            "Lake-Shore 336 Temperature Controller",
            **kwargs
        )

    def set_output_mode(self, channel, mode, input_source, pe=0):
        """ Set the output mode of a given channel.

        :param channel: Which channel to configure output mode for.
        :param mode: Output mode of the channel.
        :param input_source: Input for closed loop control of this channel.
        :param pe: Powerup enable. Should output remain on or shut off after a power cycle.
        """
        # ensure input parameters are valid #
        strict_discrete_set(channel, [1, 2, 3, 4])
        strict_discrete_set(mode, list(self.outmode_map.keys()))
        strict_discrete_set(input_source, list(self.input_map.keys()))
        mode = self.outmode_map[mode]
        input_source = self.input_map[input_source]

        self.write(f"OUTMODE {channel},{mode},{input_source},{pe}")

    def set_pid(self, channel, p, i, d):
        """ Set the pid values for the specified channel.

        :param channel: Which channel to set pid values on.
        :param p: proportional gain term, 0.1 - 1000
        :param i: integral term, 0.1 - 1000
        :param d: derivative term, 0 - 200
        """
        strict_discrete_set(channel, [1, 2, 3, 4])
        p = truncated_range(p, [0.1, 1000])
        i = truncated_range(i, [0.1, 1000])
        d = truncated_range(d, [0, 200])

        self.write(f"PID {channel},{p},{i},{d}")

