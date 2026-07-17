"""Smoke test: every example script under examples/ runs to completion.

The example scripts are the primary demo surface, but they live outside the
``tests/test-cases`` fixtures that ``test_examples.py`` drives, so nothing else
guards them against engine/grammar drift. This runs each one as a subprocess and
asserts a clean exit, catching import errors, parse failures, and evaluation
regressions.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"

EXAMPLE_SCRIPTS = sorted(EXAMPLES_DIR.glob("*.py"))


def test_example_scripts_discovered():
    """Guard the guard: fail loudly if the glob stops finding scripts."""
    assert EXAMPLE_SCRIPTS, f"no example scripts found under {EXAMPLES_DIR}"


@pytest.mark.parametrize("script", EXAMPLE_SCRIPTS, ids=lambda p: p.name)
def test_example_script_runs(script: Path):
    # PYTHONPATH=src lets the scripts' ``from srl ...`` imports resolve without
    # a separate install step, mirroring pytest's own ``pythonpath = ["src"]``.
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"{script.name} exited with {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
