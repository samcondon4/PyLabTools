""" hw.py

This module provides the hardware configuration file for focus calibration. The following hardware is implemented:

    1) FLIR camera
    2) Collimator:
        2.1) focuser
        2.2) horizontal stage
        2.3) vertical stage
        2.4) linear absolute gauge
        2.5) shutter
    3) Microscope:
        3.1) focuser
        3.2) horizontal stage
        3.3) vertical stage
        3.4) linear absolute gauge
        3.5) shutter
    4) Relay:
        4.1) gimbal 1
        4.2) gimbal 2
        4.3) lift stage
        4.4) linear stage
"""
from spherexlabtools.instruments.flir import Flea3 as _Fl3

# - 1) Camera ------------------------------------------------------------------- #
try:
    Camera = {
        "instance_name": "Camera",
        "resource_name": _Fl3.cam_list[0],
        "manufacturer": "flir",
        "instrument": "Flea3",
        "params": {
            "acquisition_frame_rate_en": True,
            "acquisition_frame_rate_auto": "Off",
            "gain_auto": "Off",
            "gain": 0,
            "blacklevel_en": False,
            "gamma_en": False,
            "sharpess_en": False,
            "offset_x": 0,
            "offset_y": 0,
            "exposure_width": 2448,
            "exposure_height": 2048,
            "exposure_mode": "Timed",
            "exposure_auto": "Off",
            "pixel_format": "Mono16"
        }
    }
except IndexError:
    Camera = {'instance_name': 'Camera'}

print(Camera)

# - resource names ------------------------------------------------------- #
mscope_gauge_resource_name = 'ASRL/dev/ttyUSB0::INSTR'
coll_gauge_resource_name = 'ASRL/dev/ttyUSB2::INSTR'
col_mscope_resource_name = 'ASRL/dev/ttyUSB3::INSTR'
relay_resource_name = "ASRL/dev/ttyUSB1::INSTR"
#shutter_resource_name = 'ASRL/dev/ttyUSB4::INSTR'

# - 2) Collimator -------------------------------------------------------- #
collimator_focuser = {
    'instance_name': 'fstage',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    "kwargs": {
        "address": 0,
        "homedir": "CCW",
        "encoder_enabled": False,
    },
    "params": {
        "turns_per_step": 1 / 3600,
        "units_per_turn": 1.87,
        "units": "mm",
    }
}

collimator_horizontal = {
    'instance_name': 'horizontal',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    'kwargs': {
        'address': 1,
        'homedir': 'CCW',
        'encoder_enabled': True
    },
    'params': {
        'encoder_motor_ratio': 1,
        'turns_per_step': 1 / 1600,
        'units_per_turn': 1,
        'units': 'mm',
        'homespeed': 3000,
    }
}

collimator_vertical = {
    'instance_name': 'vertical',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    'kwargs': {
        'address': 2,
        'homedir': 'CCW',
        'encoder_enabled': True
    },
    'params': {
        'encoder_motor_ratio': 1,
        'turns_per_step': 1 / 1600,
        'units_per_turn': 1,
        'units': 'mm',
        'homespeed': 3000,
    }
}

collimator_gauge = {
    "instance_name": "gauge",
    "resource_name": coll_gauge_resource_name,
    "manufacturer": "heidenhain",
    "instrument": "ND287",
    "params": {
        "units": "mm",
    },
    "kwargs": {
        "baud_rate": 115200
    }
}

Collimator = {
    "instance_name": "Collimator",
    "resource_name": "dummy",
    "manufacturer": "focuser",
    "instrument": "Focuser",
    "sub_instruments": [
        collimator_focuser,
        collimator_horizontal,
        collimator_vertical,
        collimator_gauge,
    ],
    "kwargs": {
        "gauge_name": "gauge",
        "stage_name": "fstage",
    }
}

# - 3) Microscope ------------------------------------------------------------------- #
mscope_focuser = {
    'instance_name': 'fstage',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    "kwargs": {
        "address": 3,
        "homedir": "CCW",
        "encoder_enabled": False,
    },
    "params": {
        "turns_per_step": 1 / 3600,
        "units_per_turn": 1.87,
        "units": "mm",
    }
}

mscope_horizontal = {
    'instance_name': 'horizontal',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    'kwargs': {
        'address': 4,
        'homedir': 'CCW',
        'encoder_enabled': True
    },
    'params': {
        'encoder_motor_ratio': 1,
        'turns_per_step': 1 / 1600,
        'units_per_turn': 1,
        'units': 'mm',
        'homespeed': 3000,
    }
}

mscope_vertical = {
    'instance_name': 'vertical',
    'resource_name': col_mscope_resource_name,
    'manufacturer': 'anaheimautomation',
    'instrument': 'LinearStageController',
    'kwargs': {
        'address': 5,
        'homedir': 'CCW',
        'encoder_enabled': True
    },
    'params': {
        'encoder_motor_ratio': 1,
        'turns_per_step': 1 / 1600,
        'units_per_turn': 1,
        'units': 'mm',
        'homespeed': 3000,
    }
}

mscope_gauge = {
    "instance_name": "gauge",
    "resource_name": mscope_gauge_resource_name,
    "manufacturer": "heidenhain",
    "instrument": "ND287",
    "params": {
        "units": "mm",
    },
    "kwargs": {
        "baud_rate": 115200
    }
}

"""
mscope_shutter = {
    "instance_name": "shutter",
    "resource_name": shutter_resource_name,
    "manufacturer": "spherex",
    "instrument": "CSLD",
    "kwargs": {
        "baud_rate": 115200,
        "write_termination": "\r"
    }
}
"""

Mscope = {
    "instance_name": "Mscope",
    "resource_name": "dummy",
    "manufacturer": "focuser",
    "instrument": "Focuser",
    "sub_instruments": [
        mscope_focuser,
        mscope_horizontal,
        mscope_vertical,
        mscope_gauge,
        #mscope_shutter,
    ],
    "kwargs": {
        "gauge_name": "gauge",
        "stage_name": "fstage",
    }
}

# - Relay ---------------------------------------------- #

# relay gimbal1 az config
relay_gimbal1_az = {
    "instance_name": "g1az",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 6,
        "homedir": "CCW",
    },
    "params": {
        "turns_per_step": 1/1600,
        "units_per_turn": 5,
        "encoder_motor_ratio_override": 2.5,
        "units": "degrees",
        "encoder_enabled": True,
    }
}

# relay gimbal1 zth config
relay_gimbal1_zth = {
    "instance_name": "g1za",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 7,
        "homedir": "CCW",
    },
    "params": {
        "turns_per_step": 1 / 1600,
        "units_per_turn": 5,
        "encoder_motor_ratio_override": 2.5,
        "units": "degrees",
        "encoder_enabled": True,
    }
}

# - relay gimbal2 az config - #
relay_gimbal2_az = {
    "instance_name": "g2az",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 8,
        "homedir": "CCW",
    },
    "params": {
        "turns_per_step": 1 / 1600,
        "units_per_turn": 5,
        "encoder_motor_ratio_override": 2.5,
        "units": "degrees",
        "encoder_enabled": True,
    }
}

# - relay gimbal2 za config - #
relay_gimbal2_zth = {
    "instance_name": "g2za",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 9,
        "homedir": "CCW",
    },
    "params": {
        "turns_per_step": 1 / 1600,
        "units_per_turn": 5,
        "encoder_motor_ratio_override": 2.5,
        "units": "degrees",
        "encoder_enabled": True,
    }
}

# - lift config - #
lift_stage = {
    "instance_name": "lift",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 10,
        "homedir": "CCW",
    }
}

# - linear stage config - #
linear_stage = {
    "instance_name": "linear",
    "resource_name": relay_resource_name,
    "manufacturer": "anaheimautomation",
    "instrument": "LinearStageController",
    "kwargs": {
        "address": 11,
        "homedir": "CCW"
    },
    "params": {
        "encoder_motor_ratio": 8,
        "turns_per_step": 1 / 200,
        "units_per_turn": 0.1,
        "units": "in.",
        "encoder_enabled": True,
        "maxspeed": 1000
    }
}

Relay = {
    "instance_name": "Relay",
    "resource_name": "",
    "sub_instruments": [
        relay_gimbal1_az,
        relay_gimbal1_zth,
        relay_gimbal2_az,
        relay_gimbal2_zth,
        lift_stage,
        linear_stage
    ],
}
