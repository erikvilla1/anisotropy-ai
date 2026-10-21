"""The CalculiX runner and .dat parser, and the composite-shell conventions re-detected whenever the solver is present (ADR-0030)."""

import os
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.response import ply_surfaces
from anisotropy_engine.rotation import stress_transformation
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.model import section_plies
from anisotropy_fea.calculix import ENV_VARIABLE, CalculixError, find_ccx, parse_dat, run_calculix
from anisotropy_fea.compare import layer_values, load_conventions
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.recovery import element_ply_states
from anisotropy_fea.spec import parse_spec, to_si
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_calculix import write_calculix
from anisotropy_fea import paths  # where the files live (ADR-0036)

FIXTURES = Path(__file__).parent / "fixtures"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason=f"CalculiX not found: set {ENV_VARIABLE} or put ccx on PATH (docs/installation-fea-tools.md)")


def test_find_ccx_precedence(tmp_path, monkeypatch):
    fake = tmp_path / "ccx.exe"
    fake.write_bytes(b"")
    assert find_ccx(fake) == fake
    monkeypatch.setenv(ENV_VARIABLE, str(fake))
    assert find_ccx() == fake
    monkeypatch.setenv(ENV_VARIABLE, str(tmp_path / "missing.exe"))
    with pytest.raises(CalculixError, match="not found"):
        find_ccx()
    monkeypatch.delenv(ENV_VARIABLE)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert find_ccx() is None


def test_parse_dat_reads_every_block_of_a_real_run():
    dat = parse_dat((FIXTURES / "small-coupon-ccx.dat.txt").read_text(encoding="utf-8"))
    kinds = sorted({(b.quantity, b.set_name) for b in dat.blocks})
    assert ("total force", "GRIP-TOP") in kinds and ("displacements", "PROBE-CENTRE") in kinds and ("global coordinates", "PROBE-CENTRE") in kinds
    forces = dat.forces("Grip-Top")
    assert forces.components == ("fx", "fy", "fz") and forces.ids.shape[1] == 1 and forces.values.shape[1] == 3
    total = dat.total_force("Grip-Top")
    assert total.shape == (3,) and total[1] > 0
    scale = float(np.max(np.abs(total)))
    assert np.allclose(forces.values.sum(axis=0), total, rtol=1e-5, atol=1e-5 * scale)  # the .dat prints seven significant digits
    assert np.allclose(dat.total_force("Grip-Bottom"), -total, rtol=1e-5, atol=1e-5 * scale)
    stresses = dat.stresses("Probe-centre")
    assert stresses.components[:2] == ("elem", "integ.pnt.") and stresses.ids.shape == (64, 2) and stresses.values.shape == (64, 6)
    assert stresses.ids[:, 1].tolist() == list(range(1, 65))
    assert stresses.row(int(stresses.ids[0, 0]), 1).shape == (6,)
    with pytest.raises(KeyError, match="no 'strains' block for set 'Nowhere'"):
        dat.strains("Nowhere")


def test_parse_dat_refuses_malformed_rows():
    text = " displacements (vx,vy,vz) for set N and time  0.1000000E+01\n\n         1  1.0  x  2.0\n"
    with pytest.raises(CalculixError, match="cannot read"):
        parse_dat(text)
    tagged = parse_dat(" displacements (vx,vy,vz) for set N and time  0.1000000E+01\n\n         1  1.0  2.0  3.0 _shell_0000000001\n")
    assert tagged.blocks[0].tags == ("_shell_0000000001",) and tagged.blocks[0].values.tolist() == [[1.0, 2.0, 3.0]]
    with pytest.raises(CalculixError, match="no printed block"):
        parse_dat("nothing here\n")


def test_conventions_file_is_complete_and_what_the_mapper_implements():
    conventions = load_conventions(paths.CONVENTIONS)
    assert conventions["layer_order"] == "first-line-bottom" and conventions["shear_strain"] == "tensor"
    assert conventions["points_per_layer_thickness"] == 2 and conventions["in_plane_points"] == 4
    assert conventions["calculix_version"].startswith("2.")


def test_layer_values_groups_points_by_z():
    z = np.repeat(np.array([-0.3, -0.1, 0.1, 0.3]), 4)  # two plies, two levels each, four in-plane points per level
    values = np.arange(16, dtype=float).reshape(16, 1)
    bottom, top = layer_values(values, z, plies=2, points_per_layer=2)
    assert bottom[0] == pytest.approx(np.mean(range(8))) and top[0] == pytest.approx(np.mean(range(8, 16)))
    with pytest.raises(Exception, match="z levels"):
        layer_values(values, z, plies=3, points_per_layer=2)


@needs_ccx
def test_calculix_runs_the_small_coupon_in_equilibrium_and_the_conventions_hold(tmp_path):
    """The detection run, repeated: layer order, points per layer, per-ply orientation, shear convention, against the engine."""
    text = (FIXTURES / "small-coupon-spec.toml").read_text(encoding="utf-8")
    spec = to_si(parse_spec(text, source_path="small-coupon-spec.toml"))
    model = build_model(spec)
    deck = tmp_path / "small.inp"
    deck.write_text(write_calculix(model, el_print_coord=True), encoding="utf-8")
    result = run_calculix(deck, workdir=tmp_path)
    assert result.errors == () and result.returncode == 0 and result.frd_path is not None
    dat = parse_dat(result.dat_text)
    top, bottom = dat.total_force("Grip-Top"), dat.total_force("Grip-Bottom")
    assert top[1] > 0 and np.allclose(top[:2], -bottom[:2], rtol=1e-6, atol=1e-6 * abs(top[1]))
    # the kernel's order-1 twin on the same corner nodes
    twin = build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 1})}), model.mesh.corner_mesh())
    kernel_deck = tmp_path / "twin.inp"
    kernel_deck.write_text(write_abaqus(twin), encoding="utf-8")
    solution = solve_membrane(read_deck(kernel_deck, spec.units))
    ours = solution.reaction_of(read_deck(kernel_deck, spec.units).nsets["Grip-Top"])
    assert top[1] == pytest.approx(ours[1], rel=0.02)
    e = twin.probe_elements["centre"]
    S, E, C = dat.stresses("Probe-centre"), dat.strains("Probe-centre"), dat.coordinates("Probe-centre")
    z = C.values[:, 2]
    plies = model.section.plies
    assert np.unique(np.round(z, 9)).size == 2 * len(plies)  # two integration levels per layer
    assert S.ids[:4, 1].tolist() == [1, 2, 3, 4] and np.allclose(z[:4], z[0])  # points numbered by level, four per level
    # Layer mapping and orientation, isolated from the element difference: push CalculiX's own mean strain through the engine's
    # plies and compare ply by ply with what CalculiX printed at the z levels of each layer.
    mean = E.values[:, [0, 1, 3]].mean(axis=0)
    eps_ccx = np.array([mean[0], mean[1], 2.0 * mean[2]])  # tensor shear to engineering shear
    engine_plies = ply_surfaces(section_plies(read_deck(kernel_deck, spec.units).parts["Coupon"].sections[0], read_deck(kernel_deck, spec.units).materials), eps_ccx, np.zeros(3))[0::2]
    layers = layer_values(S.values[:, [0, 1, 3]], z, len(plies), 2)
    scale = max(np.max(np.abs(p.stress_xy)) for p in engine_plies) / 1e6
    for k, ply in enumerate(plies):
        engine = engine_plies[k].stress_xy / 1e6
        assert layers[k] == pytest.approx(engine, abs=0.03 * scale), f"ply {k + 1} ({ply.angle_deg} deg): first line is the bottom ply and orientations are honoured"
        assert stress_transformation(ply.angle_deg) @ layers[k] == pytest.approx(engine_plies[k].stress_12 / 1e6, abs=0.03 * scale)
    # the coarse 2 by 8 mesh with 20 mm tabs: the element types agree on the axial strain within a few percent; the transverse
    # strain, a Poisson effect constrained by the nearby rigid tabs, differs more (12 % seen) and is not a conventions matter
    field = element_ply_states(solution)
    assert mean[1] == pytest.approx(solution.strain[e][1], rel=0.05) and mean[0] == pytest.approx(solution.strain[e][0], rel=0.2)
    assert field.stress_xy[e].shape == (len(plies), 3)


@needs_ccx
def test_calculix_prints_tensor_shear_strain(tmp_path):
    """One isotropic S8R shell given the exact field u = 0.01 y: engineering shear 0.01, printed exy must be 0.005."""
    deck = tmp_path / "shear.inp"
    deck.write_text(
        "*HEADING\nshear convention\n*NODE\n1, 0., 0., 0.\n2, 10., 0., 0.\n3, 10., 10., 0.\n4, 0., 10., 0.\n5, 5., 0., 0.\n6, 10., 5., 0.\n7, 5., 10., 0.\n8, 0., 5., 0.\n"
        "*ELEMENT, TYPE=S8R, ELSET=EALL\n1, 1, 2, 3, 4, 5, 6, 7, 8\n*NSET, NSET=NALL\n1, 2, 3, 4, 5, 6, 7, 8\n*NSET, NSET=BOTTOM\n1, 2, 5\n*NSET, NSET=MID\n6, 8\n"
        "*NSET, NSET=TOP\n3, 4, 7\n*MATERIAL, NAME=ALU\n*ELASTIC\n70000., 0.33\n*SHELL SECTION, ELSET=EALL, MATERIAL=ALU\n2.\n*BOUNDARY\nNALL, 2, 6\nBOTTOM, 1, 1\n"
        "*STEP\n*STATIC\n*BOUNDARY\nMID, 1, 1, 0.05\nTOP, 1, 1, 0.1\n*NODE PRINT, NSET=TOP, TOTALS=YES\nRF\n*EL PRINT, ELSET=EALL, GLOBAL=YES\nS, E\n*END STEP\n",
        encoding="utf-8")
    dat = parse_dat(run_calculix(deck, workdir=tmp_path).dat_text)
    G = 70000.0 / (2 * 1.33)
    assert dat.total_force("TOP")[0] == pytest.approx(G * 0.01 * 2 * 10, rel=1e-6)
    strains = dat.strains("EALL").values
    assert strains[:, 3] == pytest.approx(np.full(len(strains), 0.005), abs=1e-9)  # tensor: half the engineering shear
    assert dat.stresses("EALL").values[:, 3] == pytest.approx(np.full(len(strains), G * 0.01), rel=1e-6)


def test_the_environment_variable_is_documented():
    assert ENV_VARIABLE == "ANISOTROPY_CCX" and "ANISOTROPY_CCX" in (Path(__file__).parents[2] / "docs" / "installation-fea-tools.md").read_text(encoding="utf-8")
    assert os.environ.get(ENV_VARIABLE) is None or find_ccx() is not None


def synthetic_fabric_spec(transverse: str):
    """The small fixture coupon with a [0/45]s layup of a made-up fabric-like material (E1 = E2, nu12 far below nu23): the layup whose
    plies want different thickness contractions. The constants are test inputs, not a material; no source."""
    base = (FIXTURES / "small-coupon-spec.toml").read_text(encoding="utf-8").replace("\r\n", "\n")
    head, rest = base.split("[material]")
    _, tail = rest.split("[grips]")
    head = head.replace("angles = [45, 0, -45, 90]", "angles = [0, 45]").replace('ply_thickness = "library"', "ply_thickness = 0.125")
    tail = tail.replace('fpf_criteria = ["max_stress", "tsai_hill", "tsai_wu"]', "fpf_criteria = []")
    material = "[material]\nE1 = 50000.0\nE2 = 50000.0\nG12 = 5000.0\nnu12 = 0.05\n[material.transverse]\nG13 = 4000.0\nG23 = 4000.0\ntransverse_isotropy = true\n"
    return to_si(parse_spec(head + material + transverse + "\n[grips]" + tail))


@needs_ccx
@pytest.mark.parametrize("transverse, coupled", [("plane_stress = false\nnu23 = 0.4\n", True), ("plane_stress = true\n", False)], ids=["nu23-given", "plane-stress"])
def test_plane_stress_removes_the_through_thickness_coupling_of_calculix_composite_shells(tmp_path, transverse, coupled):
    """CalculiX expands the composite S8R into one brick: with nonzero nu13, nu23 the plies' different thickness contractions are locked
    together and a through-thickness stress appears (12 % of the axial stress seen); with plane_stress = true it vanishes (ADR-0030, amendment 1)."""
    spec = synthetic_fabric_spec(transverse)
    model = build_model(spec)
    deck = tmp_path / "fabric.inp"
    deck.write_text(write_calculix(model, el_print_coord=True), encoding="utf-8")
    dat = parse_dat(run_calculix(deck, workdir=tmp_path).dat_text)
    S = dat.stresses("Probe-centre").values
    szz_ratio = np.abs(S[:, 2]).max() / np.abs(S[:, 1]).max()
    twin = build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 1})}), model.mesh.corner_mesh())
    kernel_deck = tmp_path / "twin.inp"
    kernel_deck.write_text(write_abaqus(twin), encoding="utf-8")
    read = read_deck(kernel_deck, spec.units)
    ours = solve_membrane(read).reaction_of(read.nsets["Grip-Top"])[1]
    top = dat.total_force("Grip-Top")[1]
    if coupled:
        assert szz_ratio > 0.05, "the coupled run must show the through-thickness stress this test exists for"
    else:
        assert szz_ratio < 0.005
        assert top == pytest.approx(ours, rel=0.02)  # 4686 against 4724 N on the coarse 2 by 8 mesh: S8R against Q4
