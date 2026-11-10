""" pylabtools.analysis.plot: lineplot and scatterplot of RecordViews. """
import numpy as np
import pandas as pd
import pytest

mpl = pytest.importorskip("matplotlib")
mpl.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402

import pylabtools as plab  # noqa: E402
from pylabtools.analysis import RecordView  # noqa: E402
from pylabtools.analysis.plot import AveragingWarning, lineplot, scatterplot  # noqa: E402
from pylabtools.recorders import DATA_INDEX, EMIT_INDEX  # noqa: E402

F = np.linspace(5.99e9, 6.01e9, 11)
MAG_DB = "20*np.log10(np.sqrt(I**2 + Q**2))"


def vna_view():
    """ Three setpoints x two modes x two traces; I = setpoint * (trace + 1), Q = 0. """
    data, params, meta = [], [], []
    index = 0
    for setpoint in [0.05, 0.1, 0.2]:
        for mode in ["a", "b"]:
            for trace in range(2):
                n = len(F)
                data.append(pd.DataFrame({"RecordGroup": 0, "RecordGroupInd": index, "RecordRow": np.arange(n),
                                          "frequency": F, "I": np.full(n, setpoint * (trace + 1)),
                                          "Q": np.zeros(n)}))
                params.append({"RecordGroup": 0, "RecordGroupInd": index, "setpoint": setpoint, "mode": mode,
                               "power": -20.0})
                meta.append({"RecordGroup": 0, "RecordGroupInd": index, "trace": trace, "power": -19.5})
                index += 1
    return RecordView("vna", pd.concat(data).set_index(DATA_INDEX),
                      pd.DataFrame(params).set_index(EMIT_INDEX), pd.DataFrame(meta).set_index(EMIT_INDEX))


@pytest.fixture
def vna():
    return vna_view()


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


# - basics --------------------------------------------------------------------------------------- #
def test_lineplot_columns(vna):
    fig, ax = lineplot(vna, x="frequency", y="I")
    assert fig is ax.figure
    assert len(ax.lines) == len(vna) == 12
    np.testing.assert_allclose(ax.lines[0].get_xdata(), F)
    np.testing.assert_allclose(ax.lines[0].get_ydata(), 0.05)
    assert ax.get_xlabel() == "frequency" and ax.get_ylabel() == "I"
    assert ax.get_title() == ""
    assert ax.get_legend() is None and len(fig.axes) == 1


def test_lineplot_expression(vna):
    _, ax = lineplot(vna, x="frequency / 1e9", y=MAG_DB)
    np.testing.assert_allclose(ax.lines[1].get_xdata(), F / 1e9)
    np.testing.assert_allclose(ax.lines[1].get_ydata(), 20 * np.log10(0.1))
    assert ax.get_ylabel() == MAG_DB


def test_expressions_see_params_and_meta(vna):
    _, ax = lineplot(vna, x="frequency", y="I * proc_power + meta_trace + setpoint")
    np.testing.assert_allclose(ax.lines[1].get_ydata(), 0.1 * -20 + 1 + 0.05)
    _, ax = lineplot(vna, x="frequency", y="setpoint")        # - scalars are repeated - #
    np.testing.assert_allclose(ax.lines[0].get_ydata(), np.full(len(F), 0.05))


def test_labels_title_and_kwargs(vna):
    _, ax = lineplot(vna, x="frequency", y="I", xlabel="f (Hz)", ylabel="I (V)", title="Sweep", lw=3, ls="--")
    assert (ax.get_xlabel(), ax.get_ylabel(), ax.get_title()) == ("f (Hz)", "I (V)", "Sweep")
    assert ax.lines[0].get_linewidth() == 3 and ax.lines[0].get_linestyle() == "--"


def test_draws_on_given_axes(vna):
    fig, ax = plt.subplots(1, 2)
    out_fig, out_ax = lineplot(vna.where(mode="a"), x="frequency", y="I", ax=ax[1])
    assert out_fig is fig and out_ax is ax[1]
    assert len(ax[1].lines) == 6 and len(ax[0].lines) == 0


def test_plot_is_reachable_lazily():
    assert plab.analysis.lineplot is lineplot
    assert plab.analysis.plot.scatterplot is scatterplot


# - colouring ------------------------------------------------------------------------------------ #
def test_numeric_color_by_adds_colorbar(vna):
    fig, ax = lineplot(vna, x="frequency", y="I", color_by="setpoint")
    assert len(fig.axes) == 2
    colorbar_ax = fig.axes[1]
    assert colorbar_ax.get_ylabel() == "setpoint"
    cmap, norm = mpl.colormaps["viridis"], mcolors.Normalize(0.05, 0.2)
    for line, setpoint in zip(ax.lines, vna.proc_params.setpoint):
        assert mcolors.to_rgba(line.get_color()) == pytest.approx(cmap(norm(setpoint)))
    assert len(ax.lines) == 12                      # - every trace drawn, not averaged - #


def test_color_by_options(vna):
    norm = mcolors.LogNorm()
    fig, ax = lineplot(vna, x="frequency", y="I", color_by="setpoint * 1e3", cmap="plasma", norm=norm,
                       clabel="T (mK)")
    assert (norm.vmin, norm.vmax) == pytest.approx((50, 200))
    assert fig.axes[1].get_ylabel() == "T (mK)"
    assert mcolors.to_rgba(ax.lines[0].get_color()) == pytest.approx(mpl.colormaps["plasma"](norm(50)))
    fig, _ = lineplot(vna, x="frequency", y="I", color_by="setpoint", colorbar=False)
    assert len(fig.axes) == 1


def test_text_color_by_adds_legend(vna):
    _, ax = lineplot(vna, x="frequency", y="I", color_by="mode")
    legend = ax.get_legend()
    assert legend.get_title().get_text() == "mode"
    assert [t.get_text() for t in legend.get_texts()] == ["a", "b"]
    colors = {mcolors.to_hex(line.get_color()) for line in ax.lines}
    assert len(colors) == 2 and len(ax.lines) == 12
    _, ax = lineplot(vna, x="frequency", y="I", color_by="mode", legend=False)
    assert ax.get_legend() is None


def test_color_by_prefixed_and_meta(vna):
    _, ax = lineplot(vna, x="frequency", y="I", color_by="meta_power")
    assert len(ax.figure.axes) == 2
    _, ax = lineplot(vna, x="frequency", y="I", color_by="trace")
    assert len(ax.figure.axes) == 2


# - averaging ------------------------------------------------------------------------------------ #
def test_average_by_color_value(vna):
    fig, ax = lineplot(vna, x="frequency", y="I", color_by="setpoint", average=True)
    assert len(ax.lines) == 3
    # - traces 0 and 1 have I = setpoint and 2 * setpoint - #
    np.testing.assert_allclose([line.get_ydata()[0] for line in ax.lines], [0.075, 0.15, 0.3])
    assert len(fig.axes) == 2


def test_average_columns_before_the_expression(vna):
    _, ax = lineplot(vna.where(setpoint=0.1), x="frequency", y="I**2", average=True)
    assert len(ax.lines) == 1
    np.testing.assert_allclose(ax.lines[0].get_ydata(), 0.15 ** 2)   # - (mean I)^2, not mean(I^2) - #


def test_average_by_text_value(vna):
    _, ax = lineplot(vna, x="frequency", y="I", color_by="mode", average=True)
    assert len(ax.lines) == 2
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["a", "b"]


def test_average_can_use_shared_params_only(vna):
    _, ax = lineplot(vna, x="frequency", y="I * proc_power", color_by="setpoint", average=True)
    np.testing.assert_allclose(ax.lines[0].get_ydata(), 0.075 * -20)
    with pytest.raises(NameError, match="'trace'"):
        lineplot(vna, x="frequency", y="I + trace", color_by="setpoint", average=True)


def test_average_with_differing_x_warns(vna):
    # - an I-Q "circle": x = I differs between the two traces of every setpoint - #
    with pytest.warns(AveragingWarning, match=r"color_by values \[0.05, 0.1, 0.2\].*xaverage_silent") as record:
        _, ax = scatterplot(vna, x="I", y="Q", color_by="setpoint", average=True)
    assert len(record) == 1                                   # - one warning per call - #
    assert record[0].filename == __file__                     # - points at the caller - #
    assert len(ax.collections) == 3
    np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 0], 1.5 * 0.05)
    with pytest.warns(AveragingWarning, match="all emits"):
        lineplot(vna.where(setpoint=0.1), x="I", y="Q", average=True)


def test_xaverage_silent(vna):
    # - warnings are errors in this test suite, so no warning may be issued - #
    _, ax = scatterplot(vna, x="I", y="Q", color_by="setpoint", average=True, xaverage_silent=True)
    assert len(ax.collections) == 3
    lineplot(vna, x="I", y="Q", color_by="mode", average=True, xaverage_silent=True)


def test_average_with_matching_x_does_not_warn(vna):
    lineplot(vna, x="frequency", y="I", color_by="setpoint", average=True)


def test_average_needs_equal_row_counts(vna):
    rows = vna.data.index
    keep = ~((rows.get_level_values("RecordGroupInd") == 0) & (rows.get_level_values("RecordRow") >= 5))
    view = RecordView("vna", vna.data[keep], vna.proc_params, vna.meta)     # - emit 0 has 5 rows - #
    with pytest.raises(ValueError, match="different numbers of rows"):
        lineplot(view, x="frequency", y="I", color_by="setpoint", average=True)


# - scatter -------------------------------------------------------------------------------------- #
def test_scatterplot(vna):
    fig, ax = scatterplot(vna, x="frequency", y=MAG_DB, color_by="setpoint", s=4, title="S")
    assert len(ax.collections) == 12
    np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 0], F)
    np.testing.assert_allclose(ax.collections[0].get_offsets()[:, 1], 20 * np.log10(0.05))
    assert ax.collections[0].get_sizes()[0] == 4
    assert ax.get_title() == "S" and len(fig.axes) == 2
    _, ax = scatterplot(vna, x="frequency", y="I", color_by="mode", average=True)
    assert len(ax.collections) == 2 and ax.get_legend() is not None


# - errors --------------------------------------------------------------------------------------- #
def test_errors(vna):
    with pytest.raises(ValueError, match="no emits"):
        lineplot(vna.where(setpoint=1.0), x="frequency", y="I")
    with pytest.raises(NameError, match="nope.*Available"):
        lineplot(vna, x="frequency", y="nope * 2")
    with pytest.raises(NameError, match="both a procedure parameter and metadata"):
        lineplot(vna, x="frequency", y="I * power")
    with pytest.raises(ValueError, match="one value per emit"):
        lineplot(vna, x="frequency", y="I", color_by="np.arange(3)")
    with pytest.raises(NameError, match="color_by 'I'"):
        lineplot(vna, x="frequency", y="I", color_by="I")         # - data columns are not per-emit - #
    with pytest.raises(ValueError, match="shape"):
        lineplot(vna, x="frequency", y="I[:3]")
    with pytest.raises(ValueError, match="color="):
        lineplot(vna, x="frequency", y="I", color_by="setpoint", color="k")
