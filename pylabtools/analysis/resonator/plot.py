""" Plots of resonator traces (magnitude, phase and the I-Q plane side by side) and of fit results
against swept parameters.

.. code-block:: python

    from pylabtools.analysis.resonator import plot_res_data, plot_res_params

    fig, axes = plot_res_data(vna, color_by="power")
    axes["mag"].set_xlim(5.995e9, 6.005e9)
    fig, axes = plot_res_params(fitted, x="power")
"""
import warnings
from collections.abc import Mapping

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors
from matplotlib.cm import ScalarMappable

from ...recorders.base import DATA_INDEX, RECORD_ROW
from ..dataset import RecordView
from ..expressions import Names, evaluate
from ..plot import _numeric_colors, _shared, lineplot, scatterplot
from .calibration import _check_trace

__all__ = ["plot_res_data", "plot_res_params"]

MAGNITUDE = "20*np.log10(np.hypot(I, Q))"
PHASE = "np.unwrap(np.arctan2(Q, I))"
PANELS = ("mag", "phase", "iq")
FREQUENCY_UNITS = {"Hz": 1.0, "kHz": 1e3, "MHz": 1e6, "GHz": 1e9}
FREQUENCY_NAMES = ("frequency", "fr")      # - a plotted name that is a frequency - #


def _frequency_scale(unit):
    if unit not in FREQUENCY_UNITS:
        raise ValueError(f"freq_unit must be one of {list(FREQUENCY_UNITS)}, not {unit!r}.")
    return FREQUENCY_UNITS[unit]


def _in_unit(name, scale):
    """ The expression plotting frequency ``name`` in the unit of ``scale`` Hz. """
    return name if scale == 1.0 else f"{name} / {scale!r}"


def plot_res_data(view, color_by=None, average=False, xaverage_silent=False, axes=None, xlabel=None,
                  title=None, cmap="viridis", norm=None, colorbar=True, clabel=None, legend=True,
                  scatter_kwargs=None, freq_unit="GHz", **kwargs):
    """ Plot resonator traces as magnitude and phase against frequency, and Q against I.

    Every emit of ``view`` must have the data columns ``frequency``, ``I`` and ``Q``. The panels
    are drawn with :func:`~pylabtools.analysis.plot.lineplot` and
    :func:`~pylabtools.analysis.plot.scatterplot`:

    ``"mag"``
        ``20*np.log10(np.hypot(I, Q))`` (dB) against frequency, in ``freq_unit`` (GHz by default).
    ``"phase"``
        ``np.unwrap(np.arctan2(Q, I))`` (rad) against frequency, unwrapped along each trace.
    ``"iq"``
        Q against I, with equal scales on both axes.

    .. code-block:: python

        plot_res_data(vna)
        plot_res_data(vna, color_by="power", clabel="Power (dBm)")
        plot_res_data(vna.rows("abs(frequency - 6e9) < 2e6"), color_by="setpoint", average=True)

    The arguments are those of :func:`~pylabtools.analysis.plot.lineplot` without ``x`` and ``y``,
    and apply to all three panels. ``color_by`` gives one colour bar (numbers) or one legend (other
    values) for the whole figure. With ``average=True``, I and Q are averaged row by row and the
    magnitude and phase computed from the averages; the I-Q panel never warns that ``x`` differs,
    as averaging I-Q circles is intended, while the frequency panels warn if the emits'
    frequencies differ (unless ``xaverage_silent=True``).

    :param view: The :class:`~pylabtools.analysis.RecordView` to plot.
    :param axes: Optional three Axes to draw on, as a mapping with the keys ``"mag"``, ``"phase"``
        and ``"iq"`` or a sequence in that order. By default a new figure is made, with the
        magnitude above the phase (sharing the frequency axis) and the I-Q plane beside them.
    :param xlabel: Frequency axis label (default ``"frequency (GHz)"``, with ``freq_unit``).
    :param title: Optional figure title (default: none).
    :param scatter_kwargs: Keyword arguments for :meth:`~matplotlib.axes.Axes.scatter` in the I-Q
        panel (default ``{"s": 6}``).
    :param freq_unit: Unit of the frequency axis: ``"GHz"`` (default), ``"MHz"``, ``"kHz"`` or
        ``"Hz"``.
    :param kwargs: Passed to :meth:`~matplotlib.axes.Axes.plot` for the magnitude and phase lines.
    :return: ``(fig, axes)``, where ``axes`` is a dict with the keys ``"mag"``, ``"phase"`` and
        ``"iq"``.

    See :func:`~pylabtools.analysis.plot.lineplot` for ``color_by``, ``average``,
    ``xaverage_silent``, ``cmap``, ``norm``, ``colorbar``, ``clabel`` and ``legend``.
    """
    _check_trace(view)
    frequency = _in_unit("frequency", _frequency_scale(freq_unit))
    fig, axes = _axes(axes)
    numeric = _numeric_colors(view, color_by) if len(view) else None
    if numeric:
        norm = mcolors.Normalize() if norm is None else norm   # - one norm, so all panels agree - #
        cmap = matplotlib.colormaps[cmap] if isinstance(cmap, str) else cmap
    common = dict(color_by=color_by, average=average, cmap=cmap, norm=norm, colorbar=False, clabel=clabel)
    scatter_kwargs = {"s": 6} if scatter_kwargs is None else dict(scatter_kwargs)
    xlabel = f"frequency ({freq_unit})" if xlabel is None else xlabel

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        lineplot(view, x=frequency, y=MAGNITUDE, ax=axes["mag"], xlabel="", ylabel="Magnitude (dB)",
                 legend=legend, xaverage_silent=xaverage_silent, **common, **kwargs)
        lineplot(view, x=frequency, y=PHASE, ax=axes["phase"], xlabel=xlabel, ylabel="Phase (rad)",
                 legend=False, xaverage_silent=xaverage_silent, **common, **kwargs)
        scatterplot(view, x="I", y="Q", ax=axes["iq"], xlabel="I", ylabel="Q", legend=False,
                    xaverage_silent=True, **common, **scatter_kwargs)
    _reissue(caught)

    axes["iq"].set_aspect("equal", adjustable="datalim")
    if numeric and colorbar:
        fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), ax=list(axes.values()),
                     label=color_by if clabel is None else clabel)
    if title is not None:
        fig.suptitle(title)
    return fig, axes


def _axes(axes):
    if axes is None:
        fig = plt.figure(figsize=(11, 5.5), layout="constrained")
        axes = fig.subplot_mosaic([["mag", "iq"], ["phase", "iq"]], width_ratios=[1.4, 1])
        axes["mag"].sharex(axes["phase"])
        axes["mag"].tick_params(labelbottom=False)
        return fig, {key: axes[key] for key in PANELS}
    if isinstance(axes, Mapping):
        missing = [key for key in PANELS if key not in axes]
        if missing:
            raise KeyError(f"axes needs the keys {list(PANELS)}; missing {missing}.")
        axes = {key: axes[key] for key in PANELS}
    else:
        axes = list(axes)
        if len(axes) != len(PANELS):
            raise ValueError(f"axes needs three Axes ({', '.join(PANELS)}), got {len(axes)}.")
        axes = dict(zip(PANELS, axes))
    return axes["mag"].figure, axes


def _reissue(caught):
    """ Issue the panels' warnings once each, pointing at the caller of :func:`plot_res_data`. """
    seen = set()
    for record in caught:
        key = (record.category, str(record.message))
        if key not in seen:
            seen.add(key)
            warnings.warn(record.message, stacklevel=3)


Q_VALUES = ("Ql", "Qc", "Qi")
_Q_LABELS = {"Ql": "Ql (loaded)", "Qc": "Qc (coupling)", "Qi": "Qi (internal)"}


def plot_res_params(view, x, qs=Q_VALUES, fit="res_params", errors=True, axes=None, xlabel=None, title=None,
                    errorbar_kwargs=None, freq_unit="GHz", **kwargs):
    """ Plot the fitted quality factors (top) and resonance frequency (bottom) against a swept
    parameter, one point per emit, with error bars.

    .. code-block:: python

        fitted = fit_res_params(cal, "hanger")
        fig, axes = plot_res_params(fitted, x="power", xlabel="Power (dBm)")
        plot_res_params(fitted, x="setpoint", qs=("Qi", "Qc"))
        plot_res_params(fitted.where("ls_success"), x="setpoint", qs="Qi")
        axes["Q"].set_yscale("log")

    Each series is drawn with :func:`~pylabtools.analysis.plot.scatterplot` on a view with one data
    row per emit, holding that emit's row of ``view.fits[fit]``, so ``x`` can be a procedure
    parameter, metadata item or fit result, or an expression of them (e.g. ``"setpoint * 1e3"``).
    The quality factors share the top axes, one colour each, with a legend; ``fr`` is on the bottom
    axes, in ``freq_unit`` (GHz by default), which share ``x`` with the top. An ``x`` of exactly
    ``"fr"`` or ``"frequency"`` is plotted in ``freq_unit`` too. With ``errors``, error bars come from the ``<name>_err``
    columns of :func:`~pylabtools.analysis.resonator.fit_res_params` (and from ``<x>_err`` if ``x``
    is a fit result). Emits whose fit failed (NaN) are left out, and so are quality factors with no
    finite value, such as ``Qc`` and ``Qi`` of an inline resonator.

    :param view: A :class:`~pylabtools.analysis.RecordView` with ``fits[fit]``.
    :param x: Name or expression for the horizontal axis, e.g. a swept parameter.
    :param qs: The quality factors to plot, any of ``"Ql"``, ``"Qc"`` and ``"Qi"`` (default all
        three), as a sequence or one name.
    :param fit: Which table of :attr:`~pylabtools.analysis.RecordView.fits` to plot (default
        ``"res_params"``).
    :param errors: Whether to draw error bars.
    :param axes: Optional two Axes to draw on, as a mapping with the keys ``"Q"`` and ``"fr"`` or a
        sequence in that order. By default a new figure is made, the two sharing ``x``.
    :param xlabel: Label of the ``x`` axis (default ``x``).
    :param title: Optional figure title.
    :param errorbar_kwargs: Keyword arguments for :meth:`~matplotlib.axes.Axes.errorbar`
        (default ``{"capsize": 2, "lw": 1}``).
    :param freq_unit: Unit of the plotted frequencies: ``"GHz"`` (default), ``"MHz"``, ``"kHz"`` or
        ``"Hz"``.
    :param kwargs: Passed to :func:`~pylabtools.analysis.plot.scatterplot` and on to
        :meth:`~matplotlib.axes.Axes.scatter` (``s``, ``marker``, ...), for every series.
    :return: ``(fig, axes)``, ``axes`` a dict with the keys ``"Q"`` and ``"fr"``.
    :raises KeyError: If ``view`` has no ``fits[fit]``, or it lacks a column to plot.
    :raises ValueError: For an unknown name in ``qs``, or an empty ``qs``.
    """
    qs = [qs] if isinstance(qs, str) else list(qs)
    unknown = [q for q in qs if q not in Q_VALUES]
    if unknown or not qs:
        raise ValueError(f"qs must name one or more of {list(Q_VALUES)}, not {unknown or qs}.")
    if len(view) == 0:
        raise ValueError(f"{view.name!r}: the view has no emits to plot.")
    points = _fit_view(view, fit)
    missing = [c for c in qs + ["fr"] if c not in points.columns]
    if missing:
        raise KeyError(f"fits[{fit!r}] has no columns {missing}; its columns are {points.columns}.")
    scale = _frequency_scale(freq_unit)
    x_name = x
    x_scale = scale if x in FREQUENCY_NAMES else 1.0
    x_label = (f"{x} ({freq_unit})" if x in FREQUENCY_NAMES else x) if xlabel is None else xlabel
    x = _in_unit(x, x_scale)
    fig, axes = _param_axes(axes)
    xs = _per_emit(points, x)
    xerr = _scaled(_column_or_none(points, f"{x_name}_err"), x_scale) if errors and x_name in points.columns \
        else None
    bar_kwargs = {"capsize": 2, "lw": 1, **(errorbar_kwargs or {})}
    palette = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0", "C1", "C2"])
    plotted = 0

    for i, q in enumerate(qs):
        values = points.data[q].to_numpy(dtype=float)
        if not np.any(np.isfinite(values)):
            continue
        colour = palette[Q_VALUES.index(q) % len(palette)]
        scatterplot(points, x=x, y=q, ax=axes["Q"], color=colour, label=_Q_LABELS[q], **kwargs)
        if errors:
            _bars(axes["Q"], xs, values, xerr, _column_or_none(points, f"{q}_err"), colour, bar_kwargs)
        plotted += 1
    if plotted:   # - every emit is its own collection: one legend entry per quality factor - #
        handles, labels = axes["Q"].get_legend_handles_labels()
        unique = dict(zip(labels, handles))
        axes["Q"].legend(unique.values(), unique.keys())
    axes["Q"].set_ylabel("Quality factor")
    axes["Q"].set_xlabel("")

    colour = palette[3 % len(palette)]
    scatterplot(points, x=x, y=_in_unit("fr", scale), ax=axes["fr"], color=colour, xlabel=x_label,
                ylabel=f"fr ({freq_unit})", **kwargs)
    if errors:
        _bars(axes["fr"], xs, points.data["fr"].to_numpy(dtype=float) / scale, xerr,
              _scaled(_column_or_none(points, "fr_err"), scale), colour, bar_kwargs)
    if title is not None:
        fig.suptitle(title)
    return fig, axes


def _fit_view(view, fit):
    """ A view with one data row per emit, holding that emit's results of ``view.fits[fit]``. """
    if fit not in view.fits:
        raise KeyError(f"{view.name!r} has no fit results {fit!r}; it has {list(view.fits)}. Run the fit first, "
                       "e.g. fit_res_params().")
    data = view.fits[fit].reset_index().assign(**{RECORD_ROW: 0}).set_index(DATA_INDEX)
    return RecordView(view.name, data, view.proc_params, view.meta, fits=view.fits)


def _per_emit(points, expression):
    """ ``expression`` evaluated for every emit of a one-row-per-emit view, in emit order. """
    shared = _shared(points)
    return np.array([evaluate(expression, Names(e.data, e.params, e.meta, shared), 1)[0] for e in points],
                    dtype=float)


def _column_or_none(points, column):
    return points.data[column].to_numpy(dtype=float) if column in points.columns else None


def _scaled(values, scale):
    return None if values is None else values / scale


def _bars(ax, xs, ys, xerr, yerr, colour, kwargs):
    if xerr is None and yerr is None:
        return
    ax.errorbar(xs, ys, xerr=xerr, yerr=yerr, fmt="none", ecolor=colour, **kwargs)


def _param_axes(axes):
    if axes is None:
        fig, (q_ax, fr_ax) = plt.subplots(2, 1, sharex=True, figsize=(6, 6), layout="constrained")
        return fig, {"Q": q_ax, "fr": fr_ax}
    if isinstance(axes, Mapping):
        missing = [key for key in ("Q", "fr") if key not in axes]
        if missing:
            raise KeyError(f"axes needs the keys ['Q', 'fr']; missing {missing}.")
        axes = {"Q": axes["Q"], "fr": axes["fr"]}
    else:
        axes = list(axes)
        if len(axes) != 2:
            raise ValueError(f"axes needs two Axes (Q, fr), got {len(axes)}.")
        axes = dict(zip(("Q", "fr"), axes))
    return axes["Q"].figure, axes
