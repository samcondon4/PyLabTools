from . import hw
from . import control
from . import measure
from . import procedures


INSTRUMENT_SUITE = [
    hw.mono,
    #hw.sr830,
    hw.readout
]

CONTROLLERS = [
    #control.LockinLogCntrl,
    control.SpecCalProcCntrl,
    control.NoiseProcCntrl,
    control.MonoController,
    #control.Sr830Controller
]

VIEWERS = [
    measure.LockinViewer
]

RECORDERS = [
    #measure.LockinCsvLog,
    measure.SpecCalCsvLog,
    measure.NoiseCsvLog,
]

PROCEDURES = [
    #measure.LockinLogProc,
    measure.SpecCalProc,
    measure.NoiseProc
]
