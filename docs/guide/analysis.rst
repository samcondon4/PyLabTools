Analysing data
##############

:mod:`pylabtools.analysis` works on recorded datasets while keeping the PyLabTools structure:
emits, their procedure parameters and metadata, and the ``RecordGroup`` / ``RecordGroupInd`` /
``RecordRow`` indices. It needs only pandas.

Opening a dataset
=================

.. code-block:: python

    import pylabtools as plab

    ds = plab.analysis.Dataset("cooldown_12.h5")   # or a CSVRecorder directory
    ds.records                                     # ['fridge', 's21']
    s21 = ds["s21"]                                # a RecordView (read once, then cached)
    latest = ds.record("s21", groups=-1)           # read only some RecordGroups

A :class:`~pylabtools.analysis.RecordView` keeps the three tables apart:

``s21.data``
    one row per data row, indexed by ``(RecordGroup, RecordGroupInd, RecordRow)``
``s21.proc_params`` and ``s21.meta``
    one row per emit, indexed by ``(RecordGroup, RecordGroupInd)``

``s21.emit_table()`` puts the parameters and metadata of every emit side by side as ``proc_<name>``
and ``meta_<name>`` columns, and ``s21.to_frame()`` gives the joined frame of
:func:`~pylabtools.read_hdf`. ``s21.groups``, ``s21.params`` and ``s21.columns`` list the
RecordGroups, parameter names and data columns; ``len(s21)`` is the number of emits.

Selecting emits
===============

Views are immutable; selections return new views, with the data rows subset to match.

.. code-block:: python

    s21.group(-1)                                       # the latest RecordGroup
    s21.where("setpoint < 0.1")                         # an expression
    s21.where("0.01 < setpoint < 0.1 and trace == 0")   # all conditions must hold
    s21.where("power in [-20, -10]", "trace != 1")
    s21.where(power=-20)                                # a value, e.g. a variable in a loop
    s21.where(power=[-20, -10], trace=0)                # any of several values

Conditions are written as Python expressions of the parameter and metadata names and ``np``, the
same as the plotting expressions below. They are evaluated for all emits at once, so comparisons
and ``and`` / ``or`` / ``not`` / ``in [...]`` work element-wise, and chained comparisons such as
``a < x < b`` work too. The keyword form matches values, which is handy for selecting by a Python
variable without writing it into a string.

Names are looked up among the procedure parameters and then the metadata. If a name is in both,
prefix it: ``where("proc_power > -15")`` or ``where(meta_power=-19.5)``. Floats are compared with
a relative tolerance of 1e-9, both by ``==`` / ``in`` and by the keywords, so ``0.15 - 0.05``
matches a stored ``0.1``. A boolean array or Series with one value per emit also works as a
condition, e.g. one computed with ``reduce()``:

.. code-block:: python

    depth = s21.reduce(lambda d: d.s21.min(), name="depth")["depth"]
    s21.where(depth < -3)

Selecting rows within emits
---------------------------

:meth:`~pylabtools.analysis.RecordView.rows` keeps only the data rows that meet the conditions,
inside every emit, e.g. a frequency window of every VNA trace:

.. code-block:: python

    s21.rows("9e9 < frequency < 10e9")
    s21.rows("abs(frequency - f0) < 2e6")              # around each emit's own metadata f0
    s21.where(power=-20).rows("frequency > 9e9", "I**2 + Q**2 > 1e-6")

The expressions see each emit's data columns as arrays, and its parameters and metadata as values,
so a condition can depend on the emit. Every emit is kept with its parameters and metadata, even if
it has no rows left, and the kept rows keep their ``RecordRow`` numbers, so they still line up
across emits when plotting with ``average=True``.

:meth:`~pylabtools.analysis.RecordView.values` lists the distinct values of a parameter or metadata
item in a view, sorted, with the same name lookup. Floats that ``where()`` treats as equal are
merged, so each value selects the emits it stands for:

.. code-block:: python

    s21.values("power")                        # [-20.0, -10.0, 0.0]
    s21.group(-1).values("setpoint")           # only the latest RecordGroup
    for power in s21.values("power"):
        sel = s21.where(power=power)

Combining views
===============

:func:`~pylabtools.analysis.concat` combines views, e.g. the same record from two datasets, so
they can be selected and plotted together:

.. code-block:: python

    both = plab.analysis.concat({"cooldown 1": ds1["s21"], "cooldown 2": ds2["s21"]})
    plot_res_data(both, color_by="dataset")              # one legend entry per dataset
    both.where("dataset == 'cooldown 2' and power == -10")

Given a mapping, every emit gets a ``dataset`` metadata item (``label=`` changes the name) holding
its key; a list combines the views without one. The RecordGroups of each view are renumbered to
follow those of the view before, since emits are numbered within each view. Columns, parameters or
metadata that only some views have are NaN for the others. Views of different records are combined
only when ``name=`` gives the new record name.

Iterating and reducing
======================

``s21.emits()`` (or iterating over the view) yields one :class:`~pylabtools.analysis.Emit` per emit,
with ``group``, ``index``, ``params``, ``meta``, ``timestamp`` and ``data`` (indexed by
``RecordRow``):

.. code-block:: python

    for emit in s21.where(trace=0):
        plt.plot(emit.data.f, emit.data.s21, label=f"{emit.params['power']} dBm")

:meth:`~pylabtools.analysis.RecordView.reduce` turns every emit into a few numbers and returns the
emit table with the results as extra columns, one row per emit, ready to pivot or plot against the
swept parameters:

.. code-block:: python

    s21.reduce("mean")                                     # mean of every numeric column
    s21.reduce(lambda d: d.s21.min(), name="depth")
    table = s21.reduce(lambda d: {"f_min": d.f[d.s21.idxmin()], "depth": d.s21.min()})
    table.pivot_table(index="proc_setpoint", columns="proc_power", values="depth")

Aligning records
================

:meth:`~pylabtools.analysis.RecordView.align` attaches statistics of another record to every emit,
for example the fridge temperatures measured during each VNA trace. The statistics become new
metadata of the returned view, so they work with ``where()``, ``emits()`` and ``reduce()``:

.. code-block:: python

    s21 = ds["s21"].align(ds["fridge"])               # mean of each fridge column per RecordGroup
    s21.meta[["fridge_T5", "fridge_n"]]
    s21.where("fridge_T5 < 0.05").reduce(...)

``by`` chooses which rows of the other record belong to an emit:

``by="group"`` (default)
    all rows in the same ``RecordGroup``. With ``group_by="setpoint"`` (see :doc:`sequences`) that
    is everything measured at the same setpoint.
``by="nearest"``
    the emit nearest in time; also adds ``<prefix>dt``, the matched emit's time minus this emit's
    time. ``tolerance="10s"`` leaves emits without a match within 10 s as NaN.
``by="window"``
    all emits within ``window`` of this emit: ``window=30`` (seconds either side) or
    ``window=("60s", 0)`` (the minute before).

``agg`` is the statistic (``"mean"``, ``"median"``, ``"std"``, ``"min"``, ``"max"`` or a function of a
Series), ``columns`` limits the aggregated columns (default: all numeric ones), and ``prefix``
changes the new column names (default ``<record>_``). A list of statistics adds one column per
statistic, named ``<prefix><column>_<agg>``:

.. code-block:: python

    s21 = ds["s21"].align(ds["fridge"], agg=["mean", "std"], columns=["T5"])
    s21.meta[["fridge_T5_mean", "fridge_T5_std", "fridge_n"]]

Functions in such a list are named by their ``__name__``, so define them with ``def`` rather than
``lambda``. ``<prefix>n`` is the number of rows each
statistic was computed from. Times are the ``timestamp`` metadata of each emit, i.e. when it was
emitted.

Plotting
========

:mod:`pylabtools.analysis.plot` draws views with matplotlib (``pip install pylabtools[analysis]``).
:func:`~pylabtools.analysis.plot.lineplot` and :func:`~pylabtools.analysis.plot.scatterplot` take
the same arguments, draw one line (or set of points) per emit with ``ax.plot`` / ``ax.scatter``, and
return ``(fig, ax)``:

.. code-block:: python

    from pylabtools.analysis.plot import lineplot, scatterplot

    mag_db = "20*np.log10(np.sqrt(I**2 + Q**2))"
    fig, ax = lineplot(vna, x="frequency", y=mag_db, ylabel="|S21| (dB)")
    ax.set_xlim(5.995e9, 6.005e9)                     # carry on with the Axes as usual

``x`` and ``y`` are column names or Python expressions, evaluated for every emit with the data
columns, ``np``, and the emit's parameters and metadata (names looked up as in ``where()``). Scalars
are repeated for every row, so ``y="I * proc_power"`` works. The axis labels default to the strings
you passed; ``xlabel=``, ``ylabel=`` and ``title=`` override them (there is no title by default).
Pass ``ax=`` to draw onto existing axes, e.g. one panel of ``fig.subplots(1, 2)``; other keyword
arguments (``lw``, ``ls``, ``marker``, ``s``, ``alpha``, ...) go to ``ax.plot`` / ``ax.scatter``.

Colouring by a parameter
------------------------

``color_by`` colours every emit by a parameter or metadata value, or an expression of them:

.. code-block:: python

    lineplot(vna, x="frequency", y=mag_db, color_by="setpoint")            # colour bar
    lineplot(vna, x="frequency", y=mag_db, color_by="setpoint * 1e3", clabel="T (mK)",
             cmap="plasma", norm=matplotlib.colors.LogNorm())
    lineplot(vna, x="frequency", y=mag_db, color_by="mode")                # legend
    lineplot(vna.align(fridge), x="frequency", y=mag_db, color_by="fridge_T5")

Numeric values are mapped onto ``cmap`` (through ``norm``, whose unset limits come from the data)
with a colour bar (``colorbar=False`` to omit it). Other values, such as strings, get one colour
per distinct value and a legend (``legend=False`` to omit it). ``clabel`` sets the colour bar or
legend title, by default the ``color_by`` string.

Averaging
---------

Every emit is drawn by default. With ``average=True`` the emits sharing a ``color_by`` value (or all
emits, without ``color_by``) become one line:

.. code-block:: python

    lineplot(vna, x="frequency", y=mag_db, color_by="setpoint", average=True)

The numeric data columns are averaged row by row (by ``RecordRow``) *before* ``x`` and ``y`` are
evaluated, so the example above averages I and Q and then takes the magnitude. To average the
magnitudes instead, emit or compute them as a column first. The emits of a group must have the
same number of rows; parameters that differ within a group (e.g. a trace number) cannot be used in
``x`` or ``y``.

Rows are matched by ``RecordRow``, so averaging normally expects every emit of a group to have the
same ``x`` (the same frequency grid, say). If ``x`` differs, the emits are still averaged but an
:class:`~pylabtools.analysis.plot.AveragingWarning` names the affected groups. That is expected when
averaging I-Q circles, where ``x`` is itself measured; silence it with ``xaverage_silent=True``:

.. code-block:: python

    scatterplot(vna, x="I", y="Q", color_by="setpoint", average=True, xaverage_silent=True)

Resonator traces
================

:mod:`pylabtools.analysis.resonator` works on resonator traces: emits whose data has the columns
``frequency``, ``I`` and ``Q``. :func:`~pylabtools.analysis.resonator.plot_res_data` draws the
magnitude (dB) and the unwrapped phase against frequency, and Q against I with equal scales, in one
figure:

.. code-block:: python

    from pylabtools.analysis.resonator import plot_res_data

    fig, axes = plot_res_data(vna, color_by="power", clabel="Power (dBm)")
    axes["mag"].set_xlim(5.995e9, 6.005e9)                    # "mag", "phase" and "iq"

    window = vna.rows("abs(frequency - 6e9) < 2e6")
    plot_res_data(window, color_by="setpoint", average=True)

It takes the arguments of :func:`~pylabtools.analysis.plot.lineplot` except ``x`` and ``y``, with
one colour bar or legend for the whole figure. ``axes=`` draws onto three existing Axes,
``scatter_kwargs`` styles the I-Q points, and other keyword arguments style the lines. With
``average=True``, I and Q are averaged row by row; only differing frequencies are warned about.

Calibration
-----------

Calibration steps remove the measurement environment from the traces. Each returns a new view with
corrected ``I`` and ``Q``, and records its results in the view's
:attr:`~pylabtools.analysis.RecordView.fits`: a table per step, with one row per emit indexed by
``(RecordGroup, RecordGroupInd)``. The tables follow every selection (``where()``, ``group()``,
``rows()``, ``concat()``), so they always describe the emits of the view.

:func:`~pylabtools.analysis.resonator.calibrate_cable_delay` fits the unwrapped phase of every
trace with a straight line, ``phase = slope * frequency + offset``, and removes the slope:

.. code-block:: python

    from pylabtools.analysis.resonator import calibrate_cable_delay

    cal = calibrate_cable_delay(vna)
    cal.fits["cable_delay"]                  # slope (rad/Hz), offset (rad), delay (s), n per emit
    plot_res_data(cal, color_by="power")

    # - fit only the rows away from the resonance, but correct them all - #
    cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - 6e9) > 2e6")
    cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")   # per emit

The offset is recorded but not removed; the environment's overall phase is calibrated with its
amplitude in a later step. By default every row is fitted, including the resonance, whose phase
change biases the slope: a little for a hanger, a lot for an overcoupled reflection, whose phase
turns through 2 pi. ``fit_rows`` takes expressions as in ``rows()`` and fits only the rows they
select, while correcting every row; ``n`` in the table is the number of rows fitted. Gaps left by
the excluded rows are bridged without phase slips. A step can be applied once per view:
calibrating the cable delay of a calibrated view raises an error.

:func:`~pylabtools.analysis.resonator.calibrate_constant_scaling` then follows Probst et al. (2015):
it fits a circle to every trace algebraically, fits the phase about the circle's centre,
``theta(f) = theta0 + 2*arctan(2*Ql*(1 - f/fr))``, and divides the trace by the off-resonant point
(the point of the circle opposite the resonance), so the off-resonant point becomes 1:

.. code-block:: python

    from pylabtools.analysis.resonator import calibrate_constant_scaling

    cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")
    cal = calibrate_constant_scaling(cal, "hanger", refine_cable_delay=True)
    cal.fits["constant_scaling"][["fr", "Ql", "a", "alpha", "delay_correction"]]

``geometry`` is ``"hanger"``, ``"reflection"`` or ``"transmission"``. With
``refine_cable_delay=True``, the remaining delay is refined first, by choosing the correction that
makes the points lie best on a circle: only the right delay gives a circle, and this uses the whole
trace, resonance included, so it removes the bias of the straight-line fit. The total delay removed
is ``fits["cable_delay"]["delay"] + fits["constant_scaling"]["delay_correction"]``.

With evenly spaced frequencies, most points crowd near the off-resonant point and decide the
circle in an unweighted fit, so a background that is not constant over the span distorts it; the
trace ends then often curl inside the fitted circle. ``weights="arc_length"`` makes every point
count by the length of circle it covers instead:

.. code-block:: python

    cal = calibrate_constant_scaling(cal, "reflection", refine_cable_delay=True, weights="arc_length")

The weights apply to the circle and phase fits. This removes most of the background's systematic
error in ``Ql`` and the circle's diameter, but leaves the diameter noisier, since it rests mostly
on the off-resonant points; with a constant background and only noise the unweighted fit is
better. The delay refinement stays unweighted: weighting it tripled the delay's scatter without
reducing any bias. A linear slope of the background amplitude is not removed by weighting.

An inline (``"transmission"``) resonator has its off-resonant point at the origin, so it is
normalised to the resonance point instead (``S21(fr) = 1``), and its circle constrains a delay
refinement only weakly; see :func:`~pylabtools.analysis.resonator.calibrate_constant_scaling`.

Fitting the resonator parameters
--------------------------------

:func:`~pylabtools.analysis.resonator.fit_res_params` fits calibrated traces, whose off-resonant
point is 1: a circle, the phase about its centre (``fr``, ``Ql``), and from the circle the coupling
and internal quality factors of the ``geometry``'s model, with the impedance mismatch as a complex
coupling ``1/Qc_complex = exp(-i*phi)/|Qc|`` (Probst et al. 2015):

.. code-block:: python

    from pylabtools.analysis.resonator import fit_res_params

    cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")
    cal = calibrate_constant_scaling(cal, "hanger", refine_cable_delay=True, weights="arc_length")
    cal = fit_res_params(cal, "hanger", weights="arc_length")
    cal.fits["res_params"][["fr", "Ql", "Qc", "Qi", "phi"]]

The circle's diameter is ``Ql/|Qc|`` for a hanger and ``2*Ql/|Qc|`` for a reflection; its centre
gives ``phi``. ``Qc = |Qc|/cos(phi)`` and ``1/Qi = 1/Ql - cos(phi)/|Qc|`` are the diameter-corrected
values. An inline (``"transmission"``) resonator normalised at its resonance gives only ``fr`` and
``Ql``.

By default (``least_squares=True``) the circle-fit values start a final least-squares fit of the
full complex model, with a remaining scale ``A``, phase ``alpha`` and delay ``delta_tau`` of the
environment free again, and each value gets an uncertainty ``<name>_err`` from the fit's
covariance. Because the environment is refitted with the resonator, the calibration's errors and
their correlations with ``Qc``, ``Qi`` and ``phi`` are included; ``A``, ``alpha`` and
``delta_tau`` show how far the calibration was off. The noise is estimated from the residuals
(``sigma``), so the uncertainties are statistical: they assume independent noise of equal size on
every point and do not cover a background the model does not describe. With
``weights="arc_length"`` the final fit is weighted too, with the matching (sandwich) covariance.

.. code-block:: python

    table = cal.fits["res_params"]
    table[["Qi", "Qi_err", "Qc", "Qc_err", "phi", "phi_err", "A", "delta_tau"]]

The data are not changed; the results are a table in ``fits["res_params"]``, one row per
emit, so they can be joined to the swept parameters:

.. code-block:: python

    results = cal.emit_table().join(cal.fits["res_params"])

:func:`~pylabtools.analysis.resonator.plot_res_params` plots them against a swept parameter: the
quality factors on top, one colour each, and ``fr`` below, with error bars:

.. code-block:: python

    from pylabtools.analysis.resonator import plot_res_params

    fig, axes = plot_res_params(cal, x="power", xlabel="Power (dBm)")
    plot_res_params(cal, x="setpoint * 1e3", qs=("Qi", "Qc"), xlabel="T (mK)")
    plot_res_params(cal.where("ls_success"), x="power", qs="Qi")
    axes["Q"].set_yscale("log")

``x`` is a parameter, metadata item or fit result, or an expression of them; ``qs`` picks any of
``"Ql"``, ``"Qc"`` and ``"Qi"`` (default all three).

