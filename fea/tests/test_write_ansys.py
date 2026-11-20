"""The Ansys Mechanical APDL file of a model (ADR-0129): read back by the small reader below and compared with the model it was written
from, the conventions checked by hand-made cases, and the mesh blocks read by an independent open-source reader when it is installed.
Nothing here runs Ansys: that check is the founder's, on his own computer (ADR-0129, "How we will know it was wrong")."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.femodel import BoundaryDefinition, FEModel, build_model
from anisotropy_fea.spec import load_spec, parse_spec, to_si
from anisotropy_fea.write_ansys import EFFECTIVE_ZERO, NOT_CHECKED, AnsysWriterError, component_name, write_ansys

NODAL = paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8")
COUPLING = paths.spec_path("unnotched-im7-8552-coupling").read_text(encoding="utf-8")
PRESSURE = (paths.CHECKS / "plate-pressure-isotropic" / "plate-pressure-isotropic.toml").read_text(encoding="utf-8")
FORCE = ('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0')
DOF = {"UX": 1, "UY": 2, "UZ": 3, "ROTX": 4, "ROTY": 5, "ROTZ": 6}
FORCE_DOF = {"FX": 1, "FY": 2, "FZ": 3, "MX": 4, "MY": 5, "MZ": 6}


def model_of(text: str, order: int | None = None) -> FEModel:
    spec = to_si(parse_spec(text))
    if order is not None:
        spec = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": order})})
    return build_model(spec)


def read_back(text: str) -> dict:
    """The file as plain data, in the file's own units: every command this reader does not know is an error, so nothing is written unread."""
    lines = text.splitlines()
    data: dict = {"comments": [], "nodes": {}, "elements": {}, "components": {}, "mp": {}, "tbdata": {}, "layers": [], "d": [], "f": [], "sfe": [],
                  "cp": [], "keyopt": {}, "commands": [], "selected": None}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("!"):
            data["comments"].append(line)
            continue
        assert "!" not in line, f"a comment follows a command: {line}"
        head, *rest = line.split(",")
        if head == "NBLOCK":
            assert lines[i] == "(3i9,6e21.13e3)"
            i += 1
            while not lines[i].startswith("N,R5.3,LOC"):
                row = lines[i]
                assert len(row) == 27 + 63
                data["nodes"][int(row[:9])] = tuple(float(row[27 + 21 * k:48 + 21 * k]) for k in range(3))
                assert int(row[9:18]) == 0 and int(row[18:27]) == 0
                i += 1
            i += 1
            assert int(rest[2]) == int(rest[3]) == len(data["nodes"])
        elif head == "EBLOCK":
            assert lines[i] == "(19i10)"
            i += 1
            while lines[i] != "-1":
                fields = [int(lines[i][k:k + 10]) for k in range(0, len(lines[i]), 10)]
                assert len(fields) == 11 + fields[8]
                data["elements"][fields[10]] = {"mat": fields[0], "type": fields[1], "real": fields[2], "section": fields[3], "esys": fields[4],
                                               "rest": fields[5:8] + [fields[9]], "nodes": fields[11:]}
                i += 1
            i += 1
            assert int(rest[2]) == int(rest[3]) == len(data["elements"])
        elif head == "CMBLOCK":
            assert lines[i] == "(8i10)"
            i += 1
            count, members = int(rest[2]), []
            while len(members) < count:
                assert len(lines[i]) <= 80
                members += [int(lines[i][k:k + 10]) for k in range(0, len(lines[i]), 10)]
                i += 1
            assert len(members) == count and rest[0] not in data["components"]
            data["components"][rest[0]] = (rest[1], members)
        elif head == "MP":
            assert rest[1] == "1"
            data["mp"][rest[0]] = float(rest[2])
        elif head == "TBDATA":
            for k, value in enumerate(rest[1:]):
                data["tbdata"][int(rest[0]) + k] = float(value)
        elif head == "SECDATA":
            data["layers"].append((float(rest[0]), int(rest[1]), float(rest[2]), int(rest[3])))
        elif head == "D":
            data["d"].append((rest[0], DOF[rest[1]], float(rest[2])))
        elif head == "F":
            data["f"].append((rest[0], FORCE_DOF[rest[1]], float(rest[2])))
        elif head == "SFE":
            assert rest[2] == "PRES" and rest[3] == ""
            data["sfe"].append((rest[0], int(rest[1]), float(rest[4])))
        elif head == "CMSEL":
            assert rest[0] == "S"
            data["selected"] = rest[1]
        elif head == "CP":
            assert rest == ["NEXT", rest[1], "ALL"] and data["selected"] is not None
            data["cp"].append((data["selected"], DOF[rest[1]]))
        elif head == "ALLSEL":
            data["selected"] = None
        elif head == "KEYOPT":
            assert rest[0] == "1"
            data["keyopt"][int(rest[1])] = int(rest[2])
        elif head in ("/PREP7", "/TITLE", "/UNITS", "ET", "LOCAL", "CSYS", "TB", "SECTYPE", "SECOFFSET", "FINISH", "/SOLU", "ANTYPE", "NLGEOM", "OUTRES",
                      "SOLVE", "/POST1", "SET", "FCTYP", "PRRSOL", "PRNSOL"):
            data["commands"].append(line)
        else:
            raise AssertionError(f"a command the reader does not know: {line}")
    return data


def test_the_file_reads_back_as_the_model_it_was_written_from():
    model = model_of(NODAL)
    text = write_ansys(model)
    assert text == write_ansys(model) and text.isascii() and max(len(line) for line in text.splitlines()) <= 240  # the same text each time
    back = read_back(text)
    mesh = model.mesh
    assert sorted(back["nodes"]) == list(range(1, mesh.node_count + 1))
    assert np.array([back["nodes"][n] for n in sorted(back["nodes"])]) == pytest.approx(np.column_stack([mesh.xy * 1e3, np.zeros(mesh.node_count)]), rel=1e-12, abs=1e-12)
    assert [back["elements"][e]["nodes"] for e in sorted(back["elements"])] == (mesh.connectivity() + 1).tolist()
    assert all(e == {"mat": 1, "type": 1, "real": 1, "section": 1, "esys": 11, "rest": [0, 0, 0, 0], "nodes": e["nodes"]} for e in back["elements"].values())
    expected = {component_name("N", name): ("NODE", (members + 1).tolist()) for name, members in model.node_sets.items()}
    expected |= {component_name("E", name): ("ELEM", (members + 1).tolist()) for name, members in model.element_sets.items()}
    assert back["components"] == expected and "N_GRIP_TOP" in expected and "E_GAUGE" in expected and "N_PROBE_CENTRE" in expected
    m = model.material
    assert back["mp"] == pytest.approx({"EX": m.E1 / 1e6, "EY": m.E2 / 1e6, "EZ": m.E3 / 1e6, "PRXY": m.nu12, "PRYZ": m.nu23, "PRXZ": m.nu13, "GXY": m.G12 / 1e6,
                                        "GYZ": m.G23 / 1e6, "GXZ": m.G13 / 1e6}, rel=1e-9)
    assert back["layers"] == [(pytest.approx(ply.thickness_m * 1e3, rel=1e-9), 1, ply.angle_deg, 3) for ply in model.section.plies]
    assert [layer[2] for layer in back["layers"]] == [45, 0, -45, 90, 90, -45, 0, 45]  # the whole stack, bottom first, not the listed half
    assert back["keyopt"] == {1: 0, 3: 0, 8: 2}
    for line in ("/PREP7", "/UNITS,MPA", "ET,1,181", "LOCAL,11,0,0.,0.,0.,90.", "CSYS,0", "TB,FCLI,1,1,20,1", "SECTYPE,1,SHELL", "SECOFFSET,MID", "/SOLU",
                 "ANTYPE,STATIC", "NLGEOM,OFF", "SOLVE", "/POST1", "SET,LAST", "PRRSOL", "PRNSOL,U,COMP"):
        assert line in back["commands"], line
    assert text.index("/PREP7") < text.index("NBLOCK") < text.index("N,R5.3,LOC") < text.index("LOCAL,11")  # the nodes are read in the global system
    assert text.index("LOCAL,11") < text.index("EBLOCK") < text.index("SECTYPE") < text.index("\nD,") < text.index("/SOLU") < text.index("/POST1")


def test_supports_and_the_pull_are_stated_on_the_grip_components():
    model = model_of(NODAL)
    back = read_back(write_ansys(model))
    stated = [(component_name("N", b.target), dof, b.value * 1e3 if dof <= 3 else b.value) for b in model.boundaries for dof in range(b.dof_first, b.dof_last + 1)]
    assert back["d"] == stated and ("N_GRIP_TOP", 2, 1.0) in back["d"] and len(back["d"]) == 12
    assert not back["f"] and not back["cp"] and not back["sfe"]


def test_strength_limits_are_negative_in_compression_and_leave_the_thickness_unchecked():
    model = model_of(NODAL)
    s, back = model.material.strengths, read_back(write_ansys(model))
    far = NOT_CHECKED * s.F1t / 1e6
    assert [back["tbdata"][k] for k in range(1, 10)] == pytest.approx([s.F1t / 1e6, -s.F1c / 1e6, s.F2t / 1e6, -s.F2c / 1e6, far, -far, s.F6 / 1e6, far, far], rel=1e-9)
    assert model.material.f12_star == 0.0 and back["tbdata"][10] == EFFECTIVE_ZERO  # a zero would mean Ansys's default of -1
    half = read_back(write_ansys(dataclasses.replace(model, material=dataclasses.replace(model.material, f12_star=-0.5))))
    assert half["tbdata"][10] == -1.0  # XYCP = 2 f12*: our -0.5 is Ansys's default
    unstated = write_ansys(dataclasses.replace(model, material=dataclasses.replace(model.material, f12_star=None)))
    assert 10 not in read_back(unstated)["tbdata"] and "states no Tsai-Wu interaction term" in unstated
    plain = write_ansys(dataclasses.replace(model, material=dataclasses.replace(model.material, strengths=None, f12_star=None)))
    assert "TB,FCLI" not in plain and "TBDATA" not in plain and "FCTYP" not in plain
    # Mechanical APDL 2026 R1 lists no failure measure while the maximum strain criterion is asked for and no strain limit is stated
    text = write_ansys(model)
    assert text.index("SET,LAST") < text.index("FCTYP,DELE,ALL\nFCTYP,ADD,SMAX\n") < text.index("PRRSOL")


def test_a_layer_angle_is_counted_from_the_length_axis_in_the_element_system():
    """The hand-made convention check. System 11 is the global one turned 90 degrees about z, so its x is global y. A layer's fibre then
    lies at 90 + angle from global x, which must be the engine's fibre direction for the same ply (ADR-0065), and every element is counted
    counter-clockwise, so its normal is +z and the first layer is the bottom one."""
    text = NODAL.replace("angles = [45, 0, -45, 90]", "angles = [30, 90, 0, -60]")
    assert text != NODAL
    model = model_of(text)
    back = read_back(write_ansys(model))
    assert [layer[2] for layer in back["layers"]] == [30, 90, 0, -60, -60, 0, 90, 30]
    x_axis = (math.cos(math.radians(90.0)), math.sin(math.radians(90.0)))  # LOCAL,11,0,0,0,0,90: the first angle turns x toward y about z
    assert x_axis == pytest.approx((0.0, 1.0))
    for (_, _, angle, _), ply in zip(back["layers"], model.section.plies):
        ours = math.radians(ply.fibre_deg)
        theirs = math.radians(90.0 + angle)
        assert abs(math.cos(ours) * math.cos(theirs) + math.sin(ours) * math.sin(theirs)) == pytest.approx(1.0)  # the same line
    first = back["layers"][0]
    assert first[2] == 30 and model.section.plies[0].fibre_deg == -60  # +30 from the length axis leans toward global -x: 120 degrees from x
    xy = np.array([back["nodes"][n][:2] for n in sorted(back["nodes"])])
    for element in back["elements"].values():
        p = xy[np.array(element["nodes"][:4]) - 1]
        assert sum(p[k, 0] * p[(k + 1) % 4, 1] - p[(k + 1) % 4, 0] * p[k, 1] for k in range(4)) > 0.0


def test_an_eight_node_mesh_is_shell281_and_a_full_integration_request_sets_keyopt_3():
    model = model_of(NODAL, order=2)
    text = write_ansys(model)
    back = read_back(text)
    assert "ET,1,281" in text and back["keyopt"] == {1: 0, 8: 2}
    assert all(len(e["nodes"]) == 8 for e in back["elements"].values())
    assert [back["elements"][e]["nodes"] for e in sorted(back["elements"])] == (model.mesh.connectivity() + 1).tolist()  # corners, then midsides, as S8R
    s4 = model_of(NODAL.replace("abaqus = { ", 'abaqus = { element = "S4", ', 1))
    assert s4.spec.output.abaqus.element == "S4" and read_back(write_ansys(s4))["keyopt"][3] == 2


def test_coupled_grips_become_supports_on_the_grip_nodes_and_a_coupled_set_under_a_force():
    moved = model_of(COUPLING)
    assert moved.couplings and moved.reference_points
    back = read_back(write_ansys(moved))
    assert len(back["nodes"]) == moved.mesh.node_count  # no reference node: Ansys has one numbering, and the grip's nodes stand in for it
    assert {(name, dof) for name, dof, value in back["d"] if value == 0.0} == ({("N_GRIP_BOTTOM", dof) for dof in range(1, 7)}
                                                                              | {("N_GRIP_TOP", dof) for dof in (1, 3, 4, 5, 6)})
    assert ("N_GRIP_TOP", 2, 1.0) in back["d"] and not back["cp"] and not back["f"]
    assert "CMSEL,S,N_GRIP_TOP\nPRRSOL" in write_ansys(moved)  # the reaction is listed at the grip, not at a reference point
    forced = model_of(COUPLING.replace(*FORCE))
    assert forced.loads[0].target == "RF-Top"
    back = read_back(write_ansys(forced))
    assert back["cp"] == [("N_GRIP_TOP", 2)] and ("N_GRIP_TOP", 2) not in {(name, dof) for name, dof, _ in back["d"]}
    first = int(forced.node_sets["Grip-Top"].min()) + 1
    assert back["f"] == [(str(first), 2, 5000.0)]  # on the first node of the coupled set, which carries it for the whole grip
    rigid = model_of(NODAL.replace(*FORCE).replace("[loading]", "[loading]\nrigid_grip = true"))
    assert read_back(write_ansys(rigid))["cp"] == [("N_GRIP_TOP", 2)]


def test_a_force_on_nodal_grips_is_one_force_per_node_and_sums_to_the_total():
    model = model_of(NODAL.replace(*FORCE).replace('region = "tabs"', 'region = "line"'))
    back = read_back(write_ansys(model))
    assert len(back["f"]) == 11 and all(dof == 2 for _, dof, _ in back["f"]) and sum(value for _, _, value in back["f"]) == pytest.approx(5000.0)
    assert [name for name, _, _ in back["f"]] == [load.target.rsplit(".", 1)[-1] for load in model.loads] and not back["cp"]


def test_a_pressure_is_written_on_the_top_face_with_the_coupons_own_sign():
    model = model_of(PRESSURE)
    assert model.pressures[0].value == pytest.approx(-0.01e6)  # the spec's -0.01 MPa: negative, so toward +z
    text = write_ansys(model)
    back = read_back(text)
    assert back["sfe"] == [("E_FACE", 2, -0.01)]  # face 2 is the top; positive presses on it, against the normal: no change of sign, unlike *Dload P
    assert back["components"]["E_FACE"][0] == "ELEM" and back["components"]["N_FACE"][0] == "NODE"  # one name space: the two sets keep apart
    assert back["mp"]["EX"] == back["mp"]["EY"] == 70000.0 and len(back["mp"]) == 9 and back["layers"] == [(1.0, 1, 0.0, 3)] and "TB,FCLI" not in text
    assert ("N_EDGE_LEFT", 3, 0.0) in back["d"] and ("N_EDGE_LEFT", 4, 0.0) in back["d"] and ("N_CORNER_X", 2, 0.0) in back["d"]


def test_one_isotropic_material_is_one_layer_with_two_constants():
    model = build_model(load_spec(paths.CHECKS / "d638-type-i-plastic" / "d638-type-i-plastic.toml"))
    assert model.material.isotropic and model.section.homogeneous
    text = write_ansys(model)
    back = read_back(text)
    assert back["mp"] == pytest.approx({"EX": model.material.E1 / 1e6, "PRXY": model.material.nu12})  # G follows from the two, in Ansys as in ours
    assert back["layers"] == [(pytest.approx(model.section.plies[0].thickness_m * 1e3), 1, model.section.plies[0].angle_deg, 3)]


def test_the_file_is_written_in_metres_and_pascals_when_asked():
    model = model_of(NODAL)
    text = write_ansys(model, "m-Pa")
    back = read_back(text)
    assert "/UNITS,SI" in text and back["mp"]["EX"] == pytest.approx(model.material.E1) and back["layers"][0][0] == pytest.approx(model.section.plies[0].thickness_m)
    assert ("N_GRIP_TOP", 2, 1e-3) in back["d"] and back["nodes"][2][0] == pytest.approx(model.mesh.xy[1, 0])


def test_what_the_file_cannot_state_is_refused_by_name():
    model = model_of(COUPLING)
    turned = dataclasses.replace(model, boundaries=tuple(b for b in model.boundaries if not (b.target == "RF-Top" and b.dof_last == 6))
                                 + (BoundaryDefinition("RF-Top", 3, 5),))
    with pytest.raises(AnsysWriterError, match="RF-Top of the grip Grip-Top may turn"):
        write_ansys(turned)
    with pytest.raises(AnsysWriterError, match="35 characters; Mechanical APDL takes 32"):
        component_name("N", "a" * 33)
    assert component_name("N", "Probe-near grip.1") == "N_PROBE_NEAR_GRIP_1"


def test_a_heading_is_written_in_ascii_without_losing_a_sign():
    model = model_of(NODAL)
    text = write_ansys(dataclasses.replace(model, heading=("thickness 0.18 mm · 45° ± 2 × 3 ≤ 7 “ζ”",)))
    assert text.splitlines()[0] == '! thickness 0.18 mm * 45 deg +/- 2 x 3 <= 7 "\\u03b6"'
    long = write_ansys(dataclasses.replace(model, heading=("word " * 120,)))
    assert all(line.startswith("!") and len(line) <= 240 for line in long.splitlines()[:3]) and long.splitlines()[1].startswith("!   word")


def test_an_independent_reader_finds_the_same_mesh(tmp_path):
    """mapdl-archive (MIT, numpy only) reads Ansys archive files without Ansys: our nodes, elements, element type, key options and
    components, read by code we did not write."""
    mapdl_archive = pytest.importorskip("mapdl_archive")
    for order, number in ((1, 181), (2, 281)):
        model = model_of(COUPLING, order=order)
        path = tmp_path / f"coupon-{order}.cdb"
        path.write_text(write_ansys(model), encoding="ascii", newline="\n")
        archive = mapdl_archive.Archive(str(path), parse_vtk=False)
        assert archive.nnum.tolist() == list(range(1, model.mesh.node_count + 1))
        assert archive.nodes[:, :2] == pytest.approx(model.mesh.xy * 1e3, rel=1e-12, abs=1e-12) and not archive.nodes[:, 2].any()
        assert archive.ekey.tolist() == [[1, number]] and archive.key_option[1][-1] == [8, 2]
        elements = [np.asarray(element).tolist() for element in archive.elem]
        assert [element[10:] for element in elements] == (model.mesh.connectivity() + 1).tolist()
        assert {tuple(element[:5]) for element in elements} == {(1, 1, 1, 1, 11)}  # material, type, real constant, section, element system
        for name, members in model.node_sets.items():
            assert sorted(archive.node_components[component_name("N", name)].tolist()) == sorted((members + 1).tolist())
        for name, members in model.element_sets.items():
            assert sorted(archive.element_components[component_name("E", name)].tolist()) == sorted((members + 1).tolist())
