""" The :class:`Consumer` base class: a thread that processes records from a queue.

Recorders and viewers are consumers. A consumer must be running (``consumer.start()`` or
``with consumer:``) before a procedure emits records to it. Stopping a consumer processes every
record that is still queued before the thread exits, so no emitted data is dropped.

All consumer hooks (:meth:`Consumer.on_start`, :meth:`Consumer.handle`,
:meth:`Consumer.on_run_end`, :meth:`Consumer.on_stop`) run on the consumer's own thread, so a
subclass can keep file handles and other state without locking.
"""
import atexit
import contextlib
import queue
import threading
import time
import weakref

from .log import get_logger
from .record import Record

logger = get_logger(__name__)

# - consumers that are running; drained at interpreter exit so queued records are not lost - #
_RUNNING = weakref.WeakSet()


@atexit.register
def _stop_running_consumers():
    # - runs after non-daemon threads (including active runs) have been joined - #
    for consumer in list(_RUNNING):
        try:
            consumer.stop(timeout=30)
        except Exception as exc:
            logger.error("Could not stop %s at exit: %r", consumer.name, exc)


@contextlib.contextmanager
def running(*consumers):
    """ Context manager that starts several consumers and stops them all on exit::

        with plab.running(hdf, csv, view):
            plab.run(proc)

    Consumers are stopped in reverse order, even if starting a later one or the body fails.
    """
    with contextlib.ExitStack() as stack:
        for consumer in consumers:
            stack.enter_context(consumer)
        yield consumers


class ConsumerError(RuntimeError):
    """ Raised when records are sent to a consumer that is not running or has failed. """


class _RunEnd:
    """ Queue message sent when a run that routes records to the consumer has ended. """

    def __init__(self, run_id):
        self.run_id = run_id


_STOP = object()


class Consumer:
    """ Base class for objects that receive :class:`~pylabtools.record.Record` objects on a thread.

    Subclasses implement :meth:`handle`, and optionally :meth:`on_start`, :meth:`on_run_end` and
    :meth:`on_stop`.

    :param name: Name used in log messages. Defaults to the class name.
    :param maxsize: Maximum queue length. 0 (default) means unbounded; a positive value makes
        ``emit()`` block when the consumer falls behind, bounding memory use.

    :cvar critical: If True, a failure in this consumer fails the run that feeds it (recorders, so
        that data is never silently lost). If False, the failure is logged and records are no
        longer sent to it, but the run continues (viewers).
    """

    critical = True

    def __init__(self, name=None, maxsize=0):
        self.name = name if name is not None else type(self).__name__
        self._queue = queue.Queue(maxsize=maxsize)
        self._thread = None
        self._exception = None
        self._lock = threading.Lock()

    # - lifecycle ------------------------------------------------------------------------------ #
    def start(self):
        """ Start the consumer thread. Calling start() on a running consumer has no effect. """
        with self._lock:
            if self.running:
                return self
            self._exception = None
            self._queue = queue.Queue(maxsize=self._queue.maxsize)
            started = threading.Event()
            self._thread = threading.Thread(target=self._loop, args=(started,),
                                            name=f"pylabtools-{self.name}", daemon=True)
            self._thread.start()
            _RUNNING.add(self)
        started.wait()
        if self._exception is not None:
            raise ConsumerError(f"{self.name} failed to start: {self._exception!r}") from self._exception
        return self

    def stop(self, timeout=None):
        """ Process every queued record, run :meth:`on_stop`, and stop the thread.

        :param timeout: Seconds to wait for the queue to drain. None waits indefinitely.
        :raises TimeoutError: If the thread does not finish within ``timeout``.
        """
        thread = self._thread
        if thread is None or not thread.is_alive():
            _RUNNING.discard(self)
            return
        self._queue.put(_STOP)
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError(f"{self.name} did not stop within {timeout} s.")
        _RUNNING.discard(self)

    @property
    def running(self):
        """ True while the consumer thread is alive. """
        return self._thread is not None and self._thread.is_alive()

    @property
    def failed(self):
        """ True if :meth:`handle` (or another hook) raised an exception. """
        return self._exception is not None

    @property
    def exception(self):
        """ The exception that made the consumer fail, or None. """
        return self._exception

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    # - producer side -------------------------------------------------------------------------- #
    def put(self, record):
        """ Queue a record for processing. Called by ``Procedure.emit()``.

        :raises ConsumerError: If the consumer has failed or is not running.
        """
        if self._exception is not None:
            raise ConsumerError(f"{self.name} has failed: {self._exception!r}") from self._exception
        if not self.running:
            raise ConsumerError(f"{self.name} is not running. Start it with `{self.name}.start()` or "
                                f"`with {self.name}:` before running the procedure.")
        self._queue.put(record)

    def notify_run_end(self, run_id):
        """ Queue a notification that the run ``run_id`` has ended. Called by the run. """
        if self.running:
            self._queue.put(_RunEnd(run_id))

    def join_queue(self, timeout=None):
        """ Block until every record queued so far has been processed.

        :param timeout: Seconds to wait. None waits indefinitely.
        :return: True if the queue was drained, False on timeout or if the consumer stopped.
        """
        if not self.running:
            return False
        done = threading.Event()
        self._queue.put(done)
        deadline = None if timeout is None else time.monotonic() + timeout
        # - poll so that a consumer which stops (or a Ctrl-C) cannot leave us blocked forever - #
        while not done.wait(0.05):
            if not self.running:
                return False
            if deadline is not None and time.monotonic() >= deadline:
                return False
        return True

    # - consumer thread ------------------------------------------------------------------------ #
    def _loop(self, started):
        try:
            self.on_start()
        except Exception as exc:
            self._fail(exc, "on_start")
            started.set()
            return
        started.set()

        while True:
            item = self._queue.get()
            if item is _STOP:
                break
            if isinstance(item, threading.Event):
                item.set()
                continue
            if self._exception is not None:
                continue  # - failed: discard remaining messages until stopped - #
            try:
                if isinstance(item, _RunEnd):
                    self.on_run_end(item.run_id)
                elif isinstance(item, Record):
                    self.handle(item)
            except Exception as exc:
                self._fail(exc, "handle" if isinstance(item, Record) else "on_run_end")

        try:
            self.on_stop()
        except Exception as exc:
            self._fail(exc, "on_stop")

    def _fail(self, exc, where):
        self._exception = exc
        logger.error("%s failed in %s(): %r", self.name, where, exc, exc_info=exc)

    # - hooks for subclasses ------------------------------------------------------------------- #
    def on_start(self):
        """ Called on the consumer thread when it starts. """

    def handle(self, record):
        """ Process one record. Must be implemented by subclasses. """
        raise NotImplementedError("Consumer subclasses must implement handle().")

    def on_run_end(self, run_id):
        """ Called on the consumer thread after every record of run ``run_id`` has been handled. """

    def on_stop(self):
        """ Called on the consumer thread after the queue has drained, when the consumer stops. """

    def __repr__(self):
        state = "failed" if self.failed else ("running" if self.running else "stopped")
        return f"<{type(self).__name__}(name={self.name!r}, {state})>"
