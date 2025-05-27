lakeshore218 = {
    'instance_name': 'ls218',
    'manufacturer': 'lakeshore',
    'instrument': 'LakeShore218',
    'resource_name': 'ASRL/dev/ttyUSB0::INSTR',
}

lakeshore224_2 = {
    'instance_name': 'ls224_2',
    'manufacturer': 'lakeshore',
    'instrument': 'LakeShore224',
    'resource_name': 'TCPIP::192.168.1.22::7777::SOCKET'
}

lakeshore224_3 = {
    'instance_name': 'ls224_3',
    'manufacturer': 'lakeshore',
    'instrument': 'LakeShore224',
    'resource_name': 'TCPIP::192.168.1.23::7777::SOCKET'
}

vacuum_gauge = {
    'instance_name': 'vacuum_gauge',
    'manufacturer': 'pfeiffer',
    'instrument': 'TPG361',
    'resource_name': 'ASRL/dev/ttyUSB1::INSTR',
    'kwargs': {
        'baud_rate': 115200
    }
}

vacuum_gauge_low = {
    'instance_name': 'vacuum_gauge_low',
    'manufacturer': 'pfeiffer',
    'instrument': 'TPG361',
    'resource_name': 'ASRL/dev/ttyUSB2::INSTR',
    'kwargs': {
        'baud_rate': 115200
    }
}

pyhk_socket = {
    'instance_name': 'pyhk_socket',
    'manufacturer': 'instrument',
    'instrument': 'Instrument',
    'resource_name': 'TCPIP::192.168.1.99::6550::SOCKET',
    'kwargs': {
        'name': 'pyhk_socket'
    }
}
