################################################
Keysight P9374A Streamline USB Network Analyzer
################################################

.. autoclass:: pylabtools.instruments.keysight.KeysightP9374a
    :members:
    :show-inheritance:

Acquiring complete traces
=========================

:meth:`~pylabtools.instruments.keysight.KeysightP9374a.acquire_trace` follows the remote-control
practice in Keysight's network analyzer documentation:

- without averaging (or with point averaging), ``SENS:SWE:MODE SING;*OPC?`` takes one sweep and
  replies only once it is complete;
- with sweep averaging, ``SENS:AVER:CLE`` restarts averaging, ``SENS:SWE:GRO:COUN <averages>``
  and ``SENS:SWE:MODE GRO;*OPC?`` take exactly the sweeps needed for one complete average.

``*OPC?`` blocks until the sweeps are done, so the VISA timeout is raised for the duration of the
wait (by default to 1.5 times the expected time plus 10 s). Afterwards the channel is in HOLD; set
``sweep_mode = "CONT"`` to resume free-running sweeps, e.g. in a procedure's ``shutdown()``.

Reading :attr:`~pylabtools.instruments.keysight.KeysightP9374a.trace_data` alone does not trigger
a sweep, so right after a settings change it can return stale or partially averaged data.
