# PyLabTools

PyLabTools is a Python framework for laboratory measurement automation: procedures emit
records that are routed to recorders (data archival) and viewers (live display), built on top
of [PyMeasure](https://pymeasure.readthedocs.io) instrument drivers.

> **Status:** PyLabTools 1.0 is a ground-up rewrite under development on the `dev/1.0` branch.
> The core is usable headless from scripts and notebooks; the Qt GUI is an optional layer.

## Legacy 0.9

The previous, configuration-file based release is preserved at the `v0.9.1` tag:

```bash
pip install "git+https://github.com/samcondon4/PyLabTools.git@v0.9.1"
```

PyLabTools was initially developed under the name *SPHERExLabTools* for the optical calibration of
NASA's SPHEREx telescope; see the
[SPHERExLabTools conference proceedings](https://arxiv.org/abs/2208.05099).
