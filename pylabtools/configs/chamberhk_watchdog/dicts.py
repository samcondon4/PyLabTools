# - procedures ------------------------------ #
hk_watchdog = {
    'instance_name': 'KasiHkWatchdog',
    'type': 'KasiHkWatchdog',
    'hw': [],
    'records': {
        #'activity': {'viewer': 'ActivityViewer'}
    },
    'kwargs': {
        'check_values': ['no_activity_count'],
        'address': 'spherexlabalert@gmail.com',
        'password': 'gciuddtilkexgpyl',
        'smtp_dict': {
            'smtp.gmail.com': [
                'samcondon44@gmail.com',
                'scondon@caltech.edu'
            ]
        }
    }
}

# - controllers ---------------------------- #
hk_wd_control = {
    'instance_name': 'KasiHkWatchdogController',
    'type': 'ProcedureController',
    'procedure': 'KasiHkWatchdog',
}

# - viewers -------------------------------- #
activity_viewer = {
    'instance_name': 'ActivityViewer',
    'type': 'LineViewer',
}
