import sshtunnel
import urllib.parse
from sqlalchemy import create_engine, String, Float, Integer

CONFIGURE_REMOTE_SQL = False

sql_types = {
    "RecordGroup": String(20),
    "RecordGroupInd": String(20),
    "RecordRow": String(20),
    "baseplate_temp": Float,
    "heater_ir_emission": Float,
    "heater_voltage": Float,
    "timestamp": String(255),
    "meta_camera_gain": Float,
    "meta_camera_frame_height": Integer,
    "meta_camera_frame_width": Integer,
    "proc_heater_voltage": Float,
    "proc_sample_time": Float,
    "proc_sample_rate": Float
}

# - Local SQLRecorder configuration - #
loc_user = 'sam'
loc_pwd = '44KEEPgoing'
loc_host = 'localhost'
loc_name = 'DevMock'
engine_str = 'mysql+pymysql://%s:%s@%s/%s' % (
    loc_user, loc_pwd, loc_host, loc_name
)
loc_engine = create_engine(engine_str)

SqlArchive_Local = {
    'instance_name': 'sql_archive',
    'type': 'SQLRecorder',
    'params': {
        '_rgroup_val_str': 'mock_%06i'
    },
    'kwargs': {
        'table': 'sql_test',
        'engine': loc_engine,
        'type_dict': sql_types
    }
}

# - Ragnarok SQLRecorder configuration - #
SqlArchive_Ragnarok = {}
ssh_host = 'ragnarok.caltech.edu'
ssh_username = 'spherex_lab'
ssh_password = 'r@gP4$ph!'
remote_bind_address = ('127.0.0.1', 3306)

rg_host = '127.0.0.1'
rg_user = 'root'
rg_passwd = urllib.parse.quote_plus('$PHEREx_B111')
rg_dbname = 'test'

# - mysql+pymysql://<user>:<password>@<host>[:<port>]/<dbname>
engine_str = 'mysql+pymysql://%s:%s@%s:%s/%s'
if CONFIGURE_REMOTE_SQL:
    tunnel = sshtunnel.SSHTunnelForwarder(
        (ssh_host, 22),
        ssh_username=ssh_username,
        ssh_password=ssh_password,
        remote_bind_address=remote_bind_address
    )
    tunnel.start()

    def close_results(self):
        print('closing results')
        tunnel.close()

    engine_str %= (rg_user, rg_passwd, rg_host, tunnel.local_bind_port, rg_dbname)
    engine = create_engine(engine_str)

    SqlArchive_Ragnarok.update(
        {
            'instance_name': 'sql_archive',
            'type': 'SQLRecorder',
            'params': {
                '_rgroup_val_str': 'mock_%06i',
                'close_results': close_results
            },
            'kwargs': {
                'table': 'mock',
                'engine': engine,
                'type_dict': sql_types
            }
        }
    )
