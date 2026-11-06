""" Analysis of datasets recorded by PyLabTools.

The core of this subpackage (:class:`Dataset`, :class:`RecordView`, :class:`Emit`) needs only
pandas. Plotting (:mod:`pylabtools.analysis.plot`) needs matplotlib (``pip install
pylabtools[analysis]``) and is imported only when first used, e.g. as
``pylabtools.analysis.lineplot``.
"""
from .dataset import Dataset, Emit, RecordView

__all__ = ["Dataset", "Emit", "RecordView", "lineplot", "plot", "scatterplot"]


def __getattr__(name):
    # - import matplotlib lazily, so the core never requires it - #
    if name in ("plot", "lineplot", "scatterplot"):
        import importlib
        plot = importlib.import_module(".plot", __name__)
        return plot if name == "plot" else getattr(plot, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
