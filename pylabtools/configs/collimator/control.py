Collimator_Controller = {
    'instance_name': 'CollCntrl',
    'type': 'InstrumentController',
    'hw': 'Collimator',
    'control_parameters': [
        {'name': 'absolute_position', 'type': 'float'},
        {'name': 'fstage_step_position', 'type': 'int'},
        {'name': 'horizontal_step_position', 'type': 'int'},
        {'name': 'vertical_step_position', 'type': 'int'},
        {'name': 'fstage_absolute_position', 'type': 'float'},
        {'name': 'horizontal_absolute_position', 'type': 'float'},
        {'name': 'vertical_absolute_position', 'type': 'float'},
    ],
    'status_parameters': [
        {'name': 'absolute_position', 'type': 'float'},
        {'name': 'fstage_step_position', 'type': 'int'},
        {'name': 'horizontal_step_position', 'type': 'int'},
        {'name': 'vertical_step_position', 'type': 'int'},
        {'name': 'fstage_absolute_position', 'type': 'str'},
        {'name': 'horizontal_absolute_position', 'type': 'str'},
        {'name': 'vertical_absolute_position', 'type': 'str'},
    ],
    'status_refresh': 'manual',
    'actions': [
        'horizontal_home',
        'vertical_home',
        'horizontal_stop',
        'vertical_stop',
        'fstage_stop',
    ]
}

MScope_Controller = {
    'instance_name': 'MscopeCntrl',
    'type': 'InstrumentController',
    'hw': 'Mscope',
    'control_parameters': [
        {'name': 'horizontal_step_position', 'type': 'int'},
        {'name': 'vertical_step_position', 'type': 'int'},
        {'name': 'horizontal_absolute_position', 'type': 'str'},
        {'name': 'vertical_absolute_position', 'type': 'str'},
        {'name': 'fstage_step_position', 'type': 'int'},
        {'name': 'absolute_position', 'type': 'float'},
        {'name': 'fstage_outputs', 'type': 'int'},
    ],
    'status_parameters': [
        {'name': 'horizontal_step_position', 'type': 'int'},
        {'name': 'vertical_step_position', 'type': 'int'},
        {'name': 'horizontal_absolute_position', 'type': 'str'},
        {'name': 'vertical_absolute_position', 'type': 'str'},
        {'name': 'fstage_step_position', 'type': 'int'},
        {'name': 'absolute_position', 'type': 'str'},
        {'name': 'fstage_outputs', 'type': 'int'},
    ],
    'status_refresh': 'manual',
    'actions': [
        'horizontal_home',
        'vertical_home',
        'horizontal_stop',
        'vertical_stop',
        'fstage_stop'
    ]
}

Camera_Controller = {
    'instance_name': 'CameraCntrl',
    'type': 'InstrumentController',
    'hw': 'Camera',
    'control_parameters': [
        {'name': 'gain', 'type': 'float'},
        {'name': 'acquisition_frame_rate_en', 'type': 'bool'},
        {'name': 'acquisition_frame_rate_auto', 'type': 'list', 'limits': [
            'Off', 'Continuous']},
        {'name': 'acquisition_frame_rate', 'type': 'float'},
        {'name': 'exposure_mode', 'type': 'list', 'limits': [
            'Timed', 'TriggerWidth']},
        {'name': 'exposure_auto', 'type': 'list', 'limits': [
            'Off', 'Once', 'Continuous']},
        {'name': 'exposure_time', 'type': 'float'},
        {'name': 'pixel_format', 'type': 'list', 'limits': [
            'Mono8', 'Mono16', 'Mono12Packed']}
    ], 'status_parameters': [
        {'name': 'gain', 'type': 'float'},
        {'name': 'acquisition_frame_rate_en', 'type': 'bool'},
        {'name': 'acquisition_frame_rate_auto', 'type': 'list', 'limits': [
            'Off', 'Continuous']},
        {'name': 'acquisition_frame_rate', 'type': 'float'},
        {'name': 'exposure_mode', 'type': 'list', 'limits': [
            'Timed', 'TriggerWidth']},
        {'name': 'exposure_auto', 'type': 'list', 'limits': [
            'Off', 'Once', 'Continuous']},
        {'name': 'exposure_time', 'type': 'float'},
        {'name': 'pixel_format', 'type': 'list', 'limits': [
            'Mono8', 'Mono16', 'Mono12Packed']}
    ],
    'status_refresh': 'manual'
}

CamViewProc_Cntrl = {
    'instance_name': 'CamViewProcCntrl',
    'type': 'ProcedureController',
    'procedure': 'CamViewProc'
}

CollimatorCalProc_Cntrl = {
    'instance_name': 'CollimatorCalProcCntrl',
    'type': 'ProcedureController',
    'procedure': 'CollimatorCalProc'
}

Relay_Controller = {
    'instance_name': 'RelayMotorCntrl',
    'type': 'InstrumentController',
    'hw': 'Relay',
    'control_parameters': [
        {'name': 'g1az_step_position', 'type': 'int'},
        {'name': 'g1az_absolute_position', 'type': 'str'},
        {'name': 'g1za_step_position', 'type': 'int'},
        {'name': 'g1za_absolute_position', 'type': 'str'},
        {'name': 'g2az_step_position', 'type': 'int'},
        {'name': 'g2az_absolute_position', 'type': 'str'},
        {'name': 'g2za_step_position', 'type': 'int'},
        {'name': 'g2za_absolute_position', 'type': 'str'},
        {'name': 'linear_step_position', 'type': 'int'},
        {'name': 'linear_absolute_position', 'type': 'str'},
        {'name': 'lift_step_position', 'type': 'int'},
    ],
    'status_parameters': [
        {'name': 'g1az_step_position', 'type': 'int'},
        {'name': 'g1az_absolute_position', 'type': 'str'},
        {'name': 'g1za_step_position', 'type': 'int'},
        {'name': 'g1za_absolute_position', 'type': 'str'},
        {'name': 'g2az_step_position', 'type': 'int'},
        {'name': 'g2az_absolute_position', 'type': 'str'},
        {'name': 'g2za_step_position', 'type': 'int'},
        {'name': 'g2za_absolute_position', 'type': 'str'},
        {'name': 'linear_step_position', 'type': 'int'},
        {'name': 'linear_absolute_position', 'type': 'str'},
        {'name': 'lift_step_position', 'type': 'int'},
    ],
    'actions': [
        'g1az_stop',
        'g1az_home',
        'g1za_stop',
        'g1za_home',
        'g2az_stop',
        'g2az_home',
        'g2za_stop',
        'g2za_home',
        'lift_stop',
        'lift_home',
        'linear_stop',
        'linear_home',
    ],
    'status_refresh': 'manual',
}
