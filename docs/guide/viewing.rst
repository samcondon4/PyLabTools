Live plotting
#############

Viewers buffer recent data; :mod:`pylabtools.gui` draws them. The GUI needs the ``gui`` extra.

.. code-block:: python

    view = plab.LineViewer(x="f", y=["s21_mag", "s21_phase"], max_rows=1601,
                           clear_on_new_run=True, title="S21",
                           colors={"s21_mag": "y"})

``y``
    Column or list of columns to plot. If omitted, every numeric column except ``x`` is plotted.
``x``
    Column for the horizontal axis; if omitted, points are plotted against their buffer position.
``max_rows``
    Number of rows kept. For a trace, set it to the trace length to show only the latest trace; for
    a time series, it is the length of the rolling window.
``clear_on_new_run``
    Empty the plot when a new run starts.

Plots redraw at most ``fps`` times per second (default 20), and only when new data arrived, so a
fast procedure never floods the display.

In a script
===========

.. code-block:: python

    with plab.running(hdf, temp_view, trace_view):
        run = plab.start_sequence(proc, steps)
        plab.gui.show(temp_view, trace_view, run=run, columns=2, block=True)
        plab.wait(run)

``block=True`` runs the Qt event loop until you close the window. Pressing **Ctrl-C** in the
terminal stops the runs passed as ``run=``, waits for their ``shutdown()``, closes the window and
raises ``KeyboardInterrupt``. Closing the window does *not* stop the run; ``plab.wait(run)`` then
waits for it (Ctrl-C there also stops it cleanly).

In Jupyter
==========

.. code-block:: python

    window = plab.gui.show(temp_view, trace_view, run=run, drive="asyncio")

The window updates while you keep working in the notebook. ``drive="asyncio"`` processes Qt
events from a small task on the kernel's own asyncio loop, every 20 ms, so it keeps running while
the kernel is idle. One task serves all windows and ends when the last window is closed;
call ``show(..., drive="asyncio")`` again to open a new one.

This is an option of ``show()`` rather than a separate "start the event loop" call because there
is nothing to start or stop by hand: the task lives exactly as long as the windows it drives.

The alternative is IPython's Qt integration: run ``%gui qt`` once per kernel, then call
``plab.gui.show(...)`` without ``drive``. On some Windows setups the window hangs with ``%gui qt``;
``drive="asyncio"`` avoids that mechanism. The two should not run together, so if ``%gui qt`` is
active, ``drive="asyncio"`` warns and leaves the window to it; run ``%gui`` (no argument) to turn
it off.

Cell execution blocks the kernel's loop, so a plain long-running cell (``time.sleep``, or
``plab.wait(run)``) freezes the window until it finishes. Start runs with ``plab.start(...)``,
which returns immediately, and let the cell end.

.. note::

    On Windows, the most robust option for live plotting is still a script with ``block=True``.

Viewer failures
===============

If a viewer fails, for example because a ``y`` column is not in the record, the error is logged,
the plot title shows it, and the run and recorders carry on unaffected.

Custom viewers
==============

Subclass :class:`~pylabtools.Viewer` and override ``select(record)`` to choose what to buffer;
read the buffer from the GUI thread with ``snapshot()``.
