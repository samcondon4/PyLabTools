import time
import queue
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText

from spherexlabtools.log import LOGGER_NAME
from spherexlabtools.parameters import FloatParameter, Parameter
from spherexlabtools.procedures import Procedure, AlertProcedure


# - Globals ----------------------------------------------- #
LogName = '%s.%s' % (LOGGER_NAME, __name__.split('.')[-1])
Logger = logging.getLogger(LogName)
HkToAlert_Q = queue.Queue()


class KasiHkLog(Procedure):
    sample_rate = FloatParameter('Sample Rate', units='hz', default=3)
    ls218_channels = [1, 2, 3, 4, 5, 6, 7, 8]
    ls224_channels = ['A', 'B'] + ['C%i' % i for i in range(1, 6)] + ['D%i' % i for i in range(1, 6)]

    def __init__(self, cfg, exp, **kwargs):
        self.vacuum_gauge = exp.hw.vacuum_gauge
        self.vacuum_gauge_low = exp.hw.vacuum_gauge_low
        self.ls218 = exp.hw.ls218
        self.ls224_2 = exp.hw.ls224_2
        self.ls224_3 = exp.hw.ls224_3
        super().__init__(cfg, exp, **kwargs)

    def execute(self):
        """ Log temperature data.
        :return:
        """
        while not self.should_stop():
            dt_now = datetime.now()
            pressure = self.vacuum_gauge.pressure[-1]
            pressure_low = self.vacuum_gauge_low.pressure[-1]
            ls218_temps = self.ls218.input_0.kelvin
            ls224_2_temps = self.ls224_2.input_0.kelvin
            ls224_3_temps = self.ls224_3.input_0.kelvin
            ls218_dict = {
                'ls218_%s' % self.ls218_channels[i]: ls218_temps[i] for i in range(len(self.ls218_channels))
            }
            ls224_2_dict = {
                'ls224_2_%s' % self.ls224_channels[i]: ls224_2_temps[i] for i in range(len(self.ls224_channels))
            }
            ls224_3_dict = {
                'ls224_3_%s' % self.ls224_channels[i]: ls224_3_temps[i] for i in range(len(self.ls224_channels))
            }
            archive_dict = dict(ls224_2_dict, **ls224_3_dict)
            archive_dict.update(ls218_dict)
            archive_dict.update({'kasi_vacuum_shell_pressure': pressure,
                                 'kasi_vacuum_shell_pressure_low': pressure_low,
                                 'datetime': dt_now})

            # - send values to the Alarm Queue - #
            HkToAlert_Q.put(archive_dict)

            # - send out to viewers and recorders ------------------------------------------- #
            self.emit('pressure_view', {'kasi_vacuum_shell_pressure': pressure,
                                        'kasi_vacuum_shell_pressure_low': pressure_low})
            self.emit('ls218_view', ls218_dict)
            self.emit('ls224_2_view', ls224_2_dict)
            self.emit('ls224_3_view', ls224_3_dict)
            self.emit('kasi_hk_log', archive_dict)

            time.sleep(1 / self.sample_rate)


class KASIHkAlert(AlertProcedure):
    """ Subclass the basic AlertProcedure to return values from the HkToAlert_Q queue object.
    """

    @staticmethod
    def get():
        return HkToAlert_Q.get()

