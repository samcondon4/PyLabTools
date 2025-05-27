Configuration Dictionaries
###########################

| As discussed in ample places throughout this documentation, PyLabTools is configured by populating 5 *configuration variables*
  with *configuration dictionaries.* These *configuration variables* are as follows:

    1. :ref:`INSTRUMENT_SUITE <user_guide/configuration:Hardware Configuration (INSTRUMENT_SUITE)>`
    2. :ref:`PROCEDURES <user_guide/configuration:Procedure Configuration (PROCEDURES)>`
    3. :ref:`CONTROLLERS <user_guide/configuration:Controller Configuration (CONTROLLERS)>`
    4. :ref:`RECORDERS <user_guide/configuration:Recorder Configuration (RECORDERS)>`
    5. :ref:`VIEWERS <user_guide/configuration:Viewer Configuration (VIEWERS)>`

| This section defines the syntax of the configuration dictionaries that populate these variables.

Hardware Configuration (INSTRUMENT_SUITE)
------------------------------------------

| The basic syntax of a hardware configuration dictionary is as follows:

.. code-block:: python

    HwCfgVar0 = {
        "instance_name": 'user selected string name of the instrument',
        "manufacturer": 'string name of the manufacturer of the instrument.',
        "instrument": 'string with the name of the instrument driver class.',
        "resource_name": 'pyvisa intrument resource name.',
        "subinstruments": '(OPTIONAL) should only be present when configuring a CompoundInstrument, otherwise leave this out!'
        "kwargs": '(OPTIONAL) key-word arguments passed to the instrument initialization function.',
        "params": '(OPTIONAL) set of initial intrument parameter values.'
    }

| Note that the structure of the PyLabTools (and PyMeasure) instrument repositories is:

    instruments/
        - manufacturer/
            - instrument_driver.py
                -InstrumentDriverClass

| So the 'manufacturer' key in the dictionary above must contain the name of a manufacturer folder within either the PyMeasure or PyLabTools
  instrument repositories. Likewise, the 'instrument' key must contain the name of a driver class defined within the specified 'manufacturer' folder.

| All instrument drivers in PyLabTools and PyMeasure utilize the **PyVisa** libary under-the-hood to handle the low-level instrument communication
  details. For every instrument connected to a computer, PyVisa assigns a unique **Resource Name**. The 'resource_name' key must contain a string that
  matches the pyvisa assigned resource name. This value can be determined for a given instrument by executing the following code in a Python interactive
  session:

.. code-block:: python

        import pyvisa as pv

        rm = pv.ResourceManager()
        print(rm.list_resources())

| Also note the 'subinstruments' key. This key is used **only when configuring CompoundInstrument classes**.


Procedure Configuration (PROCEDURES)
-------------------------------------

| Below is the syntax for procedure configuration dictionaries:

.. code-block:: python

    ProcCfgVar = {
        "instance_name": 'string name of the procedure.',
        "type": 'string name of the procedure class.',
        "hw": 'list of the hardware resources that the procedure needs. Entries match the "instance_name" of hardware configuration dictionaries.',
        "records": 'dictionary enumerating the output data products from the procedure.',
        "kwargs": '(OPTIONAL) key-word arguments passed to the procedure initialization function.',
        "params": '(OPTIONAL) set of initial procedure parameter values.'
    }

| Note that the **type** key must contain the name of a class that has been imported into the namespace **procedures**. I.e., PyLabTools takes
  the string written in **type** (say 'ProcClass') and tries to instantiate the class with: procedures.ProcClass.

| The **hw** key is a list of instrument **instance names** i.e. those strings that we used for the **instance_name** key in our hardware configuration
  dictionaries.

| **records** contains another dictionary of the following form:

.. code-block:: python

    "records": {
        'record_name': {'viewer': "viewer-name", 'recorder': "recorder-name"}
    }

| Where 'record_name' is replaced with anything the user desires (that is ideally descriptive of the corresponding data product)
  and "viewer-name" is replaced with the instance name of the viewer that the record should be sent to and "recorder-name" is
  replaced with the instance name of the recorder that the record should be sent to.


Controller Configuration (CONTROLLERS)
--------------------------------------

| Controllers come in two flavors:

    1. Instrument Controllers.
    2. Procedure Controllers.

| The syntax for configuring these two types of controllers varies slightly.

Instrument Controllers
***********************

.. code-block:: python

    InstCntrlCfg = {
        "instance_name": 'string name of the controller',
        "type": "InstrumentController",
        "hw": "instance name of the hardware to be controlled",
        "control_parameters": ['list of pyqtgraph parameter tree entries to control hardware parameters'],
        "status_parameters": ['list of pyqtgraph parameter tree entries to display hardware parameter status'],
        "status_refresh": 'The type of refreshing applied to status_parameters.',
        "kwargs": '(OPTIONAL) key-word arguments passed to the controller initialization function.',
        "params": '(OPTIONAL) set of initial controller parameter values.'
    }

| Note that **type always contains the string InstrumentController**

| **control_parameters** and **status_parameters** are lists of dictionaries corresponding to pyqtgraph parameter tree entries.
  See `PyqtGraph Parameter Trees <https://pyqtgraph.readthedocs.io/en/latest/parametertree/index.html>`_ for details. Also,
  see :ref:`Step-by-Step Config Tutorial <tutorials/stepbystep_config/index:2) First instrument controller>` for example instrument
  controller config dictionaries.

| **status_refresh** defines the manner in which the status parameters are updated. Options for this key include:

    - "manual": status parameters are manually refreshed by pressing a refresh button.
    - "after_set": status parameters are automatically refreshed after being set in the controller.
    - An integer value with the number of milliseconds between queries to instrument parameters.

Procedure Controllers
*********************

.. code-block:: python

    ProcCntrlCfg = {
        "instance_name": 'string name of the controller',
        "type": "ProcedureController",
        "procedure": 'instance name of the procedure to control',
        "kwargs": '(OPTIONAL) key-word arguments passed to the controller initialization function.',
        "params": '(OPTIONAL) set of initial controller parameter values.'
    }

| Here, **type** always contains the string **ProcedureController**.


Recorder Configuration (RECORDERS)
----------------------------------

.. code-block:: python

    RecCfg = {
        "instance_name": 'string name of the recorder.',
        "type": 'name of the recorder class to use.',
        "kwargs": '(OPTIONAL) key-word arguments passed to the recorder initialization function.',
        "params": '(OPTIONAL) set of initial recorder parameter values.'
    }


Viewer Configuration (VIEWERS)
------------------------------

.. code-block:: python

    ViewCfg = {
        "instance_name": 'string name of the viewer',
        "type": 'name of the viewer class to use',
        "kwargs": '(OPTIONAL) key-word arguments passed to the viewer initialization function.',
        "params": '(OPTIONAL) set of initial viewer parameter values.'
    }

|