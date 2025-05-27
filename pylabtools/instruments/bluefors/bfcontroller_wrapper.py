""" bfcontroller_wrapper.py

Implement a minimal wrapper around the BlueFTController class
to achieve compatibility with SPHERExLabTools.

Sam Condon, 2025-05-24
"""
from .BlueforsController import BlueFTController

class TControlMeta(type):
    def __new__(cls, name, bases, namespace):
        def make_properties(i):
            def resistance_method(self):
                return self.get_channel_resistance(i)
            def temperature_method(self):
                return self.get_channel_temperature(i)
            resistance_property = property(fget=resistance_method)
            temperature_property = property(fget=temperature_method)
            return (resistance_property, temperature_property)

        # - define the properties for all 8 channels - #
        for i in range(1, 9):
            rchannel, tchannel = make_properties(i)
            namespace[f"channel_{i}_resistance"] = rchannel
            namespace[f"channel_{i}_temperature"] = tchannel

        return super().__new__(cls, name, bases, namespace)
        
class TControllerWrapper(BlueFTController, metaclass=TControlMeta):

    def __init__(
        self,
        ip: str,
        mixing_chamber_channel_id: int = None,
        port: int = 49098,
        key: str = None,
        debug: bool = False,
    ):

        super().__init__(ip, mixing_chamber_channel_id, port, key, debug)
    
    # - MXC Channels - #
    @property
    def mxc_temperature(self):
        return self.get_mxc_temperature()

    @property
    def mxc_resistance(self):
        return self.get_mxc_resistance()
