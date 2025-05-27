mono_host = '131.215.200.118'
mono_port = 6550
mono_rec_name = f'TCPIP::%s::%s::SOCKET' % (mono_host, mono_port)
mono = {
    'instance_name': 'mono',
    'manufacturer': 'spherex',
    'resource_name': mono_rec_name,
    'instrument': 'MonoControlClient',
    'params': {
        'units': 'UM'
    },
    'kwargs': {
        'timeout': 10000
    }
}

sr830 = {
    'instance_name': 'sr830',
    'manufacturer': 'srs',
    'resource_name': 'GPIB0::15::INSTR',
    'instrument': 'SR830'
}

readout = {
    'instance_name': 'readout',
    'manufacturer': 'spherex',
    'resource_name': "",
    'instrument': 'DetectorCom'
}
