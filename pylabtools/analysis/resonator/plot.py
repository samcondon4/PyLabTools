""" Plots of resonator traces: magnitude, phase and the I-Q plane side by side.

.. code-block:: python

    from pylabtools.analysis.resonator import plot_res_data

    fig, axes = plot_res_data(vna, color_by="power")
    axes["mag"].set_xlim(5.995e9, 6.005e9)
"""
import warnings
from collections.abc import Mapping

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.cm import ScalarMappable

from ..plot import _numeric_colors, lineplot, scatterplot
from .calibration import _check_trace

__all__ = ["plot_res_data"]

MAGNITUDE = "20*np.log10(np.hypot(I, Q))"
PHASE = "np.unwrap(np.arctan2(Q, I))"
PANELS = ("mag", "phase", "iq")


def plot_res_data(view, color_by=None, average=False, xaverage_silent=False, axes=None, xlabel=None,
                  title=None, cmap="viridis", norm=None, colorbar=True, clabel=None, legend=True,
                  scatter_kwargs=None, **kwargs):
    """ Plot resonator traces as magnitude and phase against frequency, and Q against I.

    Every emit of ``view`` must have the data columns ``frequency``, ``I`` and ``Q``. The panels
    are drawn with :func:`~pylabtools.analysis.plot.lineplot` and
    :func:`~pylabtools.analysis.plot.scatterplot`:

    ``"mag"``
        ``20*np.log10(np.hypot(I, Q))`` (dB) against frequency.
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
    :param xlabel: Frequency axis label (default ``"frequency"``).
    :param title: Optional figure title (default: none).
    :param scatter_kwargs: Keyword arguments for :meth:`~matplotlib.axes.Axes.scatter` in the I-Q
        panel (default ``{"s": 6}``).
    :param kwargs: Passed to :meth:`~matplotlib.axes.Axes.plot` for the magnitude and phase lines.
    :return: ``(fig, axes)``, where ``axes`` is a dict with the keys ``"mag"``, ``"phase"`` and
        ``"iq"``.

    See :func:`~pylabtools.analysis.plot.lineplot` for ``color_by``, ``average``,
    ``xaverage_silent``, ``cmap``, ``norm``, ``colorbar``, ``clabel`` and ``legend``.
    """
    _check_trace(view)
    fig, axes = _axes(axes)
    numeric = _numeric_colors(view, color_by) if len(view) else None
    if numeric:
        norm = mcolors.Normalize() if norm is None else norm   # - one norm, so all panels agree - #
        cmap = matplotlib.colormaps[cmap] if isinstance(cmap, str) else cmap
    common = dict(color_by=color_by, average=average, cmap=cmap, norm=norm, colorbar=False, clabel=clabel)
    scatter_kwargs = {"s": 6} if scatter_kwargs is None else dict(scatter_kwargs)
    xlabel = "frequency" if xlabel is None else xlabel

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        lineplot(view, x="frequency", y=MAGNITUDE, ax=axes["mag"], xlabel="", ylabel="Magnitude (dB)",
                 legend=legend, xaverage_silent=xaverage_silent, **common, **kwargs)
        lineplot(view, x="frequency", y=PHASE, ax=axes["phase"], xlabel=xlabel, ylabel="Phase (rad)",
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
