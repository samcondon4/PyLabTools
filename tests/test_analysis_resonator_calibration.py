""" pylabtools.analysis.resonator.calibrate_cable_delay, and RecordView.fits. """
import numpy as np
import pandas as pd
import pytest

import pylabtools as plab
from pylabtools.analysis import RecordView
from pylabtools.analysis.resonator import calibrate_cable_delay
from pylabtools.recorders import DATA_INDEX, EMIT_INDEX

F = np.linspace(5.99e9, 6.01e9, 401)
DELAYS = [30e-9, 60e-9, 90e-9, 120e-9]
ALPHA = 0.4


def trace(f, delay, resonance=True, a=0.3):
    s = a * np.exp(1j * ALPHA) * np.exp(-2j * np.pi * f * delay)
    if resonance:
        s = s * (1 - 0.4 / (1 + 2j * 2e4 * (f / 6e9 - 1)))
    return s


def delay_view(resonance=True, frequencies=F):
    data, params = [], []
    for index, delay in enumerate(DELAYS):
        s = trace(frequencies, delay, resonance)
        data.append(pd.DataFrame({"RecordGroup": index // 2, "RecordGroupInd": index % 2,
                                  "RecordRow": np.arange(len(frequencies)), "frequency": frequencies,
                                  "I": s.real, "Q": s.imag, "flag": 7}))
        params.append({"RecordGroup": index // 2, "RecordGroupInd": index % 2, "delay_set": delay})
    params = pd.DataFrame(params)
    return RecordView("vna", pd.concat(data).set_index(DATA_INDEX), params.set_index(EMIT_INDEX),
                      params[EMIT_INDEX].set_index(EMIT_INDEX))


def phase(view):
    return [np.unwrap(np.arctan2(e.data.Q, e.data.I)) for e in view]


def test_pure_delay_is_removed_exactly():
    view = delay_view(resonance=False)
    cal = calibrate_cable_delay(view)
    table = cal.fits["cable_delay"]
    assert list(table.columns) == ["slope", "offset", "delay", "n"]
    assert table["n"].tolist() == [len(F)] * 4                            # - every row fitted - #
    assert table.index.equals(view.keys)
    np.testing.assert_allclose(table["delay"], DELAYS, rtol=1e-9)
    np.testing.assert_allclose(table["slope"], -2 * np.pi * np.array(DELAYS), rtol=1e-9)
    np.testing.assert_allclose(table["offset"], ALPHA, atol=1e-6)        # - wrapped into (-pi, pi] - #
    for p in phase(cal):
        np.testing.assert_allclose(p, ALPHA, atol=1e-6)                   # - flat; offset kept - #
    np.testing.assert_allclose(np.hypot(cal.data.I, cal.data.Q), np.hypot(view.data.I, view.data.Q))


def test_with_resonance():
    view = delay_view()
    cal = calibrate_cable_delay(view)
    np.testing.assert_allclose(cal.fits["cable_delay"]["delay"], DELAYS, rtol=0.02)   # - biased by the resonance - #
    # - the corrected traces equal the originals times exp(-i * slope * f) - #
    slope = cal.fits["cable_delay"]["slope"].to_numpy()
    for emit, original, k in zip(cal, view, slope):
        expected = (original.data.I + 1j * original.data.Q) * np.exp(-1j * k * original.data.frequency)
        np.testing.assert_allclose(emit.data.I + 1j * emit.data.Q, expected)


def test_keeps_everything_else():
    view = delay_view()
    cal = calibrate_cable_delay(view)
    assert cal.name == view.name and cal.columns == view.columns
    pd.testing.assert_frame_equal(cal.proc_params, view.proc_params)
    pd.testing.assert_frame_equal(cal.meta, view.meta)
    assert cal.data.index.equals(view.data.index)
    assert (cal.data["flag"] == 7).all() and cal.data["frequency"].equals(view.data["frequency"])
    assert view.fits == {} and "cable_delay" not in view.fits           # - input unchanged - #
    np.testing.assert_allclose(view.data.I, np.concatenate([trace(F, d).real for d in DELAYS]))


def test_descending_and_unsorted_frequencies():
    shuffled = np.random.default_rng(1).permutation(F)
    for frequencies in (F[::-1], shuffled):
        table = calibrate_cable_delay(delay_view(resonance=False, frequencies=frequencies)).fits["cable_delay"]
        np.testing.assert_allclose(table["delay"], DELAYS, rtol=1e-9)


def test_unusable_emits_and_rows():
    view = delay_view(resonance=False)
    data = view.data.copy()
    data.loc[(0, 0, 5), "I"] = np.nan                                     # - one bad row - #
    keep = ~((data.index.get_level_values("RecordGroup") == 1)
             & (data.index.get_level_values("RecordGroupInd") == 0)
             & (data.index.get_level_values("RecordRow") > 0))            # - emit (1, 0) has one row - #
    view = RecordView("vna", data[keep], view.proc_params, view.meta)
    view = view.rows("frequency > 0").where("delay_set != 120e-9").rows("frequency > 0")
    cal = calibrate_cable_delay(plab.analysis.concat([view, view.rows("frequency < 0")]))
    table = cal.fits["cable_delay"]
    assert table.loc[(0, 0), "delay"] == pytest.approx(DELAYS[0], rel=1e-9)
    assert np.isnan(cal.data.loc[(0, 0, 5), "I"])
    assert table.loc[(1, 0), ["slope", "offset", "delay"]].isna().all()   # - too few rows: not corrected - #
    assert table.loc[(1, 0), "n"] == 1
    pd.testing.assert_frame_equal(cal.group(1).data, view.group(1).data)
    assert table.loc[[(2, 0), (2, 1)], ["slope", "offset", "delay"]].isna().all().all()   # - no rows - #


def test_fits_follow_selections():
    cal = calibrate_cable_delay(delay_view())
    table = cal.fits["cable_delay"]
    sel = cal.where("delay_set > 50e-9")
    assert sel.fits["cable_delay"].index.tolist() == [(0, 1), (1, 0), (1, 1)]
    pd.testing.assert_frame_equal(sel.fits["cable_delay"], table.loc[sel.keys])
    assert cal.group(-1).fits["cable_delay"].index.tolist() == [(1, 0), (1, 1)]
    pd.testing.assert_frame_equal(cal.rows("frequency > 6e9").fits["cable_delay"], table)
    assert "cable_delay" in repr(cal)
    with pytest.raises(TypeError):
        cal.fits["other"] = table                                         # - read-only - #


def test_fits_through_concat():
    cal = calibrate_cable_delay(delay_view())
    both = plab.analysis.concat({"cal": cal, "raw": delay_view()})
    table = both.fits["cable_delay"]
    assert table.index.equals(both.keys) and len(table) == 8
    np.testing.assert_allclose(table.loc[both.where(dataset="cal").keys, "delay"], cal.fits["cable_delay"]["delay"])
    assert table.loc[both.where(dataset="raw").keys].isna().all().all()  # - not calibrated: NaN - #


# - fit_rows ------------------------------------------------------------------------------------- #
WIDE = np.linspace(5.98e9, 6.02e9, 801)


def reflection_view(frequencies=WIDE, delay=60e-9):
    """ Overcoupled reflection traces: the phase turns through 2 pi across the resonance. """
    data, params = [], []
    for index, fr in enumerate([6e9, 6.001e9]):
        ql = 1.2e4
        s = 0.2 * np.exp(1j * ALPHA) * np.exp(-2j * np.pi * frequencies * delay)
        s = s * (1 - (2 * ql / 1.5e4) / (1 + 2j * ql * (frequencies / fr - 1)))
        data.append(pd.DataFrame({"RecordGroup": 0, "RecordGroupInd": index,
                                  "RecordRow": np.arange(len(frequencies)), "frequency": frequencies,
                                  "I": s.real, "Q": s.imag}))
        params.append({"RecordGroup": 0, "RecordGroupInd": index, "f0": fr, "Ql": ql})
    params = pd.DataFrame(params)
    return RecordView("refl", pd.concat(data).set_index(DATA_INDEX), params.set_index(EMIT_INDEX),
                      params[EMIT_INDEX].set_index(EMIT_INDEX))


def test_fit_rows_excludes_the_resonance():
    view = reflection_view()
    everything = calibrate_cable_delay(view).fits["cable_delay"]
    assert (everything["delay"] > 80e-9).all()                         # - the 2 pi turn spoils the fit - #
    away = calibrate_cable_delay(view, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")   # - per emit - #
    table = away.fits["cable_delay"]
    np.testing.assert_allclose(table["delay"], 60e-9, rtol=0.01)
    assert table["n"].tolist() == [int((np.abs(WIDE - fr) > 5 * fr / 1.2e4).sum()) for fr in (6e9, 6.001e9)]
    # - every row is still corrected, with the slope fitted on the selected ones - #
    for emit, original, slope in zip(away, view, table["slope"]):
        expected = (original.data.I + 1j * original.data.Q) * np.exp(-1j * slope * original.data.frequency)
        np.testing.assert_allclose(emit.data.I + 1j * emit.data.Q, expected)
    assert len(away.data) == len(view.data)


def test_fit_rows_across_a_wide_gap():
    # - 120 ns over the excluded 10 MHz is 7.5 rad: unwrapping across the gap alone would slip 2 pi - #
    view = delay_view(resonance=False)
    for fit_rows in ("abs(frequency - 6e9) > 5e6", ["frequency < 5.995e9 or frequency > 6.005e9"]):
        table = calibrate_cable_delay(view, fit_rows=fit_rows).fits["cable_delay"]
        np.testing.assert_allclose(table["delay"], DELAYS, rtol=1e-9)
        np.testing.assert_allclose(table["offset"], ALPHA, atol=1e-6)


def test_fit_rows_isolated_rows_and_several_conditions():
    view = delay_view(resonance=False)
    table = calibrate_cable_delay(view, fit_rows="np.arange(len(frequency)) % 2 == 0").fits["cable_delay"]   # - no runs of two - #
    np.testing.assert_allclose(table["delay"], DELAYS, rtol=1e-9)
    table = calibrate_cable_delay(view, fit_rows=["frequency > 6e9", "delay_set < 100e-9"]).fits["cable_delay"]
    assert table["n"].tolist() == [200, 200, 200, 0]
    assert np.isnan(table["delay"].iloc[3])


def test_fit_rows_selecting_nothing():
    view = delay_view()
    cal = calibrate_cable_delay(view, fit_rows="frequency < 0")
    assert cal.fits["cable_delay"][["slope", "offset", "delay"]].isna().all().all()
    assert cal.fits["cable_delay"]["n"].tolist() == [0] * 4
    pd.testing.assert_frame_equal(cal.data, view.data)                  # - nothing corrected - #


def test_errors():
    cal = calibrate_cable_delay(delay_view())
    with pytest.raises(ValueError, match="already has fit results 'cable_delay'"):
        calibrate_cable_delay(cal)
    view = delay_view()
    with pytest.raises(KeyError, match="'Q'"):
        calibrate_cable_delay(RecordView("x", view.data.drop(columns="Q"), view.proc_params, view.meta))
    with pytest.raises(TypeError, match="fit_rows conditions are expression strings"):
        calibrate_cable_delay(view, fit_rows=[lambda d: d.frequency > 6e9])
    with pytest.raises(NameError, match="'nope'"):
        calibrate_cable_delay(view, fit_rows="nope > 1")
    empty = calibrate_cable_delay(view.where("delay_set > 1"))
    assert len(empty) == 0 and len(empty.fits["cable_delay"]) == 0


def test_exported():
    assert plab.analysis.resonator.calibrate_cable_delay is calibrate_cable_delay


# - calibrate_constant_scaling ---------------------------------------------------------------------- #
from pylabtools.analysis.resonator import CalibrationWarning, arc_length_weights, calibrate_constant_scaling  # noqa: E402,E501
from pylabtools.analysis.resonator.calibration import _fit_circle  # noqa: E402

SPAN = np.linspace(5.99e9, 6.01e9, 801)
TRUE = {"fr": 6e9, "ql": 1.2e4, "qc": 3e4, "phi": 0.3, "a": 0.2, "alpha": 0.7, "delay": 60e-9}


def resonator(geometry, f=SPAN, fr=TRUE["fr"], ql=TRUE["ql"], qc=TRUE["qc"], phi=TRUE["phi"], a=TRUE["a"],
              alpha=TRUE["alpha"], delay=TRUE["delay"]):
    x = 2j * ql * (f / fr - 1)
    if geometry == "hanger":
        shape = 1 - (ql / qc) * np.exp(1j * phi) / (1 + x)
    elif geometry == "reflection":
        shape = 1 - (2 * ql / qc) * np.exp(1j * phi) / (1 + x)
    else:
        shape = (ql / qc) / (1 + x)
    return a * np.exp(1j * alpha) * np.exp(-2j * np.pi * f * delay) * shape


def resonator_view(traces, f=SPAN):
    data, params = [], []
    for index, s in enumerate(traces):
        data.append(pd.DataFrame({"RecordGroup": 0, "RecordGroupInd": index, "RecordRow": np.arange(len(f)),
                                  "frequency": f, "I": s.real, "Q": s.imag}))
        params.append({"RecordGroup": 0, "RecordGroupInd": index, "f0": TRUE["fr"], "Ql": TRUE["ql"]})
    params = pd.DataFrame(params)
    return RecordView("res", pd.concat(data).set_index(DATA_INDEX), params.set_index(EMIT_INDEX),
                      params[EMIT_INDEX].set_index(EMIT_INDEX))


def delay_calibrated(view):
    return calibrate_cable_delay(view, fit_rows="abs(frequency - f0) > 5 * f0 / Ql")


def test_fit_circle():
    t = np.linspace(0, 1.5 * np.pi, 200)
    np.testing.assert_allclose(_fit_circle(0.3 + 0.02 * np.cos(t), -0.1 + 0.02 * np.sin(t)), (0.3, -0.1, 0.02))
    rng = np.random.default_rng(0)
    noisy = _fit_circle(0.3 + 0.02 * np.cos(t) + rng.normal(0, 1e-3, 200),
                        -0.1 + 0.02 * np.sin(t) + rng.normal(0, 1e-3, 200))
    np.testing.assert_allclose(noisy, (0.3, -0.1, 0.02), atol=5e-4)
    assert _fit_circle(np.linspace(0, 1, 10), np.linspace(0, 2, 10)) is None          # - a line - #
    assert _fit_circle(np.ones(5), np.ones(5)) is None                                # - one point - #


EXPECTED_CIRCLE = {   # - the normalised circle: centre and radius - #
    "hanger": (1 - TRUE["ql"] / (2 * TRUE["qc"]) * np.exp(1j * TRUE["phi"]), TRUE["ql"] / (2 * TRUE["qc"])),
    "reflection": (1 - TRUE["ql"] / TRUE["qc"] * np.exp(1j * TRUE["phi"]), TRUE["ql"] / TRUE["qc"]),
    "transmission": (0.5, 0.5),
}


@pytest.mark.parametrize("weights", [None, "arc_length"])
@pytest.mark.parametrize("geometry", ["hanger", "reflection", "transmission"])
def test_refined_calibration_recovers_the_resonator(geometry, weights):
    first = delay_calibrated(resonator_view([resonator(geometry)]))
    cal = calibrate_constant_scaling(first, geometry, refine_cable_delay=True, weights=weights)
    table = cal.fits["constant_scaling"]
    assert list(table.columns) == ["delay_correction", "xc", "yc", "r", "circle_rms", "theta0", "Ql", "fr", "a",
                                   "alpha", "n"]
    row = table.iloc[0]
    total = first.fits["cable_delay"]["delay"].iloc[0] + row["delay_correction"]
    inline = geometry == "transmission"
    # - an inline circle hardly changes shape with the delay (to first order it only changes Ql), so the
    #   delay is pinned down far less precisely; alpha inherits that error times f / span - #
    delay_rtol = 1e-5 if inline else 1e-9
    assert total == pytest.approx(TRUE["delay"], rel=delay_rtol, abs=0)
    assert row["fr"] == pytest.approx(TRUE["fr"], rel=1e-10)
    assert row["Ql"] == pytest.approx(TRUE["ql"], rel=1e-6)
    scale = TRUE["ql"] / TRUE["qc"] if inline else 1.0             # - inline: the resonance point - #
    assert row["a"] == pytest.approx(TRUE["a"] * scale, rel=1e-6)
    alpha_tolerance = max(2 * np.pi * TRUE["fr"] * delay_rtol * TRUE["delay"], 1e-5)    # - from the delay's - #
    assert np.angle(np.exp(1j * (row["alpha"] - TRUE["alpha"]))) == pytest.approx(0, abs=alpha_tolerance)
    assert row["circle_rms"] / row["r"] < 1e-6 and row["n"] == len(SPAN)
    # - the normalised data lie on the canonical circle - #
    s = cal.data.I.to_numpy() + 1j * cal.data.Q.to_numpy()
    centre, radius = EXPECTED_CIRCLE[geometry]
    np.testing.assert_allclose(_fit_circle(s.real, s.imag), (np.real(centre), np.imag(centre), radius), atol=1e-6)
    assert list(cal.fits) == ["cable_delay", "constant_scaling"]


def test_without_refinement():
    first = delay_calibrated(resonator_view([resonator("hanger")]))
    cal = calibrate_constant_scaling(first, "hanger")
    row = cal.fits["constant_scaling"].iloc[0]
    assert row["delay_correction"] == 0
    # - the data are only divided by the point; the linear fit's small delay error remains - #
    expected = (first.data.I + 1j * first.data.Q) / (row["a"] * np.exp(1j * row["alpha"]))
    np.testing.assert_allclose(cal.data.I + 1j * cal.data.Q, expected)
    assert row["Ql"] == pytest.approx(TRUE["ql"], rel=0.1)             # - near, but biased by the delay - #
    assert row["circle_rms"] / row["r"] > 1e-3


def test_noisy_traces():
    rng = np.random.default_rng(5)
    traces = [resonator("hanger") + 2e-3 * (rng.normal(size=SPAN.size) + 1j * rng.normal(size=SPAN.size))
              for _ in range(3)]
    table = calibrate_constant_scaling(delay_calibrated(resonator_view(traces)), "hanger",
                                       refine_cable_delay=True).fits["constant_scaling"]
    np.testing.assert_allclose(table["fr"], TRUE["fr"], rtol=2e-6)
    np.testing.assert_allclose(table["Ql"], TRUE["ql"], rtol=0.03)
    np.testing.assert_allclose(table["a"], TRUE["a"], rtol=0.01)


def test_opposite_phase_convention():
    # - conjugated data circle the other way; Ql is still reported positive - #
    view = resonator_view([np.conj(resonator("hanger"))])
    table = calibrate_constant_scaling(delay_calibrated(view), "hanger", refine_cable_delay=True).fits["constant_scaling"]
    assert table["Ql"].iloc[0] == pytest.approx(TRUE["ql"], rel=1e-6)
    assert table["fr"].iloc[0] == pytest.approx(TRUE["fr"], rel=1e-10)
    assert table["a"].iloc[0] == pytest.approx(TRUE["a"], rel=1e-6)


def test_several_emits_and_selection():
    view = resonator_view([resonator("hanger", fr=6e9 + d) for d in (0, 2e5, -2e5)])
    cal = calibrate_constant_scaling(delay_calibrated(view), "hanger", refine_cable_delay=True)
    np.testing.assert_allclose(cal.fits["constant_scaling"]["fr"], [6e9, 6.0002e9, 5.9998e9], rtol=1e-10)
    sel = cal.where("f0 > 0").group(0)
    assert sel.fits["constant_scaling"].index.equals(sel.keys)


def test_unusable_emits_warn():
    view = resonator_view([resonator("hanger"), resonator("hanger")])
    short = view.rows("frequency < 5.99e9 + 3 * 25e3")                  # - 3 rows per emit - #
    with pytest.warns(CalibrationWarning, match="could not fit 2 emit"):
        cal = calibrate_constant_scaling(short, "hanger")
    assert cal.fits["constant_scaling"].drop(columns="n").isna().all().all()
    assert cal.fits["constant_scaling"]["n"].tolist() == [3, 3]
    pd.testing.assert_frame_equal(cal.data, short.data)                   # - left unnormalised - #


def test_weights_leave_the_delay_refinement_unweighted():
    rng = np.random.default_rng(4)
    s = drooping_reflection(0.05) + 2e-3 * (rng.normal(size=SPAN.size) + 1j * rng.normal(size=SPAN.size))
    view = delay_calibrated(resonator_view([s]))
    plain = calibrate_constant_scaling(view, "reflection", refine_cable_delay=True).fits["constant_scaling"]
    weighted = calibrate_constant_scaling(view, "reflection", refine_cable_delay=True,
                                          weights="arc_length").fits["constant_scaling"]
    assert weighted["delay_correction"].iloc[0] == plain["delay_correction"].iloc[0]
    assert weighted["Ql"].iloc[0] != plain["Ql"].iloc[0]                  # - the fits are weighted - #


def test_arc_length_weights():
    w = arc_length_weights(SPAN, TRUE["fr"], TRUE["ql"])
    assert w.mean() == pytest.approx(1)
    assert SPAN[np.argmax(w)] == pytest.approx(TRUE["fr"])
    x = 2 * TRUE["ql"] * (SPAN / TRUE["fr"] - 1)
    np.testing.assert_allclose(w / w.max(), 1 / (1 + x * x) / np.max(1 / (1 + x * x)))
    # - equal to the ideal circle's arc length per frequency step - #
    s = resonator("hanger", delay=0)
    step = np.abs(np.gradient(s, SPAN))
    np.testing.assert_allclose(w / w.mean(), step / step.mean(), rtol=1e-2)   # - a finite-difference step - #


def drooping_reflection(curvature):
    """ An overcoupled reflection trace whose background amplitude falls towards both ends. """
    u = 2 * (SPAN - TRUE["fr"]) / np.ptp(SPAN)
    return resonator("reflection", qc=1.5e4, phi=0.1) * (1 - curvature * u * u)


def test_weights_resist_a_curved_background():
    view = delay_calibrated(resonator_view([drooping_reflection(0.05)]))
    plain = calibrate_constant_scaling(view, "reflection", refine_cable_delay=True).fits["constant_scaling"]
    weighted = calibrate_constant_scaling(view, "reflection", refine_cable_delay=True,
                                          weights="arc_length").fits["constant_scaling"]
    diameter = 2 * 1.2e4 / 1.5e4
    assert abs(plain["Ql"].iloc[0] / TRUE["ql"] - 1) > 0.015               # - pulled by the background - #
    assert abs(weighted["Ql"].iloc[0] / TRUE["ql"] - 1) < 0.004
    assert abs(2 * plain["r"].iloc[0] / plain["a"].iloc[0] - diameter) > 0.02
    assert abs(2 * weighted["r"].iloc[0] / weighted["a"].iloc[0] - diameter) < 0.005


def test_constant_scaling_errors():
    view = delay_calibrated(resonator_view([resonator("hanger")]))
    with pytest.raises(ValueError, match="geometry must be one of"):
        calibrate_constant_scaling(view, "notch")
    with pytest.raises(ValueError, match="weights must be one of"):
        calibrate_constant_scaling(view, "hanger", weights="density")
    cal = calibrate_constant_scaling(view, "hanger")
    with pytest.raises(ValueError, match="already has fit results 'constant_scaling'"):
        calibrate_constant_scaling(cal, "hanger")
    with pytest.raises(KeyError, match="'I'"):
        calibrate_constant_scaling(RecordView("x", view.data.drop(columns="I"), view.proc_params, view.meta), "hanger")
