from . import hw
from . import control
from . import measure
from . import recorders
from . import procedures

VIEWERS = [
    measure.pressure_view,
    measure.ls218_view,
    measure.ls224_2_view,
    measure.ls224_3_view,
]

RECORDERS = [
    measure.kasi_hk_csv
]

PROCEDURES = [
    measure.temp_logging,
    measure.alert_system
]

CONTROLLERS = [
    control.temp_proc_cntrl,
    control.alert_cntrl
]

INSTRUMENT_SUITE = [
    hw.vacuum_gauge,
    hw.vacuum_gauge_low, 
    hw.lakeshore218,
    hw.lakeshore224_2,
    hw.lakeshore224_3,
]
