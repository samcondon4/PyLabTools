""" PyLabTools quickstart: one run, recorded to HDF5 and plotted live.

    python examples/quickstart.py            # with the live plot (needs pylabtools[gui])
    python examples/quickstart.py --no-gui   # headless
"""
import argparse

from fake_wave import WaveLog
from pymeasure.instruments.fakes import SwissArmyFake

import pylabtools as plab


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="quickstart.h5", help="output HDF5 file")
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--no-gui", action="store_true", help="do not open the live plot")
    args = parser.parse_args(argv)

    plab.log.enable()  # - print run progress to the terminal - #

    inst = SwissArmyFake(wait=0)
    proc = WaveLog(inst, samples=args.samples)

    hdf = plab.HDFRecorder(args.out)
    view = plab.LineViewer(x="t", y="V", max_rows=500, title="Fake wave")
    proc.connect("wave", hdf, view)

    with hdf, view:
        run = plab.start(proc, amplitude=2.5)
        if not args.no_gui:
            plab.gui.show(view, run=run, block=True)  # - returns when the window is closed - #
        plab.wait(run)  # - Ctrl-C stops the run cleanly - #

    print(run)
    df = plab.read_hdf(args.out, "wave", groups=-1)  # - -1: the most recent run in the file - #
    print(df.head())
    return run


if __name__ == "__main__":
    main()
