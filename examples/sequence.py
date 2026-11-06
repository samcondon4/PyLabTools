""" PyLabTools sequence example: sweep a parameter, store the whole sweep as one RecordGroup.

    python examples/sequence.py            # with the live plot (needs pylabtools[gui])
    python examples/sequence.py --no-gui   # headless
"""
import argparse

from fake_wave import WaveLog
from pymeasure.instruments.fakes import SwissArmyFake

import pylabtools as plab


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="sequence.h5", help="output HDF5 file")
    parser.add_argument("--csv", default=None, help="optional directory for CSV output as well")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--no-gui", action="store_true", help="do not open the live plot")
    args = parser.parse_args(argv)

    plab.log.enable()

    proc = WaveLog(SwissArmyFake(wait=0))
    recorders = [plab.HDFRecorder(args.out)]
    if args.csv:
        recorders.append(plab.CSVRecorder(args.csv))
    view = plab.LineViewer(y="V", max_rows=4 * args.samples, title="Amplitude sweep")
    proc.connect("wave", *recorders, view)

    # - 4 steps; every value is validated before the first step starts - #
    steps = plab.sweep(amplitude=[0.5, 1.0, 2.0, 4.0])

    with plab.running(view, *recorders):
        run = plab.start_sequence(proc, steps, samples=args.samples, interval=0.01)
        if not args.no_gui:
            plab.gui.show(view, run=run, block=True)
        plab.wait(run)

    print(run)
    df = plab.read_hdf(args.out, "wave", groups=-1)  # - the whole sweep is the latest RecordGroup - #
    print(df.groupby("proc_amplitude")["V"].agg(["count", "min", "max"]))
    return run


if __name__ == "__main__":
    main()
