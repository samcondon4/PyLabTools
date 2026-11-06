""" Package-level guarantees: a headless core with no import-time side effects. """
import logging
import subprocess
import sys

import pylabtools
from pylabtools import log


def test_version_is_1_0_series():
    assert pylabtools.__version__.startswith("1.0")


def test_import_has_no_side_effects(tmp_path):
    """ Importing pylabtools must not import Qt, create a QApplication, or write files (0.9 did all three). """
    code = (
        "import sys, pylabtools; "
        "bad = [m for m in ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'pyqtgraph') if m in sys.modules]; "
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True)
    assert list(tmp_path.iterdir()) == []


def test_library_logger_only_has_null_handler():
    handlers = log.logger.handlers
    assert any(isinstance(h, logging.NullHandler) for h in handlers)


def test_get_logger_returns_children():
    assert log.get_logger() is log.logger
    assert log.get_logger("pylabtools.recorders").name == "pylabtools.recorders"
    assert log.get_logger("viewers").name == "pylabtools.viewers"


def test_enable_and_disable_file_logging(tmp_path):
    path = tmp_path / "plt.log"
    handlers = log.enable(file=path, stream=False)
    try:
        log.get_logger("test").info("hello")
    finally:
        log.disable(handlers)
    assert "hello" in path.read_text()
    assert not any(h in log.logger.handlers for h in handlers)
