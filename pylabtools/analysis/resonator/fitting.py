""" Fitting the resonator parameters of calibrated traces. """
import warnings

import numpy as np
import pandas as pd

from scipy import optimize

from ...recorders.base import EMIT_INDEX
from .calibration import (CIRCLE_MIN_ROWS, GEOMETRIES, WEIGHTS, CalibrationWarning, _check_trace,
                          arc_length_weights, circle_and_phase, trace_points)

__all__ = ["fit_res_params"]

RESONATOR = ["fr", "Ql", "absQc", "phi", "Qc", "Qi"]
ENVIRONMENT = ["A", "alpha", "delta_tau"]
COLUMNS = (RESONATOR + [f"{p}_err" for p in RESONATOR] + ENVIRONMENT + [f"{p}_err" for p in ENVIRONMENT]
           + ["sigma", "ls_success", "xc", "yc", "r", "circle_rms", "theta0", "n"])


def fit_res_params(view, geometry, weights=None, least_squares=True):
    """ Fit the resonance frequency and quality factors of every calibrated trace.

    Run on traces normalised by :func:`~pylabtools.analysis.resonator.calibrate_constant_scaling`,
    so that the off-resonant point is 1. For each emit:

    1. **Circle fit.** A circle (centre ``c``, radius ``r``) is fitted to ``I + iQ`` algebraically,
       with Pratt's constraint.
    2. **Phase fit.** About ``c``, ``theta(f) = theta0 + 2*arctan(2*Ql*(1 - f/fr))`` is fitted for
       ``theta0``, ``Ql`` and ``fr``.
    3. **Resonator parameters**, from the circle and the model of ``geometry``, with the impedance
       mismatch as a complex coupling ``1/Qc_complex = exp(-i*phi) / |Qc|`` (Probst et al. 2015):

       ``"hanger"``
           ``S21 = 1 - (Ql/|Qc|) * exp(i*phi) / (1 + 2i*Ql*(f/fr - 1))``: the circle's diameter is
           ``Ql/|Qc|``, so ``|Qc| = Ql / (2*r)``.
       ``"reflection"``
           ``S11 = 1 - (2*Ql/|Qc|) * exp(i*phi) / (1 + 2i*Ql*(f/fr - 1))``: the diameter is
           ``2*Ql/|Qc|``, so ``|Qc| = Ql / r``.

       For both, the centre is ``c = 1 - r*exp(i*phi)``, so ``phi = arg(1 - c)``, and with the
       diameter correction ``Qc = 1/Re(1/Qc_complex) = |Qc| / cos(phi)`` and
       ``1/Qi = 1/Ql - cos(phi)/|Qc|``.

       ``"transmission"``
           An inline resonator normalised at its resonance gives ``S21 = 1 / (1 + 2i*Ql*(f/fr - 1))``,
           whatever its couplings: only ``fr`` and ``Ql`` are determined, and ``absQc``, ``phi``,
           ``Qc`` and ``Qi`` are NaN. Separating them needs an absolute calibration of the
           transmission.

    4. **Complex least squares** (``least_squares=True``, the default). Starting from steps 1-3, the
       full complex model, with the environment free again,

       ``S = A * exp(i*alpha) * exp(-2*pi*i*(f - fm)*delta_tau) * [model of geometry]``

       (``fm`` the mean frequency; ``A = 1``, ``alpha = 0``, ``delta_tau = 0`` to start), is fitted
       to ``I + iQ`` by least squares: ``fr``, ``Ql``, ``absQc``, ``phi``, ``A``, ``alpha`` and
       ``delta_tau`` (for ``"transmission"``: ``fr``, ``Ql``, ``A``, ``alpha``, ``delta_tau``).
       ``fr``, ``Ql``, ``absQc``, ``phi``, ``Qc`` and ``Qi`` are then those of this fit.

    **Uncertainties** (``<name>_err``, one standard deviation) come from the covariance matrix of
    the final fit. Because ``A``, ``alpha`` and ``delta_tau`` are fitted together with the
    resonator, the errors of the earlier calibration steps and their correlations with the
    resonator parameters are included; ``A``, ``alpha`` and ``delta_tau`` show how far the
    calibration was off. The noise is estimated from the residuals,
    ``sigma**2 = sum(|S - data|**2) / (2*N - p)`` per quadrature, so the uncertainties are
    statistical only: they assume independent noise of equal size on every point, and do not
    include a systematic error from a background the model does not describe. With
    ``weights="arc_length"`` the fit is weighted and the covariance is the sandwich estimate
    ``B @ (J.T @ W**2 @ J) @ B * sigma**2``, ``B = inv(J.T @ W @ J)``, which is correct for a
    weighted fit of equal-noise data. ``Qc_err`` and ``Qi_err`` are propagated from the
    covariance of ``Ql``, ``absQc`` and ``phi``. With ``least_squares=False``, the error columns,
    ``A``, ``alpha``, ``delta_tau`` and ``sigma`` are NaN.

    The final fit can only correct small calibration errors. If it does not converge, or ends with
    ``fr`` outside the trace or a non-positive ``Ql``, ``absQc`` or ``A``, the emit keeps the
    circle-fit values without uncertainties (``ls_success`` False), with a
    :class:`~pylabtools.analysis.resonator.CalibrationWarning`. Inline traces with little signal
    off resonance are the usual case: their cable delay is hard to calibrate (see
    :func:`~pylabtools.analysis.resonator.calibrate_constant_scaling`).

    The data are not changed: the returned view holds the results in ``fits["res_params"]``.

    .. code-block:: python

        cal = calibrate_cable_delay(vna, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")
        cal = calibrate_constant_scaling(cal, "hanger", refine_cable_delay=True, weights="arc_length")
        cal = fit_res_params(cal, "hanger", weights="arc_length")
        cal.fits["res_params"][["fr", "Ql", "Qc", "Qi", "phi"]]

    Emits with fewer than five usable rows, or whose fits fail, get NaN results, with a
    :class:`~pylabtools.analysis.resonator.CalibrationWarning`. A negative ``Qi`` means that
    ``cos(phi)/|Qc|`` exceeds ``1/Ql``, which data normalised as assumed do not give.

    :param view: A calibrated :class:`~pylabtools.analysis.RecordView` of resonator traces, with the
        data columns ``frequency``, ``I`` and ``Q``.
    :param geometry: ``"hanger"``, ``"reflection"`` or ``"transmission"``.
    :param weights: None (default) for equal point weights, or ``"arc_length"`` (see
        :func:`~pylabtools.analysis.resonator.calibrate_constant_scaling`), in the circle, phase
        and least-squares fits.
    :param least_squares: If True (default), finish with the complex least-squares fit (step 4)
        and report uncertainties.
    :return: The view with ``fits["res_params"]``: one row per emit, indexed by ``(RecordGroup,
        RecordGroupInd)``, with the columns

        ``fr`` (Hz), ``Ql``
            the resonance frequency and loaded quality factor.
        ``absQc``, ``phi`` (rad)
            the modulus of the complex coupling quality factor and the impedance-mismatch angle.
        ``Qc``, ``Qi``
            the diameter-corrected coupling and internal quality factors.
        ``fr_err``, ``Ql_err``, ``absQc_err``, ``phi_err``, ``Qc_err``, ``Qi_err``
            their uncertainties.
        ``A``, ``alpha`` (rad), ``delta_tau`` (s), with ``_err``
            the environment's remaining scale, phase and delay, relative to the calibrated data.
        ``sigma``
            the noise per quadrature estimated from the residuals.
        ``ls_success``
            whether the least-squares fit converged (False if it was not run).
        ``xc``, ``yc``, ``r``, ``circle_rms``, ``theta0`` (rad)
            the circle and phase fits, in the normalised data's units.
        ``n``
            the number of rows fitted.
    :raises ValueError: For an unknown ``geometry`` or ``weights``, or if the view was already
        fitted.
    :raises KeyError: If a trace column is missing.
    """
    if geometry not in GEOMETRIES:
        raise ValueError(f"geometry must be one of {list(GEOMETRIES)}, not {geometry!r}.")
    if weights not in WEIGHTS:
        raise ValueError(f"weights must be one of {list(WEIGHTS)}, not {weights!r}.")
    _check_trace(view)
    frequency = view.data["frequency"].to_numpy(dtype=float)
    signal = view.data["I"].to_numpy(dtype=float) + 1j * view.data["Q"].to_numpy(dtype=float)
    rows = view.data.groupby(level=EMIT_INDEX, sort=False).indices

    results, failed = [], []
    for key in view.keys:
        positions = rows.get(key, np.array([], dtype=int))
        result = _fit_trace(frequency[positions], signal[positions], geometry, weights, least_squares)
        if not np.isfinite(result["Ql"]):
            failed.append(key)
        results.append(result)
    if failed:
        warnings.warn(f"fit_res_params() could not fit {len(failed)} emit(s) {failed[:5]}"
                      f"{' ...' if len(failed) > 5 else ''}; their results are NaN.", CalibrationWarning,
                      stacklevel=2)
    unconverged = [k for k, r in zip(view.keys, results) if least_squares and np.isfinite(r["Ql"])
                   and not r["ls_success"]]
    if unconverged:
        warnings.warn(f"fit_res_params(): the least-squares fit did not converge for {len(unconverged)} emit(s) "
                      f"{unconverged[:5]}{' ...' if len(unconverged) > 5 else ''}; they keep the circle-fit "
                      "values, without uncertainties.", CalibrationWarning, stacklevel=2)

    table = pd.DataFrame(results, columns=COLUMNS)
    table.index = view.keys
    table["n"] = table["n"].astype(np.int64)
    table["ls_success"] = table["ls_success"].astype(bool)
    return view.with_data(view.data, step="res_params", table=table)


def _fit_trace(frequency, signal, geometry, weights, least_squares):
    f, z = trace_points(frequency, signal)
    result = dict.fromkeys(COLUMNS, np.nan)
    result.update(n=len(f), ls_success=False)
    if len(f) < CIRCLE_MIN_ROWS or np.ptp(f) == 0:
        return result
    fit = circle_and_phase(f, z, weights)
    if fit is None:
        return result
    result.update({k: fit[k] for k in ("fr", "Ql", "xc", "yc", "r", "circle_rms", "theta0")})
    result.update(resonator_parameters(geometry, fit["xc"] + 1j * fit["yc"], fit["r"], fit["Ql"]))
    if least_squares:
        w = arc_length_weights(f, fit["fr"], fit["Ql"]) if weights == "arc_length" else None
        result.update(_complex_fit(f, z, geometry, result, fit["orientation"], w))
    return result


def _model(geometry, f, fm, p):
    """ The full complex model; ``p`` = (fr, Ql, absQc, phi, A, alpha, delta_tau), or for
    ``"transmission"`` (fr, Ql, A, alpha, delta_tau). The sign of ``Ql`` sets only the direction
    the trace circles in. """
    if geometry == "transmission":
        fr, ql, a, alpha, delta_tau = p
        shape = 1 / (1 + 2j * ql * (f / fr - 1))
    else:
        fr, ql, abs_qc, phi, a, alpha, delta_tau = p
        k = 1 if geometry == "hanger" else 2
        shape = 1 - k * (abs(ql) / abs_qc) * np.exp(1j * phi) / (1 + 2j * ql * (f / fr - 1))
    return a * np.exp(1j * alpha) * np.exp(-2j * np.pi * (f - fm) * delta_tau) * shape


def _complex_fit(f, z, geometry, start, orientation, w):
    """ Step 4 for one trace: the fitted values, their uncertainties, ``sigma`` and ``ls_success``.
    ``orientation`` (+1/-1) is the direction the trace circles in: the model's ``Ql`` carries it
    (a negative ``Ql`` circles the other way), and ``Ql`` is reported positive. """
    inline = geometry == "transmission"
    names = ["fr", "Ql"] + ([] if inline else ["absQc", "phi"]) + ENVIRONMENT
    x0 = [start["fr"], orientation * start["Ql"]] + ([] if inline else [start["absQc"], start["phi"]]) + \
        [1.0, 0.0, 0.0]
    scale = [start["fr"] / start["Ql"], start["Ql"]] + ([] if inline else [start["absQc"], 1.0]) + \
        [1.0, 1.0, 1 / (2 * np.pi * np.ptp(f))]
    fm = f.mean()
    root_w = np.ones_like(f) if w is None else np.sqrt(w)

    def residual(p):
        r = (_model(geometry, f, fm, p) - z) * root_w
        return np.concatenate([r.real, r.imag])

    out = dict.fromkeys([f"{n}_err" for n in RESONATOR] + ENVIRONMENT + [f"{n}_err" for n in ENVIRONMENT]
                        + ["sigma"], np.nan)
    out["ls_success"] = False
    if not np.all(np.isfinite(x0)) or 2 * len(f) <= len(names):
        return out
    fit = optimize.least_squares(residual, x0, x_scale=scale, ftol=1e-12, xtol=1e-12, gtol=1e-12)
    values = dict(zip(names, fit.x))
    plausible = (f.min() <= values["fr"] <= f.max() and orientation * values["Ql"] > 0 and values["A"] > 0
                 and (inline or values["absQc"] > 0))
    if not fit.success or not np.all(np.isfinite(fit.x)) or not plausible:
        return out
    covariance, sigma = _covariance(fit.jac, root_w, (_model(geometry, f, fm, fit.x) - z), len(names))
    errors = dict(zip(names, np.sqrt(np.diag(covariance)))) if covariance is not None else {}

    values["Ql"] = abs(values["Ql"])
    out.update(values, sigma=sigma, ls_success=True)
    out.update({f"{n}_err": errors.get(n, np.nan) for n in names})
    if not inline:
        out.update(_derived(values["Ql"], values["absQc"], values["phi"], covariance, names))
    return out


def _covariance(jac, root_w, residual, n_params):
    """ ``(covariance, sigma)`` of a least-squares fit whose residuals were multiplied by
    ``root_w``: the plain estimate without weights, the sandwich estimate with them. ``sigma`` is
    the noise per quadrature from the unweighted residuals. """
    n_rows = 2 * len(residual)
    sigma = float(np.sqrt(np.sum(np.abs(residual) ** 2) / (n_rows - n_params)))
    w = np.concatenate([root_w, root_w]) ** 2                     # - per real residual - #
    unweighted = jac / np.sqrt(w)[:, None]                       # - the Jacobian of the plain residuals - #
    try:
        bread = np.linalg.inv(unweighted.T @ (unweighted * w[:, None]))
    except np.linalg.LinAlgError:
        return None, sigma
    meat = unweighted.T @ (unweighted * (w * w)[:, None])
    covariance = bread @ meat @ bread * sigma ** 2
    if not np.all(np.isfinite(covariance)):
        return None, sigma
    return covariance, sigma


def _derived(ql, abs_qc, phi, covariance, names):
    """ ``Qc``, ``Qi`` and their uncertainties, propagated from the covariance of ``Ql``,
    ``absQc`` and ``phi``. """
    inverse_qi = 1 / ql - np.cos(phi) / abs_qc
    qc, qi = abs_qc / np.cos(phi), (1 / inverse_qi if inverse_qi != 0 else np.inf)
    out = dict(Qc=qc, Qi=qi, Qc_err=np.nan, Qi_err=np.nan)
    if covariance is None:
        return out
    index = [names.index(n) for n in ("Ql", "absQc", "phi")]
    sub = covariance[np.ix_(index, index)]
    grad_qc = np.array([0.0, 1 / np.cos(phi), abs_qc * np.sin(phi) / np.cos(phi) ** 2])
    grad_qi = qi ** 2 * np.array([1 / ql ** 2, -np.cos(phi) / abs_qc ** 2, -np.sin(phi) / abs_qc])
    out.update(Qc_err=float(np.sqrt(grad_qc @ sub @ grad_qc)), Qi_err=float(np.sqrt(grad_qi @ sub @ grad_qi)))
    return out


def resonator_parameters(geometry, centre, radius, ql):
    """ ``absQc``, ``phi``, ``Qc`` and ``Qi`` from the circle of normalised data (see
    :func:`fit_res_params`); NaN for ``"transmission"``. """
    if geometry == "transmission":
        return dict(absQc=np.nan, phi=np.nan, Qc=np.nan, Qi=np.nan)
    diameter = 2 * radius if geometry == "hanger" else radius      # - Ql/|Qc| from the circle - #
    abs_qc = ql / diameter
    phi = float(np.angle(1 - centre))
    inverse_qi = 1 / ql - np.cos(phi) / abs_qc
    return dict(absQc=abs_qc, phi=phi, Qc=abs_qc / np.cos(phi), Qi=1 / inverse_qi if inverse_qi != 0 else np.inf)
