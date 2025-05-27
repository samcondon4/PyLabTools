Output Data Standard
#####################

Overview
---------

| While PyLabTools supports output to many file types, the principles of how experiment data is organized for
  archival are common to all types. As described in :ref:`Fundamentals <user_guide/fundamentals/index:Fundamentals>`, data
  is generated and sent out for archival via :ref:`Procedures <user_guide/fundamentals/index:Procedures>`. Execution of an **individual procedure**
  generates data which is wrapped into a **Record**. A **procedure sequence** is a set of multiple procedures which execute in a loop to
  generate a **RecordGroup**.

| In addition to the measured quantities of an experiment (voltage, temperature, images, etc.), Records also contain instrument
  metadata, procedure parameters, timestamps, etc. Generally, information within a Record is placed into one of 3 categories:

    1. **Data**: The measured quantities of the experiment.
    2. **Procedure Parameters**: Parameters of the procedure that generated the measured quantities.
    3. **Metadata**: Other relevant information about the state of the experiment and the instruments within the experiment testbed.

| For any given output filetype, these pieces of information are separated but linked together via two indices called *RecordGroup*
  and *RecordGroupInd*. *RecordGroup* is an integer identifying a set of records that are grouped together, for instance after being
  generated from the same Procedure Sequence. *RecordGroupInd* identifies unique records within the larger Record Group.

| Depending on the specific recorder in use, these categories can be merged together into a single larger table, or kept
  separate.

Example
--------

| *note*: data values generated here are clearly physically unrealistic. Values in tables are simply to provide a demonstration of the
  manner in which experimental data is organized with PyLabTools.

| Let's consider an example using the fake experiment generated in the :ref:`Step-by-Step Experiment Configuration <tutorials/stepbystep_config/index:Step-by-Step Experiment Configuration>`
  tutorial.

| In this experiment, the temperature of a cryostat baseplate is monitored in response to some voltage applied to a heater. Additionally, the thermal emission of
  the heater is monitored via an IR camera.

  The measured quantities of the experiment are:

    - Baseplate temperature (K)
    - Heater IR emission intensity (W)
    - Heater voltage (V)
    - Timestamp at which quantities are measured (YYYYMMDD_HHMMSS)

  The parameters of the Procedure recording the above information are:

    - Heater voltage (V)
    - Sample Time (s)
    - Sample Rate (hz)

  Other metadata relevant to the experiment are:

    - Camera gain
    - Camera Frame Width
    - Camera Frame Height

| Now lets take a look at the data generated for each of the three categories after a few measurements.

1) 10 seconds of data at a single heater voltage
*************************************************

| Suppose that to start, our cryostat baseplate temperature is stable at 40K. Then, we apply 5V. to the heater input and record
  data every second for 10 seconds. Our procedure parameters then look like:

    - Heater input voltage = 5
    - Sample Time = 10
    - Sample Rate = 1

| After the procedure completes its 10 seconds of data collection, we will have three tables generated corresponding to the three categories
  **1. Data**, **2. Procedure Parameters**, and **3. Metadata**. These tables will look something like:

  **1. Data:**

    .. figure:: fig/Data_rg0.png

        Data table after the first measurement.

  **2. Procedure Parameters**

    .. figure:: fig/PP_rg0.png

        Procedure parameters table after the first measurement.

  **3. Metadata**

    .. figure:: fig/Meta_rg0.png

        Metadata table after the first measurement.

| Note that since we recorded data every second for 10-seconds, our individual **Record** has 10 rows, indicated by the *RecordRow* column
  in the data table. The procedure parameters and metadata tables are linked to the 10 rows of measurements through the *RecordGroup* and *RecordGroupInd*
  indices.

2) 2 seconds of data at several heater voltages
*************************************************

| Now suppose that we would like to run a sequence of measurements in which we record just 2 seconds of data at several heater voltages.
  Say that we have 5 total heater voltages that we would like to run, the list of which being: **heater_voltage = [0.0, 2.0, 4.0, 6.0, 0.0]**

| After constructing the appropriate Procedure Sequence and running the measurement, our tables will then look something like:

  **1. Data:**

    .. figure:: fig/Data_rg1.png

        Data table after the procedure sequence.

  **2. Procedure Parameters**

    .. figure:: fig/PP_rg1.png

        Procedure parameters table after the procedure sequence.

  **3. Metadata**

    .. figure:: fig/Meta_rg1.png

        Metadata table after the procedure sequence.

| Note the resulting structure of the tables. The *RecordGroup* increments from 0 to 1, since we appended to the existing
  tables. Also, since we ran this measurement all within the same procedure sequence, all of the new data falls with *RecordGroup = 1*.
  The *RecordGroupInd* scales from 0 to 4 since we took measurements at 5 separate heater voltages within the same
  procedure sequence. Finally, for every new *RecordGroup* and *RecordGroupInd* pair, there are two values of *RecordRow* since
  we measured two seconds of data at every heater voltage.

3) Merging the tables
**********************

| The **Data**, **Procedure Parameters**, and **Metadata** tables are all generated internally by the base recorder class.
  Depending on the output file format desired, i.e. the specific recorder class in use, these tables may be merged into
  a single table to facilitate writing to a single file or database entry. Note that when these tables are merged, all
  column labels from the **Procedure Parameters** table are prepended with the string 'proc' while **Metadata** column
  labels are prepended with 'meta.'

| Merging of all tables generated in this example produces a table of the following form:

.. raw:: html
    :file: merged_table.html


Recorders and Output-File Formats
----------------------------------

| Specific recorders which write the **Data**, **Procedure Parameters**, and **Metadata** tables out to files or databases
  can be classified as *merging* or *non-merging*. *Merging* recorders write the merged table illustrated in :ref:`3) <user_guide/data_output/standard:3) Merging the tables>`
  to a single file or database entry, while *non-merging* recorders keep the tables separate. Generally, plaintext or database
  output formats are *merging* recorders while binary formats are *non-merging*.

| Links to recorder API documentation are provided below, classified by *merging* and *non-merging*:

**Merging Recorders**

- :ref:`Comma-Separated-Values (CSV) Recorder <api/recorders/plaintext/csv:Comma-Separated Values (CSV) Recorder>`
- :ref:`Structured-Query-Language (SQL) Database Recorder <api/recorders/database/sql:Structured-Query-Language (SQL) Database Recorder>`

**Non-Merging Recorders**

- :ref:`Hierarchical-Data-Format 5 (HDF5) Recorder <api/recorders/binary/hdf:Hierarchical-Data-Format 5 (HDF5) Recorder>`



