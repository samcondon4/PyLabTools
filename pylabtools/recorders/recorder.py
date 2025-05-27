import os
import logging
import numpy as np
import pandas as pd
from pyqtgraph.parametertree.parameterTypes import FileParameter

import spherexlabtools.log as slt_log
from spherexlabtools.thread import QueueThread

log_name = f"{slt_log.LOGGER_NAME}.{__name__.split('.')[-1]}"
logger = logging.getLogger(log_name)


class Recorder(QueueThread):
    """ Abstract base-class for all recorders. This class generates the 'RecordGroup', 'RecordGroupInd', and
    'RecordRow' indices used in output dataframes.
    """

    _rgroup_col_str = "RecordGroup"
    _rgroupind_col_str = "RecordGroupInd"
    _rrow_col_str = "RecordRow"
    _merge_on = [_rgroup_col_str, _rgroupind_col_str]

    _rgroup_val_str = "%06i"
    _rgroupind_val_str = "%06i"
    _rrow_val_str = "%06i"

    _rgroup_val_prepend_str = ''
    _rgroupind_val_prepend_str = ''
    _rrow_val_prepend_str = ''

    def __init__(self, cfg, exp, extension, merge=False, **kwargs):
        super().__init__(**kwargs)
        self.name = cfg["instance_name"]
        self.extension = extension
        self.opened_results = None
        self.record_group = None
        self.record_group_ind = None
        self.record_row = None
        self.record_group_changed = False
        self.data_index = None
        self.meta_index = None
        self.procedure_start_time = None
        # - should record tables be merged before written out? - #
        self.merge = merge

        # - copies of record tables - #
        self.data_df = None
        self.pp_df = None
        self.meta_df = None
        self.merged_df = None

        # - configure parameters - #
        name = 'Results Path'
        directory = os.getcwd()
        self.results_path = FileParameter(
            name=name,
            winTitle=name,
            directory=directory,
            value=os.path.join(directory, self.name)
        )
        self.results_path_changed = True
        self.results_path.sigValueChanged.connect(self.update_results_path_changed)

    def handle(self, record):
        """ Update the record_group, record_group_ind, and record_row attributes, then call overridden methods to
        write to the output file.
        """
        should_open, fp_exists = self.should_open()
        should_close = True if self.data_df is not None else False
        if should_open and should_close:
            self.close_results()
            self.record_group, self.record_group_ind = self.open_results(fp_exists)
        elif should_open:
            self.record_group, self.record_group_ind = self.open_results(fp_exists)

        # - if record_group and/or record_group_ind is a string, update to be an integer ----------- #
        if type(self.record_group) is str:
            self.record_group = int(''.join([c for c in self.record_group if c.isdigit()]))
        if type(self.record_group_ind) is str:
            self.record_group_ind = int(''.join([c for c in self.record_group_ind if c.isdigit()]))

        self.update_record_group(record)
        self.update_dataframes(record)
        self.update_results()

    def update_record_group(self, record):
        # - update record_group - #
        self.record_group_changed = False
        if self.procedure_start_time != record.procedure_start_time:
            self.record_group += 1
            self.record_group_changed = True
            self.procedure_start_time = record.procedure_start_time

        # - update record_group_ind - #
        if self.record_group_changed:
            self.record_group_ind = 0
        else:
            self.record_group_ind += 1

        self.record_row = record.data.shape[0]

    def update_dataframes(self, record):
        """ Update the pandas indices based on the current record_group and record_group_ind.
        """
        rgroup_str = self._rgroup_val_prepend_str + (self._rgroup_val_str % self.record_group)
        rgroupind_str = self._rgroupind_val_prepend_str + (self._rgroupind_val_str % self.record_group_ind)
        # - update indices - #
        self.data_index = pd.MultiIndex.from_product([[rgroup_str], [rgroupind_str],
                                                      [self._rrow_val_str % i for i in np.arange(self.record_row)]],
                                                      names=[self._rgroup_col_str, self._rgroupind_col_str, self._rrow_col_str])

        self.meta_index = pd.MultiIndex.from_tuples([(rgroup_str, rgroupind_str)],
                                                    names=[self._rgroup_col_str, self._rgroupind_col_str])

        # - update dataframes - #
        self.data_df = record.data.set_index(self.data_index)
        self.pp_df = record.proc_params.set_index(self.meta_index)
        self.meta_df = None if record.meta is None else record.meta.set_index(self.meta_index)

        # - if merge, then merge all dataframes into one - #
        if self.merge:
            self.pp_df.columns = ["_".join(["proc", col]) for col in self.pp_df.columns]
            self.meta_df.columns = ["_".join(["meta", col]) for col in self.meta_df.columns]
            merged0 = pd.merge(self.pp_df, self.meta_df, on=self._merge_on)
            self.merged_df = pd.merge(self.data_df, merged0, on=self._merge_on)
            self.merged_df.index = self.data_df.index

    def should_open(self):
        """ Check if new results should be opened via open_results().

        :return: Tuple of the following form:
        (Boolean indicating if should_open() should be called, Boolean indicating if the file exists)
        """
        # - add the extension to the results path if it is not there. Check if the file exists. - #
        fp = self.results_path.value()
        if not fp.endswith(self.extension):
            fp += self.extension
            self.results_path.setValue(fp)
        fp_exists = os.path.exists(fp)

        # - check the conditions for if should_open() should be called. - #
        if not fp_exists or self.results_path_changed:
            ret = True
            self.results_path_changed = False
        elif self.opened_results is None:
            ret = True
        else:
            ret = False

        # - log --------------------------- #
        if ret:
            logger.info('Opening file %s' % fp)

        return ret, fp_exists

    def update_results_path_changed(self):
        """ Slot for the self.results_path.sigValueChanged signal.
        """
        self.results_path_changed = True

    def open_results(self, exists):
        """ Open the results file and return the record_group and record_group_ind. This method must be implemented in
        subclasses and must return those values after opening (or creating) the results file.

        Overrides of this method in subclasses should use the self.results_path attribute as the path to the output
        file to open.

        :param: Boolean indicating if the file exists or not.
        :return: Return the initial record_group and record_group_ind for a new file.
        """
        raise NotImplementedError("The open_results() method must be implemented in a subclass!")

    def update_results(self):
        """ Update the results file in the format determined by recorder subclasses.
        """
        raise NotImplementedError("The update_results() method must be implemented in a subclass!")

    def close_results(self):
        """ Close the currently opened results file. This method must be implemented in subclasses.
        """
        raise NotImplementedError("The close_results() method must be implemented in a subclass!")
