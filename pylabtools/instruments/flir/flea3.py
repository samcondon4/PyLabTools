import time

import PySpin
import logging
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set

logger = logging.getLogger(__name__)


class FlirInstrument:
    """ Subclass of the pymeasure Instrument object that overrides the property factories
        for property getting/setting specific to the Flir Spinnaker API.
    """

    @staticmethod
    def control(node_name, node_type, docs,
                validator=lambda v, vs: v, values=(), map_values=False,
                get_process=lambda v: v, set_process=lambda v: v,
                ):
        """ Returns a property for the class based on the supplied name and type. This property
            may be set and read from the instrument.
        
        :param: node_name: Name of the property to get/set.
        :param: node_type: Type of the property to get/set.
        :param: docs: Docstring for the property. 
        :param: validator: A function that takes both a value and a group of valid values
                           and returns either a valid value or raises an exception when an
                           invalid value is provided.
        :param: values: A list, tuple, range, or dictionary of valid values that can be used
                        to map values if :code:`map_values` is True.
        :param: map_values: A boolean flag that determines if the values should be interpretted
                            as a mapping.
        :param: get_process: A function that take a value and allows processing
                            before value mapping, returning the processed value
        :param: set_process: A function that takes a value and allows processing
                            before value mapping, returning the processed value
        """
        nodeclass_dict = {
            "enum": PySpin.CEnumerationPtr,
            "cmd": PySpin.CCommandPtr,
            "float": PySpin.CFloatPtr,
            "bool": PySpin.CBooleanPtr,
            "int": PySpin.CIntegerPtr,
            "str": PySpin.CStringPtr
        }

        def fget(self):
            # get the node value with special handling for enum nodes. 
            node = nodeclass_dict[node_type](self.nodemap.GetNode(node_name))
            if node_type == "enum":
                val = node.GetCurrentEntry().GetSymbolic()
            else:
                val = get_process(node.GetValue())
            return val

        def fset(self, val):
            value = set_process(validator(val, values))
            # set the node value with special handling for enum nodes.
            node = nodeclass_dict[node_type](self.nodemap.GetNode(node_name))
            if node_type == "enum":
                entry = node.GetEntryByName(value).GetValue()
                node.SetIntValue(entry)
            else:
                node.SetValue(value)

        fget.__doc__ = docs

        return property(fget, fset)


class Flea3:
    # class level initialization #
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()

    # Analog Control properties #
    gain = FlirInstrument.control("Gain", "float", "This float property represents the camera gain.")
    gain_auto = FlirInstrument.control("GainAuto", "enum", "This enum property represents the state of the camera "
                                                           "auto gain. This property can be set with the following"
                                                           "values: 'Off', 'Once', 'Continuous'")
    blacklevel = FlirInstrument.control("BlackLevel", "float", "This float property represents the camera black level.")
    blacklevel_en = FlirInstrument.control("BlackLevelEnabled", "bool", "This boolean property represents the black "
                                                                        "level enabled flag.")
    gamma = FlirInstrument.control("Gamma", "float", "This float property represents the camera gamma level.")
    gamma_en = FlirInstrument.control("GammaEnabled", "bool", "This boolean property represents the camera gamma "
                                                              "correction enabled flag.")
    sharpness = FlirInstrument.control("Sharpness", "int", "This integer property represents the camear sharpness "
                                                           "level.")
    sharpness_en = FlirInstrument.control("SharpnessEnabled", "bool", "This boolean property represents the state of "
                                                                      "the camera sharpness enabled flag.")
    hue_en = FlirInstrument.control("HueEnabled", "bool", "This boolean property represents the camera hue correction "
                                                          "flag.")
    sat_en = FlirInstrument.control("SaturationEnabled", "bool", "This boolean property represents the saturation "
                                                                 "correction enabled flag.")

    # Acquisition Control properties #
    acquisition_mode = FlirInstrument.control("AcquisitionMode", "enum",
                                              "This enum property represents the state of the camera acquisition mode.",
                                              validator=strict_discrete_set, values=["SingleFrame", "MultiFrame",
                                                                                     "Continuous"])
    acquisition_frame_count = FlirInstrument.control("AcquisitionFrameCount", "int", "This integer property represents "
                                                                                     "the number of frames the camera "
                                                                                     "should acquire on the next "
                                                                                     "exposure.")
    acquisition_frame_rate = FlirInstrument.control("AcquisitionFrameRate", "float", "This float parameter represents "
                                                                                     "the number of frames the camera "
                                                                                     "should acquire per second.")
    acquisition_frame_rate_en = FlirInstrument.control("AcquisitionFrameRateEnabled", "bool", "Boolean parameter "
                                                                                              "representing the flag "
                                                                                              "allowing the frame rate "
                                                                                              "to be modified.")
    acquisition_frame_rate_auto = FlirInstrument.control("AcquisitionFrameRateAuto", "enum",
                                                         "Auto set acq. frame rate", validator=strict_discrete_set,
                                                         values=["Off", "Continuous"])
    exposure_mode = FlirInstrument.control("ExposureMode", "enum", "Enum property representing the exposure mode "
                                                                   "of the camera.")
    exposure_time = FlirInstrument.control("ExposureTime", "float", "Float property representing the time in seconds "
                                                                    "that the camera should take for each exposure.")
    exposure_auto = FlirInstrument.control("ExposureAuto", "enum",
                                           "Enum property representing the state of the exposure "
                                           "auto function on the camera.")

    # image format properties #
    offset_x = FlirInstrument.control("OffsetX", "int", "Integer property representing the camera x-pixel offset.")
    offset_y = FlirInstrument.control("OffsetY", "int", "Integer property representing the camera y-pixel offset.")
    exposure_height = FlirInstrument.control("Height", "int",
                                             "Integer property representing the height in pixels of an "
                                             "image.")
    exposure_width = FlirInstrument.control("Width", "int", "Integer property representing the width in pixels of an "
                                                            "image.")

    pixel_format = FlirInstrument.control("PixelFormat", "enum", "Enum property that can be set with the following"
                                                                 "values: ['Mono8', 'Mono12Packed', 'Mono16']",
                                          values=["Mono8", "Mono16", "Mono12Packed"])

    def __init__(self, resource):
        """ Initialize the interface to the camera object provided.
        :param: resource: PySpin Camera object.
        """
        # initialize camera # 
        self.cam = resource
        self.cam.Init()

        # get nodemaps #
        self.nodemap_tldevice = resource.GetTLDeviceNodeMap()
        self.nodemap = self.cam.GetNodeMap()

        # stream active flag #
        self._stream_active = False

    def get_frames(self, n=1, timeout=35000):
        """ This method retrieves a set number of frames from the camera.
        :param: n: Integer parameter specifying the number of frames to retrieve.
        :param: timeout: Time in miliseconds to wait before timing out during image acquisition. 
        :return: frames: List of all of the frames acquired from the camera during acquisition. 
        """
        if n > 1 and type(n) is int:
            self.acquisition_mode = "MultiFrame"
            self.acquisition_frame_count = int(n)
            frames = [None for _ in range(n)]
            self.cam.BeginAcquisition()
            for i in range(n):
                im_result = self.cam.GetNextImage(timeout)
                frames[i] = im_result.GetNDArray()
                im_result.Release()
        else:
            self.acquisition_mode = "SingleFrame"
            self.cam.BeginAcquisition()
            time.sleep(0.1)
            im_result = self.cam.GetNextImage(timeout)
            time.sleep(0.1)
            frames = im_result.GetNDArray()
            im_result.Release()
        self.cam.EndAcquisition()
        return frames

    @property
    def stream_active(self):
        """ This boolean property represents the state of camera streaming.
        """
        return self._stream_active

    @stream_active.setter
    def stream_active(self, val):
        self._stream_active = bool(val)

    @property
    def latest_frame(self):
        """ Property representing the frame retrieved from the camera. If the camera is not in streaming
        mode, then get_frames() is called to return a frame.
        """
        if self.stream_active:
            latest_frame = self.get_stream_frame()
        else:
            latest_frame = self.get_frames()
        return latest_frame

    def start_stream(self):
        """ This method starts continuous frame streaming.
        """
        logger.debug("Starting camera stream!")
        # set acquisition mode #
        self.acquisition_mode = "Continuous"
        self.cam.BeginAcquisition()
        self.stream_active = True

    def stop_stream(self):
        """ This method stops continuous frame streaming.
        """
        logger.debug("Stopping camera stream!")
        self.cam.EndAcquisition()
        self.acquisition_mode = "SingleFrame"
        self.stream_active = False

    def get_stream_frame(self, timeout=35000):
        """ This method retrieves the latest frame and returns it as a numpy array when
            the camera is continuously streaming data.
        
        :param timeout: Time in milliseconds before an image acquisition event should time-out. 
        """
        im = self.cam.GetNextImage(timeout)
        im_arr = im.GetNDArray()
        im.Release()
        return im_arr

    def shutdown(self):
        """ Releases communication with camera, bringing it to a safe and stable state."""
        self.cam.DeInit()
        del self.cam
        self.cam_list.Clear()
        self.system.ReleaseInstance()
