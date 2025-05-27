import time
import logging
import datetime
import numpy as np
from spherexlabtools.procedures import Procedure
from spherexlabtools.parameters import FloatParameter, IntegerParameter, BooleanParameter

logger = logging.getLogger(__name__)


class CamProc(Procedure):
    """ Base class defining microscope camera startup and shutdown methods.
    """

    refresh_rate = FloatParameter("Exposure Time us.", default=100000, minimum=30, maximum=5929218.769073486)

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.cam = self.hw.Camera

    def startup(self):
        Procedure.startup(self)
        try:
            self.cam.acquisition_frame_rate_en = False
            self.cam.exposure_time = self.refresh_rate
        except AttributeError:
            pass


class CamViewProc(CamProc):

    wait_time = FloatParameter('Wait Time', default=0)
    record_period = FloatParameter('Record Period', default=1)
    record_frames = IntegerParameter('Record Frames', default=0)
    stream_mode = BooleanParameter('Stream Mode', default=False)
    continuous_frames = BooleanParameter('Continuous Frames', default=True)

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.recorded_frames = 0
        self.start_time = None
        self.time_delta = None
        self.recording = False

    def startup(self):
        super().startup()
        if self.stream_mode:
            self.cam.start_stream()

        if self.record_frames > 0:
            self.recording = True
        self.start_time = datetime.datetime.now()
        self.time_delta = datetime.timedelta(seconds=self.record_period)

    def execute(self):
        while not self.should_stop():
            ts = datetime.datetime.now()
            if self.continuous_frames:
                image = self.cam.latest_frame
                self.emit('image_view', image)
            if self.recording and self.recorded_frames < self.record_frames:
                if not self.continuous_frames:
                    image = self.cam.latest_frame
                    self.emit('image_view', image)
                self.emit('image_record', image, meta={'timestamp': ts})
                self.recorded_frames += 1
            elif self.recording and self.recorded_frames >= self.record_frames:
                self.recording = False
                self.start_time = datetime.datetime.now()
                self.recorded_frames = 0
            elif (not self.recording) and (ts - self.start_time) > self.time_delta:
                self.recording = True

            time.sleep(self.wait_time)

    def shutdown(self):
        if self.cam.stream_active:
            self.cam.stop_stream()


class CollimatorCalProc(CamProc):
    """ Main collimator focus measurement procedure.
    """

    focus_position = FloatParameter("Absolute Focus Position mm.", default=0)
    frames_per_image = IntegerParameter("Frames Per Image", default=10)
    images = IntegerParameter("Images", default=1)
    wait_time = FloatParameter("Wait Time", default=0)
    light_frame = IntegerParameter("Light Frame", default=1)

    def __init__(self, cfg, exp, **kwargs):
        """
        """
        super().__init__(cfg, exp, **kwargs)
        self.mscope = self.hw.Mscope
        self.inst_params = {}

    def startup(self):
        """ Override startup to get instrument parameters
        """
        super().startup()
        # - move the focuser and wait for its motion to complete - #
        self.mscope.absolute_position = self.focus_position
        self.mscope.fstage_wait_for_completion()

        # - set camera exposure time - #
        self.cam.acquisition_frame_rate_en = False
        self.cam.exposure_time = self.refresh_rate

        # - set the shutter state - #
        self.mscope.fstage_outputs = self.light_frame

        self.inst_params.update({"focus_position": self.mscope.absolute_position,
                                 "camera_gain": self.cam.gain,
                                 "camera_exposure_time": self.cam.exposure_time,
                                 "light_frame": self.mscope.fstage_outputs})

    def execute(self):

        frame_width = self.cam.exposure_width
        frame_height = self.cam.exposure_height

        # take a set of images averaged over several frames #
        for _ in range(int(self.images)):
            if self.should_stop():
                break
            image = np.zeros([frame_height, frame_width], dtype=np.float64)
            for __ in range(self.frames_per_image):
                if self.should_stop():
                    break
                time.sleep(self.wait_time)
                exp = self.cam.latest_frame
                image = image + (exp / self.frames_per_image)
                # write out to viewers #
                self.emit("frame", exp)
                self.emit("frame_avg", image)

            self.emit("image", image, meta=self.inst_params)
