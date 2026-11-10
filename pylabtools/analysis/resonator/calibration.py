""" Calibration steps that remove the measurement environment from resonator traces.

Each step returns a new :class:`~pylabtools.analysis.RecordView` with corrected ``I`` and ``Q`` and
records its per-emit fit results in the view's :attr:`~pylabtools.analysis.RecordView.fits`.
"""
import warnings

import numpy as np
import pandas as pd
from scipy import linalg, optimize

from ...recorders.base import EMIT_INDEX

__all__ = ["CalibrationWarning", "arc_length_weights", "calibrate_cable_delay", "calibrate_constant_scaling"]

TRACE_COLUMNS = ("frequency", "I", "Q")
GEOMETRIES = ("hanger", "reflection", "transmission")
WEIGHTS = (None, "arc_length")


class CalibrationWarning(UserWarning):
    """ Issued when a calibration step could not do its job well for some emits. """


def calibrate_cable_delay(view, fit_rows=None):
    """ Fit and remove a linear phase slope (the cable delay) from every trace.

    For each emit, the phase ``np.unwrap(np.arctan2(Q, I))``, unwrapped in order of frequency, is
    fitted by least squares with a straight line::

        phase = slope * frequency + offset

    and the slope is removed from all rows of the emit,
    ``I + iQ -> (I + iQ) * exp(-i * slope * frequency)``. The offset is fitted but not removed:
    the overall phase of the environment is calibrated together with its amplitude in a later
    step. A cable delay ``delay`` multiplies the signal by ``exp(-2*pi*i*frequency*delay)``, so
    ``delay = -slope / (2*pi)``.

    .. code-block:: python

        cal = calibrate_cable_delay(vna)
        cal.fits["cable_delay"]                 # slope, offset, delay, n of every emit
        cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - 6e9) > 1e6")
        cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")   # per emit

    By default every row is fitted, including the resonance, whose own phase change biases the
    slope. ``fit_rows`` restricts the fit to the rows away from the resonance, while still
    correcting every row. The phase of those rows is unwrapped after removing a first estimate of
    the slope from the whole trace, so that gaps left by excluded rows, and a resonance whose
    phase turns through 2 pi (an overcoupled reflection), do not upset the unwrapping.

    Rows with a non-finite frequency, I or Q are left out of the fit and stay as they are; emits
    with fewer than two fitted rows (at different frequencies) are not corrected and get NaN
    results.

    :param view: A :class:`~pylabtools.analysis.RecordView` of resonator traces, with the data
        columns ``frequency``, ``I`` and ``Q``.
    :param fit_rows: Optional expression string, or list of them that must all hold, selecting
        the rows to fit, as in :meth:`~pylabtools.analysis.RecordView.rows`: evaluated per emit
        with its data columns, parameters and metadata.
    :return: A new :class:`~pylabtools.analysis.RecordView` with the corrected ``I`` and ``Q``, and
        ``fits["cable_delay"]``: a table with one row per emit, indexed by ``(RecordGroup,
        RecordGroupInd)``, with the columns ``slope`` (rad/Hz), ``offset`` (rad, the fitted
        phase at zero frequency, wrapped into (-pi, pi] since unwrapping fixes it only up to a
        multiple of 2 pi), ``delay`` (s) and ``n``, the number of rows fitted.
    :raises KeyError: If a trace column is missing.
    :raises ValueError: If the cable delay of ``view`` was already calibrated.
    """
    _check_trace(view)
    conditions = [] if fit_rows is None else [fit_rows] if isinstance(fit_rows, str) else list(fit_rows)
    selected = view._row_mask(conditions, "fit_rows")
    frequency = view.data["frequency"].to_numpy(dtype=float)
    signal = view.data["I"].to_numpy(dtype=float) + 1j * view.data["Q"].to_numpy(dtype=float)
    corrected = signal.copy()
    rows = view.data.groupby(level=EMIT_INDEX, sort=False).indices

    results = {}
    for key in view.keys:
        positions = rows.get(key, np.array([], dtype=int))
        slope, offset, n = _fit_phase_line(frequency[positions], signal[positions], selected[positions])
        if np.isfinite(slope):
            corrected[positions] = signal[positions] * np.exp(-1j * slope * frequency[positions])
        results[key] = (slope, offset, n)

    table = pd.DataFrame.from_dict(results, orient="index", columns=["slope", "offset", "n"])
    table.index = pd.MultiIndex.from_tuples(table.index, names=EMIT_INDEX) if len(table) else view.keys[:0]
    table["delay"] = -table["slope"] / (2 * np.pi)
    table = table[["slope", "offset", "delay", "n"]].astype({"n": np.int64})
    data = view.data.assign(I=corrected.real, Q=corrected.imag)
    return view.with_data(data, step="cable_delay", table=table)


def _fit_phase_line(frequency, signal, selected):
    """ ``(slope, offset, n)``: the line fitted to the unwrapped phase of the ``selected`` rows,
    or NaNs if fewer than two rows can be fitted. """
    usable = np.isfinite(frequency) & np.isfinite(signal)
    fitted = usable & selected
    n = int(fitted.sum())
    if n < 2:
        return np.nan, np.nan, n
    first = _segment_slope(frequency[usable], signal[usable], selected[usable])
    if first is None:                       # - no two adjacent fitted rows: unwrap them as they are - #
        first = 0.0
    # - unwrap the fitted rows relative to the first slope, across the gaps, and fit them all - #
    residual = signal[fitted] * np.exp(-1j * first * frequency[fitted])
    refined = _line(frequency[fitted], residual)
    if refined is None:
        return np.nan, np.nan, n
    slope, offset = first + refined[0], refined[1]
    return float(slope), float(np.angle(np.exp(1j * offset))), n   # - offset is known up to 2*pi*k: wrap it - #


def _segment_slope(frequency, signal, selected):
    """ The phase slope common to the runs of adjacent selected rows (in frequency order), each
    unwrapped on its own so that no unwrapping crosses an excluded row; None without a run of two
    or more rows at different frequencies. """
    order = np.argsort(frequency, kind="stable")
    f, s, keep = frequency[order], signal[order], selected[order]
    edges = np.flatnonzero(np.diff(np.concatenate([[0], keep.astype(np.int8), [0]])))
    numerator = denominator = 0.0
    for start, stop in zip(edges[::2], edges[1::2]):
        if stop - start < 2:
            continue
        df = f[start:stop] - f[start:stop].mean()
        phase = np.unwrap(np.angle(s[start:stop]))
        numerator += np.sum(df * (phase - phase.mean()))
        denominator += np.sum(df * df)
    return numerator / denominator if denominator > 0 else None


def _line(frequency, signal):
    """ ``(slope, intercept)`` of a straight line fitted to the unwrapped phase, or None. """
    if len(frequency) < 2 or np.ptp(frequency) == 0:
        return None
    order = np.argsort(frequency, kind="stable")
    f = frequency[order]
    phase = np.unwrap(np.angle(signal[order]))
    centre = f.mean()                       # - fit about the centre, so the problem is well scaled - #
    slope, intercept = np.polyfit(f - centre, phase, 1)
    return slope, intercept - slope * centre


def _check_trace(view):
    missing = [c for c in TRACE_COLUMNS if c not in view.columns]
    if missing:
        raise KeyError(f"{view.name!r} has no data columns {missing}; resonator traces need 'frequency', "
                       f"'I' and 'Q'. Columns are {view.columns}.")


# - constant scaling ------------------------------------------------------------------------------ #
_CIRCLE_MIN_ROWS = 5                 # - a circle needs 3 points; the phase fit 3 parameters more - #
_DELAY_TOLERANCE = 1e-6              # - rad: refined until the correction turns the trace by less - #
_DELAY_MAX_PASSES = 20


def calibrate_constant_scaling(view, geometry, refine_cable_delay=False, weights=None):
    """ Fit the resonance circle of every trace and normalise it to the off-resonant point.

    Run after :func:`calibrate_cable_delay`. For each emit:

    1. **Circle fit.** A circle is fitted to the points ``I + iQ`` algebraically (Pratt's
       constraint, solved as a generalised eigenvalue problem, as in Chernov & Lesort and Probst et
       al. 2015). With ``refine_cable_delay=True``, a remaining delay ``delta_tau`` is removed
       first: the data are multiplied by ``exp(2*pi*i*frequency*delta_tau)`` and the circle refitted,
       with ``delta_tau`` chosen to minimise the sum of squared distances of the points from the
       fitted circle. This is repeated on the corrected data until the correction turns the trace by
       less than 1e-6 rad over its frequency span. Only with the right delay do the points lie on a
       circle, so this uses the whole trace, resonance included.
    2. **Phase fit.** About the circle's centre ``c``, the angle of the points follows
       ``theta(f) = theta0 + 2*arctan(2*Ql*(1 - f/fr))`` for every geometry. ``theta0``, ``Ql``
       and ``fr`` are fitted by least squares, in stages as Probst et al. do: ``theta0`` and
       ``fr`` with ``Ql`` fixed, then ``Ql`` and ``theta0``, then all three.
    3. **Normalisation.** For ``"hanger"`` and ``"reflection"`` the off-resonant point, reached
       far from the resonance, is the point of the circle opposite the resonance,
       ``P = c + r*exp(i*(theta0 + pi))``. It is the environment's constant scaling
       ``a*exp(i*alpha)``, and all rows are divided by it, so the off-resonant point becomes 1.
       For ``"transmission"`` (inline), the off-resonant point is the origin, which cannot be
       normalised to; the trace is divided by the resonance point ``c + r*exp(i*theta0)``
       instead, so that ``S21(fr) = 1``. This removes the phase offset but folds the coupling into
       ``a``: separating the internal and coupling quality factors of an inline resonator needs an
       absolute calibration of the transmission.

    .. code-block:: python

        cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")
        cal = calibrate_constant_scaling(cal, "hanger", refine_cable_delay=True)
        cal.fits["constant_scaling"][["fr", "Ql", "a", "alpha"]]

    For an inline resonator, ``refine_cable_delay`` constrains the delay only weakly: near the
    resonance a small delay error changes the circle, to first order, just like a change of ``Ql``,
    so the circle stays a circle. With noise the refined delay can then scatter by many ns while
    ``fr``, ``Ql`` and ``a`` stay accurate; ``alpha`` inherits the delay error, multiplied by the
    frequency over the span.

    **Weights.** Evenly spaced frequencies put most points in a dense cluster near the off-resonant
    point, and an unweighted fit lets that cluster decide the circle: a background that is not
    constant over the span (an amplitude slope or curvature, ripple) then distorts it, typically
    making the trace ends curl inside the fitted circle. ``weights="arc_length"`` weights every
    point by the length of circle it covers, :func:`arc_length_weights`: the circle and phase fits
    are run unweighted for ``fr`` and ``Ql``, then again with these weights. This removes most of
    the background's systematic error in ``Ql`` and the circle's diameter, at the cost of more
    noise in the diameter, which rests mostly on the off-resonant points it discounts. The delay
    refinement stays unweighted: weighting it was found to triple the scatter of the refined delay
    without reducing its (small) bias or the bias of ``Ql`` and the diameter. A background whose
    amplitude has a linear slope over the span is not removed by weighting; it biases the refined
    delay and ``Ql`` with or without weights.

    Emits with fewer than five usable rows, or whose fits fail, are not normalised and get NaN
    results, with a :class:`CalibrationWarning`. ``Ql`` is reported positive; a trace that circles
    the other way (the opposite phase convention) gives the same results.

    :param view: A :class:`~pylabtools.analysis.RecordView` of resonator traces, with the data
        columns ``frequency``, ``I`` and ``Q``.
    :param geometry: ``"hanger"``, ``"reflection"`` or ``"transmission"``.
    :param refine_cable_delay: If True, refine the cable delay with the circle fit (step 1).
    :param weights: None (default) for equal point weights, or ``"arc_length"``.
    :return: A new :class:`~pylabtools.analysis.RecordView` with the normalised ``I`` and ``Q``, and
        ``fits["constant_scaling"]``: one row per emit, indexed by ``(RecordGroup,
        RecordGroupInd)``, with the columns

        ``delay_correction``
            ``delta_tau`` (s), 0 without ``refine_cable_delay``. The total delay removed is
            ``fits["cable_delay"]["delay"] + delay_correction``.
        ``xc``, ``yc``, ``r``
            the circle's centre and radius, after the delay correction and before normalising.
        ``circle_rms``
            the root mean square distance of the points from the circle, in the same units
            (weighted, with ``weights``).
        ``theta0`` (rad), ``Ql``, ``fr`` (Hz)
            the phase fit.
        ``a``, ``alpha`` (rad)
            the modulus and phase of the point normalised to.
        ``n``
            the number of rows fitted.
    :raises ValueError: For an unknown ``geometry`` or ``weights``, or if the view was already
        normalised.
    :raises KeyError: If a trace column is missing.
    """
    if geometry not in GEOMETRIES:
        raise ValueError(f"geometry must be one of {list(GEOMETRIES)}, not {geometry!r}.")
    if weights not in WEIGHTS:
        raise ValueError(f"weights must be one of {list(WEIGHTS)}, not {weights!r}.")
    _check_trace(view)
    frequency = view.data["frequency"].to_numpy(dtype=float)
    signal = view.data["I"].to_numpy(dtype=float) + 1j * view.data["Q"].to_numpy(dtype=float)
    corrected = signal.copy()
    rows = view.data.groupby(level=EMIT_INDEX, sort=False).indices

    results, failed, at_bound = {}, [], []
    for key in view.keys:
        positions = rows.get(key, np.array([], dtype=int))
        result = _scale_trace(frequency[positions], signal[positions], geometry, refine_cable_delay, weights)
        results[key] = result
        if not np.isfinite(result["a"]):
            failed.append(key)
            continue
        if result.pop("at_bound"):
            at_bound.append(key)
        factor = np.exp(2j * np.pi * frequency[positions] * result["delay_correction"])
        corrected[positions] = signal[positions] * factor / (result["a"] * np.exp(1j * result["alpha"]))
    if failed:
        warnings.warn(f"calibrate_constant_scaling() could not fit {len(failed)} emit(s) {failed[:5]}"
                      f"{' ...' if len(failed) > 5 else ''}; they are left unnormalised with NaN results.",
                      CalibrationWarning, stacklevel=2)
    if at_bound:
        warnings.warn(f"calibrate_constant_scaling(): the delay correction of emit(s) {at_bound[:5]} reached "
                      "the search limit of half a turn over the trace; calibrate the cable delay first "
                      "(calibrate_cable_delay, e.g. with fit_rows) so that the remaining delay is small.",
                      CalibrationWarning, stacklevel=2)

    columns = ["delay_correction", "xc", "yc", "r", "circle_rms", "theta0", "Ql", "fr", "a", "alpha", "n"]
    table = pd.DataFrame([{c: results[k][c] for c in columns} for k in view.keys], columns=columns)
    table.index = view.keys
    table["n"] = table["n"].astype(np.int64)
    data = view.data.assign(I=corrected.real, Q=corrected.imag)
    return view.with_data(data, step="constant_scaling", table=table)


def _scale_trace(frequency, signal, geometry, refine, weights):
    """ Steps 1-3 for one trace; NaN results if a step fails. The delay is refined unweighted; with
    ``weights="arc_length"``, the circle and phase fits run unweighted for ``fr`` and ``Ql``, then
    again with the weights these give. """
    usable = np.isfinite(frequency) & np.isfinite(signal)
    f, z = frequency[usable], signal[usable]
    order = np.argsort(f, kind="stable")
    f, z = f[order], z[order]
    result = dict.fromkeys(["delay_correction", "xc", "yc", "r", "circle_rms", "theta0", "Ql", "fr", "a", "alpha"],
                           np.nan)
    result.update(n=len(f), at_bound=False)
    if len(f) < _CIRCLE_MIN_ROWS or np.ptp(f) == 0:
        return result

    # - 1a. the delay refinement: unweighted, as the off-resonant arms show a delay error best - #
    delta_tau, at_bound = (_refine_delay(f, z) if refine else (0.0, False))
    if not np.isfinite(delta_tau):
        return result
    z = z * np.exp(2j * np.pi * f * delta_tau)

    # - 1b-2. circle and phase fits on the corrected trace, then weighted if asked - #
    fit = _circle_and_phase(f, z, None)
    if fit is not None and weights == "arc_length":
        fit = _circle_and_phase(f, z, arc_length_weights(f, fit["fr"], fit["Ql"]))
    if fit is None:
        return result
    fit.update(delay_correction=delta_tau, at_bound=at_bound)

    # - 3. the point normalised to: off resonance, or the resonance itself for an inline resonator - #
    centre = fit["xc"] + 1j * fit["yc"]
    point = centre + fit["r"] * np.exp(1j * (fit["theta0"] if geometry == "transmission" else fit["theta0"] + np.pi))
    result.update(fit, a=float(np.abs(point)), alpha=float(np.angle(point)))
    return result


def _circle_and_phase(f, z, w):
    """ The circle and phase fits with point weights ``w`` (None: equal), as a dict, or None if a
    fit fails. """
    circle = _fit_circle(z.real, z.imag, w)
    if circle is None:
        return None
    xc, yc, r = circle

    # - 2. phase about the centre - #
    phase = _fit_centred_phase(f, z - (xc + 1j * yc), w)
    if phase is None:
        return None
    theta0, ql, fr = phase
    return dict(xc=xc, yc=yc, r=r, circle_rms=_circle_rms(z, xc, yc, r, w), theta0=theta0, Ql=ql, fr=fr)


def arc_length_weights(frequency, fr, ql):
    """ Point weights proportional to the length of the resonance circle per unit frequency at each
    point, ``1 / (1 + x**2)`` with ``x = 2*Ql*(f/fr - 1)``, scaled to a mean of 1.

    Evenly spaced frequencies put most points near the off-resonant point; these weights make each
    point count by how much of the circle it covers instead.
    """
    x = 2 * ql * (np.asarray(frequency, dtype=float) / fr - 1)
    w = 1 / (1 + x * x)
    return w / w.mean()


def _fit_circle(x, y, w=None):
    """ ``(xc, yc, r)`` of the circle fitted algebraically with Pratt's constraint, or None.
    ``w``: optional point weights, multiplying each point's squared algebraic distance. """
    w = np.ones_like(x) if w is None else w
    total = w.sum()
    xm, ym = np.sum(w * x) / total, np.sum(w * y) / total
    scale = np.sqrt(np.sum(w * ((x - xm) ** 2 + (y - ym) ** 2)) / total)
    if not np.isfinite(scale) or scale == 0:
        return None
    u, v = (x - xm) / scale, (y - ym) / scale         # - centred and scaled, for a well-posed problem - #
    terms = np.column_stack([u * u + v * v, u, v, np.ones_like(u)])
    moments = (terms * w[:, None]).T @ terms / total
    constraint = np.array([[0.0, 0, 0, -2], [0, 1, 0, 0], [0, 0, 1, 0], [-2, 0, 0, 0]])
    values, vectors = linalg.eig(moments, constraint)
    values = values.real
    tolerance = 1e-10 * np.max(np.abs(values[np.isfinite(values)]), initial=1.0)
    candidates = np.flatnonzero(np.isfinite(values) & (values > -tolerance))
    if not len(candidates):
        return None
    a, b, c, d = vectors[:, candidates[np.argmin(values[candidates])]].real
    if abs(a) < 1e-12:                                # - the points lie on a line - #
        return None
    radius_sq = (b * b + c * c - 4 * a * d) / (4 * a * a)
    if radius_sq <= 0:
        return None
    return xm + scale * (-b / (2 * a)), ym + scale * (-c / (2 * a)), scale * np.sqrt(radius_sq)


def _circle_rms(z, xc, yc, r, w=None):
    """ Root mean square distance of the points from the circle, weighted by ``w``. """
    distance = np.abs(z - (xc + 1j * yc)) - r
    return float(np.sqrt(np.average(distance ** 2, weights=w)))


def _delay_residual(f, z, delta_tau):
    """ Sum of squared distances of the points from their algebraic circle, after removing
    ``delta_tau``; frequencies are taken about their mean (a constant turn changes nothing). """
    turned = z * np.exp(2j * np.pi * (f - f.mean()) * delta_tau)
    circle = _fit_circle(turned.real, turned.imag)
    if circle is None:
        return np.inf
    return float(np.sum((np.abs(turned - (circle[0] + 1j * circle[1])) - circle[2]) ** 2))


def _refine_delay(f, z):
    """ ``(delta_tau, at_bound)`` minimising the circle residual, refined pass by pass until the
    last pass's correction turns the trace by less than ``_DELAY_TOLERANCE``. """
    span = np.ptp(f)
    limit = 0.5 / span                               # - half a turn over the trace - #
    tolerance = _DELAY_TOLERANCE / (2 * np.pi * span)
    total, at_bound = 0.0, False
    grid = np.linspace(-limit, limit, 41)
    for _ in range(_DELAY_MAX_PASSES):
        current = z * np.exp(2j * np.pi * (f - f.mean()) * total)
        # - a coarse grid first, so the bounded search starts in the right dip - #
        coarse = np.array([_delay_residual(f, current, dt) for dt in grid])
        if not np.any(np.isfinite(coarse)):
            return np.nan, False
        k = int(np.argmin(coarse))
        low, high = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
        best = optimize.minimize_scalar(lambda dt: _delay_residual(f, current, dt), bounds=(low, high),
                                        method="bounded", options={"xatol": tolerance / 10})
        if not np.isfinite(best.fun):
            return np.nan, False
        step = float(best.x)
        at_bound = abs(step) > 0.99 * limit
        total += step
        if abs(step) < tolerance:
            break
    return total, at_bound


def _fit_centred_phase(f, z, w=None):
    """ ``(theta0, Ql, fr)`` fitted to the angle of ``z`` (the points about the circle's centre),
    ``theta = theta0 + 2*arctan(2*Ql*(1 - f/fr))``, or None. ``f`` is sorted; ``w`` are optional
    point weights on the squared residuals. """
    root_w = 1.0 if w is None else np.sqrt(w)
    angle = np.angle(z)
    unwrapped = np.unwrap(angle)
    guess = _phase_guess(f, unwrapped)
    if guess is None:
        return None
    theta0, ql, fr = guess
    width = fr / abs(ql)

    def residual(theta0, ql, fr):
        return root_w * np.angle(np.exp(1j * (angle - theta0 - 2 * np.arctan(2 * ql * (1 - f / fr)))))

    scales = {"theta0": 1.0, "ql": abs(ql), "fr": width}
    params = {"theta0": theta0, "ql": ql, "fr": fr}
    for free in (("theta0", "fr"), ("ql", "theta0"), ("theta0", "ql", "fr")):
        def stage(x, free=free):
            trial = dict(params, **dict(zip(free, x)))
            return residual(trial["theta0"], trial["ql"], trial["fr"])
        fit = optimize.least_squares(stage, [params[k] for k in free], x_scale=[scales[k] for k in free])
        if not np.all(np.isfinite(fit.x)):
            return None
        params.update(zip(free, fit.x))
    if params["fr"] <= 0 or params["ql"] == 0:
        return None
    return float(np.angle(np.exp(1j * params["theta0"]))), float(abs(params["ql"])), float(params["fr"])


def _phase_guess(f, unwrapped):
    """ Starting values from the steepest point of the unwrapped phase and its half-turn width. """
    window = max(1, len(f) // 50)
    smooth = np.convolve(unwrapped, np.ones(window) / window, mode="same") if window > 1 else unwrapped
    slope = np.gradient(smooth, f)
    if window > 1:                                   # - the edges of a moving average are biased - #
        slope[:window] = slope[-window:] = 0
    if not np.any(np.isfinite(slope)) or np.nanmax(np.abs(slope)) == 0:
        return None
    k = int(np.nanargmax(np.abs(slope)))
    fr, theta0 = f[k], unwrapped[k]
    # - theta = theta0 -/+ pi/2 one half-linewidth either side: fr / (f+ - f-) = Ql - #
    above = _crossing(f[k:], unwrapped[k:] - theta0, np.pi / 2)
    below = _crossing(f[:k + 1][::-1], unwrapped[:k + 1][::-1] - theta0, np.pi / 2)
    if above is not None and below is not None and above > below:
        ql = fr / (above - below)
    else:
        ql = abs(slope[k]) * fr / 4                  # - d(theta)/df at fr is -4*Ql/fr - #
    return theta0, -np.sign(slope[k]) * ql, fr


def _crossing(f, offset, level):
    """ The first frequency where ``|offset|`` reaches ``level``, interpolated, or None. """
    reached = np.flatnonzero(np.abs(offset) >= level)
    if not len(reached) or reached[0] == 0:
        return None
    i = reached[0]
    f0, f1, y0, y1 = f[i - 1], f[i], abs(offset[i - 1]), abs(offset[i])
    return f0 + (level - y0) * (f1 - f0) / (y1 - y0) if y1 != y0 else f1
