""" This module provides the driver for the Oriel/Newport Cs260 Monochromator.
"""
import time
import subprocess as sp
from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set


class CS260:

    shutter = Instrument.control("SHUTTER?", "SHUTTER %s", """String property representing the current
    shutter setting. This property can be set.""",
                                 validator=strict_discrete_set,
                                 values={0: "C", 1: "O", "0": "C", "1": "O"},
                                 map_values=True,
                                 set_process=int)

    units = Instrument.control("UNITS?", "UNITS %s", """String property representing the current units of the
    wavelength setting. This property can be set with "NM" for nanometers and "UM" for microns.""",
                               validator=strict_discrete_set,
                               values=["NM", "UM"])

    _grating = Instrument.control("GRAT?", "GRAT %i", """Integer property representing
    the current grating setting. This property can be set.""",
                                  validator=strict_discrete_set,
                                  values=[1, 2, 3],
                                  get_process=lambda g: g.split(",")[0])

    _osf = Instrument.control("FILTER?", "FILTER %i", """Integer property representing the current
    order sort filter setting. This property can be set.""",
                              validator=strict_discrete_set,
                              values=[1, 2, 3, 4, 5, 6])

    _wavelength = Instrument.control("WAVE?", "GOWAVE %f", """Float property representing
    the current wavelength setting in um. or nm. This property can be set.""")

    # grating transition wavelengths #
    GRATING_RANGES = {
        1: [0, 1.4],
        2: [1.4, 2.5],
        3: [2.5, 1000]
    }
    OSF_RANGES = {
        6: [0, 0.7],
        1: [0.7, 1.4],
        2: [1.4, 1.75],
        3: [1.75, 2.5],
        4: [2.5, 3.7],
        5: [3.7, 1000]
    }

    def __init__(self, resourceName, pend_time=3, **kwargs):
        """ Initialize communication with the CS260 monochromator. Note that the USB interface
        of this device utilizes a set of Newport proprietary DLL drivers. The provided C++EXE.exe
        file wraps the communication with these files in a compiled binary that python can execute
        with the subprocess (:module:`.sp`) module.

        :param resourceName: Path to the compiled exe driver for DLL utilization. This should remain static.
        """

        self.resource_name = resourceName
        self.cs260_open()
        self.units = "UM"
        self.osf_auto = False
        self.grating_auto = False
        self.pend_time = pend_time

    def update_grating_and_osf_from_wavelength(self, wave):
        """ Update the grating and order sort filter based on a wavelength. This method is
        used as a **get_process** for when the grating/osf settings are set to auto.
        """
        if self.osf_auto:
            cur_osf = self._osf
            for osf, rnge in self.OSF_RANGES.items():
                if rnge[0] < wave <= rnge[1] and osf != cur_osf:
                    self._osf = int(osf)

        if self.grating_auto:
            cur_g = self._grating
            for g, rnge in self.GRATING_RANGES.items():
                if rnge[0] < wave <= rnge[1] and g != cur_g:
                    self._grating = int(g)

    @property
    def grating(self):
        """Integer property representing the current grating setting. This property can be set."""
        return self._grating

    @grating.setter
    def grating(self, g):
        if g == "Auto":
            self.grating_auto = True
        else:
            self.grating_auto = False
            self._grating = int(g)

    @property
    def osf(self):
        """Integer property representing the current osf setting. This property can be set."""
        return self._osf

    @osf.setter
    def osf(self, osf):
        if osf == "Auto":
            self.osf_auto = True
        else:
            self.osf_auto = False
            self._osf = int(osf)

    @property
    def wavelength(self):
        """Float property representing the current wavelenth setting. This property can be set."""
        return self._wavelength

    @wavelength.setter
    def wavelength(self, w):
        w = float(w)
        self.update_grating_and_osf_from_wavelength(w)
        self._wavelength = w

    # C++ EXE Methods ###################################################################
    def cs260_open(self):
        cp = sp.run([self.resource_name, 'open'], capture_output=True, check=True)
        return cp

    def close(self):
        cp = sp.run([self.resource_name, 'close'], capture_output=True, check=True)
        return cp

    def list(self):
        cp = sp.run([self.resource_name, 'list'], capture_output=True, check=True)
        return cp

    def write(self, cmd):
        args = [self.resource_name, 'write', cmd]
        if not cmd == "GRAT Auto" and not cmd == "OSF Auto":
            cp = sp.run(args, capture_output=True, check=True)
        else:
            cp = None
        return cp

    def values(self, cmd):
        args = [self.resource_name, 'ask', cmd]
        cp = sp.run(args, capture_output=True, check=True)
        return cp.stdout.decode("utf-8")
