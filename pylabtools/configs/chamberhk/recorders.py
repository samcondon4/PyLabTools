import os
import datetime
import pandas as pd
from spherexlabtools.recorders import CSVRecorder


class KASIHkRecorder(CSVRecorder):

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, **kwargs)

    def update_results(self):
        # - call normal write method - #
        super().update_results()

        # - create temperature/pressure directories for y/m/d - #
        dt = pd.Timestamp(self.data_df.datetime.values[0])
        year = str(dt.year)
        month = '%02i' % dt.month
        day = '%02i' % dt.day
        dir_path = os.path.join('/data', 'hk', year, month, day)
        temp_path = os.path.join(dir_path, 'temperature')
        pressure_path = os.path.join(dir_path, 'pressure')
        os.makedirs(temp_path, exist_ok=True)
        os.makedirs(pressure_path, exist_ok=True)

        ts = round(datetime.datetime.timestamp(dt), 3)
        self.data_df.datetime = ts
        for key in self.data_df.to_dict().keys():
            df = self.data_df[['datetime', key]]
            if 'ls' in key:
                fp = os.path.join(temp_path, key+'.txt')
            elif 'pressure' in key:
                fp = os.path.join(pressure_path, key+'.txt')

            if key != 'datetime':
                df.to_csv(fp, sep='\t', header=False, index=False, mode='a')

