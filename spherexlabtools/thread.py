""" Implement the set of base thread classes from which Recorders, Viewers, and Procedures inherit.

Sam Condon, 02/05/2022
"""
import queue
from time import time
from threading import Thread, Event


# CLASSES WITHIN THIS BLOCK COPIED FROM PYMEASURE W/ MINOR CHANGES #########################################
class InterruptableEvent(Event):
    """
    This subclass solves the problem indicated in bug
    https://bugs.python.org/issue35935 that prevents the
    wait of an Event to be interrupted by a KeyboardInterrupt.
    """

    def wait(self, timeout=None):
        if timeout is None:
            while not super().wait(0.1):
                pass
        else:
            timeout_start = time()
            while not super().wait(0.1) and time() <= timeout_start + timeout:
                pass


class StoppableThread(Thread):
    """ Base class for Threads which require the ability
    to be stopped by a thread-safe method call
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._should_stop = InterruptableEvent()
        self._should_stop.clear()

    def join(self, timeout=0):
        """ Joins the current thread and forces it to stop after
        the timeout if necessary

        :param timeout: Timeout duration in seconds
        """
        self._should_stop.wait(timeout)
        if not self.should_stop():
            self.stop()
        return super().join(0)

    def stop(self):
        self._should_stop.set()

    def should_stop(self):
        return self._should_stop.is_set()

    def __repr__(self):
        return "<{}(should_stop={})>".format(
            self.__class__.__name__, self.should_stop())
######################################################################################################


class StoppableReusableThread:
    """ Wrapper around the :class:`.StoppableThread` which creates new Thread instances every time
        it is run. This abstracts away the need to create new thread instances each time.
    """

    def __init__(self, **kwargs):
        self.thread = None

    def start(self):
        """ Start running a thread, assuming it is not already running.
        """
        if self.thread is None or not self.thread.is_alive():
            self.thread = StoppableThread(target=self.run)
            self.thread.start()
        else:
            raise RuntimeError("Thread already running!")

    def run(self):
        """ Call the thread execution methods, which should be overridden in subclasses.
        """
        self.startup()
        self.execute()

    def stop(self):
        """ Stop a running thread.
        """
        self.thread.stop()
        self.shutdown()
        #self.thread.join()

    def should_stop(self):
        """
        """
        return self.thread.should_stop()

    def startup(self):
        """ Initialize thread state.
        """
        pass

    def execute(self):
        """ Core of thread execution.
        """
        pass

    def shutdown(self):
        """ Close down to leave system in a known state.
        """
        pass


class QueueThread(StoppableReusableThread):
    """Subclass of :class:`.StoppableReusableThread` to implement processing around a queue.
    """

    def __init__(self, q=None, timeout=1):
        """
        :param: q: Queue object. Does not need to be provided.
        :param: timeout: queue get timeout.
        """
        super().__init__()
        self.queue = q if q is not None else queue.Queue(maxsize=1)
        self.timeout = timeout
        self.data = None

    def execute(self):
        """ Override base execute() method to get and handle queue data.
        """
        # when the thread is set to none, it has been stopped.
        while not self.thread.should_stop():
            try:
                self.data = self.queue.get(timeout=self.timeout)
                self.handle()
            except queue.Empty:
                pass

    def handle(self):
        """ Method called to process data in the queue. Must be overridden in subclasses.
        """
        raise NotImplementedError("handle() must be implemented in subclasses!")


