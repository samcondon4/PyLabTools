""" SPHEREx QM FPA Testing Procedures
"""
import time
import logging
import datetime

import spherexlabtools.log as slt_log
from spherexlabtools.procedures import Procedure, LoggingProcedure
from spherexlabtools.parameters import IntegerParameter, FloatParameter, Parameter, ListParameter, BooleanParameter


log_name = f'%s.%s' % (slt_log.LOGGER_NAME, __name__.split('.')[-1])
logger = logging.getLogger(log_name)


DEBUG = False
TS_FMT = '%Y%m%d_%H%M%S'


class FpaTestProcedure(Procedure):
    """ Baseclass for Procedures that run QMFPA exposures.
    """

    light_source = Parameter('Light Source', default='SLS301F')
    cryo_shutter = ListParameter('Cryo Shutter', default='Open', choices=[
        'Open',
        'Closed',
    ])
    exposures = IntegerParameter('Exposures', default=1)
    exposure_time = IntegerParameter('Exposure Time', default=30)
    padding_time = IntegerParameter('Padding Time', default=17)
    surcnt = IntegerParameter('SUR Count', default=393)
    surlim = IntegerParameter('SUR Limit', default=400)
    comment = Parameter('Comment', default='')
    generate_fits = IntegerParameter('Generate FITS', default=1)
    run_line_fit = IntegerParameter('Run Line Fit', default=1)
    det_idsn = Parameter('Detector ID-SN', default='04-22407')

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.readout = self.hw.readout
        self.data = {
            'fileid': '',
            'filename': '',
            'timestamp': '',
        }
        self.meta = {
            'detid': '',
            'detsn': '',
            'start': '',
            'surcnt': 393,
            'exposure_time': 10.0,
            'miscval': '',
            'miscset': None,
        }
        self._rg_prepend_override = None
        self.i = 0

        # - detector id/sn attributes - #
        self.detid = None
        self.detsn = None

    def startup(self):
        super().startup()
        # - resolve the detector id/sn from the det_idsn parameter check for user input errors and log -------------- #
        det_idsn_split = self.det_idsn.split('-')
        error_msg = ''
        # - check the length of the detector idsn argument - #
        if len(self.det_idsn) != 8:
            error_msg += 'incorrect length argument for det-idsn. Should have received 8 characters, but %i were ' \
                         'provided' % len(self.det_idsn)
        # - check the detector id - #
        try:
            self.detid = '%02i' % int(det_idsn_split[0])
        except ValueError:
            error_msg += '\nnon-integer value %s provided for detector id! Detector id must be an integer argument!' % \
                         (det_idsn_split[0])

        # - check the detector serial number - #
        try:
            self.detsn = '%05i' % int(det_idsn_split[1])
        except ValueError:
            error_msg += '\nnon-integer value %s provided for detector serial number! Detector serial number must be' \
                         ' an integer argument!'
        except IndexError:
            error_msg += '\nunable to parse the det-idsn argument. Did you forget the hyphen (-) separator?'

        # - if an error was found in the det-idsn argument, then log it and stop procedure execution ----------------- #
        if not error_msg == '':
            logger.error(error_msg)
            self.stop()

    def execute(self):

        for iExp in range(self.exposures):

            # - check if the 'Abort Procedure' button was pressed. -------------------------------------------------- #
            if self.should_stop():
                break

            # - get a timestamp and start an exposure --------------------------------------------------------------- #
            if not DEBUG:
                # - note, the readout instrument driver generates a timestamp internally, and this is returned into
                # - readout_response (along with other readout information)
                nofits = {1: 0, 0: 1}[self.generate_fits]
                logger.info(
                    'starting exposure with: TIME=%s; COMMENT=%s; NOFITS=%s; DETID=%s; DETSN=%s;' %
                    (str(self.padding_time + self.exposure_time), self.comment, nofits, self.detid, self.detsn)
                )
                readout_response = self.readout.start_exposure(self.padding_time + self.exposure_time, self.comment,
                                                               nofits=nofits, pend_for_complete=True, detid=self.detid,
                                                               detsn=self.detsn, surcnt=self.surcnt)
                readout_response = readout_response['testcom']
                logger.info(
                    f'exposure complete. Received: {readout_response}'
                )

            else:
                timestamp = datetime.datetime.now().strftime(TS_FMT)
                nofits = {1: 0, 0: 1}[self.generate_fits]
                logger.info(
                    'starting exposure with: TIME=%s; COMMENT=%s; NOFITS=%s; DETID=%s; DETSN=%s;' %
                    (str(self.padding_time + self.exposure_time), self.comment, nofits, self.detid, self.detsn)
                )
                readout_response = {
                    'fileid': 'ID',
                    'filename': 'SPXFILE',
                    'detid': self.detid,
                    'detsn': self.detsn,
                    'start': 'rob1',
                    'surcnt': 393,
                    'exposure': 10,
                    'comment': 'asdf',
                    'nofits': 1,
                    'miscval': '[393, 400, 1, 2, 3, 4]',
                    'timestamp': timestamp
                }
                logger.info(
                    f'exposure complete. Received: {readout_response}'
                )
                #time.sleep(self.exposure_time + self.padding_time)

            # - update the data dictionary ------------------------------------ #
            self.data['fileid'] = readout_response.pop('fileid')
            self.data['filename'] = readout_response.pop('filename')
            self.data['timestamp'] = readout_response.pop('timestamp')

            # - update the metadata dictionary ------------------------------------ #
            self.meta['exposure_time'] = readout_response.pop('exposure')
            self.meta['miscval'] = str(readout_response.pop('miscval'))
            self.meta.update(readout_response)

            # - write out the exposure parameters --------------------------------- #
            self.emit('exposure', self.data, meta=self.meta)
            #time.sleep(0.1)


class SpectralCalProcedure(FpaTestProcedure):
    """ Procedure to run full spectral cal.
    """

    mono_shutter = ListParameter('Mono Shutter', default='Open', choices=[
        'Open',
        'Closed'
    ])
    mono_shutter_map_f = {'Open': 1, 'Closed': 0, '': ''}
    mono_shutter_map_b = {v: k for k, v in mono_shutter_map_f.items()}
    mono_osf = Parameter('Mono OSF', default='Auto')
    mono_grating = Parameter('Mono Grating', default='Auto')
    mono_wavelength = FloatParameter('Mono Wavelength (um)', default=0.5)
    mono_back_slit = IntegerParameter('Mono Back Slit (um)', default=500)
    mono_front_slit = IntegerParameter('Mono Front Slit (um)', default=500)
    ndf_position = IntegerParameter('NDF Position', default=1)

    # - sleep parameters ----- #
    mono_set_sleep = FloatParameter('Mono Set Sleep Time', default=0)
    lockin_tc_sleep = FloatParameter('Lockin TC Sleep Time', default=6)

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.mono = self.hw.mono

    def startup(self):
        super().startup()
        # - set the monochromator parameters -------------------------------------------------------------------- #
        if not DEBUG:
            logger.info(
                'setting mono params: OSF=%s; GRATING=%s; WAVE=%s; SHUTTER=%s' % (
                    str(self.mono_osf), str(self.mono_grating), str(self.mono_wavelength), str(self.mono_shutter)
                )
            )
            self.mono.osf = self.mono_osf if self.mono_osf == 'Auto' else int(self.mono_osf)
            self.mono.grating = self.mono_grating if self.mono_grating == 'Auto' else int(self.mono_grating)
            self.mono.wavelength = self.mono_wavelength
            self.mono.shutter = self.mono_shutter_map_f[self.mono_shutter]

            # - sleep after setting monochromator parameters -------- #
            time.sleep(self.mono_set_sleep)

            # - query received values ------- #
            shutter = self.mono.shutter
            osf = self.mono.osf
            grating = self.mono.grating
            wavelength = self.mono.wavelength

            logger.info(
                'received mono params: OSF=%s; GRATING=%s; WAVE=%s; SHUTTER=%s' % (
                    str(osf), str(grating), str(wavelength), str(shutter)
                )
            )

        else:
            shutter = 1
            osf = 2
            grating = 2
            wavelength = 1.0

        # - read the resulting mono parameters, update metadata dictionary - #
        meta_dict = {
            'mono_shutter': self.mono_shutter_map_b[shutter],
            'mono_osf': osf,
            'mono_grating': grating,
            'mono_wavelength': wavelength,
            'ndf_position': None,
        }
        self.meta.update(meta_dict)
        time.sleep(self.lockin_tc_sleep)

    def shutdown(self):
        self.mono.shutter = 0
        super().shutdown()


class LockinLogging(LoggingProcedure):
    """ Subclass of the logging procedure implemented to record timestamps to associate with lockin sampling.
    """

    detector = Parameter('Reference Detector ID', default='PDA20H')
    time_constant = FloatParameter('Time Constant', default=1)
    sensitivity = FloatParameter('Sensitivity', default=0.5)

    def __init__(self, cfg, exp, data, meta, **kwargs):
        super(LockinLogging, self).__init__(cfg, exp, data, meta, **kwargs)
        self.lockin = self.hw.sr830

    def startup(self):
        self.lockin.sensitivity = self.sensitivity
        self.lockin.time_constant = self.time_constant
        super().startup()

    def execute(self):
        while not self.should_stop():
            ts = datetime.datetime.now()
            self.data_dict['timestamp'] = ts
            for inst, param in self.data_params:
                inst = getattr(self.hw, inst)
                val = getattr(inst, param)
                self.data_dict[param] = val
            self.emit(self.record, self.data_dict, meta=self.meta_dict)
            time.sleep(1 / self.sample_rate)
