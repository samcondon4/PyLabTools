""" Analysis of microwave resonator traces.

Traces are emits whose data has the columns ``frequency``, ``I`` and ``Q`` (the real and imaginary
parts of the measured S parameter). Three coupling geometries are supported, chosen with
``geometry=``:

``"hanger"``
    a resonator side-coupled to a feedline (also called notch type), measured in S21: a dip.
``"reflection"``
    a resonator at the end of a line, measured in S11.
``"transmission"``
    an inline resonator coupled at both ends, measured in S21: a peak.

Calibration steps (:func:`calibrate_cable_delay`, :func:`calibrate_constant_scaling`) return new
views with corrected data and record their fit results in the view's
:attr:`~pylabtools.analysis.RecordView.fits`. Plotting
(:func:`plot_res_data`) needs matplotlib (``pip install pylabtools[analysis]``) and is imported
only when first used.
"""
from .calibration import (GEOMETRIES, WEIGHTS, CalibrationWarning, arc_length_weights, calibrate_cable_delay,
                          calibrate_constant_scaling)

__all__ = ["GEOMETRIES", "WEIGHTS", "CalibrationWarning", "arc_length_weights", "calibrate_cable_delay",
           "calibrate_constant_scaling", "plot_res_data"]


def __getattr__(name):
    # - import matplotlib lazily, so the fitting code never requires it - #
    if name in ("plot", "plot_res_data"):
        import importlib
        plot = importlib.import_module(".plot", __name__)
        return plot if name == "plot" else getattr(plot, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
