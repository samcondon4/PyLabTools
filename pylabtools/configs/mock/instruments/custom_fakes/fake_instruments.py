import time
import threading
import numpy as np
from pymeasure.instruments.fakes import SwissArmyFake


# - fake instrument configuration parameters - #
LOCK = threading.Lock()
HEATER_VRANGE = [0, 10]
HEATER_VOLTAGE = 0
HEATER_VNOISE = 1e-3
PLATE_TRANGE = [40, 100]
PLATE_TEMP = 40
PLATE_TNOISE = 0.2


class TemperatureController(SwissArmyFake):
    """ Fake temperature controller driver with a temperature input and heater output.
    """

    def __init__(self, wait=.1, **kwargs):
        super().__init__(wait, **kwargs)

    @property
    def heater_voltage(self):
        """ Add noise to the heater output voltage and return.
        """
        global HEATER_VOLTAGE, HEATER_VNOISE, LOCK
        with LOCK:
            time.sleep(self._wait)
            v_noise = np.random.uniform(-HEATER_VNOISE, HEATER_VNOISE, 1)
            HEATER_VOLTAGE += v_noise
            return HEATER_VOLTAGE

    @heater_voltage.setter
    def heater_voltage(self, value):
        """ Set the base heater voltage.
        :param value: voltage between the heater vrange values.
        """
        global HEATER_VRANGE, HEATER_VOLTAGE, PLATE_TEMP, LOCK
        with LOCK:
            time.sleep(self._wait)
            if HEATER_VRANGE[0] < value < HEATER_VRANGE[1]:
                HEATER_VOLTAGE = value
                heater_frac = HEATER_VOLTAGE / HEATER_VRANGE[-1]
                PLATE_TEMP = PLATE_TRANGE[0] + heater_frac*(PLATE_TRANGE[1] - PLATE_TRANGE[0])

    @property
    def plate_temperature(self):
        """ Return the temperature of the baseplate.

        :return: Baseplate temperature in Kelvin.
        """
        global PLATE_TEMP, PLATE_TNOISE, LOCK
        with LOCK:
            time.sleep(self._wait)
            t_noise = np.random.uniform(-PLATE_TNOISE, PLATE_TNOISE, 1)[0]
            PLATE_TEMP += t_noise
            return PLATE_TEMP


class Camera(SwissArmyFake):
    """ Fake Camera used to image the thermal emission of the heater.
    """

    def __init__(self, wait=0.1, **kwargs):
        super().__init__(wait, **kwargs)
        self._gain = 0

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, value):
        self._gain = value

