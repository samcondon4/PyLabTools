""" Metadata attached to records, including plab.Metadata limited with records=. """
import pytest
from conftest import ListConsumer
from pymeasure.experiment import FloatParameter
from pymeasure.experiment import Metadata as PyMeasureMetadata

import pylabtools as plab
from pylabtools import HDFRecorder, Status


class FakeVNA:
    def __init__(self):
        self.power = -50.0


class Scoped(plab.Procedure):
    power = FloatParameter("Power", units="dBm", default=-20)

    vna_power = plab.Metadata("VNA power", units="dBm", fget="vna.power", records="s21")
    both = plab.Metadata("Both", fget="read_both", records=["s21", "summary"])
    everywhere = PyMeasureMetadata("Everywhere", fget="read_everywhere")

    def __init__(self, vna, **kwargs):
        super().__init__(**kwargs)
        self.vna = vna

    def read_both(self):
        return "b"

    def read_everywhere(self):
        return 1.5

    @plab.every(0.01)
    def poll(self):
        self.emit("fridge", {"T": 0.01})

    def startup(self):
        self.vna.power = self.power

    def execute(self):
        self.emit("s21", {"x": 1.0})
        self.emit("summary", {"y": 2.0})
        self.sleep(0.05)


def connected(proc, names=("s21", "summary", "fridge")):
    consumers = {name: ListConsumer() for name in names}
    for name, consumer in consumers.items():
        proc.connect(name, consumer)
    return consumers


def test_metadata_is_limited_to_its_records():
    proc = Scoped(FakeVNA())
    cons = connected(proc)
    with plab.running(*cons.values()):
        plab.run(proc, power=-10.0)
    s21, summary, fridge = (dict(cons[n].records[0].meta) for n in ("s21", "summary", "fridge"))
    assert s21 == {"vna_power": -10.0, "both": "b", "everywhere": 1.5}
    assert summary == {"both": "b", "everywhere": 1.5}
    assert fridge == {"everywhere": 1.5}  # - background task records get only unscoped metadata - #
    assert all("vna_power" not in r.meta for r in cons["fridge"].records)


def test_scoped_metadata_in_hdf_tables(tmp_path):
    hdf = HDFRecorder(tmp_path / "scoped.h5")
    proc = Scoped(FakeVNA()).connect("s21", hdf).connect("summary", hdf).connect("fridge", hdf)
    with plab.running(hdf):
        run = plab.run_sequence(proc, plab.sweep(power=[-30.0, -20.0]))
    assert run.status is Status.FINISHED
    s21 = plab.read_hdf(hdf.path, "s21")
    fridge = plab.read_hdf(hdf.path, "fridge")
    assert s21["meta_vna_power"].tolist() == [-30.0, -20.0]  # - read after startup() set it - #
    assert "meta_vna_power" not in fridge.columns and "meta_both" not in fridge.columns
    assert set(fridge["meta_everywhere"]) == {1.5}


@pytest.mark.parametrize("records", ["", [], [""], [1], ["s21", None]])
def test_invalid_records_argument(records):
    with pytest.raises(ValueError, match="records must be"):
        plab.Metadata("Bad", fget="x", records=records)


def test_records_must_be_connected_when_the_run_starts():
    proc = Scoped(FakeVNA())
    cons = connected(proc, names=("summary", "fridge"))  # - "s21" not connected - #
    with plab.running(*cons.values()):
        with pytest.raises(ValueError, match=r"limited to record\(s\) \['s21'\], which are not connected"):
            plab.start(proc)
    assert proc._run is None


def test_plab_metadata_without_records_goes_everywhere():
    class Unscoped(plab.Procedure):
        level = plab.Metadata("Level", fget="read")

        def read(self):
            return 7

        def execute(self):
            self.emit("a", 1)
            self.emit("b", 2)

    proc = Unscoped()
    cons = connected(proc, names=("a", "b"))
    with plab.running(*cons.values()):
        plab.run(proc)
    assert cons["a"].records[0].meta["level"] == cons["b"].records[0].meta["level"] == 7
