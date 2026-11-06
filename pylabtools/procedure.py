""" The :class:`Procedure` base class for measurements.

A PyLabTools procedure is an upstream :class:`pymeasure.experiment.Procedure`: parameters are
declared as class attributes with PyMeasure parameter types, and the measurement is written in
``startup()``, ``execute()`` and ``shutdown()``. PyLabTools adds:

- :meth:`Procedure.connect`, which routes a named record to recorders and viewers;
- :meth:`Procedure.emit`, which sends a :class:`~pylabtools.record.Record` to those consumers;
- :meth:`Procedure.should_stop`, :meth:`Procedure.is_last` and :meth:`Procedure.sleep`, backed by
  the active :class:`~pylabtools.runner.Run`;
- :func:`every`, which marks a method as a background task that runs at a fixed interval for the
  whole run;
- :class:`Metadata`, upstream PyMeasure metadata that can be limited to specific records.

Instruments and any other resources are ordinary constructor arguments::

    class VoltageLog(Procedure):
        samples = IntegerParameter("Samples", default=100)

        def __init__(self, inst, **kwargs):
            super().__init__(**kwargs)
            self.inst = inst

        def execute(self):
            for i in range(self.samples):
                if self.should_stop():
                    break
                self.emit("voltage", {"i": i, "V": self.inst.voltage})
"""
import inspect
import numbers
import time

from pymeasure.experiment import Procedure as _PyMeasureProcedure
from pymeasure.experiment.parameters import Metadata as _PyMeasureMetadata
from pymeasure.experiment.parameters import Parameter

from .consumers import Consumer

__all__ = ["Metadata", "Procedure", "every"]


class Metadata(_PyMeasureMetadata):
    """ PyMeasure :class:`~pymeasure.experiment.parameters.Metadata`, optionally limited to records.

    Metadata values are read from ``fget`` before and after ``startup()`` of every run or sequence
    step, and stored in the ``meta`` table as ``meta_<attribute name>``. Plain PyMeasure ``Metadata``
    is added to *every* record the procedure emits; with ``records``, only to the named ones::

        vna_power = plab.Metadata("VNA power", units="dBm", fget="vna.power", records="s21")

    :param name: Display name.
    :param fget: Attribute path from the procedure (e.g. ``"vna.power"``), method name, or callable.
    :param records: Record name, or list of record names, that receive this metadata. None
        (default) means every record. Each name must be connected when the run starts.
    :param kwargs: Further PyMeasure ``Metadata`` arguments (``units``, ``default``, ``fmt``).
    """

    def __init__(self, name, fget=None, records=None, **kwargs):
        if records is not None:
            records = (records,) if isinstance(records, str) else tuple(records)
            if not records or not all(isinstance(r, str) and r for r in records):
                raise ValueError(f"Metadata {name!r}: records must be a record name or a non-empty "
                                 f"list of record names, got {records!r}.")
            records = frozenset(records)
        self.records = records
        super().__init__(name, fget=fget, **kwargs)

_TASK_ATTR = "_pylabtools_every"


def every(interval):
    """ Mark a procedure method as a background task that runs every ``interval`` seconds.

    The run calls the method on its own thread, at a fixed cadence, for the *whole* run: it starts
    once the first step's parameters are set (just before the first ``startup()``) and stops after
    the last ``shutdown()``, so a sequence is covered without gaps between steps. Records emitted by
    a task carry the parameters of the step that is active at that moment. If a task raises, the
    run is stopped and ends ``FAILED``. A tick that takes longer than the interval skips the missed
    ticks rather than running them back to back.

    Tasks should return promptly; they run concurrently with ``startup()``/``execute()``, so only
    use instruments that tolerate access from two threads::

        class Sweep(plab.Procedure):
            poll_interval = FloatParameter("Poll interval", units="s", default=5)

            @plab.every("poll_interval")
            def poll_fridge(self):
                self.emit("fridge", {"T6": self.tc.temperature(6)})

    :param interval: Seconds between calls, or the attribute name of a parameter holding the
        interval (read before every call, so it can change between sequence steps).
    """
    if callable(interval):
        raise TypeError("every() needs an interval: use @plab.every(seconds) or @plab.every('parameter').")
    if isinstance(interval, numbers.Real):
        if isinstance(interval, bool) or interval <= 0:
            raise ValueError(f"every() interval must be a positive number of seconds, got {interval!r}.")
    elif not isinstance(interval, str):
        raise TypeError(f"every() interval must be seconds or a parameter name, got {interval!r}.")

    def decorate(method):
        setattr(method, _TASK_ATTR, interval)
        return method

    return decorate


class Procedure(_PyMeasureProcedure):
    """ Base class for PyLabTools measurement procedures.

    :param kwargs: Initial parameter values, by attribute name. Unknown names raise TypeError.
    """

    def __init__(self, **kwargs):
        known = self.parameter_names()
        unknown = sorted(set(kwargs) - set(known))
        if unknown:
            raise TypeError(f"{type(self).__name__} got unknown parameter(s) {unknown}; "
                            f"known parameters are {sorted(known)}.")
        self._routes = {}
        self._run = None
        super().__init__(**kwargs)

    @classmethod
    def parameter_names(cls):
        """ Attribute names of the procedure's parameters. """
        return [name for name, obj in inspect.getmembers(cls) if isinstance(obj, Parameter)]

    @classmethod
    def tasks(cls):
        """ Background tasks declared with :func:`every`, as ``{method name: interval}``. """
        return {name: getattr(obj, _TASK_ATTR) for name, obj in inspect.getmembers(cls)
                if callable(obj) and hasattr(obj, _TASK_ATTR)}

    # - routing -------------------------------------------------------------------------------- #
    def connect(self, record_name, *consumers):
        """ Route the record ``record_name`` to one or more consumers (recorders and viewers).

        :param record_name: The name passed to :meth:`emit`.
        :param consumers: :class:`~pylabtools.consumers.Consumer` instances.
        :return: The procedure, so calls can be chained.
        """
        if not isinstance(record_name, str) or not record_name:
            raise ValueError("record_name must be a non-empty string.")
        if not consumers:
            raise ValueError("connect() needs at least one consumer.")
        for consumer in consumers:
            if not isinstance(consumer, Consumer):
                raise TypeError(f"Expected a Consumer (recorder or viewer), got {type(consumer).__name__}.")
        self._check_not_running("connect consumers")
        routed = self._routes.setdefault(record_name, [])
        for consumer in consumers:
            if consumer not in routed:
                routed.append(consumer)
        return self

    def disconnect(self, record_name=None, consumer=None):
        """ Remove routes. With no arguments, remove all of them.

        :param record_name: Only remove routes of this record.
        :param consumer: Only remove routes to this consumer.
        """
        self._check_not_running("disconnect consumers")
        names = list(self._routes) if record_name is None else [record_name]
        for name in names:
            if consumer is None:
                self._routes.pop(name, None)
            elif consumer in self._routes.get(name, []):
                self._routes[name].remove(consumer)
                if not self._routes[name]:
                    del self._routes[name]

    @property
    def routes(self):
        """ Mapping of record name to the tuple of consumers it is routed to. """
        return {name: tuple(consumers) for name, consumers in self._routes.items()}

    def consumers(self):
        """ All consumers connected to this procedure, without duplicates. """
        unique = []
        for consumers in self._routes.values():
            unique.extend(c for c in consumers if c not in unique)
        return unique

    # - methods used inside startup/execute/shutdown ------------------------------------------- #
    def emit(self, record_name, data, meta=None):
        """ Send data to every consumer connected to ``record_name``.

        A new immutable :class:`~pylabtools.record.Record` is created on every call, holding a copy
        of ``data``, the current parameter values, and the metadata.

        :param record_name: Name of the record. Must have been connected with :meth:`connect`.
        :param data: Data to emit; see :func:`pylabtools.record.to_dataframe` for accepted types.
        :param meta: Optional mapping of metadata for this emit. Values from PyMeasure ``Metadata``
            attributes of the procedure are included automatically; ``meta`` overrides them.
        :return: The emitted Record.
        :raises KeyError: If ``record_name`` is not connected.
        :raises RuntimeError: If called outside of a run.
        """
        run = self._run
        if run is None:
            raise RuntimeError("emit() can only be called while the procedure is running; "
                               "start it with pylabtools.start() or pylabtools.run().")
        if record_name not in self._routes:
            raise KeyError(f"Record {record_name!r} is not connected to any consumer. Connected records: "
                           f"{sorted(self._routes)}. Use procedure.connect({record_name!r}, recorder, ...).")
        return run._emit(record_name, data, meta, self._routes[record_name])

    def should_stop(self):
        """ True once a stop has been requested for the active run. Check this regularly in execute(). """
        run = self._run
        return run is not None and run.stop_requested

    def is_last(self):
        """ True if the current step is the last step of the active run or sequence. """
        run = self._run
        return run is None or run.step == len(run.steps) - 1

    def sleep(self, seconds):
        """ Wait ``seconds``, returning early if a stop is requested.

        Use instead of ``time.sleep()`` for long waits such as thermal settling, so that a stop (or a
        failing background task) takes effect immediately::

            if not self.sleep(self.settle_time):
                return  # - stopped while waiting - #

        :return: True if the full time elapsed, False if the wait ended because of a stop.
        """
        run = self._run
        if run is None:
            time.sleep(seconds)
            return True
        return not run._stop.wait(max(0.0, seconds))

    # - helpers -------------------------------------------------------------------------------- #
    def _metadata_scopes(self):
        """ ``{metadata attribute: frozenset of record names}`` for metadata limited with ``records``. """
        return {item: metadata.records for item, metadata in self._metadata.items()
                if getattr(metadata, "records", None) is not None}

    def _evaluate_metadata(self):
        """ Evaluate PyMeasure ``Metadata`` attributes and return ``{name: value}``.

        Unlike upstream ``evaluate_metadata()``, this can be called once per run: metadata with an
        ``fget`` is re-read each time instead of raising on re-evaluation.
        """
        values = {}
        for item, metadata in self._metadata.items():
            new_value = None if metadata.fget is not None else getattr(self, item)
            value = metadata.evaluate(parent=self, new_value=new_value)
            setattr(self, item, value)
            values[item] = value
        return values

    def _check_not_running(self, action):
        if self._run is not None:
            raise RuntimeError(f"Cannot {action} while the procedure is running.")
