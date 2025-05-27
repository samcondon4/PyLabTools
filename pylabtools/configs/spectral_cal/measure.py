# - VIEWERS AND RECORDERS - #########################
LockinViewer = {
    'instance_name': 'LockinView',
    'type': 'LineViewer',
    'kwargs': {
        'lines': {
            'x': 'r',
            'y': 'g'
        }
    }
}

LockinCsvLog = {
    'instance_name': 'LockinLog',
    'type': 'CSVRecorder'
}

NoiseCsvLog = {
    'instance_name': 'NoiseCsvLog',
    'type': 'CSVRecorder',
    'params': {
        '_rgroup_val_prepend_str': 'noise_'
    }
}

SpecCalCsvLog = {
    'instance_name': 'SpecCalCsvLog',
    'type': 'CSVRecorder',
    'params': {
        '_rgroup_val_prepend_str': 'spec_'
    }
}

PersistenceCsvLog = {
    'instance_name': 'PersistenceCsvLog',
    'type': 'CSVRecorder'
}

# - PROCEDURES --------------------------------------------------------- #
LockinLogProc = {
    'instance_name': 'LockinLogProc',
    'type': 'LockinLogging',
    'hw': ['sr830'],
    'records': {
        'lockin_data': {'viewer': 'LockinView', 'recorder': 'LockinLog'}
    },
    'kwargs': {
        'data': {
            'sr830': ['x', 'y']
        },
        'meta': {
            'sr830': ['sensitivity', 'time_constant']
        }
    }
}

NoiseProc = {
    'instance_name': 'NoiseProcedure',
    'type': 'FpaTestProcedure',
    'hw': ['readout'],
    'records': {
        'exposure': {'recorder': 'NoiseCsvLog'}
    },
}

SpecCalProc = {
    'instance_name': 'SpectralCalProcedure',
    'type': 'SpectralCalProcedure',
    'hw': ['readout', 'mono'],
    'records': {
        'exposure': {'recorder': 'SpecCalCsvLog'}
    },
}
