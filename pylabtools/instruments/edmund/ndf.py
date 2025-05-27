"""ndf:

    This module implements the class:
        :class:`.NDF`
"""

import os
import clr
import sys
import logging
import numpy as np
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_range
sys.path.append(os.path.join(os.environ["SPHEREXLABTOOLS"], "spherexlabtools", "instruments", "edmund", "NDFWheel_DLLs"))
clr.AddReference("OptecHID_FilterWheelAPI")
from OptecHID_FilterWheelAPI import FilterWheels
from OptecHID_FilterWheelAPI import FilterWheel


logger = logging.getLogger(__name__)


class NDF(Instrument):
    """ Represents an Edmund Optics high speed filter wheel device.

    """
    validator = strict_discrete_range
    values = np.arange(1, 9)
    _cmd_sep = " "

    def __init__(self, rec_name=None):

        self.HSFW = FilterWheels().FilterWheelList[0]
        self.home()

    @property
    def position(self):
        """ Integer property representing the position of the filter wheel.
        """
        return self.HSFW.CurrentPosition

    @position.setter
    def position(self, pos):
        # run validator #
        value = NDF.validator(pos, self.values, self.values[-1] - self.values[-2])
        self.HSFW.CurrentPosition = value

    def home(self):
        """ Home the filter wheel.
        """
        self.HSFW.HomeDevice()

    def check_errors(self):
        """ Check the error state of the filter wheel.
        """
        err_state = self.HSFW.ErrorState
        if err_state != 0:
            logger.error(f"Error {err_state} seen on filter wheel")
        return err_state

    def write(self, cmd):
        """ Send a command to the filter wheel. Since position is the only property that can be
            set, this directly interfaces with the HSFW position property.

        :param cmd: Command to send to the filter wheel.
        :type cmd: str
        """
        cmd_split = cmd.split(self._cmd_sep)
        if cmd == "POS?":
            return self.HSFW.position
        elif len(cmd_split) > 1 and cmd_split[0] == "POS":
            self.HSFW.position = int(cmd_split[1])

