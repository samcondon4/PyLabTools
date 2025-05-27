from . import hw
from . import control
from . import measure
from . import procedures
from . import instruments

INSTRUMENT_SUITE = [
    hw.Collimator,
    #hw.collimator_gauge,
    hw.Mscope,
    hw.Camera,
    hw.Relay,
]

VIEWERS = [
    measure.CamView,
    measure.CollimatorCamView,
    measure.CollimatorCamViewAvg,
]

RECORDERS = [
    measure.CollimatorHDF,
    measure.CamViewHDF,
]

CONTROLLERS = [
    control.MScope_Controller,
    control.Collimator_Controller,
    control.CamViewProc_Cntrl,
    control.CollimatorCalProc_Cntrl,
    control.Relay_Controller
]

PROCEDURES = [
    measure.CamViewProc,
    measure.CollimatorCalProc
]
