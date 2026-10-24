"""The constructed cases' expected values are the closed forms of validation/closed_forms.py, which does not use
the engine (ADR-0007, ADR-0042). A mistyped number in a case, or a reference that drifted, fails here, apart from the
engine's own run of the case in test_validation_cases.py."""

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

VALIDATION = Path(__file__).parents[1] / "validation"
REFERENCES = VALIDATION / "closed_forms.py"


def closed_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", REFERENCES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", sorted(closed_forms().CASES))
def test_every_expected_value_is_the_closed_form(name):
    case = tomllib.loads((VALIDATION / "cases" / f"{name}.toml").read_text(encoding="utf-8"))
    reference = closed_forms().CASES[name](case)
    expected = {key: value for key, value in case["expected"].items() if key != "tolerance"}
    assert expected, "the case states no expected values"
    for key, value in expected.items():
        rows = value if isinstance(value, dict) else {"": value}  # per-ply results are keyed by ply number
        want = reference[key] if isinstance(value, dict) else {"": reference[key]}
        scale = max(np.max(np.abs(np.atleast_1d(v))) for v in want.values())  # zeros are judged against the group, as compare() does
        for ply, row in rows.items():
            np.testing.assert_allclose(row, want[ply], rtol=1e-9, atol=1e-9 * scale, err_msg=f"{name}: {key} {ply}")


def test_the_references_do_not_use_the_engine():
    script = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('r', sys.argv[1]); m = importlib.util.module_from_spec(s); "
              "s.loader.exec_module(m); print(sorted(n for n in sys.modules if n.startswith('anisotropy')))")
    run = subprocess.run([sys.executable, "-I", "-c", script, str(REFERENCES)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[]"
