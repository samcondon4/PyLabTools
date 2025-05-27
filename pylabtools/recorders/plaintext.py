""" This module implements Recorder sub-classes that write to plain-text output files.
"""

import os
import logging
import pandas as pd

import spherexlabtools.log as slt_log
from spherexlabtools.recorders import Recorder


class CSVRecorder(Recorder):
    """ A merging recorder that writes to a CSV text file.
    """

    def __init__(self, cfg, exp, **kwargs):
        super().__init__(cfg, exp, extension=".csv", merge=True, **kwargs)

    def open_results(self, exists):
        """ Open the results csv file and return the record_group and record_group_ind. Since csvs do not
        need to stay open, use the opened_results attribute as a flag for if the csv output file exists.

        :return: Return the initial record_group and record_group_ind for a new file.
        """
        if exists:
            results_df = pd.read_csv(self.results_path.value())
            rec_group = results_df[self._rgroup_col_str].values[-1]
            rec_group_ind = results_df[self._rgroupind_col_str].values[-1]
            self.opened_results = True
        else:
            rec_group = -1
            rec_group_ind = -1
            self.opened_results = False

        return rec_group, rec_group_ind

    def close_results(self):
        """ Don't need this for the csv recorder.
        """
        pass

    def update_results(self):
        """ Check if the output file already exists. If so, just append to the existing file. If not, create the file
        and write the column header.
        """
        # - initialize key-words for to_csv() - #
        mode = "w"
        header = True
        if self.opened_results:
            mode = "a"
            header = False
        self.opened_results = True

        fp = self.results_path.value()
        self.merged_df.to_csv(fp, header=header, mode=mode)

