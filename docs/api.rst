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

GUI
===

.. automodule:: pylabtools.gui
    :members: show, ViewerWindow, LineViewerWidget, widget_for
    :no-show-inheritance:

Logging
=======

.. automodule:: pylabtools.log
    :members: enable, disable, get_logger
