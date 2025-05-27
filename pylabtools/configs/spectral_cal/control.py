# - Monochromator control ----------------------------------------------------- #
MonoController = {
    'instance_name': 'MonoCntrl',
    'type': 'InstrumentController',
    'hw': 'mono',
    'control_parameters': [
        {'name': 'osf', 'type': 'list', 'limits': [1, 2, 3, 4, 5, 6, 'Auto']},
        {'name': 'grating', 'type': 'list', 'limits': [1, 2, 3, 'Auto']},
        {'name': 'wavelength', 'type': 'str'},
        {'name': 'shutter', 'type': 'list', 'limits': [0, 1]}
    ],
    'status_parameters': [
        {'name': 'osf', 'type': 'list', 'limits': [1, 2, 3, 4, 5, 6]},
        {'name': 'grating', 'type': 'list', 'limits': [1, 2, 3]},
        {'name': 'wavelength', 'type': 'str'},
        {'name': 'shutter', 'type': 'list', 'limits': [0, 1]},
    ],
    'status_refresh': 'manual',
}

# - Sr830 Control - #
sens_units_map = {
    'nV.': 1e-9,
    'uW.': 1e-6,
    'mV.': 1e-3,
    'V.': 1
}

tc_units_map = {
    'uS.': 1e-6,
    'mS.': 1e-3,
    'S.': 1,
    'kS.': 1e3
}

sensitivity_children = [
    {'name': 'Value', 'type': 'list', 'limits': [1, 2, 5]},
    {'name': 'Multiplier', 'type': 'list', 'limits': [1, 1e1, 1e2]},
    {'name': 'Units', 'type': 'list', 'limits': ['nV.', 'uV.', 'mV.', 'V.']}
]

timeconstant_children = [
    {'name': 'Value', 'type': 'list', 'limits': [1, 3]},
    {'name': 'Multiplier', 'type': 'list', 'limits': [1, 1e1, 1e2]},
    {'name': 'Units', 'type': 'list', 'limits': ['uS.', 'mS.', 'S.', 'kS.']}
]


def tc_sens_setting(parameter, units_mapping):
    children = {p.name(): p.value() for p in parameter.children()}
    val = children['Value']
    mult = children['Multiplier']
    units = units_mapping[children['Units']]

    return val * mult * units


Sr830Controller = {
    'instance_name': 'Sr830Cntrl',
    'type': 'InstrumentController',
    'hw': 'sr830',
    'control_parameters': [
        {'name': 'sensitivity', 'type': 'group', 'children': sensitivity_children,
         'set_process': lambda param, units_mapping=sens_units_map: tc_sens_setting(param, units_mapping)},

        {'name': 'time_constant', 'type': 'group', 'children': timeconstant_children,
         'set_process': lambda param, units_mapping=tc_units_map: tc_sens_setting(param, units_mapping)},
    ],
    'status_parameters': [
        {'name': 'sensitivity', 'type': 'float'},
        {'name': 'time_constant', 'type': 'float'},
    ],
    'status_refresh': 'after_set'
}

# - Procedure controllers ----------------------- #
LockinLogCntrl = {
    'instance_name': 'LockinLogProcedure',
    'type': 'ProcedureController',
    'procedure': 'LockinLogProc',
}

NoiseProcCntrl = {
    'instance_name': 'NoiseProcedure',
    'type': 'ProcedureController',
    'procedure': 'NoiseProcedure'
}

SpecCalProcCntrl = {
    'instance_name': 'SpecCalProcCntrl',
    'type': 'ProcedureController',
    'procedure': 'SpectralCalProcedure'
}
