""" heater_measurements:

    Module implementing the procedure for the fake experiment in the step-by-step configuration tutorial
"""

import time
import logging
import datetime
import numpy as np
import pandas as pd
from spherexlabtools.procedures import Procedure
from spherexlabtools.parameters import FloatParameter


class HeaterProc(Procedure):

    heater_voltage = FloatParameter("Heater Voltage", default=0, units="V", minimum=0, maximum=10)
    sample_time = FloatParameter("Sample Time", default=10, units="s")
    sample_rate = FloatParameter("Sample Rate", default=1, units="hz")

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.cam = exp.hw.camera
        self.temp_control = exp.hw.temp_controller
        self.baseplate_temp_arr = None
        self.heater_voltage_arr = None
        self.heater_ir_emission_arr = None
        self.timestamps_arr = None
        self.meta_dict = None

    def startup(self):
        """ Set the heater voltage.
        """
        super().startup()
        self.temp_control.heater_voltage_arr = self.heater_voltage_arr
        # - set up the vectors for measured quantities - #
        samples = int(self.sample_time * self.sample_rate)
        self.baseplate_temp_arr = np.zeros(samples)
        self.heater_voltage_arr = np.zeros_like(self.baseplate_temp_arr)
        self.heater_ir_emission_arr = np.zeros_like(self.baseplate_temp_arr)
        self.timestamps_arr = np.zeros_like(self.heater_ir_emission_arr)
        self.meta_dict = {
            "camera_gain": [self.cam.gain],
            "camera_frame_width": [self.cam.frame_width],
            "camera_frame_height": [self.cam.frame_height],
        }

    def execute(self):
        for i in range(len(self.baseplate_temp_arr)):
            if self.should_stop():
                break

            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.%f")
            frame = self.cam.frame
            baseplate = self.temp_control.plate_temperature

            # - emit live data for real-time feedback - #
            self.emit("live_frame", frame)
            #self.emit('frame_hist', frame)
            #self.emit("live_baseplate", baseplate)

            # - write to lists for archival - #
            self.heater_voltage_arr[i] = self.heater_voltage
            self.baseplate_temp_arr[i] = baseplate
            self.heater_ir_emission_arr[i] = self.get_heater_ir(frame)
            self.timestamps_arr[i] = ts

            time.sleep(1 / self.sample_rate)

        data_dict = {
            "baseplate_temp": self.baseplate_temp_arr,
            "heater_ir_emission": self.heater_ir_emission_arr,
            "heater_voltage": self.heater_voltage_arr,
            "timestamp": self.timestamps_arr
        }
        self.emit("archive", pd.DataFrame(data_dict), meta=pd.DataFrame(self.meta_dict), timestamp=False)

    @staticmethod
    def get_heater_ir(frame):
        """ Calculate heater IR emission from an image.

        :param frame:
        :return:
        """
        return frame.mean()
