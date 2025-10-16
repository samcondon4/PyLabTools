""" Minimal driver for the Keysight P9374A using the Pymeasure instrument driver 
framework.

Sam Condon, 2025-05-26
"""

#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2025 PyMeasure Developers
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
from pymeasure.instruments import Instrument
from pymeasure.instruments.generic_types import SCPIMixin
from pymeasure.instruments.validators import truncated_discrete_set, truncated_range, strict_discrete_set


class KeysightP9374a(SCPIMixin, Instrument):

    def __init__(self, adapter, name="KeysightP9374a", **kwargs):
        super().__init__(
            adapter,
            name,
            **kwargs
        )

        # - output data format initialization - #
        self.write('CALC:PAR:SEL CH1_S11_1')
        self.write('FORM REAL,32')
        self.write('FORM:BORD NORM')

    @property
    def trace_data(self):
        """ Return the active trace data as a numpy array.
        """
        data = self.adapter.connection.query_binary_values(
            'CALC:DATA? FDATA', datatype='f', is_big_endian=True
        )
        return np.array(data)

    @property
    def frequency_axis(self):
        """ Return the frequency axis as a numpy array.
        """
        start = self.start
        stop = self.stop
        points = self.points
        return np.linspace(start, stop, points)

    # - properties ---------------------------------------------- #
    output_enabled = Instrument.control(
        ':OUTPut?', ':OUTPut %i',
        """Turn on/off the RF output power.""",
        validator=truncated_discrete_set,
        values=[0, 1]
    )

    power = Instrument.control(
        'SOUR:POW?', 'SOUR:POW %f',
        """Control the RF output power in dBm.""",
        validator=truncated_range,
        values=[-40, 20],
    )

    if_bandwidth = Instrument.control(
        'SENS:BAND?', 'SENS:BAND %f',
        """Control the VNA IF bandwidth.""",
        validator=truncated_range,
        values=[10, 1.2e6]
    )

    averages_enabled = Instrument.control(
        'SENS:AVER?', 'SENS:AVER %i',
        """Control if a trace is averaged.""",
        validator=truncated_discrete_set,
        values=[0, 1]
    )

    averages = Instrument.control(
        'SENS:AVER:COUN?', 'SENS:AVER:COUN %i',
        """Controls the number of averages to run.""",
        validator=truncated_range,
        values=[1, 65536],
    )

    start = Instrument.control(
        'SENS:FREQ:STAR?', 'SENS:FREQ:STAR %f',
        """Control the VNA scan starting frequency (Hz.)""",
        validator=truncated_range,
        values=[0, 20e9],
    )

    stop = Instrument.control(
        'SENS:FREQ:STOP?', 'SENS:FREQ:STOP %f',
        """Control the VNA scan stopping frequency (Hz.)""",
        validator=truncated_range,
        values=[0, 20e9],
    )

    points = Instrument.control(
        'SENS:SWE:POIN?', 'SENS:SWE:POIN %i',
        """Control the number of points in the VNA trace.""",
        validator=truncated_range,
        values=[1, 100001],
        get_process=int
    )

    s_param = Instrument.control(
        'CALC:PAR:CAT:EXT?', 'CALC:PAR:MOD:EXT %s',
        """Control the VNA s-parameter being measured.""",
        validator=strict_discrete_set,
        values=['S11', 'S12', 'S21', 'S22'],
        get_process=lambda s: s.pop().strip('"')
    )

    trace_format = Instrument.control(
        'CALC:FORM?', 'CALC:FORM %s',
        """String indicating the format that trace data will be recorded in.""",
        validator=strict_discrete_set,
        values=['MLIN', 'MLOG', 'PHAS', 'UPH', 'IMAG', 'REAL', 'POLAR'],
    )

    electrical_delay = Instrument.control(
        'CALC:CORR:EDEL:TIME?', 'CALC:CORR:EDEL:TIME %0.12f',
        """Float indicating electrical delay in a signal propagating down line.""",
        validator=truncated_range,
        values=[0, 1e5],
    )
