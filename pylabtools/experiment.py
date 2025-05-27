""" spherexlabtools.experiment

Sam Condon, 01/27/2022
"""
import logging
import os.path
import threading

import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore, QtGui
from .loader import load_objects_from_cfg_list
import spherexlabtools.log as slt_log
import spherexlabtools.viewers as slt_view
import spherexlabtools.procedures as slt_proc
import spherexlabtools.recorders as slt_record
import spherexlabtools.controllers as slt_control
from spherexlabtools.instruments import InstrumentSuite
from spherexlabtools.ui import TopUI, StackedHelper


# - configure top gui and logging parameters - #
app = pg.mkQApp("SPHERExLabTools")
top_widget = QtWidgets.QWidget()
top_ui = TopUI(top_widget)
slt_log.LOGGER_GUI_SIGNAL = top_ui.ui_log_signal
slt_log.configure_slt_log()
logger = logging.getLogger(slt_log.LOGGER_NAME)


class Experiment:
    """ The core class of the spherexlabtools package. The basic operating principle of spherexlabtools
        is implemented by this class. Namely, that every action that is performed in an experiment, be
        that the recording of data, or setting instrument parameters via a gui, is executed in its own thread.
        This class handles the scheduling of all threads and ensures that each thread has the resources that
        it needs to operate. All gui windows are run in the main thread.
    """

    def __init__(self, exp_pkg):
        """ Initialize an experiment. This init function performs the following tasks:
                - imports the hw.py module and instantiates an :class:`.InstrumentSuite`
                  instance using the INSTRUMENT_SUITE name found within.

                - imports the measure.py module and creates a set of recorders using the
                  RECORDERS name found within.

                - imports the view.py module and creates a set of viewers using the VIEWERS
                  name found within.

        :param: exp_pkg: Python package containing the experiment configuration modules.
        """
        self.exp_pkg = exp_pkg
        self.layout = QtWidgets.QGridLayout()
        self.active_threads = {}

        logger.info("Initializing experiment: %s" % exp_pkg.__name__)

        # - Top-level ui - #
        self.slt_top_widget = top_widget
        self.slt_top_ui = top_ui
        self.viewer_stack = StackedHelper()
        self.procedure_controller_stack = StackedHelper()
        self.instrument_controller_stack = StackedHelper()

        # initialize instrument-suite #############################################
        self.dev_links = {}
        if "dev_links_path" in dir(exp_pkg):
            with open(exp_pkg.dev_links_path, "r") as dev_file:
                df_lines = dev_file.readlines()
                for df_l in df_lines:
                    df_split = df_l.split(" -> ")
                    dl0 = "".join([c for c in df_split[0] if c.isalnum() or c == os.path.sep])
                    dl1 = "".join([c for c in df_split[1] if c.isalnum() or c == os.path.sep])
                    dl1 = "ASRL" + dl1
                    dl1 += "::INSTR"
                    self.dev_links[dl0] = dl1
        self.hw = InstrumentSuite(exp_pkg.INSTRUMENT_SUITE, exp_pkg, dev_links=self.dev_links)

        # initialize viewers ######################################################
        viewer_cfgs = exp_pkg.VIEWERS
        try:
            search_order = [exp_pkg.viewers, slt_view]
        except AttributeError:
            search_order = [slt_view]
        self.viewers = load_objects_from_cfg_list(search_order, self, viewer_cfgs)

        # initialize recorders ####################################################
        rec_cfgs = exp_pkg.RECORDERS
        try:
            search_order = [exp_pkg.recorders, slt_record]
        except AttributeError:
            search_order = [slt_record]
        self.recorders = load_objects_from_cfg_list(search_order, self, rec_cfgs)

        # initialize procedures ###################################################
        proc_cfgs = exp_pkg.PROCEDURES
        # get all compound procedure configurations #
        compound_proc_cfgs = []
        for proc in proc_cfgs:
            if "subprocedures" in proc.keys():
                compound_proc_cfgs.append(proc)
                proc_cfgs.remove(proc)
        try:
            search_order = [exp_pkg.procedures, slt_proc]
        except AttributeError:
            search_order = [slt_proc]
        self.procedures = load_objects_from_cfg_list(search_order, self, proc_cfgs, hw=self.hw,
                                                     viewers=self.viewers, recorders=self.recorders)

        # initialize controllers ##################################################
        control_cfgs = exp_pkg.CONTROLLERS
        try:
            search_order = [exp_pkg.controllers, slt_control]
        except AttributeError:
            search_order = [slt_control]
        self.controllers = load_objects_from_cfg_list(search_order, self, control_cfgs, hw=self.hw,
                                                      procs=self.procedures)
        logger.info("Experiment initialization complete.")

    def start(self):
        """ Start the top-level interface that includes all viewers, controllers, procedures, etc.
        """
        self._init_ui()
        # - start all controllers, viewers, and recorders - #
        for c in self.controllers.values():
            c.start()
        for v in self.viewers.values():
            v.start()
        for r in self.recorders.values():
            r.start()
        self.slt_top_widget.show()

    def stop(self):
        """ Stop the top-level interface.
        """
        # - start all controllers, viewers, and recorders - #
        for c in self.controllers.values():
            c.stop()
        for v in self.viewers.values():
            v.stop()
        for r in self.recorders.values():
            r.stop()
        self.slt_top_widget.close()

    def _init_ui(self):
        """ Initialize the top-level interface after start_top_ui() has been called.
        """

        # - get controller objects ---------------------------------------------------------------------------------- #
        controllers = [c for c in self.controllers.values()]

        # - initialize procedure_controllers in the top widget ------------------------------------------------------ #
        procedure_controllers = {
            c.procedure.name: c for c in controllers if type(c) is slt_control.ProcedureController
        }
        procedure_records = {
            p.name: p.records_interface for p in self.procedures.values()
        }
        for pname, controller in procedure_controllers.items():
            records_interface = procedure_records[pname]
            controller.tree.addParameters(records_interface)
        if len(procedure_controllers) > 0:
            self.procedure_controller_stack.configure_stack(list(procedure_controllers.values()),
                                                            "Procedure Controllers", "Controller Select")
            self.slt_top_ui.top_horizontal_splitter.addWidget(self.procedure_controller_stack.stack)

        # - initialize viewers in the top widget -------------------------------------------------------------------- #
        viewers = [None for _ in range(len(self.viewers))]
        i = 0
        for name, viewer in self.viewers.items():
            widget = viewer.widget(name=name)
            viewer.update.connect(widget.update)
            viewers[i] = widget
            i += 1
        if len(viewers) > 0:
            self.viewer_stack.configure_stack(viewers, "Viewers", "Viewer Select")
            self.slt_top_ui.top_horizontal_splitter.addWidget(self.viewer_stack.stack)

        # - initialize instrument_controllers in the top widget ----------------------------------------------------- #
        instrument_controllers = [c for c in controllers if type(c) is slt_control.InstrumentController]
        if len(instrument_controllers) > 0:
            self.instrument_controller_stack.configure_stack(instrument_controllers, "Instrument Controllers",
                                                             "Controller Select")
            self.slt_top_ui.top_horizontal_splitter.addWidget(self.instrument_controller_stack.stack)

        """
        if len(controllers) > 0:
            self.controller_stack.configure_stack(controllers, "Procedure Controllers", "Controller Select")
            self.slt_top_ui.top_horizontal_layout.addWidget(self.controller_stack.stack)
        """

        # - initialize procedures in the top widget - #
        """
        if len(procedure_records) > 0:
            self.procedure_stack.configure_stack(procedure_records, "Procedures", "Procedure Select")
            self.slt_top_ui.top_horizontal_layout.addWidget(self.procedure_stack.stack)
        """

    def start_viewer(self, viewer_key):
        """ Start a viewer thread.
        """
        logger.info("Starting viewer: %s" % viewer_key)
        viewer = self.viewers[viewer_key]
        self.start_thread(viewer_key, viewer)

    def stop_viewer(self, viewer_key):
        """ Stop a viewer thread.
        """
        logger.info("Killing viewer: %s" % viewer_key)
        self.stop_thread(viewer_key)

    def start_recorder(self, rec_key):
        """ Start a recorder thread.
        """
        logger.info("Starting recorder: %s" % rec_key)
        recorder = self.recorders[rec_key]
        self.start_thread(rec_key, recorder)

    def stop_recorder(self, rec_key):
        """ Kill a recorder thread.
        """
        logger.info("Killing recorder: %s" % rec_key)
        self.stop_thread(rec_key)

    def start_procedure(self, proc_key, **kwargs):
        """ Start a procedure thread.
        """
        pass

    def stop_procedure(self, proc_key):
        """ Kill a procedure thread.
        """
        pass

    def start_controller(self, cntrl_key):
        """ Start a controller thread.
        """
        logger.info("Starting controller: %s" % cntrl_key)
        controller = self.controllers[cntrl_key]
        # controller guis run in the main thread. #
        controller.start()

    def stop_controller(self, cntrl_key):
        """ Kill a controller thread.
        """
        logger.info("Killing controller: %s" % cntrl_key)
        controller = self.controllers[cntrl_key]
        controller.stop()

    def start_thread(self, thread_key, thread, stop_thread=False, **tkwargs):
        """ Start a thread and update the active_threads dictionary. This should only be called internally.

        :param thread_key: String key name to use in the active_threads dictionary.
        :param thread: Thread object to start.
        :param stop_thread: Boolean to indicate if an active thread should be stopped an restarted.
        :param tkwargs: Key-word arguments passed when the thread is started.
        """
        if thread_key not in self.active_threads.keys() or not self.active_threads[thread_key].thread.is_alive():
            thread.start(**tkwargs)
            self.active_threads[thread_key] = thread
        else:
            raise RuntimeWarning(f"Thread {thread_key} is already active! Thread reset = {stop_thread}")

    def get_start_thread_lambda(self, thread_key, thread):
        """ Return a lambda function to call the start_thread method. This is useful to generate lambda functions
            to connect to pyqt signals.

        :param thread_key: Same as for :meth:`Experiment.start_thread`
        :param thread: Same as for :meth:`Experiment.start_thread`
        """
        return lambda key=thread_key, t=thread: self.start_thread(key, t)

    def stop_thread(self, thread_key):
        """ Stop a thread and update the active_threads dictionary. This should only be called internally.

        :param thread_key: String key name for the active_threads dictionary.
        """
        if thread_key in self.active_threads.keys():
            thread = self.active_threads.pop(thread_key)
            thread.stop()

    def get_stop_thread_lambda(self, thread_key, thread):
        """ Return a lambda function to call the :meth:`Experiment.start_thread` method. This is useful to generate
            lambda functions to connect to pyqt signals.

        :param thread_key: Same as for :meth:`Experiment.start_thread`
        :param thread: Same as for :meth:`Experiment.start_thread`
        """
        return lambda key=thread_key, t=thread: self.start_thread(key, t)

    def kill_threads(self):
        """ Call the :meth:`StoppableReusableThread.stop` method on each thread in the active threads dictionary.
        """
        for t in self.active_threads.values():
            t.stop()


def create_experiment(exp_pkg):
    """ Instantiate and return an Experiment object.
    :param: exp_pkg: Python package containing the experiment configuration files.
    """
    return Experiment(exp_pkg)

