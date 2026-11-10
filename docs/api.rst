API reference
#############

Everything below is importable from the top-level package, e.g. ``plab.HDFRecorder``.

Running procedures
==================

.. autoclass:: pylabtools.Procedure
    :members: connect, disconnect, routes, consumers, emit, should_stop, is_last, sleep,
        parameter_names, tasks
    :no-inherited-members:

.. autofunction:: pylabtools.every

.. autoclass:: pylabtools.Metadata
    :members: records
    :no-inherited-members:

.. autofunction:: pylabtools.run
.. autofunction:: pylabtools.start
.. autofunction:: pylabtools.run_sequence
.. autofunction:: pylabtools.start_sequence
.. autofunction:: pylabtools.sweep
.. autofunction:: pylabtools.wait

.. autoclass:: pylabtools.Run
    :members:

.. autoclass:: pylabtools.Status
    :members:
    :undoc-members:

Records
=======

.. autoclass:: pylabtools.Record
    :members: n_rows

.. autofunction:: pylabtools.record.to_dataframe

Consumers
=========

.. autoclass:: pylabtools.Consumer
    :members:

.. autofunction:: pylabtools.running

.. autoexception:: pylabtools.ConsumerError

Recorders
=========

.. autoclass:: pylabtools.Recorder
    :members: last_record_group, write

.. autoclass:: pylabtools.HDFRecorder
    :members: path

.. autoclass:: pylabtools.CSVRecorder
    :members: file_for

.. autofunction:: pylabtools.read_hdf
.. autofunction:: pylabtools.read_csv
.. autofunction:: pylabtools.hdf_records

.. autoexception:: pylabtools.SchemaError

.. autoclass:: pylabtools.recorders.RecordTables

Viewers
=======

.. autoclass:: pylabtools.Viewer
    :members: select, snapshot, version, clear

.. autoclass:: pylabtools.LineViewer
    :members: plot_data

Analysis
========

.. autoclass:: pylabtools.analysis.Dataset
    :members: records, record

.. autoclass:: pylabtools.analysis.RecordView
    :members: groups, keys, columns, params, emit_table, to_frame, group, where, rows, values, emits,
        reduce, align, fits, with_data

.. autoclass:: pylabtools.analysis.Emit
    :members: key, timestamp

.. autofunction:: pylabtools.analysis.concat

.. autofunction:: pylabtools.analysis.plot.lineplot
.. autofunction:: pylabtools.analysis.plot.scatterplot
.. autoexception:: pylabtools.analysis.plot.AveragingWarning

Resonators
----------

.. automodule:: pylabtools.analysis.resonator
    :no-members:

.. autofunction:: pylabtools.analysis.resonator.calibrate_cable_delay
.. autofunction:: pylabtools.analysis.resonator.calibrate_constant_scaling
.. autofunction:: pylabtools.analysis.resonator.fit_res_params
.. autofunction:: pylabtools.analysis.resonator.arc_length_weights
.. autoexception:: pylabtools.analysis.resonator.CalibrationWarning
.. autofunction:: pylabtools.analysis.resonator.plot_res_data
.. autofunction:: pylabtools.analysis.resonator.plot_res_params

Converting 0.9 files
====================

.. autofunction:: pylabtools.legacy.convert_hdf

GUI
===

.. automodule:: pylabtools.gui
    :members: show, ViewerWindow, LineViewerWidget, widget_for
    :no-show-inheritance:

Logging
=======

.. automodule:: pylabtools.log
    :members: enable, disable, get_logger
