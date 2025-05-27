""" This module implements the class

"""
import logging
import traceback
from queue import Queue
from pymeasure.thread import StoppableThread

from .procedures import BaseProcedure
from .log import Logger


class FlexibleWorker(StoppableThread):
    """ New implementation of the :class:`.Worker` class to support multiple output formats.
    """

    def __init__(self, procedure, log=None, **kwargs):
        """ Initialize a new worker to run a measurement.

        :param: procedure: Instantiated procedure class defining measurement execution. Also
                           contains instantiated recorder and viewer objects.
        """
        super().__init__()
        self.procedure = procedure
        self.procedure.check_parameters()
        self.procedure.status = BaseProcedure.QUEUED

        # set up the proper queues for procedure records #
        for record in self.procedure.record_queues:
            pass

        self.logger = Logger(log)

    def join(self, timeout=0):
        try:
            super().join(timeout)
        except (KeyboardInterrupt, SystemExit):
            self.logger.log("User stopped Worker join prematurely", level=logging.WARNING)
            self.stop()
            super().join(0)

    def emit(self, topics, record):
        """ Emits data of some topic, placing it on the proper queue to be recorded in a results
            file and/or displayed in a viewer.
        """
        topics = topics if type(topics) is list else [topics]
        for topic in topics:
            if topic == "record":
                self.recorder_queue.put(record)
            elif topic == "view":
                self.viewer_queue.put(record)

    def handle_abort(self):
        self.logger.log("User stopped Worker execution prematurely", logging.ERROR)
        self.update_status(BaseProcedure.ABORTED)

    def handle_error(self):
        self.logger.log("Worker caught an error on {}".format(self.procedure), logging.ERROR)
        traceback_str = traceback.format_exc()
        self.emit('error', traceback_str)
        self.update_status(BaseProcedure.FAILED)

    def update_status(self, status):
        self.procedure.status = status
        self.emit('status', status)

    def shutdown(self):
        self.procedure.shutdown()
        if self.viewer is not None:
            self.viewer.stop()
        if self.recorder is not None:
            self.recorder.stop()

        self.stop()
        if self.should_stop() and self.procedure.status == BaseProcedure.RUNNING:
            self.update_status(BaseProcedure.ABORTED)
        elif self.procedure.status == BaseProcedure.RUNNING:
            self.update_status(BaseProcedure.FINISHED)
            self.emit('progress', 100.)

    def run(self):
        self.logger.log("Worker thread started")

        # set up procedure record queues #

        # route Procedure methods & log
        self.procedure.should_stop = self.should_stop
        self.procedure.emit = self.emit

        self.logger.log("Worker started running an instance of %r", self.procedure.__class__.__name__)
        self.update_status(BaseProcedure.RUNNING)
        self.emit('progress', 0.)

        try:
            self.procedure.startup()
            self.procedure.execute()
        except (KeyboardInterrupt, SystemExit):
            self.handle_abort()
        except Exception:
            self.handle_error()
        finally:
            self.shutdown()
            self.stop()

    def __repr__(self):
        return "<{}(port={},procedure={},should_stop={})>".format(
            self.__class__.__name__, self.port,
            self.procedure.__class__.__name__,
            self.should_stop()
        )
