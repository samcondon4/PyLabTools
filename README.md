# PyLabTools

PyLabTools is a Python framework for laboratory measurement automation. A **procedure** talks to
[PyMeasure](https://pymeasure.readthedocs.io) instrument drivers and **emits** records, which are
routed to **recorders** (HDF5, CSV) and **viewers** (live plots). Everything is plain Python, usable
from scripts and notebooks; the Qt display is optional.

> **Status:** PyLabTools 1.0 is a ground-up rewrite under development on the `dev/1.0` branch.

```python
import pylabtools as plab
from pymeasure.experiment import FloatParameter

class VoltageLog(plab.Procedure):
    setpoint = FloatParameter("Setpoint", units="V", default=1.0)

    def __init__(self, inst, **kwargs):
        super().__init__(**kwargs)
        self.inst = inst

    def execute(self):
        while not self.should_stop():
            self.emit("voltage", {"t": self.inst.time, "V": self.inst.voltage})

proc = VoltageLog(instrument)
hdf = plab.HDFRecorder("run.h5")
view = plab.LineViewer(x="t", y="V")
proc.connect("voltage", hdf, view)

with plab.running(hdf, view):
    run = plab.start(proc, setpoint=2.5)
    plab.gui.show(view, run=run, block=True)   # live plot; Ctrl-C stops the run cleanly
    plab.wait(run)

df = plab.read_hdf("run.h5", "voltage", groups=-1)
```

Every row is indexed by `RecordGroup` (one per run or sequence), `RecordGroupInd` (emit counter)
and `RecordRow`, with procedure parameters and metadata stored alongside the data.

## Install

```bash
pip install "pylabtools[gui] @ git+https://github.com/samcondon4/PyLabTools.git@dev/1.0"
```

Runnable examples using a fake instrument are in [`examples/`](examples/). Documentation sources are
in [`docs/`](docs/); build them with `pip install -e ".[docs]"` and
`sphinx-build -b html docs docs/_build/html`.

## Development

```bash
pip install -e ".[dev,gui,docs]"
pytest
```

## Legacy 0.9

The previous, configuration-file based release is preserved at the `v0.9.1` tag:

```bash
pip install "git+https://github.com/samcondon4/PyLabTools.git@v0.9.1"
```

PyLabTools was initially developed under the name *SPHERExLabTools* for the optical calibration of
NASA's SPHEREx telescope; see the
[SPHERExLabTools conference proceedings](https://arxiv.org/abs/2208.05099).
