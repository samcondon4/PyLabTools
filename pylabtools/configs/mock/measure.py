#from .sql_recorders import *

# - viewers -------------------------------------- #
FrameView = {
    'instance_name': 'frame_view',
    'type': 'ImageViewer',
}

BpView = {
    'instance_name': 'baseplate_view',
    'type': 'LineViewer',
    'params': {
        'left': 'Temperature (K)',
        'bottom': 'Sample',
    },
    'kwargs': {
        'lines': {
            'plate_temperature': 'r',
        }
    }
}

HistView = {
    'instance_name': 'histogram_view',
    'type': 'HistogramViewer',
}

# - recorders -------------------------------------------- #
FitsArchive = {
    'instance_name': 'fits_archive',
    'type': 'FITSRecorder',
    'kwargs': {
        'label_datacols': True
    }
}

Archive = {
    'instance_name': 'archive',
    'type': 'CSVRecorder',
}

TempCsv = {
    'instance_name': 'temp_csv',
    'type': 'CSVRecorder',
    'params': {
        '_rgroup_val_prepend_str': 'test_'
    }
}


# - procedures -------------------------------------------- #
HeaterMeasureProc = {
    'instance_name': 'heater_proc',
    'type': 'HeaterProc',
    'hw': ['camera', 'temp_controller'],
    'records': {
        'live_frame': {'viewer': 'frame_view'},
        #'frame_hist': {'viewer': 'histogram_view'},
        'live_baseplate': {'viewer': 'baseplate_view'},
        'archive': {'recorder': 'temp_csv'}
    },
    #'pipes': ['heater_measure_rg']
}

BasicTempLogProc = {
    'instance_name': 'basic_temp',
    'type': 'LoggingProcedure',
    'hw': ['temp_controller'],
    'records': {
        'temp_log': {'viewer': 'baseplate_view'},
    },
    'kwargs': {
        'data': {
            'temp_controller': ['plate_temperature']
        },
        'meta': {
            'temp_controller': ['heater_voltage']
        }
    },
    #'pipes': ['heater_measure_rg']
}

CamViewProc = {
    'instance_name': 'CamViewProc',
    'type': 'LoggingProcedure',
    'hw': ['camera'],
    'records': {
        'image': {'viewer': 'histogram_view'}
    },
    'kwargs': {
        'data': {
            'camera': ['frame']
        },
        'meta': {}
    }
}

