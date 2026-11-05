""" Running procedures: :class:`Run`, :func:`start`, :func:`run`, sequences and :func:`sweep`.

A :class:`Run` executes a procedure on its own worker thread, once per *step*. A plain run has a
single step; a sequence has one step per parameter set. Every record emitted during a run carries
the run's ``run_id``, so the whole run (or sequence) becomes one ``RecordGroup`` in the output, and
``RecordGroupInd`` keeps counting across steps.

The run follows the state machine ``QUEUED -> RUNNING -> FINISHED | FAILED | ABORTED``:

- ``shutdown()`` always runs on the worker thread after ``startup()``/``execute()``, even if they
  raise or a stop was requested.
- An exception ends the run as ``FAILED``; it is logged and kept in :attr:`Run.exception`.
- A run only ends once its recorders have handled every record it emitted, so ``FINISHED``
  means the data has been stored, and a recorder failure (even on the last record) is ``FAILED``.
- :meth:`Run.stop` only *requests* a stop. Procedures should check ``self.should_stop()``.
- All parameter values of every step are validated before the run starts, so a typo in step 40 of
  an overnight sequence is reported immediately rather than at 3 a.m.
"""
import enum
import itertools
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone

from pymeasure.experiment import Procedure as _PyMeasureProcedure

from .consumers import ConsumerError
from .log import get_logger
from .record import Record

logger = get_logger(__name__)

__all__ = ["Status", "Run", "start", "run", "start_sequence", "run_sequence", "sweep", "wait"]


class Status(enum.Enum):
    """ State of a :class:`Run`. """
    QUEUED = "queued"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    ABORTED = "aborted"


# - map to the integer codes of upstream pymeasure, kept on procedure.status for compatibility - #
_PYMEASURE_STATUS = {
    Status.QUEUED: _PyMeasureProcedure.QUEUED,
    Status.RUNNING: _PyMeasureProcedure.RUNNING,
    Status.FINISHED: _PyMeasureProcedure.FINISHED,
    Status.FAILED: _PyMeasureProcedure.FAILED,
    Status.ABORTED: _PyMeasureProcedure.ABORTED,
}

_POLL = 0.1  # - seconds; short waits keep the main thread responsive to Ctrl-C on all platforms - #


class Run:
    """ One execution of a procedure over one or more parameter steps.

    Normally created with :func:`start` or :func:`start_sequence` rather than directly.

    :param procedure: The :class:`~pylabtools.procedure.Procedure` to execute.
    :param steps: Sequence of ``{parameter name: value}`` dicts, applied in order. Values carry
        over from one step to the next unless overridden. Defaults to a single step with no changes.
    :param run_id: Identifier stored in every record; generated if not given.
    :raises NameError: If a step names an unknown parameter.
    :raises ValueError: If a value is invalid or a parameter has no value.
    """

    def __init__(self, procedure, steps=None, run_id=None):
        self.procedure = procedure
        self.steps = [{}] if steps is None else [dict(step) for step in steps]
        if not self.steps:
            raise ValueError("A run needs at least one step.")
        _validate_steps(procedure, self.steps)

        self.run_id = run_id if run_id is not None else uuid.uuid4().hex
        self.status = Status.QUEUED
        self.exception = None
        self.step = None
        self.started_at = None
        self.finished_at = None

        self._stop = threading.Event()
        self._done = threading.Event()
        self._thread = None
        self._consumers = []
        self._emit_lock = threading.Lock()
        self._indices = {}
        self._proc_params = {}
        self._metadata = {}

    # - control -------------------------------------------------------------------------------- #
    def start(self):
        """ Start the run on a new worker thread and return immediately.

        :raises RuntimeError: If the run was already started or the procedure is already running.
        """
        if self._thread is not None:
            raise RuntimeError("This run has already been started; create a new run instead.")
        if self.procedure._run is not None:
            raise RuntimeError(f"{type(self.procedure).__name__} is already running.")
        self.procedure._run = self
        self._consumers = self.procedure.consumers()
        self._thread = threading.Thread(target=self._target, name=f"pylabtools-run-{self.run_id[:8]}")
        self._thread.start()
        return self

    def stop(self):
        """ Request the run to stop. The procedure sees ``should_stop() == True``; ``shutdown()`` still runs. """
        if not self._done.is_set():
            logger.info("Stop requested for run %s", self.run_id[:8])
        self._stop.set()

    def wait(self, timeout=None):
        """ Wait for the run to end.

        :param timeout: Seconds to wait. None waits indefinitely.
        :return: True if the run has ended.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._done.wait(_POLL):
            if deadline is not None and time.monotonic() >= deadline:
                return False
        return True

    def raise_for_status(self):
        """ Re-raise the exception of a ``FAILED`` run. Does nothing otherwise. """
        if self.status is Status.FAILED and self.exception is not None:
            raise self.exception

    # - state ---------------------------------------------------------------------------------- #
    @property
    def done(self):
        """ True once the run has ended (finished, failed or aborted). """
        return self._done.is_set()

    @property
    def stop_requested(self):
        """ True once :meth:`stop` has been called. """
        return self._stop.is_set()

    @property
    def duration(self):
        """ Run duration in seconds so far (or in total once done), or None if not started. """
        if self.started_at is None:
            return None
        end = self.finished_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def __repr__(self):
        step = "" if self.step is None else f", step={self.step + 1}/{len(self.steps)}"
        return (f"<Run({type(self.procedure).__name__}, run_id={self.run_id[:8]}, "
                f"status={self.status.value}{step})>")

    # - worker thread -------------------------------------------------------------------------- #
    def _target(self):
        proc = self.procedure
        name = type(proc).__name__
        self.started_at = datetime.now(timezone.utc)
        self._set_status(Status.RUNNING)
        logger.info("Run %s of %s started (%d step%s)", self.run_id[:8], name,
                    len(self.steps), "" if len(self.steps) == 1 else "s")
        error = None
        try:
            for i, step in enumerate(self.steps):
                if self._stop.is_set():
                    break
                self.step = i
                self._run_step(step)
        except BaseException as exc:  # - noqa: anything raised by user code must end the run - #
            error = exc
        finally:
            for consumer in self._consumers:
                consumer.notify_run_end(self.run_id)
            # - FINISHED must mean "stored": wait until recorders have handled every record - #
            for consumer in self._consumers:
                if consumer.critical:
                    consumer.join_queue()
            if error is None:
                failed = [c for c in self._consumers if c.critical and c.failed]
                if failed:
                    error = ConsumerError(f"{failed[0].name} failed: {failed[0].exception!r}")
                    error.__cause__ = failed[0].exception

            if error is not None:
                self.exception = error
                status = Status.FAILED
                logger.error("Run %s of %s failed: %r", self.run_id[:8], name, error, exc_info=error)
            elif self._stop.is_set():
                status = Status.ABORTED
                logger.info("Run %s of %s aborted", self.run_id[:8], name)
            else:
                status = Status.FINISHED
                logger.info("Run %s of %s finished", self.run_id[:8], name)
            self.finished_at = datetime.now(timezone.utc)
            proc._run = None
            self._set_status(status)
            self._done.set()

    def _run_step(self, step):
        proc = self.procedure
        proc.set_parameters(step)
        proc.check_parameters()
        self._proc_params = proc.parameter_values()
        self._metadata = {}
        if len(self.steps) > 1:
            logger.info("Run %s step %d/%d: %s", self.run_id[:8], self.step + 1, len(self.steps), step)
        try:
            proc.startup()
            self._metadata = proc._evaluate_metadata()
            proc.execute()
        except BaseException:
            self._safe_shutdown()
            raise
        proc.shutdown()

    def _safe_shutdown(self):
        """ Run shutdown() after an error, logging (not raising) a second error from shutdown itself. """
        try:
            self.procedure.shutdown()
        except Exception as exc:
            logger.error("shutdown() of %s also failed: %r", type(self.procedure).__name__, exc, exc_info=exc)

    def _set_status(self, status):
        self.status = status
        self.procedure.status = _PYMEASURE_STATUS[status]

    def _emit(self, record_name, data, meta, consumers):
        """ Build a Record and queue it on each consumer. Called by Procedure.emit(). """
        with self._emit_lock:
            index = self._indices.get(record_name, 0)
            self._indices[record_name] = index + 1
            full_meta = dict(self._metadata)
            if meta is not None:
                full_meta.update(meta)
            record = Record(record_name, data, proc_params=self._proc_params, meta=full_meta,
                            run_id=self.run_id, index=index)
            for consumer in consumers:
                if consumer.failed and not consumer.critical:
                    continue
                consumer.put(record)
        return record


def _validate_steps(procedure, steps):
    """ Check every step's parameter names and values against copies of the procedure parameters. """
    parameters = procedure._parameters
    current = {name: getattr(procedure, name) for name in parameters}
    for i, step in enumerate(steps):
        where = "" if len(steps) == 1 else f"Step {i}: "
        unknown = sorted(set(step) - set(parameters))
        if unknown:
            raise NameError(f"{where}unknown parameter(s) {unknown} for {type(procedure).__name__}; "
                            f"known parameters are {sorted(parameters)}.")
        current = {**current, **step}
        for name, value in current.items():
            if value is None:
                raise ValueError(f"{where}parameter {name!r} of {type(procedure).__name__} has no value.")
            check = deepcopy(parameters[name])
            try:
                check.value = value
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{where}invalid value {value!r} for parameter {name!r}: {exc}") from exc


def start(procedure, **params):
    """ Start a single run of ``procedure`` in the background.

    :param procedure: The procedure to run.
    :param params: Parameter values for this run, by attribute name.
    :return: The started :class:`Run`.
    """
    return Run(procedure, [params]).start()


def run(procedure, **params):
    """ Run ``procedure`` once and wait for it to end.

    Ctrl-C requests a stop and waits for ``shutdown()`` before re-raising KeyboardInterrupt.

    :return: The finished :class:`Run`.
    :raises Exception: The procedure's exception, if the run failed.
    """
    return _wait_for(start(procedure, **params))


def start_sequence(procedure, steps, **common):
    """ Start a sequence: run ``procedure`` once per parameter set in ``steps``.

    The whole sequence shares one ``run_id``, so it is stored as a single ``RecordGroup``.
    A failing step ends the sequence as ``FAILED``.

    :param procedure: The procedure to run.
    :param steps: Iterable of ``{parameter name: value}`` dicts, e.g. from :func:`sweep`.
    :param common: Parameter values applied to every step (overridden by the step's own values).
    :return: The started :class:`Run`.
    """
    return Run(procedure, [{**common, **step} for step in steps]).start()


def run_sequence(procedure, steps, **common):
    """ Blocking version of :func:`start_sequence`; see :func:`run` for Ctrl-C handling. """
    return _wait_for(start_sequence(procedure, steps, **common))


def sweep(**values):
    """ Build the steps of a sequence as the Cartesian product of parameter values.

    The first keyword is the outermost loop. Scalars are held constant::

        >>> sweep(setpoint=[1, 2], samples=10)
        [{'setpoint': 1, 'samples': 10}, {'setpoint': 2, 'samples': 10}]

    :param values: Parameter name to a list of values (or a single value).
    :return: List of step dicts.
    """
    names = list(values)
    lists = [_as_list(values[name]) for name in names]
    return [dict(zip(names, combo)) for combo in itertools.product(*lists)]


def _as_list(value):
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        return [value]
    return list(value)


def wait(active):
    """ Wait for a started run to end, re-raising its exception if it failed.

    Ctrl-C requests a stop and waits for ``shutdown()`` before re-raising KeyboardInterrupt.

    :param active: A :class:`Run` from :func:`start` or :func:`start_sequence`.
    :return: The run.
    """
    return _wait_for(active)


def _wait_for(active):
    try:
        active.wait()
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt: stopping run %s and waiting for shutdown()", active.run_id[:8])
        active.stop()
        active.wait()
        raise
    active.raise_for_status()
    return active
