""" The :class:`Procedure` base class for measurements.

A PyLabTools procedure is an upstream :class:`pymeasure.experiment.Procedure`: parameters are
declared as class attributes with PyMeasure parameter types, and the measurement is written in
``startup()``, ``execute()`` and ``shutdown()``. PyLabTools adds:

- :meth:`Procedure.connect`, which routes a named record to recorders and viewers;
- :meth:`Procedure.emit`, which sends a :class:`~pylabtools.record.Record` to those consumers;
- :meth:`Procedure.should_stop` and :meth:`Procedure.is_last`, backed by the active
  :class:`~pylabtools.runner.Run`.

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

from pymeasure.experiment import Procedure as _PyMeasureProcedure
from pymeasure.experiment.parameters import Parameter

from .consumers import Consumer

__all__ = ["Procedure"]


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

    # - helpers -------------------------------------------------------------------------------- #
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
