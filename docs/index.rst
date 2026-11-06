PyLabTools
##########

PyLabTools is a Python framework for automating laboratory measurements. You write a measurement
as a **procedure** that talks to `PyMeasure <https://pymeasure.readthedocs.io>`_ instrument drivers
and **emits** data; each emitted record is routed to **recorders**, which archive it (HDF5, CSV),
and **viewers**, which display it live.

.. code-block:: python

    import pylabtools as plab

    proc = VoltageLog(instrument)
    hdf = plab.HDFRecorder("run.h5")
    view = plab.LineViewer(x="t", y="V")
    proc.connect("voltage", hdf, view)

    with plab.running(hdf, view):
        plab.run(proc, setpoint=2.5)

    df = plab.read_hdf("run.h5", "voltage")

Everything is plain Python: instruments, procedures, recorders and viewers are created in a script
or notebook, with no configuration files. The core runs headless; the Qt display is optional.

PyLabTools 1.0 is a rewrite of the configuration-file based 0.9 series, which grew out of
*SPHERExLabTools* for the optical calibration of NASA's SPHEREx telescope
(`Condon et al. 2022 <https://arxiv.org/abs/2208.05099>`_). See :doc:`migrating` for the changes.

.. toctree::
    :maxdepth: 2
    :caption: Getting started

    installation
    quickstart
    concepts

.. toctree::
    :maxdepth: 2
    :caption: Guides

    guide/procedures
    guide/sequences
    guide/recording
    guide/viewing

.. toctree::
    :maxdepth: 1
    :caption: Reference

    api
    api/instruments/index
    migrating
    changelog
    development
