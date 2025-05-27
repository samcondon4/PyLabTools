# - PROCEDURES ------------------------------------------------------------------------------------------ #
temp_logging = {
    'instance_name': 'KasiHkLog',
    'type': 'KasiHkLog',
    'hw': ['ls218', 'ls224_2', 'ls224_3', 'vacuum_gauge', 'vacuum_gauge_low'],
    'records': {
        'ls218_view': {'viewer': 'ls218_view'},
        'ls224_2_view': {'viewer': 'ls224_2_view'},
        'ls224_3_view': {'viewer': 'ls224_3_view'},
        'pressure_view': {'viewer': 'pressure_view'},
        'kasi_hk_log': {'recorder': 'kasi_hk_csv'},
    },
}

alert_smtp = {
    # - all recipients route through gmail server ----------------- #
    'smtp.gmail.com': [
        'scondon@caltech.edu',
        'samcondon44@gmail.com',
        'hhui@caltech.edu',
        'spadin@caltech.edu',
        'pkorngut@caltech.edu',
        'chnguyen@caltech.edu',
        'charles.d.dowell@jpl.nasa.gov',
        'hien.t.nguyen@jpl.nasa.gov',
        'kenneth.s.manatt@jpl.nasa.gov',
        '5208226335@tmomail.net', # - Chi's phone
        '9712750526@tmomail.net', # - Howard
        '6263992045@tmomail.net', # - Steve
    ],
}

alert_system = {
    'instance_name': 'KASI Housekeeping',
    'type': 'KASIHkAlert',
    'hw': [],
    'records': {},
    'kwargs': {
        'check_values': [
            'kasi_vacuum_shell_pressure',
            'kasi_vacuum_shell_pressure_low',
        ],
        'address': 'spherexlabalert@gmail.com',
        'password': 'dudzovqdaciqewvd',
        'smtp_dict': alert_smtp,
    }
}

# - LS224 VIEW and RECORD ------------------------------------------------------------------------------ #
ls224_channels = ['A', 'B'] + ['C%i' % i for i in range(1, 6)] + ['D%i' % i for i in range(1, 6)]
ls218_channels = [1, 2, 3, 4, 5, 6, 7, 8]
ls_colors = [
    '#b5b5b5', '#94bb86', '#fffe9c', '#ffffc6', '#ffc8d7', '#e99b9a',
    '#ffb684', '#92ace5', '#abc5fe', '#ffc095', '#ffd5b9', '#9ee68d'
]
ls218_view = {
    'instance_name': 'ls218_view',
    'type': 'LineViewer',
    'kwargs': {
        'lines': {'ls218_%s' % ls218_channels[i]: ls_colors[i] for i in range(len(ls218_channels))}
    }
}
ls224_2_view = {
    'instance_name': 'ls224_2_view',
    'type': 'LineViewer',
    'kwargs': {
        'lines': {'ls224_2_%s' % ls224_channels[i]: ls_colors[i] for i in range(len(ls224_channels))}
    }
}
ls224_3_view = {
    'instance_name': 'ls224_3_view',
    'type': 'LineViewer',
    'kwargs': {
        'lines': {'ls224_3_%s' % ls224_channels[i]: ls_colors[i] for i in range(len(ls224_channels))}
    }
}
pressure_view = {
    'instance_name': 'pressure_view',
    'type': 'LineViewer',
    'kwargs': {
        'lines': {'kasi_vacuum_shell_pressure': 'r', 'kasi_vacuum_shell_pressure_low': 'b'}
    }
}

kasi_hk_csv = {
    'instance_name': 'kasi_hk_csv',
    'type': 'KASIHkRecorder'
}
