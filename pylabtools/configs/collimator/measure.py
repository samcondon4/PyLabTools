# - RECORDERS - #######################################
CollimatorHDF = {
    'instance_name': 'CollimatorHDF',
    'type': 'HDFRecorder'
}

CamViewHDF = {
    'instance_name': 'CamViewHDF',
    'type': 'HDFRecorder'
}

# - VIEWERS - #########################################
CamView = {
    'instance_name': 'CamView',
    'type': 'ImageViewer',
}

CollimatorCamView= {
    'instance_name': 'CollimatorCalCamView',
    'type': 'ImageViewer'
}

CollimatorCamViewAvg = {
    'instance_name': 'CollimatorCalCamViewAvg',
    'type': 'ImageViewer'
}

# - PROCEDURES - ######################################
CamViewProc = {
    'instance_name': 'CamViewProc',
    'type': 'CamViewProc',
    'hw': ['Camera'],
    'records': {
        'image_view': {'viewer': 'CamView'},
        'image_record': {'recorder': 'CamViewHDF'},
    },
    'kwargs': {
        'data': {
            'Camera': ['latest_frame']
        },
        'meta': {
            'Camera': ['gain', 'exposure_time']
        }
    }
}

CollimatorCalProc = {
    'instance_name': 'CollimatorCalProc',
    'type': 'CollimatorCalProc',
    'hw': ['Mscope', 'Camera'],
    'records': {
        'frame': {'viewer': 'CollimatorCalCamView'},
        'frame_avg': {'viewer': 'CollimatorCalCamViewAvg'},
        'image': {'recorder': 'CollimatorHDF'}
    }
}
