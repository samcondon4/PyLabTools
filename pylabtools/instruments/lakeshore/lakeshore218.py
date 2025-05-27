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

from time import sleep, time

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set, strict_range

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class LakeShore218(Instrument):

    temperature_all = Instrument.measurement(
        "KRDG? 0", """ Query the temperature of all sensors. """
    )

    temperature1 = Instrument.measurement(
        "KRDG? 1", """ Query the temperature of the channel 1 sensor. """
    )

    temperature2 = Instrument.measurement(
        "KRDG? 2", """ Query the temperature of the channel 2 sensor. """
    )

    temperature3 = Instrument.measurement(
        "KRDG? 3", """ Query the temperature of the channel 3 sensor. """
    )

    temperature4 = Instrument.measurement(
        "KRDG? 4", """ Query the temperature of the channel 4 sensor. """
    )
    temperature5 = Instrument.measurement(
        "KRDG? 5", """ Query the temperature of the channel 5 sensor. """
    )
    temperature6 = Instrument.measurement(
        "KRDG? 6", """ Query the temperature of the channel 6 sensor. """
    )
    temperature7 = Instrument.measurement(
        "KRDG? 7", """ Query the temperature of the channel 7 sensor. """
    )

    temperature8 = Instrument.measurement(
        "KRDG? 8", """ Query the temperature of the channel 8 sensor. """
    )

    sensor1 = Instrument.measurement(
        "SRDG? 1", """ Query sensor units reading of channel 1 sensor. """
    )

    sensor2 = Instrument.measurement(
        "SRDG? 2", """ Query sensor units reading of channel 2 sensor. """
    )

    sensor3 = Instrument.measurement(
        "SRDG? 3", """ Query sensor units reading of channel 3 sensor. """
    )

    sensor4 = Instrument.measurement(
        "SRDG? 4", """ Query sensor units reading of channel 4 sensor. """
    )

    sensor5 = Instrument.measurement(
        "SRDG? 5", """ Query sensor units reading of channel 5 sensor. """
    )

    sensor6 = Instrument.measurement(
        "SRDG? 6", """ Query sensor units reading of channel 6 sensor. """
    )

    sensor7 = Instrument.measurement(
        "SRDG? 7", """ Query sensor units reading of channel 7 sensor. """
    )

    sensor8 = Instrument.measurement(
        "SRDG? 8", """ Query sensor units reading of channel 8 sensor. """
    )

    status = Instrument.measurement(
        "QSTB?", """ Query the status byte. """
    )

    def __init__(self, adapter, **kwargs):
        super().__init__(
            adapter,
            "Lake Shore 218 Temperature Controller",
            **kwargs
        )

    def delete_cal_curve(self, curve):
        """ Delete a ls218 user calibration curve.

        :param curve: Integer specifying the curve to delete. Values between 21-28 for user inputs 1-8
                      are accepted.
        """
        # check curve delete value.
        strict_discrete_set(int(curve), list(range(21, 29)))
        self.write(f"CRVDEL {curve}")

    def set_cal_curve_hdr(self, curve, name, sn, form, limit, cof):
        """ Configure a calibration curve header.

        :param curve: Specifies which curve to configure (21-28 for inputs 1-8).
        :param name: Specifies the name of the curve. Limited to 15 characters.
        :param sn: Serial number of the sensor the curve is associated with. Limited to 10 characters.
        :param form: Curve data format. 2 = V/K, 3 = Ohm/K, 4 = log Ohm/K
        :param limit: Specifies curve temperature limit in Kelvin.
        :param cof: Specifies curve temperature coefficient. 1 = negative, 2 = positive.
        """
        # check inputs #
        strict_discrete_set(int(curve), list(range(21, 29)))
        if len(name) > 15:
            name = name[0:15]
        if len(sn) > 10:
            sn = name[0:10]
        strict_discrete_set(form, [2, 3, 4])
        strict_discrete_set(cof, [1, 2])
        self.write(f"CRVHDR {curve},{name},{sn},{form},{limit},{cof}")

    def set_cal_curve_pt(self, curve, index, units_val, temp_val):
        """ Configure a user calibration curve data point.

        :param curve: Specifies which curve to configure (21-28 for inputs 1-8).
        :param index: Specifies points index within the curve (1-200).
        :param units_val: Specifies sensor units for this point to 6 digits.
        :param temp_val: Specifies corresponding temperature in Kelvin for this point to 6 digits.
        """
        strict_discrete_set(int(curve), list(range(21, 29)))
        strict_range(index, [1, 200])
        units_val = round(units_val, 6)
        temp_val = round(temp_val, 6)
        self.write(f"CRVPT {curve},{index},{units_val},{temp_val}")

    def set_cal_curve_pts(self, curve, units_val, temp_val):
        """ Set multiple user calibration curve data points.

        :param curve: Specifies which curve to configure (21-28 for inputs 1-8).
        :param units_val: List of sensor unit values for this input.
        :param temp_val: List of temperature values corresponding to unit values above.
        """
        ind = 0
        for uval in units_val:
            self.set_cal_curve_pt(curve, ind, uval, temp_val[ind])
            ind += 1
