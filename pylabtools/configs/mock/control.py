TCCntrl = {
    "instance_name": "tc_control",
    "type": "InstrumentController",
    "hw": "temp_controller",
    "control_parameters": [
        {"name": "heater_output", "type": "float", "value": 0.0}
    ],
    "status_parameters": [
        {"name": "plate_temperature", "type": "float", "value": 40}
    ],
    "status_refresh": 1000
}

CamCntrl = {
    "instance_name": "camera_control",
    "type": "InstrumentController",
    "hw": "camera",
    "control_parameters": [
        {"name": "frame_width", "type": "int", "value": 2448},
        {"name": "frame_height", "type": "int", "value": 2048},
        {"name": "frame_format", "type": "list", "limits": ["mono_8", "mono_16"]},
        {"name": "gain", "type": "float", "value": 0.0}
    ],
    "status_parameters": [
        {"name": "frame_width", "type": "str"},
        {"name": "frame_height", "type": "str"},
        {"name": "frame_format", "type": "list", "limits": ["mono_8", "mono_16"]},
        {"name": "gain", "type": "float", "value": 0.0}
    ],
    "status_refresh": "after_set"
}

HeaterProcCntrl = {
    "instance_name": "heater_proc_control",
    "type": "ProcedureController",
    "procedure": "heater_proc"
}

TempLogProcCntrl = {
    'instance_name': 'temp_proc_control',
    'type': 'ProcedureController',
    'procedure': 'basic_temp'
}

CamViewProcCntrl = {
    'instance_name': 'CamViewProcCntrl',
    'type': 'ProcedureController',
    'procedure': 'CamViewProc'
}
