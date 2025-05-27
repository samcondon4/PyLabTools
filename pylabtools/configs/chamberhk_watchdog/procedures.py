import os
import time
import pandas as pd
from datetime import datetime
import urllib.request
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError

from spherexlabtools.procedures import AlertProcedure
from spherexlabtools.parameters import Parameter, FloatParameter


class KasiHkWatchdog(AlertProcedure):
    # - temperature and pressure --------------------------------- #
    _temp_lengths = {
        'ls218_1': None,
        'ls218_2': None,
        'ls218_3': None,
        'ls218_4': None,
        'ls224_2_A': None,
        'ls224_2_B': None,
        'ls224_2_C1': None,
        'ls224_2_D1': None,
        'ls224_2_D2': None,
        'ls224_2_D3': None,
        'ls224_2_D4': None,
        'ls224_2_D5': None,
        'ls224_3_A': None,
        'ls224_3_B': None,
        'ls224_3_C1': None,
    }

    _pressure_lengths = {
        'kasi_vacuum_shell_pressure': None,
        'kasi_vacuum_shell_pressure_low': None,
    }

    # - https://pink.pyhk.net/data/export/%s/%s/%s/%s.txt -------- #
    _baseurl = 'https://pink.pyhk.net/data/export/'

    # - parameters ------------------------------ #
    #username = Parameter('Username', default='')
    #password = Parameter('Password', default='')
    query_period = FloatParameter('Query Period (s)', default=5)

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)
        self.password_mgr = None
        self.auth_handler = None
        self.opener = None
        self.no_act_count = None

    def startup(self):
        self.password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        self.password_mgr.add_password(None, urlparse(self._baseurl).netloc, 'spherex', 'spherex_lab')
        self.auth_handler = urllib.request.HTTPBasicAuthHandler(self.password_mgr)
        self.opener = urllib.request.build_opener(self.auth_handler)
        self.no_act_count = {
            val: 0 for val in self._temp_lengths.keys()
        }
        self.no_act_count.update({
            val: 0 for val in self._pressure_lengths.keys()
        })
        self.no_act_count = pd.Series(self.no_act_count)
        super().startup()

    def get(self):
        today = datetime.now().strftime('%Y%m%d')

        time.sleep(self.query_period)

        # - temperature queries ---------------------------------------- #
        for tkey, value in self._temp_lengths.items():
            url_add = 'temperature/%s/%s/%s.txt' % (today, today, tkey)
            full_url = self._baseurl + url_add
            with self.opener.open(full_url) as response:
                data = response.read()
                data_len = len(data)
                if data_len == value:
                    self.no_act_count[tkey] += 1
                self._temp_lengths[tkey] = data_len

        # - pressure queries ------------------------------------------- #
        for pkey, value in self._pressure_lengths.items():
            url_add = 'pressure/%s/%s/%s.txt' % (today, today, pkey)
            full_url = self._baseurl + url_add
            with self.opener.open(full_url) as response:
                data = response.read()
                data_len = len(data)
                if len(data) == value:
                    self.no_act_count[pkey] += 1
                self._pressure_lengths[pkey] = data_len

        return {'no_activity_count': self.no_act_count.max()}

