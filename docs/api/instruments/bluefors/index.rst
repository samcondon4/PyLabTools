.. module:: pylabtools.instruments.bluefors

########
Bluefors
########

This section contains specific documentation on the classes and methods available for Bluefors
instruments.

.. toctree::
    :maxdepth: 2

    bluefors_tc

Adapter and channel classes
===========================

The temperature controller is reached over the REST interface of the Bluefors control software, so
it uses its own adapter rather than a VISA connection. Sensors and heaters are PyMeasure channels.

.. autoclass:: pylabtools.instruments.bluefors.BlueforsHTTPAdapter
    :members: get_value, set_value
    :show-inheritance:

.. autoclass:: pylabtools.instruments.bluefors.BlueforsSensor
    :members:
    :show-inheritance:

.. autoclass:: pylabtools.instruments.bluefors.BlueforsHeater
    :members:
    :show-inheritance:

.. autoexception:: pylabtools.instruments.bluefors.BlueforsAPIError
