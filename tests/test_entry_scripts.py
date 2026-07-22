"""Every VM entry script must import in a bare interpreter.

Regression for the 2026-07-22 outage: pytest's root conftest put the repo
root on sys.path, so `from scoring.eligibility import ...` passed tests but
crashed on the VM, killing the 23:45 scoring run. runpy executes each
script's own sys.path bootstrapping without running main() (the __main__
guard stays false under run_path's default run_name).
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ["issue_forecasts.py", "score_forecasts.py", "write_latest.py",
           "download_archive.py"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_imports_in_bare_interpreter(script):
    code = f"import runpy; runpy.run_path(r'{ROOT / 'scripts' / script}')"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT / "scripts",
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
