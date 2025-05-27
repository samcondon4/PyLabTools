from . import hw
from . import control
from . import measure
from . import procedures
from . import instruments


VIEWERS = [
    measure.FrameView,
    measure.BpView,
    #measure.HistView,
]

RECORDERS = [
    #measure.FitsArchive
    measure.Archive,
    measure.TempCsv
]

PROCEDURES = [
    measure.HeaterMeasureProc,
    measure.BasicTempLogProc,
    #measure.CamViewProc
]

CONTROLLERS = [
    control.CamCntrl,
    control.TempLogProcCntrl,
    control.HeaterProcCntrl,
    #control.CamViewProcCntrl
]

INSTRUMENT_SUITE = [
    hw.TempController,
    hw.Camera
]

