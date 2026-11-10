""" pylabtools.analysis.resonator.fit_res_params, through the full calibration pipeline. """
import numpy as np
import pandas as pd
import pytest

import pylabtools as plab
from pylabtools.analysis import RecordView
from pylabtools.analysis.resonator import CalibrationWarning, calibrate_constant_scaling, fit_res_params
from pylabtools.analysis.resonator.fitting import COLUMNS, _derived, resonator_parameters

from test_analysis_resonator_calibration import (SPAN, TRUE, delay_calibrated, drooping_reflection, resonator,
                                                 resonator_view)

QC = {"hanger": 3e4, "reflection": 1.5e4, "transmission": 3e4}


def calibrated(view, geometry, weights=None):
    return calibrate_constant_scaling(delay_calibrated(view), geometry, refine_cable_delay=True, weights=weights)


def expected(geometry):
    qc = QC[geometry]
    return {"absQc": qc, "phi": TRUE["phi"], "Qc": qc / np.cos(TRUE["phi"]),
            "Qi": 1 / (1 / TRUE["ql"] - np.cos(TRUE["phi"]) / qc)}


@pytest.mark.parametrize("weights", [None, "arc_length"])
@pytest.mark.parametrize("geometry", ["hanger", "reflection", "transmission"])
def test_recovers_the_resonator(geometry, weights):
    cal = calibrated(resonator_view([resonator(geometry, qc=QC[geometry])]), geometry)
    fitted = fit_res_params(cal, geometry, weights=weights)
    table = fitted.fits["res_params"]
    assert list(table.columns) == COLUMNS
    row = table.iloc[0]
    assert row["ls_success"]
    assert row["fr"] == pytest.approx(TRUE["fr"], rel=1e-9)            # - least_squares' tolerance - #
    assert row["Ql"] == pytest.approx(TRUE["ql"], rel=1e-6)
    assert row["n"] == len(SPAN)
    if geometry == "transmission":
        assert np.isnan(row[["absQc", "phi", "Qc", "Qi"]].astype(float)).all()
        assert (row["xc"], row["yc"], row["r"]) == pytest.approx((0.5, 0, 0.5), abs=1e-6)
    else:
        for name, value in expected(geometry).items():
            assert row[name] == pytest.approx(value, rel=1e-5), name
    # - noiseless data: the environment needs no correction, and the uncertainties are tiny - #
    assert (row["A"], row["alpha"], row["delta_tau"]) == pytest.approx((1, 0, 0), abs=1e-6)
    assert row["Ql_err"] / row["Ql"] < 1e-6 and row["sigma"] < 1e-6


def test_without_least_squares():
    cal = calibrated(resonator_view([resonator("hanger")]), "hanger")
    table = fit_res_params(cal, "hanger", least_squares=False).fits["res_params"]
    errors = [c for c in COLUMNS if c.endswith("_err")] + ["A", "alpha", "delta_tau", "sigma"]
    assert table[errors].isna().all().all() and not table["ls_success"].any()
    for name, value in expected("hanger").items():
        assert table[name].iloc[0] == pytest.approx(value, rel=1e-5), name


def test_least_squares_corrects_the_calibration():
    # - spoil the calibration by a known scale, phase and delay; the final fit undoes them - #
    cal = calibrated(resonator_view([resonator("hanger")]), "hanger")
    f = cal.data["frequency"].to_numpy()
    spoil = 1.02 * np.exp(0.05j) * np.exp(-2j * np.pi * (f - f.mean()) * 1e-9)
    z = (cal.data.I + 1j * cal.data.Q).to_numpy() * spoil
    spoiled = RecordView("res", cal.data.assign(I=z.real, Q=z.imag), cal.proc_params, cal.meta)
    row = fit_res_params(spoiled, "hanger").fits["res_params"].iloc[0]
    assert (row["A"], row["alpha"], row["delta_tau"]) == pytest.approx((1.02, 0.05, 1e-9), rel=1e-5)
    for name, value in expected("hanger").items():
        assert row[name] == pytest.approx(value, rel=1e-5), name
    # - without it, the circle fit alone is thrown off - #
    plain = fit_res_params(spoiled, "hanger", least_squares=False).fits["res_params"].iloc[0]
    assert abs(plain["Qi"] / expected("hanger")["Qi"] - 1) > 0.01


@pytest.mark.parametrize("weights", [None, "arc_length"])
@pytest.mark.parametrize("geometry", ["hanger", "reflection"])
def test_uncertainties_match_the_scatter(geometry, weights):
    rows = []
    for seed in range(30):
        rng = np.random.default_rng(100 + seed)
        s = resonator(geometry, qc=QC[geometry]) + 2e-3 * (rng.normal(size=SPAN.size) + 1j * rng.normal(size=SPAN.size))
        cal = calibrated(resonator_view([s]), geometry, weights)
        rows.append(fit_res_params(cal, geometry, weights=weights).fits["res_params"].iloc[0])
    table = pd.DataFrame(rows)
    assert table["ls_success"].all()
    assert table["sigma"].mean() == pytest.approx(2e-3 / TRUE["a"], rel=0.05)   # - noise / a, per quadrature - #
    for name in ("fr", "Ql", "absQc", "phi", "Qc", "Qi"):
        ratio = table[name].std() / table[f"{name}_err"].mean()
        assert 0.6 < ratio < 1.5, f"{name}: scatter / reported error = {ratio:.2f}"
    for name, value in expected(geometry).items():                      # - unbiased within the errors - #
        assert abs(table[name].mean() - value) < 4 * table[f"{name}_err"].mean() / np.sqrt(len(table)), name


def test_propagated_errors():
    # - Qc and Qi uncertainties against a numerical propagation - #
    names = ["fr", "Ql", "absQc", "phi", "A", "alpha", "delta_tau"]
    rng = np.random.default_rng(0)
    m = rng.normal(size=(7, 7))
    covariance = m @ m.T * 1e-4
    covariance[1, 1] *= 1e8                                             # - Ql, absQc variances of order 1e4 - #
    covariance[2, 2] *= 1e8
    ql, abs_qc, phi = 12000.0, 30000.0, 0.3
    out = _derived(ql, abs_qc, phi, covariance, names)

    def qc_qi(p):
        q, a, ph = p
        return np.array([a / np.cos(ph), 1 / (1 / q - np.cos(ph) / a)])
    p0 = np.array([ql, abs_qc, phi])
    step = np.array([1e-3, 1e-3, 1e-7])
    jac = np.column_stack([(qc_qi(p0 + h * e) - qc_qi(p0 - h * e)) / (2 * h) for h, e in zip(step, np.eye(3))])
    sub = covariance[np.ix_([1, 2, 3], [1, 2, 3])]
    expected_errors = np.sqrt(np.diag(jac @ sub @ jac.T))
    assert (out["Qc_err"], out["Qi_err"]) == pytest.approx(tuple(expected_errors), rel=1e-5)


def test_keeps_the_data_and_earlier_fits():
    cal = calibrated(resonator_view([resonator("hanger")]), "hanger")
    fitted = fit_res_params(cal, "hanger")
    pd.testing.assert_frame_equal(fitted.data, cal.data)
    assert list(fitted.fits) == ["cable_delay", "constant_scaling", "res_params"]
    assert "res_params" not in cal.fits


def test_noisy_traces():
    rng = np.random.default_rng(7)
    traces = [resonator("hanger") + 1e-3 * (rng.normal(size=SPAN.size) + 1j * rng.normal(size=SPAN.size))
              for _ in range(4)]
    table = fit_res_params(calibrated(resonator_view(traces), "hanger"), "hanger").fits["res_params"]
    want = expected("hanger")
    np.testing.assert_allclose(table["Ql"], TRUE["ql"], rtol=0.02)
    np.testing.assert_allclose(table["Qi"], want["Qi"], rtol=0.03)
    np.testing.assert_allclose(table["absQc"], want["absQc"], rtol=0.02)
    np.testing.assert_allclose(table["phi"], want["phi"], atol=0.02)


def test_weights_resist_a_curved_background():
    view = resonator_view([drooping_reflection(0.05)])
    want = 1 / (1 / TRUE["ql"] - np.cos(0.1) / 1.5e4)
    plain = fit_res_params(calibrated(view, "reflection"), "reflection").fits["res_params"]["Qi"].iloc[0]
    weighted = fit_res_params(calibrated(view, "reflection", "arc_length"), "reflection",
                              weights="arc_length").fits["res_params"]["Qi"].iloc[0]
    assert abs(weighted / want - 1) < abs(plain / want - 1) / 4


def test_opposite_phase_convention():
    # - conjugated data: the circle is mirrored, so phi changes sign; the quality factors do not - #
    normal = fit_res_params(calibrated(resonator_view([resonator("hanger")]), "hanger"), "hanger").fits["res_params"]
    mirrored = fit_res_params(calibrated(resonator_view([np.conj(resonator("hanger"))]), "hanger"),
                              "hanger").fits["res_params"]
    for name in ("fr", "Ql", "absQc", "Qc", "Qi"):
        assert mirrored[name].iloc[0] == pytest.approx(normal[name].iloc[0], rel=1e-6), name
    assert mirrored["phi"].iloc[0] == pytest.approx(-normal["phi"].iloc[0], abs=1e-6)


def test_resonator_parameters():
    # - a hanger circle of diameter 0.4 tilted by phi = 0.3, with Ql = 12000 - #
    centre = 1 - 0.2 * np.exp(0.3j)
    p = resonator_parameters("hanger", centre, 0.2, 12000)
    assert p["absQc"] == pytest.approx(30000) and p["phi"] == pytest.approx(0.3)
    assert p["Qi"] == pytest.approx(1 / (1 / 12000 - np.cos(0.3) / 30000))
    p = resonator_parameters("reflection", 1 - 0.8 * np.exp(-0.2j), 0.8, 12000)
    assert p["absQc"] == pytest.approx(15000) and p["phi"] == pytest.approx(-0.2)
    assert np.isinf(resonator_parameters("hanger", 1 - 0.5, 0.5, 1.0)["Qi"])   # - 1/Qi = 0 - #


def test_unusable_emits_and_errors():
    view = calibrated(resonator_view([resonator("hanger"), resonator("hanger")]), "hanger")
    short = view.rows("frequency < 5.99e9 + 3 * 25e3")
    with pytest.warns(CalibrationWarning, match="could not fit 2 emit"):
        table = fit_res_params(short, "hanger").fits["res_params"]
    assert table.drop(columns=["n", "ls_success"]).isna().all().all() and table["n"].tolist() == [3, 3]
    assert not table["ls_success"].any()
    with pytest.raises(ValueError, match="geometry must be one of"):
        fit_res_params(view, "notch")
    with pytest.raises(ValueError, match="weights must be one of"):
        fit_res_params(view, "hanger", weights="uniform")
    with pytest.raises(ValueError, match="already has fit results 'res_params'"):
        fit_res_params(fit_res_params(view, "hanger"), "hanger")
    with pytest.raises(KeyError, match="'Q'"):
        fit_res_params(RecordView("x", view.data.drop(columns="Q"), view.proc_params, view.meta), "hanger")


def test_exported():
    assert plab.analysis.resonator.fit_res_params is fit_res_params
