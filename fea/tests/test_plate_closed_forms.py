"""The plate closed forms of tools/plate_closed_forms.py are what they claim, and the committed plate cases carry their numbers (ADR-0053)."""

import importlib.util
import math
import tomllib

import numpy as np
import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)

TOOL = paths.FEA / "tools" / "plate_closed_forms.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("plate_closed_forms", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_kirchhoff_series_gives_the_tabulated_square_plate_coefficient(tool):
    """Timoshenko and Woinowsky-Krieger tabulate w_max = 0.00406 q a^4 / D for a simply supported square plate under uniform load, nu = 0.3."""
    D, _ = tool.isotropic_section(70000.0, 0.3, 1.0)
    w = tool.navier_fields(D, None, 100.0, 100.0, ("uniform", 0.01), 50.0, 50.0)["w"]
    assert w * D[0, 0] / (0.01 * 100.0**4) == pytest.approx(0.00406, abs=0.5e-5)


def test_the_shear_deformation_series_reduces_to_kirchhoff_for_a_rigid_shear_stiffness(tool):
    D, H = tool.isotropic_section(70000.0, 0.3, 1.0)
    thin = tool.navier_fields(D, None, 100.0, 80.0, ("sinusoidal", 0.01), 30.0, 20.0)
    rigid = tool.navier_fields(D, H * 1e4, 100.0, 80.0, ("sinusoidal", 0.01), 30.0, 20.0)  # a larger factor only adds cancellation error in the solve
    for key in ("w", "theta_x", "theta_y", "Mx", "My", "Mxy"):
        assert rigid[key] == pytest.approx(thin[key], rel=1e-6)
    with_shear = tool.navier_fields(D, H, 100.0, 80.0, ("sinusoidal", 0.01), 50.0, 40.0)
    assert with_shear["w"] > thin["w"]  # shear deformation adds to the deflection
    assert with_shear["w"] / tool.navier_fields(D, None, 100.0, 80.0, ("sinusoidal", 0.01), 50.0, 40.0)["w"] == pytest.approx(1.0, abs=1e-3)  # h/a = 1/100


def test_the_sinusoidal_term_satisfies_the_plate_equation(tool):
    """One term of the Kirchhoff series: D11 w,xxxx + 2 (D12 + 2 D66) w,xxyy + D22 w,yyyy = q (Whitney 5.1)."""
    D, _, _ = tool.laminate_section([0.0, 90.0, 90.0, 0.0], 0.18288, tool.IM7)
    a, b, q0 = 100.0, 60.0, 0.01
    alpha, beta = math.pi / a, math.pi / b
    W = tool.navier_fields(D, None, a, b, ("sinusoidal", q0), a / 2.0, b / 2.0)["w"]
    assert W * (D[0, 0] * alpha**4 + 2.0 * (D[0, 1] + 2.0 * D[2, 2]) * alpha**2 * beta**2 + D[1, 1] * beta**4) == pytest.approx(q0, rel=1e-12)


def test_the_laminate_stiffness_by_hand_equals_the_engine(tool):
    from anisotropy_engine.laminate import Ply, abd_matrices
    from anisotropy_engine.lamina import Lamina

    D, H, plies = tool.laminate_section([0.0, 45.0, -45.0, 90.0], 0.18288, tool.IM7)
    m = tool.IM7
    lamina = Lamina(E1=m["E1"] * 1e6, E2=m["E2"] * 1e6, G12=m["G12"] * 1e6, nu12=m["nu12"])
    _, _, D_engine = abd_matrices([Ply(material=lamina, angle_deg=angle, thickness_m=0.18288e-3) for angle in (0.0, 45.0, -45.0, 90.0)])
    assert D == pytest.approx(D_engine * 1e3, rel=1e-12)  # N m to N mm
    assert H[0, 1] == pytest.approx(0.0, abs=1e-9)  # the +45 and -45 plies cancel the coupling term
    assert H[0, 0] == pytest.approx(5.0 / 6.0 * 0.18288 * 2.0 * (m["G13"] + m["G23"]))  # 0: G13; 90: G23; each 45: (G13 + G23) / 2


def test_the_timoshenko_strip_has_the_bending_and_shear_parts(tool):
    E, h, b, L, P = 70000.0, 2.0, 10.0, 100.0, 10.0
    tip = tool.timoshenko_strip(E, h, b, L, P, L)
    EI = E * b * h**3 / 12.0
    assert tip["w"] == pytest.approx(P * L**3 / (3.0 * EI) + P * L / (5.0 / 6.0 * E / 2.0 * b * h))
    assert tip["theta_y"] == pytest.approx(-P * L**2 / (2.0 * EI))
    assert tool.timoshenko_strip(E, h, b, L, P, 0.0)["Mx"] == pytest.approx(-P * L / b)
    assert tool.timoshenko_strip(E, h, b, L, P, 0.0)["w"] == 0.0


def test_the_committed_cases_and_decks_are_what_the_tool_writes_today(tool):
    for name, (deck_file, text, source, fields) in tool.build_cases().items():
        case_path = paths.CASES / f"{name}.toml"
        assert case_path.is_file(), f"{name}: run tools/plate_closed_forms.py --write"
        assert (paths.CHECK_DECKS / deck_file).read_text(encoding="utf-8") == text, f"{deck_file} differs from what the tool writes"
        written = tomllib.loads(case_path.read_text(encoding="utf-8"))
        assert written["source"] == source and written["title"] == fields["title"]
        expected = tool.snapped(fields["expected"])
        for group, rows in expected.items():
            if group == "tolerance":
                assert written["expected"]["tolerance"] == rows
                continue
            for label, value in rows.items():
                if group == "ply_stress_local":
                    for ply, vector in value.items():
                        np.testing.assert_allclose(written["expected"][group][label][ply], vector, rtol=1e-12, atol=0.0, err_msg=f"{name}: {group} {label} {ply}")
                else:
                    np.testing.assert_allclose(written["expected"][group][label], value, rtol=1e-12, atol=0.0, err_msg=f"{name}: {group} {label}")
