""" This module implements a set of helpers to build lakeshore 336 instrument properties.
"""

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import truncated_range, strict_discrete_set


class Lakeshore336PropHelpers:

    @staticmethod
    def get_mout_prop(channel):
        """ Create a new manual output channel property.
        """

        return Instrument.control(f"MOUT? {channel}", f"MOUT {channel},%f", f"""Manual output setting for channel 
                                  {channel}. """,
                                  validator=truncated_range,
                                  values=[0, 100])

    @staticmethod
    def get_12_range_prop(channel):
        """ Create a new output range property for channels 1 or 2.
        """

        return Instrument.control(f"RANGE? {channel}", f"RANGE {channel},%i", f""" Output range setting for channels
                                    1 and 2""",
                                  validator=strict_discrete_set,
                                  values={"Off": 0, "Low": 1, "Medium": 2, "High": 3},
                                  map_values=True)

    @staticmethod
    def get_34_range_prop(channel):
        """ Create a new output range property for channels 3 or 4.
        """

        return Instrument.control(f"RANGE? {channel}", f"RANGE {channel},%i", f""" Output range setting for channels
                                    1 and 2""",
                                  validator=strict_discrete_set,
                                  values={"Off": 0, "On": 1},
                                  map_values=True)

    @staticmethod
    def get_setpoint_prop(channel):
        """ Create a new PID setpoint property.
        """

        return Instrument.control(f"SETP? {channel}", f"SETP {channel},%f", """ Control the heater setpoint. """,
                                  validator=truncated_range,
                                  values=[10, 320])

    @staticmethod
    def get_pid_prop(channel):
        """ Create a new PID value query property.
        """

        return Instrument.measurement(f"PID? {channel}", """ Query for the channel PID values. """)

    @staticmethod
    def get_outmode_prop(channel):
        """
        """

        return Instrument.measurement(f"OUTMODE? {channel}", """ Query the output mode. """)
