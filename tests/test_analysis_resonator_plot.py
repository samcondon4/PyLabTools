""" pylabtools.analysis.resonator.plot_res_data: magnitude, phase and I-Q panels. """
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402

import pylabtools as plab  # noqa: E402
from pylabtools.analysis import RecordView  # noqa: E402
from pylabtools.analysis.plot import AveragingWarning  # noqa: E402
from pylabtools.analysis.resonator import plot_res_data  # noqa: E402
from pylabtools.recorders import DATA_INDEX, EMIT_INDEX  # noqa: E402

F = np.linspace(5.99e9, 6.01e9, 201)


def hanger(f, fr=6e9, ql=1e4, qc=2e4, a=0.5, tau=200e-9):
    """ A hanger trace with a cable delay, so the phase wraps several times. """
    s = a * np.exp(-2j * np.pi * f * tau) * (1 - (ql / qc) / (1 + 2j * ql * (f / fr - 1)))
    return s.real, s.imag


def res_view(shift=0.0):
    data, params, meta = [], [], []
    for index, (power, mode) in enumerate([(-30.0, "a"), (-30.0, "a"), (-10.0, "b"), (-10.0, "b")]):
        f = F + shift * (index % 2)
        i, q = hanger(f, a=0.5 * (1 + 0.1 * (index % 2)))
        data.append(pd.DataFrame({"RecordGroup": 0, "RecordGroupInd": index, "RecordRow": np.arange(len(f)),
                                  "frequency": f, "I": i, "Q": q}))
        params.append({"RecordGroup": 0, "RecordGroupInd": index, "power": power, "mode": mode})
        meta.append({"RecordGroup": 0, "RecordGroupInd": index, "trace": index % 2})
    return RecordView("vna", pd.concat(data).set_index(DATA_INDEX),
                      pd.DataFrame(params).set_index(EMIT_INDEX), pd.DataFrame(meta).set_index(EMIT_INDEX))


@pytest.fixture
def vna():
    return res_view()


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


def test_panels(vna):
    fig, axes = plot_res_data(vna)
    assert list(axes) == ["mag", "phase", "iq"]
    assert all(ax.figure is fig for ax in axes.values())
    assert len(fig.axes) == 3                                   # - no colour bar without color_by - #
    assert len(axes["mag"].lines) == len(axes["phase"].lines) == len(axes["iq"].collections) == 4
    i, q = hanger(F)
    np.testing.assert_allclose(axes["mag"].lines[0].get_xdata(), F)
    np.testing.assert_allclose(axes["mag"].lines[0].get_ydata(), 20 * np.log10(np.hypot(i, q)))
    phase = axes["phase"].lines[0].get_ydata()
    np.testing.assert_allclose(phase, np.unwrap(np.arctan2(q, i)))
    assert np.ptp(phase) > 2 * np.pi                           # - unwrapped, not folded into (-pi, pi] - #
    np.testing.assert_allclose(axes["iq"].collections[0].get_offsets(), np.column_stack([i, q]))
    assert axes["iq"].get_aspect() == 1.0
    assert axes["mag"].get_shared_x_axes().joined(axes["mag"], axes["phase"])
    assert (axes["phase"].get_xlabel(), axes["mag"].get_ylabel(), axes["phase"].get_ylabel()) == \
        ("frequency", "Magnitude (dB)", "Phase (rad)")
    assert (axes["iq"].get_xlabel(), axes["iq"].get_ylabel()) == ("I", "Q")
    assert fig.get_suptitle() == ""


def test_numeric_color_by_has_one_colorbar(vna):
    fig, axes = plot_res_data(vna, color_by="power", clabel="P (dBm)", cmap="plasma")
    assert len(fig.axes) == 4
    assert fig.axes[3].get_ylabel() == "P (dBm)"
    norm, cmap = mcolors.Normalize(-30, -10), mpl.colormaps["plasma"]
    expected = cmap(norm(-10.0))
    assert mcolors.to_rgba(axes["mag"].lines[2].get_color()) == pytest.approx(expected)
    assert mcolors.to_rgba(axes["phase"].lines[2].get_color()) == pytest.approx(expected)
    assert tuple(axes["iq"].collections[2].get_facecolor()[0]) == pytest.approx(expected)
    fig, _ = plot_res_data(vna, color_by="power", colorbar=False)
    assert len(fig.axes) == 3


def test_text_color_by_has_one_legend(vna):
    _, axes = plot_res_data(vna, color_by="mode")
    assert [t.get_text() for t in axes["mag"].get_legend().get_texts()] == ["a", "b"]
    assert axes["phase"].get_legend() is None and axes["iq"].get_legend() is None
    _, axes = plot_res_data(vna, color_by="mode", legend=False)
    assert axes["mag"].get_legend() is None


def test_average(vna):
    # - the two traces of each power differ only in amplitude: averaging I and Q gives 1.05x - #
    _, axes = plot_res_data(vna, color_by="power", average=True)
    assert len(axes["mag"].lines) == len(axes["iq"].collections) == 2
    i, q = hanger(F, a=0.525)
    np.testing.assert_allclose(axes["mag"].lines[0].get_ydata(), 20 * np.log10(np.hypot(i, q)))
    np.testing.assert_allclose(axes["iq"].collections[0].get_offsets(), np.column_stack([i, q]))


def test_average_warns_only_for_differing_frequencies():
    # - warnings are errors in this test suite: matching frequencies give none, even for the I-Q panel - #
    plot_res_data(res_view(), color_by="power", average=True)
    with pytest.warns(AveragingWarning, match="'frequency'") as record:
        plot_res_data(res_view(shift=1e3), color_by="power", average=True)
    assert len(record) == 1                                    # - once, not once per panel - #
    assert record[0].filename == __file__                      # - points at the caller - #
    plot_res_data(res_view(shift=1e3), color_by="power", average=True, xaverage_silent=True)


def test_options_and_given_axes(vna):
    fig, axs = plt.subplots(1, 3)
    out_fig, axes = plot_res_data(vna, axes=axs, title="Cooldown", xlabel="f (Hz)", lw=3,
                                  scatter_kwargs={"s": 20, "marker": "x"})
    assert out_fig is fig and [axes[k] for k in ("mag", "phase", "iq")] == list(axs)
    assert fig.get_suptitle() == "Cooldown"
    assert axes["phase"].get_xlabel() == "f (Hz)"
    assert axes["mag"].lines[0].get_linewidth() == 3
    assert axes["iq"].collections[0].get_sizes()[0] == 20
    _, axes = plot_res_data(vna.where("trace == 0").rows("frequency > 6e9"),
                            axes={"iq": axs[0], "phase": axs[1], "mag": axs[2]})
    assert axes["iq"] is axs[0] and len(axes["mag"].lines[0].get_xdata()) == 100


def test_errors(vna):
    view = RecordView("x", vna.data.rename(columns={"I": "i"}), vna.proc_params, vna.meta)
    with pytest.raises(KeyError, match="'I'"):
        plot_res_data(view)
    with pytest.raises(ValueError, match="three Axes"):
        plot_res_data(vna, axes=plt.subplots(1, 2)[1])
    with pytest.raises(KeyError, match="missing"):
        plot_res_data(vna, axes={"mag": None})
    with pytest.raises(ValueError, match="no emits"):
        plot_res_data(vna.where("trace == 5"))


def test_lazy_imports():
    assert plab.analysis.resonator.plot_res_data is plot_res_data
    code = "import sys, pylabtools.analysis.resonator; print('matplotlib' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# - plot_res_params ------------------------------------------------------------------------------- #
from matplotlib.collections import LineCollection, PathCollection  # noqa: E402

from pylabtools.analysis.resonator import plot_res_params  # noqa: E402


def fitted_view():
    """ Four emits with a hand-made res_params table: Qi rising with power, fr shifting. """
    view = res_view()
    table = pd.DataFrame({"fr": [6e9, 6e9 + 1e3, 6e9 + 2e3, 6e9 + 3e3], "fr_err": [10.0, 20, 30, 40],
                          "Ql": [1e4, 1.1e4, 1.2e4, 1.3e4], "Ql_err": [100.0, 100, 100, 100],
                          "Qc": [2e4] * 4, "Qc_err": [50.0] * 4,
                          "Qi": [2e4, 2.4e4, 2.8e4, 3.2e4], "Qi_err": [300.0, 300, 300, 300]}, index=view.keys)
    return view.with_data(view.data, step="res_params", table=table)


def scatter_points(ax):
    return [c for c in ax.collections if isinstance(c, PathCollection)]


def test_plot_res_params_layout():
    view = fitted_view()
    fig, axes = plot_res_params(view, x="power", xlabel="Power (dBm)", title="Fits")
    assert list(axes) == ["Q", "fr"] and len(fig.axes) == 2
    assert axes["Q"].get_shared_x_axes().joined(axes["Q"], axes["fr"])
    assert [t.get_text() for t in axes["Q"].get_legend().get_texts()] == ["Ql (loaded)", "Qc (coupling)",
                                                                           "Qi (internal)"]
    assert len(scatter_points(axes["Q"])) == 12 and len(scatter_points(axes["fr"])) == 4
    qi = sorted(tuple(c.get_offsets()[0]) for c in scatter_points(axes["Q"]) if c.get_label() == "Qi (internal)")
    assert qi == sorted(zip(view.proc_params["power"], [2e4, 2.4e4, 2.8e4, 3.2e4]))
    fr = sorted(c.get_offsets()[0][1] for c in scatter_points(axes["fr"]))
    assert fr == pytest.approx([6e9, 6e9 + 1e3, 6e9 + 2e3, 6e9 + 3e3])
    assert (axes["fr"].get_xlabel(), axes["fr"].get_ylabel(), axes["Q"].get_ylabel()) == \
        ("Power (dBm)", "fr (Hz)", "Quality factor")
    assert fig.get_suptitle() == "Fits"


def test_plot_res_params_error_bars():
    _, axes = plot_res_params(fitted_view(), x="power")
    bars = [c for c in axes["fr"].collections if isinstance(c, LineCollection)]
    assert len(bars) == 1
    lengths = sorted(np.ptp(segment[:, 1]) for segment in bars[0].get_segments())
    assert lengths == pytest.approx([20, 40, 60, 80])                   # - 2 * fr_err - #
    _, axes = plot_res_params(fitted_view(), x="power", errors=False)
    assert not any(isinstance(c, LineCollection) for c in axes["fr"].collections)


def test_plot_res_params_selects_qs():
    _, axes = plot_res_params(fitted_view(), x="power", qs=("Qi", "Qc"))
    assert [t.get_text() for t in axes["Q"].get_legend().get_texts()] == ["Qi (internal)", "Qc (coupling)"]
    assert len(scatter_points(axes["Q"])) == 8
    _, axes = plot_res_params(fitted_view(), x="power", qs="Qi")
    assert [t.get_text() for t in axes["Q"].get_legend().get_texts()] == ["Qi (internal)"]
    colours = {mcolors.to_hex(c.get_facecolor()[0]) for c in scatter_points(axes["Q"])}
    assert len(colours) == 1                                            # - Qi keeps its colour - #


def test_plot_res_params_skips_undetermined_qs_and_takes_axes():
    view = fitted_view()
    table = view.fits["res_params"].assign(Qc=np.nan, Qi=np.nan)        # - as for an inline resonator - #
    inline = view.with_data(view.data, step="other", table=table)
    fig, axs = plt.subplots(2, 1)
    out_fig, axes = plot_res_params(inline, x="power * 2", fit="other", axes=axs)
    assert out_fig is fig and axes["Q"] is axs[0]
    assert [t.get_text() for t in axes["Q"].get_legend().get_texts()] == ["Ql (loaded)"]
    assert sorted(c.get_offsets()[0][0] for c in scatter_points(axes["fr"])) == [-60, -60, -20, -20]


def test_plot_res_params_errors():
    view = fitted_view()
    with pytest.raises(ValueError, match="qs must name"):
        plot_res_params(view, x="power", qs=("Qi", "Qx"))
    with pytest.raises(ValueError, match="qs must name"):
        plot_res_params(view, x="power", qs=())
    with pytest.raises(KeyError, match="no fit results 'res_params'"):
        plot_res_params(res_view(), x="power")
    with pytest.raises(ValueError, match="two Axes"):
        plot_res_params(view, x="power", axes=plt.subplots(1, 3)[1])
    with pytest.raises(ValueError, match="no emits"):
        plot_res_params(view.where("power > 100"), x="power")
