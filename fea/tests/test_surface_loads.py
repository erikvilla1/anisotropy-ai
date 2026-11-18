"""What a model written by Abaqus/CAE usually holds beyond our own decks (ADR-0105 amendment 1, ADR-0053 amendment 1): a pressure on a
shell's face, loads along its edges, an instance moved and turned in its plane, sets a part defines. The directions are the ones Abaqus
2025 applied in the runs of 2026-11-17; the numbers held here are closed forms, the load totals and the kernel's own symmetries, never a
number of Abaqus's. The plate is the one those runs used: 40 mm square, 1 mm thick, 4 by 4 elements, clamped along x = 0."""

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import DeckError, parse_deck
from anisotropy_fea.imported import import_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.model import to_si, validate_deck

UNITS = "mm-MPa"
E, NU, SIDE, H = 70000.0, 0.3, 40.0, 1.0
TURNED = "0., 0., 0.\n0., 0., 0., 0., 0., 1., 90.\n"  # no move, then a quarter turn about z through the origin
ISOTROPIC = ("*Shell Section, elset=ALL, material=ISO\n1., 5\n", "*Material, name=ISO\n*Elastic\n70000., 0.3\n")
LAMINA = "*Material, name=UD\n*Elastic, type=LAMINA\n126000., 11000., 0.28, 6600., 6600., 3700.\n"  # nominal values for the test, not a cited material
NO_ORIENTATION = "*Shell Section, elset=ALL, composite\n1., 3, UD, 0.\n"
ORIENTATION = "*Orientation, name=ORI\n1., 0., 0., 0., 1., 0.\n3, 0.\n*Shell Section, elset=ALL, composite, orientation=ORI\n1., 3, UD, 0.\n"
TIP = 15  # the node at (40, 20), the middle of the free edge


def plate(load: str, instance: str = "", section: str = ISOTROPIC[0], material: str = ISOTROPIC[1], support: str = "FIXED, ENCASTRE") -> str:
    nodes = "\n".join(f"{1 + i + 5 * j}, {10 * i}., {10 * j}., 0." for j in range(5) for i in range(5))
    elements = "\n".join(f"{1 + i + 4 * j}, {1 + i + 5 * j}, {2 + i + 5 * j}, {7 + i + 5 * j}, {6 + i + 5 * j}" for j in range(4) for i in range(4))
    return (f"*Heading\nthe trial plate\n*Part, name=PLATE\n*Node\n{nodes}\n*Element, type=S4R\n{elements}\n*Elset, elset=ALL, generate\n1, 16, 1\n"
            f"*Nset, nset=ROOT\n1, 6, 11, 16, 21\n{section}*End Part\n*Assembly, name=Assembly\n*Instance, name=PLATE-1, part=PLATE\n{instance}*End Instance\n"
            "*Nset, nset=FIXED, instance=PLATE-1\n1, 6, 11, 16, 21\n*Elset, elset=ALLE, instance=PLATE-1, generate\n1, 16, 1\n"
            "*Elset, elset=EDGEE, instance=PLATE-1\n4, 8, 12, 16\n*Elset, elset=SIDEE, instance=PLATE-1, generate\n13, 16, 1\n"
            "*Surface, type=ELEMENT, name=TOP\nALLE, SPOS\n*Surface, type=ELEMENT, name=BOT\nALLE, SNEG\n*Surface, type=ELEMENT, name=EDGE\nEDGEE, E2\n"
            "*Surface, type=ELEMENT, name=CORNER\nEDGEE, E2\nSIDEE, E3\n*Surface, type=NODE, name=NODES\nFIXED, 1.\n"
            f"*End Assembly\n{material}*Boundary\n{support}\n*Step, nlgeom=NO\n*Static\n{load}\n*End Step\n")


def solved(text: str):
    deck = parse_deck(text)
    validate_deck(deck)
    solution = solve_deck(to_si(deck, UNITS, any_system=True))
    return solution, solution.mesh.node(("PLATE-1", TIP))


def tip(text: str) -> np.ndarray:
    """The tip node's displacement in mm (and its rotations when the shell solved)."""
    solution, k = solved(text)
    u = np.zeros(5)
    u[:solution.displacement.shape[1]] = solution.displacement[k]
    u[:3] *= 1e3
    return u


def test_a_pressure_acts_the_way_abaqus_applies_each_of_its_three_forms():
    """`*Dload` P on a shell element pushes along the element normal (+z here); `*Dsload` P pushes onto the face it names, so on the top
    face (SPOS) toward -z and on the bottom face (SNEG) toward +z. The three are one load but for the sign."""
    element, top, bottom = (tip(plate(load))[2] for load in ("*Dload\nALLE, P, 0.01", "*Dsload\nTOP, P, 0.01", "*Dsload\nBOT, P, 0.01"))
    assert element > 0 and top == pytest.approx(-element, rel=1e-12) and bottom == pytest.approx(element, rel=1e-12)
    # a clamped strip under a uniform load: between the beam's q L^4 / 8 E I and the wide plate's, stiffer by 1 - nu^2
    beam = 0.01 * SIDE ** 4 / (8 * E * H ** 3 / 12)
    assert (1 - NU ** 2) * beam < element < beam
    solution, _ = solved(plate("*Dsload\nTOP, P, 0.01"))
    assert solution.total_reaction[2] == pytest.approx(0.01 * 1e6 * (SIDE * 1e-3) ** 2, rel=1e-9)  # 16 N pressing down, carried up by the support


@pytest.mark.parametrize(("label", "component", "sign"), [("EDNOR", 0, -1), ("EDSHR", 1, +1), ("EDTRA", 2, +1)])
def test_an_edge_load_acts_the_way_abaqus_applies_it_and_carries_its_whole_force(label, component, sign):
    """On the free edge x = 40, side E2 of its elements, whose nodes run toward +y: a positive EDNOR pushes into the plate (-x), a
    positive EDSHR runs along the edge the way the element lists its nodes (+y), a positive EDTRA acts along the normal (+z)."""
    solution, k = solved(plate(f"*Dsload\nEDGE, {label}, 1.0"))
    assert np.sign(solution.displacement[k, component]) == sign
    reaction = np.zeros(3)
    reaction[:len(solution.total_reaction[:3])] = solution.total_reaction[:3]
    expected = np.zeros(3)
    expected[component] = -sign * 1.0e3 * SIDE * 1e-3  # 1 N/mm on 40 mm: 40 N, and the support answers with the opposite
    assert reaction == pytest.approx(expected, abs=1e-9)


def test_an_edge_load_on_a_plate_free_to_shrink_sideways_is_the_bar_exactly():
    """Held only against the push, the plate is in uniform stress: every node of the loaded edge moves N L / (E h), and the nodal forces
    the reader makes (half an element edge's force at each end) are the ones that give it."""
    solution, _ = solved(plate("*Dsload\nEDGE, EDNOR, 1.0", support="FIXED, 1, 1\n*Boundary\nFIXED, 3, 6\n*Boundary\nPLATE-1.1, 2, 2"))
    edge = [solution.mesh.node(("PLATE-1", n)) for n in (5, 10, 15, 20, 25)]
    assert solution.displacement[edge, 0] * 1e3 == pytest.approx(-1.0 * SIDE / (E * H), rel=1e-10)


def test_a_set_the_part_defines_is_named_from_the_assembly_through_its_instance():
    """Abaqus/CAE writes a support or a load on a set made in the Part module as `Instance.Set`."""
    through_assembly = tip(plate("*Dsload\nEDGE, EDTRA, 1.0"))
    through_part = tip(plate("*Dsload\nEDGE, EDTRA, 1.0", support="PLATE-1.ROOT, ENCASTRE"))
    assert through_part == pytest.approx(through_assembly, rel=1e-12)
    with pytest.raises(DeckError, match="node set 'PLATE-1.NOPE' is not defined in the assembly"):
        validate_deck(parse_deck(plate("*Dsload\nEDGE, EDTRA, 1.0", support="PLATE-1.NOPE, ENCASTRE")))


def test_a_surface_over_two_sides_carries_the_load_on_both():
    """A surface CAE picks along two edges of a plate lists an element set per side; the corner node gets a share from each edge."""
    one, both = solved(plate("*Dsload\nEDGE, EDNOR, 1.0"))[0], solved(plate("*Dsload\nCORNER, EDNOR, 1.0"))[0]
    assert one.total_reaction[:2] == pytest.approx([40.0, 0.0], abs=1e-9)
    assert both.total_reaction[:2] == pytest.approx([40.0, 40.0], abs=1e-9)  # -x on the edge x = 40 and -y on the edge y = 40


def test_an_instance_turned_in_its_plane_carries_its_loads_and_its_stated_orientation_with_it():
    """Abaqus moves an instance and then turns it about an axis given in the assembly's frame. The loads are stated on the elements, so
    they turn with it; so does an orientation the part states. A section with no orientation takes its fibre reference from the
    assembly's x axis wherever the instance is turned to, so turning the part then changes the answer."""
    moved = plate("*Dsload\nEDGE, EDNOR, 1.0", "5., 0., 0.\n0., 0., 0., 0., 0., 1., 90.\n")
    solution, k = solved(moved)
    assert solution.mesh.xy[k] * 1e3 == pytest.approx([-20.0, 45.0], abs=1e-9)  # (40, 20) moved to (45, 20), then turned about the origin
    still = tip(plate("*Dsload\nEDGE, EDNOR, 1.0"))
    assert solution.displacement[k] * 1e3 == pytest.approx([-still[1], still[0]], abs=1e-12)  # the displacement turned a quarter turn too
    pressure = "*Dload\nALLE, P, 0.01"
    stated = [tip(plate(pressure, instance, ORIENTATION, LAMINA)) for instance in ("", TURNED)]
    assert stated[1][2] == pytest.approx(stated[0][2], rel=1e-9)  # the fibres still run along the cantilever
    assert stated[1][3] == pytest.approx(-stated[0][4], rel=1e-9)  # and the tip's slope about y is now about x
    default = [tip(plate(pressure, instance, NO_ORIENTATION, LAMINA)) for instance in ("", TURNED)]
    assert default[0][2] == pytest.approx(stated[0][2], rel=1e-12)  # unturned, no orientation is the assembly's axes
    assert default[1][2] > 10 * default[0][2]  # turned, the fibres stay along x and now run across the cantilever
    about = plate(pressure, "0., 0., 0.\n10., 0., 0., 10., 0., -1., 90.\n")  # the axis pointing along -z: the turn is clockwise
    assert solved(about)[0].mesh.xy[solved(about)[1]] * 1e3 == pytest.approx([30.0, -30.0], abs=1e-9)


@pytest.mark.parametrize(("load", "instance", "message"), [
    ("*Dsload\nEDGE, P, 1.", "", "a pressure \\(P\\) acts on a shell's face, SPOS or SNEG; surface 'EDGE' lies on E2"),
    ("*Dsload\nTOP, EDNOR, 1.", "", "EDNOR acts on a shell's edge, E1 to E4; surface 'TOP' lies on SPOS"),
    ("*Dsload\nEDGE, EDMOM, 1.", "", "surface load label 'EDMOM' is not supported"),
    ("*Dsload\nTOP, TRVEC, 1., 1., 0., 0.", "", "a surface load line is `surface, label, value`"),
    ("*Dsload\nNODES, P, 1.", "", "names surface 'NODES', which is a node surface"),
    ("*Dsload\nNOPE, P, 1.", "", "names surface 'NOPE', which is not defined"),
    ("*Dsload, amplitude=Amp-1\nTOP, P, 1.", "", "parameter 'amplitude' is not supported"),
    ("*Dload\nALLE, P, 1.", "0., 0., 0.\n0., 0., 0., 1., 0., 0., 90.\n", "turned about an axis that is not along z"),
    ("*Dload\nALLE, P, 1.", "0., 0., 3.\n", "moved by 3 along z, out of the plane z = 0"),
])
def test_a_surface_load_or_a_placement_outside_what_is_read_is_refused_with_its_line(load, instance, message):
    with pytest.raises(DeckError, match=message) as refused:
        validate_deck(parse_deck(plate(load, instance)))
    assert str(refused.value).startswith("line ")


def test_a_model_laid_out_as_abaqus_cae_writes_one_is_read_whole_and_answers_as_it_does_unplaced():
    """The public fixture in CAE's layout: internal sets, a density, five positive strengths, the instance moved and then turned, a
    pressure on a face and a load on an edge, each on a surface. Placing a model moves no strain, so the same file with the instance
    left where the part is must give the same factors and the same deflection."""
    path = paths.CHECK_DECKS / "plate-10x5-cae-layout-im7-8552.inp"
    text = path.read_text(encoding="utf-8")
    placement = "        -10.,          20.,           0.\n        -10.,          20.,           0.,         -10.,          20.,           1.,          90.\n"
    assert placement in text
    placed, unplaced = import_model(text.encode("utf-8"), path.name, UNITS), import_model(text.replace(placement, "").encode("utf-8"), path.name, UNITS)
    assert placed["state"] == unplaced["state"] == "solved"
    reading = placed["reading"]
    assert reading["moved"] == [{"instance": "Plate-1", "by": pytest.approx([-10.0, 20.0]), "turned_deg": 90.0, "about": pytest.approx([-10.0, 20.0])}]
    assert (reading["elements"], reading["nodes"], reading["pressures"], reading["edge_loads"], reading["concentrated_loads"]) == (50, 66, 1, 1, 0)
    assert reading["layup"] == "[0/45/-45/90/90/-45/45/0]" and reading["sections"][0]["rotation_deg"] == 90.0 and unplaced["reading"]["sections"][0]["rotation_deg"] == 0.0
    assert [line.split(": ", 1)[1] for line in reading["skipped"]] == ["*preprint", "*density (mass is not used by a static step)", "*restart", "*output", "*output"]
    edge, pressure = placed["preview"]["loads"]
    assert (edge["set"], edge["control"], edge["direction"], edge["unit"], edge["nodes"]) == ("Surf-FreeEdge", "edge load, normal to the edge,", "-y", "N/mm", 6)
    assert edge["value"] == pytest.approx(5.0) and edge["total_force"] == pytest.approx(250.0)
    assert (pressure["control"], pressure["direction"], pressure["value"]) == ("pressure", "-z", pytest.approx(0.002))
    assert len(placed["preview"]["mesh"]["node_sets"]["Surf-FreeEdge"]) == 6
    a, b = np.array(placed["fields"]["nodal"]["displacement"]), np.array(unplaced["fields"]["nodal"]["displacement"])
    assert a[:, 2] == pytest.approx(b[:, 2], rel=1e-8, abs=1e-12) and a[:, 0] == pytest.approx(-b[:, 1], rel=1e-8, abs=1e-12)
    for criterion, found in unplaced["fields"]["summary"]["fpf"].items():
        same = placed["fields"]["summary"]["fpf"][criterion]
        assert same["factor"] == pytest.approx(found["factor"], rel=1e-9) and (same["ply"], same["mode"]) == (found["ply"], found["mode"])
