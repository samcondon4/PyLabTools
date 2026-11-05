import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

@pytest.mark.parametrize("script, args", [
    ("quickstart.py", ["--samples", "20"]),
    ("sequence.py", ["--samples", "10", "--csv", "csv_out"]),
])
def test_examples_run_headless(tmp_path, script, args):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run([sys.executable, str(EXAMPLES / script), "--no-gui", *args],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert "status=finished" in result.stdout
    assert any(p.suffix == ".h5" for p in tmp_path.iterdir())
