"""Closed forms for the plate bending validation cases, and the decks they run on (ADR-0053): the source of the `plate-*` and `strip-*` cases.

    uv run python tools/plate_closed_forms.py            # every case's closed form beside the kernel's value
    uv run python tools/plate_closed_forms.py --write    # rewrite the decks in checks/decks and the cases in checks/cases, then compare

The simply supported rectangular plate follows Whitney, Structural Analysis of Laminated Anisotropic Plates (1987). Without transverse
shear deformation it is the Navier solution of Chapter 5: the plate equation (5.1), the simply supported conditions (5.2) and (5.3), the
load expanded in the double sine series (5.4), the deflection (5.7) and the moments (5.8) to (5.10), with the coefficients of a uniform
load from (5.16). With transverse shear deformation it is the theory of Chapter 10: the displacement field (10.1), the shear strains
(10.4), the shear law Q = k A44..A55 gamma (10.6) and, for a symmetric laminate, the moment equations (10.19) and (10.20) with the
transverse equilibrium (10.12) without inertia; for a specially orthotropic laminate (D16 = D26 = 0, A45 = 0) one term of the series
w = W sin(alpha x) sin(beta y), psi_x = X cos(alpha x) sin(beta y), psi_y = Y sin(alpha x) cos(beta y) satisfies the simply supported
conditions (10.25) and reduces the three equations to a three-by-three linear system per term, solved here. Whitney's psi_x and psi_y are
the rotations of the normal in the x-z and y-z planes; the kernel's dofs are the rotations about the axes, theta_y = psi_x and
theta_x = -psi_y. The cantilever strip with nu = 0 follows the Timoshenko beam: M = EI phi', Q = kGA (w' - phi) with phi the bending
rotation, which for a tip load P gives w(L) = P L^3 / (3 EI) + P L / (k G A); nu = 0 makes the plate's D11 equal E h^3 / 12, so the strip
and the beam coincide. The laminate stiffness D and the transverse shear stiffness are computed here by hand from the ply constants (the
same reduced stiffness and transformation as engine/validation/closed_forms.py, which imports nothing from the engine); the shear
correction factor is 5/6 (Reissner's value, Whitney Section 10.4).

The kernel's value differs from the closed form by its discretization error only, since the Mindlin series is the exact solution of the
theory the element discretizes; each case states the tolerance that the convergence table printed by this tool supports.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anisotropy_fea import paths  # noqa: E402
from anisotropy_fea.cases import compare, load_case  # noqa: E402

ENGINE_CLOSED_FORMS = paths.ROOT / "engine" / "validation" / "closed_forms.py"
SHEAR_CORRECTION = 5.0 / 6.0
TERMS = 199  # odd harmonics up to this index in the uniform-load series; the sum converges as 1/m^5 and is settled to 1e-12 long before
IM7 = {"E1": 162095.74, "E2": 8963.18, "nu12": 0.316, "G12": 4688.43, "G13": 4688.43, "G23": 3000.0, "ply": 0.18288}  # MPa, mm: the fixture values
E_NOMINAL, NU_NOMINAL = 70000.0, 0.3  # nominal isotropic values, not a cited material


def engine_free_forms():
    spec = importlib.util.spec_from_file_location("closed_forms", ENGINE_CLOSED_FORMS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- laminate stiffness by hand ---------------------------------------------------------------------------------------------


def isotropic_section(E: float, nu: float, h: float) -> tuple[np.ndarray, np.ndarray]:
    """D and the shear-corrected transverse stiffness H of a homogeneous isotropic plate."""
    Q = E / (1.0 - nu * nu) * np.array([[1.0, nu, 0.0], [nu, 1.0, 0.0], [0.0, 0.0, (1.0 - nu) / 2.0]])
    G = E / (2.0 * (1.0 + nu))
    return Q * h**3 / 12.0, SHEAR_CORRECTION * G * h * np.eye(2)


def laminate_section(angles: list[float], ply: float, material: dict) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """D, H and the plies (angle, z bottom, z top, Q on axis, Q bar) of a laminate listed bottom first, by hand."""
    forms = engine_free_forms()
    q = forms.q_on_axis(material["E1"], material["E2"], material["G12"], material["nu12"])
    h = ply * len(angles)
    z = -h / 2.0
    D = np.zeros((3, 3))
    H = np.zeros((2, 2))
    plies = []
    for angle in angles:
        qb = forms.q_bar(q, angle)
        D += qb * ((z + ply) ** 3 - z**3) / 3.0
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        G13, G23 = material["G13"], material["G23"]
        H += ply * np.array([[G13 * c * c + G23 * s * s, (G13 - G23) * c * s], [(G13 - G23) * c * s, G13 * s * s + G23 * c * c]])
        plies.append({"angle": angle, "z0": z, "z1": z + ply, "q": q, "qbar": qb})
        z += ply
    return D, SHEAR_CORRECTION * H, plies


# --- the simply supported plate ---------------------------------------------------------------------------------------------


def navier_term(D: np.ndarray, H: np.ndarray | None, alpha: float, beta: float, qmn: float) -> tuple[float, float, float]:
    """W, X, Y of one term for a specially orthotropic plate: with H the three equations of Chapter 10, without it the Kirchhoff plate
    (Whitney 5.7), where psi_x = -w,x and psi_y = -w,y."""
    D11, D12, D22, D66 = D[0, 0], D[0, 1], D[1, 1], D[2, 2]
    if H is None:
        W = qmn / (D11 * alpha**4 + 2.0 * (D12 + 2.0 * D66) * alpha**2 * beta**2 + D22 * beta**4)
        return W, -alpha * W, -beta * W
    H11, H22 = H[0, 0], H[1, 1]
    K = np.array([
        [-(D11 * alpha**2 + D66 * beta**2 + H11), -(D12 + D66) * alpha * beta, -H11 * alpha],
        [-(D12 + D66) * alpha * beta, -(D66 * alpha**2 + D22 * beta**2 + H22), -H22 * beta],
        [-H11 * alpha, -H22 * beta, -(H11 * alpha**2 + H22 * beta**2)],
    ])
    X, Y, W = np.linalg.solve(K, [0.0, 0.0, -qmn])
    return float(W), float(X), float(Y)


def load_terms(load: tuple[str, float], terms: int) -> list[tuple[int, int, float]]:
    """(m, n, q_mn) of a load: one term for q0 sin(pi x / a) sin(pi y / b); Whitney (5.16) for a uniform q0."""
    kind, q0 = load
    if kind == "sinusoidal":
        return [(1, 1, q0)]
    if kind == "uniform":
        return [(m, n, 16.0 * q0 / (math.pi**2 * m * n)) for m in range(1, terms + 1, 2) for n in range(1, terms + 1, 2)]
    raise ValueError(f"unknown load {kind!r}")


def navier_fields(D: np.ndarray, H: np.ndarray | None, a: float, b: float, load: tuple[str, float], x: float, y: float,
                  terms: int = TERMS) -> dict[str, float]:
    """w, the kernel's rotations theta_x and theta_y, the curvatures, the moments and the shear forces at (x, y)."""
    out = dict.fromkeys(("w", "theta_x", "theta_y", "kappa_x", "kappa_y", "kappa_xy", "Mx", "My", "Mxy", "Qx", "Qy"), 0.0)
    D11, D12, D22, D66 = D[0, 0], D[0, 1], D[1, 1], D[2, 2]
    for m, n, qmn in load_terms(load, terms):
        alpha, beta = m * math.pi / a, n * math.pi / b
        W, X, Y = navier_term(D, H, alpha, beta, qmn)
        ss, cs, sc, cc = (math.sin(alpha * x) * math.sin(beta * y), math.cos(alpha * x) * math.sin(beta * y),
                          math.sin(alpha * x) * math.cos(beta * y), math.cos(alpha * x) * math.cos(beta * y))
        out["w"] += W * ss
        out["theta_y"] += X * cs  # psi_x
        out["theta_x"] += -Y * sc  # -psi_y
        kx, ky, kxy = -alpha * X * ss, -beta * Y * ss, (beta * X + alpha * Y) * cc  # psi_x,x; psi_y,y; psi_x,y + psi_y,x
        out["kappa_x"] += kx
        out["kappa_y"] += ky
        out["kappa_xy"] += kxy
        out["Mx"] += D11 * kx + D12 * ky
        out["My"] += D12 * kx + D22 * ky
        out["Mxy"] += D66 * kxy
        if H is not None:
            out["Qx"] += H[0, 0] * (X + alpha * W) * cs
            out["Qy"] += H[1, 1] * (Y + beta * W) * sc
    return out


def ply_face_stresses(plies: list[dict], kappa: np.ndarray) -> dict[str, list[float]]:
    """[sigma_1, sigma_2, tau_12] on both faces of every ply of a symmetric laminate under pure bending (eps0 = 0), keyed `k:face`."""
    forms = engine_free_forms()
    out = {}
    for k, ply in enumerate(plies, start=1):
        for face, z in (("bottom", ply["z0"]), ("top", ply["z1"])):
            strain_xy = z * kappa
            local = forms.to_fiber_axes(strain_xy, ply["angle"])
            out[f"{k}:{face}"] = [float(v) for v in ply["q"] @ local]
    return out


# --- the cantilever strip ---------------------------------------------------------------------------------------------------


def timoshenko_strip(E: float, h: float, b: float, L: float, P: float, x: float) -> dict[str, float]:
    """A strip of width b and thickness h with nu = 0, clamped at x = 0, loaded by P along +z at x = L: w, the rotation theta_y, the
    moment and the shear force per unit width at x."""
    D11 = E * h**3 / 12.0
    H11 = SHEAR_CORRECTION * (E / 2.0) * h
    return {"w": P * x / (b * H11) + P * (L * x * x / 2.0 - x**3 / 6.0) / (b * D11),
            "theta_y": -P * (L * x - x * x / 2.0) / (b * D11), "Mx": -P * (L - x) / b, "Qx": P / b}


# --- decks ------------------------------------------------------------------------------------------------------------------


def grid(nx: int, ny: int, a: float, b: float):
    label = lambda i, j: 1 + i + (nx + 1) * j  # noqa: E731
    nodes = [f"{label(i, j)}, {a * i / nx:.10g}, {b * j / ny:.10g}, 0." for j in range(ny + 1) for i in range(nx + 1)]
    elements = [f"{1 + i + nx * j}, {label(i, j)}, {label(i + 1, j)}, {label(i + 1, j + 1)}, {label(i, j + 1)}" for j in range(ny) for i in range(nx)]
    return label, nodes, elements


def rows(ids: list[int]) -> str:
    return "\n".join(", ".join(map(str, ids[k:k + 16])) for k in range(0, len(ids), 16))


def deck_text(heading: list[str], part: str, nodes: list[str], elements: list[str], part_sets: dict[str, list[int]], section: str,
              material: str, boundaries: list[str], loads: list[str], element_count: int) -> str:
    instance = f"{part}-1"
    text = "*Heading\n" + "".join(f"** {line}\n" for line in heading)
    text += f"*Part, name={part}\n*Node\n" + "\n".join(nodes) + "\n*Element, type=S4R\n" + "\n".join(elements) + "\n"
    text += f"*Elset, elset=All, generate\n1, {element_count}, 1\n{section}*End Part\n"
    text += f"*Assembly, name=Assembly\n*Instance, name={instance}, part={part}\n*End Instance\n"
    for name, ids in part_sets.items():
        text += f"*Nset, nset={name}, instance={instance}\n{rows(ids)}\n"
    text += f"*Elset, elset=All, instance={instance}, generate\n1, {element_count}, 1\n*End Assembly\n"
    text += material
    text += "*Step, name=Step-1, nlgeom=NO\n*Static\n1., 1., 1e-05, 1.\n*Boundary\n" + "\n".join(boundaries) + "\n"
    text += "\n".join(loads) + ("\n" if loads else "") + "*End Step\n"
    return text


def plate_deck(nx: int, ny: int, a: float, b: float, section: str, material: str, heading: list[str], pressure, part: str = "Plate"):
    """A simply supported rectangular plate: w and the rotation about the edge's normal held on every edge (Whitney 10.25), the in-plane
    rigid motions held at two corners. `pressure` is a number (one *Dload on the whole plate) or a function of an element's box
    (x0, x1, y0, y1) giving its pressure (one line per element). Returns the deck text and the labels of the centre node, the quarter node
    and the element whose lower-left corner is the centre node."""
    label, nodes, elements = grid(nx, ny, a, b)
    left = [label(0, j) for j in range(ny + 1)]
    right = [label(nx, j) for j in range(ny + 1)]
    bottom = [label(i, 0) for i in range(nx + 1)]
    top = [label(i, ny) for i in range(nx + 1)]
    edges = sorted(set(left + right + bottom + top))
    centre = label(nx // 2, ny // 2)
    quarter = label(nx // 4, ny // 2)
    sets = {"Left": left, "Right": right, "Bottom": bottom, "Top": top, "Edges": edges, "Centre": [centre], "Quarter": [quarter],
            "Origin": [label(0, 0)], "Corner-X": [label(nx, 0)]}
    boundaries = ["Left, 3, 4", "Right, 3, 4", "Bottom, 3, 3", "Bottom, 5, 5", "Top, 3, 3", "Top, 5, 5", "Origin, 1, 2", "Corner-X, 2, 2"]
    if callable(pressure):
        loads = ["*Dload"]
        for j in range(ny):
            for i in range(nx):
                box = (a * i / nx, a * (i + 1) / nx, b * j / ny, b * (j + 1) / ny)
                loads.append(f"{part}-1.{1 + i + nx * j}, P, {pressure(*box):.12g}")
    else:
        loads = ["*Dload", f"All, P, {pressure:.12g}"]
    text = deck_text(heading, part, nodes, elements, sets, section, material, boundaries, loads, nx * ny)
    centre_element = 1 + nx // 2 + nx * (ny // 2)  # the element whose lower-left corner is the centre node: centroid at (a/2 + a/2nx, b/2 + b/2ny)
    return text, centre, quarter, centre_element


def strip_deck(nx: int, ny: int, L: float, b: float, h: float, E: float, P: float, part: str = "Strip"):
    """A cantilever strip clamped along x = 0 and loaded by P along +z on the edge x = L as consistent nodal loads (half weight at the corners)."""
    label, nodes, elements = grid(nx, ny, L, b)
    left = [label(0, j) for j in range(ny + 1)]
    tip = [label(nx, j) for j in range(ny + 1)]
    sets = {"Left": left, "Tip": tip, "Tip-Centre": [label(nx, ny // 2)], "Root-Centre": [label(0, ny // 2)]}
    section = f"*Shell Section, elset=All, material=Nominal-Alloy\n{h:g}, 5\n"
    material = f"*Material, name=Nominal-Alloy\n*Elastic\n{E:g}, 0.\n"
    heading = [f"Fixture: a cantilever strip {L:g} mm long, {b:g} mm wide, {h:g} mm thick, clamped along x = 0, {P:g} N along +z on the free end.",
               f"Units: mm-MPa. E = {E:g} MPa and nu = 0 are nominal values chosen so the plate strip and the Timoshenko beam coincide, not a cited material.",
               "The tip load is spread over the free edge as consistent nodal loads: half weight at the two corners."]
    loads = ["*Cload"] + [f"{part}-1.{node}, 3, {P / ny * (0.5 if j in (0, ny) else 1.0):.12g}" for j, node in enumerate(tip)]
    text = deck_text(heading, part, nodes, elements, sets, section, material, ["Left, 1, 6"], loads, nx * ny)
    return text, label(nx, ny // 2), 1 + nx * (ny // 2)  # the tip centre node and the root element on the centre row


# --- the cases --------------------------------------------------------------------------------------------------------------


def isotropic_plate_case(name: str, h: float, nx: int, tolerance: float, title: str, note: str) -> tuple[str, str, dict]:
    a = 100.0
    q0 = 0.01  # MPa toward +z: the deck writes the Abaqus pressure P = -q0
    E, nu = E_NOMINAL, NU_NOMINAL
    D, H = isotropic_section(E, nu, h)
    section = f"*Shell Section, elset=All, material=Nominal-Alloy\n{h:g}, 5\n"
    material = f"*Material, name=Nominal-Alloy\n*Elastic\n{E:g}, {nu:g}\n"
    heading = [f"Fixture: a {a:g} mm square plate {h:g} mm thick, simply supported on all four edges, uniform pressure {q0:g} MPa toward +z.",
               f"Units: mm-MPa. E = {E:g} MPa and nu = {nu:g} are nominal values chosen for the test, not a cited material.",
               "Simple support: w and the rotation about the edge normal held on every edge (Whitney 10.25); the in-plane rigid motions held at two corners.",
               "The Abaqus P label is positive against the shell normal (+z for counterclockwise nodes), so the pressure is written negative."]
    text, centre, quarter, centre_element = plate_deck(nx, nx, a, a, section, material, heading, -q0)
    xc = a / 2.0 + a / (2.0 * nx)
    at_centre = navier_fields(D, H, a, a, ("uniform", q0), a / 2.0, a / 2.0)
    at_quarter = navier_fields(D, H, a, a, ("uniform", q0), a / 4.0, a / 2.0)
    at_centroid = navier_fields(D, H, a, a, ("uniform", q0), xc, xc)
    kirchhoff = navier_fields(D, None, a, a, ("uniform", q0), a / 2.0, a / 2.0)
    source = (f"The Navier series with transverse shear deformation (Whitney 1987, Chapter 10, as fea/tools/plate_closed_forms.py states it) for a "
              f"simply supported {a:g} mm square isotropic plate, E = {E:g} MPa, nu = {nu:g}, h = {h:g} mm (h/a = {h / a:g}), under a uniform "
              f"pressure q = {q0:g} MPa toward +z with D = E h^3 / (12 (1 - nu^2)) = {D[0, 0]:.10g} N mm and the shear stiffness 5/6 G h; "
              f"{TERMS} odd harmonics. The Kirchhoff value of the centre deflection, Whitney (5.7) with (5.16), is {kirchhoff['w']:.10g} mm "
              f"(Timoshenko and Woinowsky-Krieger tabulate 0.00406 q a^4 / D = {0.00406 * q0 * a**4 / D[0, 0]:.6g} mm for nu = 0.3); the "
              f"shear-deformation value, which is the exact solution of the theory the element discretizes, is {at_centre['w']:.10g} mm. "
              f"{note}")
    expected = {
        "tolerance": tolerance,
        "rf_z": {"Edges": [-q0 * a * a]},
        "w": {f"Plate-1.{centre}": [at_centre["w"]]},
        "rotation": {f"Plate-1.{quarter}": [at_quarter["theta_x"], at_quarter["theta_y"]]},
        "moment": {f"Plate-1.{centre_element}": [at_centroid["Mx"], at_centroid["My"], at_centroid["Mxy"]]},
        "curvature": {f"Plate-1.{centre_element}": [at_centroid["kappa_x"], at_centroid["kappa_y"], at_centroid["kappa_xy"]]},
    }
    return text, source, {"title": title, "expected": expected}


def cross_ply_case(name: str, nx: int, tolerance: float) -> tuple[str, str, dict]:
    a = 100.0
    q0 = 0.01
    angles = [0.0, 90.0, 90.0, 0.0]
    D, H, plies = laminate_section(angles, IM7["ply"], IM7)
    h = IM7["ply"] * len(angles)
    section = ("*Orientation, name=Ori-1\n1., 0., 0., 0., 1., 0.\n3, 0.\n*Shell Section, elset=All, composite, orientation=Ori-1, layup=Layup-1, symmetric\n"
               + "".join(f"{IM7['ply']}, 3, IM7-8552, {angle:g}., Ply-{k}\n" for k, angle in enumerate(angles[:2], start=1)))
    material = (f"*Material, name=IM7-8552\n*Elastic, type=LAMINA\n{IM7['E1']}, {IM7['E2']}, {IM7['nu12']}, {IM7['G12']}, {IM7['G13']}, {IM7['G23']}\n"
                "*Fail Stress\n2558.51, -1731.48, 64.05, -285.72, 91.15, 0.\n")
    heading = [f"Fixture: a {a:g} mm square IM7/8552 [0/90]s plate, {h:g} mm thick, simply supported on all four edges, under the pressure "
               f"q = {q0:g} sin(pi x / a) sin(pi y / a) MPa toward +z written per element as its average over the element.",
               "Units: mm-MPa. Material values from the public library dataset ncamp-im7-8552-2019-rtd-measured-v1 converted to MPa, as the other fixture decks;",
               "G13 is set equal to G12 and G23 is a nominal 3000 MPa (the shell reads both for the transverse shear stiffness).",
               "Simple support: w and the rotation about the edge normal held on every edge (Whitney 10.25); the in-plane rigid motions held at two corners.",
               "The Abaqus P label is positive against the shell normal (+z for counterclockwise nodes), so the pressure is written negative."]
    alpha = math.pi / a

    def pressure(x0, x1, y0, y1):  # the element average of q, so the total load is exact on every mesh
        return -q0 * (math.cos(alpha * x0) - math.cos(alpha * x1)) / (alpha * (x1 - x0)) * (math.cos(alpha * y0) - math.cos(alpha * y1)) / (alpha * (y1 - y0))
    text, centre, quarter, centre_element = plate_deck(nx, nx, a, a, section, material, heading, pressure, part="Plate")
    xc = a / 2.0 + a / (2.0 * nx)
    at_centre = navier_fields(D, H, a, a, ("sinusoidal", q0), a / 2.0, a / 2.0)
    at_quarter = navier_fields(D, H, a, a, ("sinusoidal", q0), a / 4.0, a / 2.0)
    at_centroid = navier_fields(D, H, a, a, ("sinusoidal", q0), xc, xc)
    kirchhoff = navier_fields(D, None, a, a, ("sinusoidal", q0), a / 2.0, a / 2.0)
    kappa = np.array([at_centroid["kappa_x"], at_centroid["kappa_y"], at_centroid["kappa_xy"]])
    faces = ply_face_stresses(plies, kappa)
    source = (f"One term of the Navier series with transverse shear deformation (Whitney 1987, Chapter 10, as fea/tools/plate_closed_forms.py states it) "
              f"for a simply supported {a:g} mm square specially orthotropic IM7/8552 [0/90]s plate, h = {h:g} mm (h/a = {h / a:g}), under "
              f"q = {q0:g} sin(pi x / a) sin(pi y / a) MPa toward +z; D by hand from the ply constants (D11 = {D[0, 0]:.10g}, D12 = {D[0, 1]:.10g}, "
              f"D22 = {D[1, 1]:.10g}, D66 = {D[2, 2]:.10g} N mm), transverse shear stiffness 5/6 times the thickness-weighted G13 and G23 "
              f"({H[0, 0]:.10g} and {H[1, 1]:.10g} N/mm). The Kirchhoff centre deflection, Whitney (5.7) with one term, is {kirchhoff['w']:.10g} mm; "
              f"the shear-deformation value is {at_centre['w']:.10g} mm. The ply stresses are Q-bar times z kappa at the centroid of the element "
              f"nearest the centre, rotated to the fibre axes, on the bottom and top face of each ply. The deck writes the sinusoidal pressure per element "
              f"as its element average, so the total load is exact; on the 32 by 32 mesh the centre deflection, the quarter-point rotation and the "
              f"centroid moments, curvatures and ply stresses agree within 0.4 % (the tool's convergence table: 1.3 % on 16 by 16, 5 % on 8 by 8).")
    expected = {
        "tolerance": tolerance,
        "w": {f"Plate-1.{centre}": [at_centre["w"]]},
        "rotation": {f"Plate-1.{quarter}": [at_quarter["theta_x"], at_quarter["theta_y"]]},
        "moment": {f"Plate-1.{centre_element}": [at_centroid["Mx"], at_centroid["My"], at_centroid["Mxy"]]},
        "curvature": {f"Plate-1.{centre_element}": [at_centroid["kappa_x"], at_centroid["kappa_y"], at_centroid["kappa_xy"]]},
        "ply_stress_local": {f"Plate-1.{centre_element}": faces},
    }
    return text, source, {"title": f"A simply supported IM7/8552 [0/90]s plate under a sinusoidal pressure: the shell reproduces Whitney's Navier solution "
                                   "with transverse shear deformation, faces included", "expected": expected}


def strip_case(nx: int, ny: int, tolerance: float) -> tuple[str, str, dict]:
    L, b, h, E, P = 100.0, 10.0, 2.0, E_NOMINAL, 10.0
    text, tip_centre, root_element = strip_deck(nx, ny, L, b, h, E, P)
    xc = L / (2.0 * nx)
    at_tip = timoshenko_strip(E, h, b, L, P, L)
    at_root = timoshenko_strip(E, h, b, L, P, xc)
    bending_only = P * L**3 / (3.0 * E * b * h**3 / 12.0)
    source = (f"The Timoshenko cantilever beam (as fea/tools/plate_closed_forms.py states it) for a strip {L:g} mm long, {b:g} mm wide, {h:g} mm thick, "
              f"E = {E:g} MPa, nu = 0 (so the plate's D11 = E h^3 / 12 is the beam's EI / b), clamped at x = 0 and loaded by {P:g} N along +z at "
              f"x = L: w(L) = P L^3 / (3 EI) + P L / (k G A) with k = 5/6 and G = E / 2, = {bending_only:.10g} + {at_tip['w'] - bending_only:.10g} = "
              f"{at_tip['w']:.10g} mm; theta_y(L) = -P L^2 / (2 EI); M_x = -P (L - x) / b and Q_x = P / b per unit width, evaluated at the centroid "
              f"of the root element on the centre row. The strip is {nx} by {ny} elements; the table printed by the tool gives the discretization error.")
    expected = {
        "tolerance": tolerance,
        "rf_z": {"Left": [-P]},
        "w": {f"Strip-1.{tip_centre}": [at_tip["w"]]},
        "rotation": {f"Strip-1.{tip_centre}": [0.0, at_tip["theta_y"]]},
        "moment": {f"Strip-1.{root_element}": [at_root["Mx"], 0.0, 0.0]},
        "shear_force": {f"Strip-1.{root_element}": [at_root["Qx"], 0.0]},
    }
    return text, source, {"title": "A cantilever strip with nu = 0 under a tip load: the shell reproduces the Timoshenko beam, shear deflection included",
                          "expected": expected}


def build_cases() -> dict[str, tuple[str, str, str, dict]]:
    """name -> (deck file name, deck text, source, case fields)."""
    cases = {}
    text, source, fields = isotropic_plate_case(
        "plate-ss-isotropic-uniform-pressure-navier", 1.0, 16, 5e-3,
        "A simply supported isotropic square plate under uniform pressure: the shell reproduces the Navier solution with transverse shear deformation",
        "The 16 by 16 mesh of MITC4 elements gives the centre deflection within 0.1 %, the quarter-point rotation within 0.3 % and the centroid "
        "moments and curvatures within 0.35 % (the tool's table); the twisting moment, half a percent of the bending moments, carries the largest "
        "relative difference.")
    cases["plate-ss-isotropic-uniform-pressure-navier"] = ("plate-ss-16x16-isotropic.inp", text, source, fields)
    text, source, fields = isotropic_plate_case(
        "plate-ss-isotropic-thin-no-locking", 0.1, 16, 5e-3,
        "The same plate a thousand times thinner than wide (h/a = 1e-3): the MITC4 shell does not lock",
        "A displacement-based bilinear plate element would lock on this plate and give a deflection orders of magnitude too small; the MITC4 tying "
        "keeps the error at the level of the thick plate's (the tool's table).")
    cases["plate-ss-isotropic-thin-no-locking"] = ("plate-ss-16x16-isotropic-thin.inp", text, source, fields)
    text, source, fields = cross_ply_case("plate-ss-cross-ply-sinusoidal-navier", 32, 1e-2)
    cases["plate-ss-cross-ply-sinusoidal-navier"] = ("plate-ss-32x32-cross-ply-im7-8552.inp", text, source, fields)
    text, source, fields = strip_case(40, 4, 3e-3)
    cases["strip-cantilever-tip-load-timoshenko"] = ("strip-40x4-cantilever-isotropic.inp", text, source, fields)
    return cases


def snapped(expected: dict) -> dict:
    """Expected values smaller than 1e-10 of their group's largest magnitude are roundoff of the closed form (a sine at pi/2) and are
    written as exactly zero, so the comparison judges them against the group as it does every exact zero."""
    for group, rows_ in expected.items():
        if group == "tolerance":
            continue
        vectors = [v for plies in rows_.values() for v in plies.values()] if group == "ply_stress_local" else list(rows_.values())
        scale = max(abs(float(x)) for v in vectors for x in v)
        for v in vectors:
            for i, x in enumerate(v):
                if abs(float(x)) < 1e-10 * scale:
                    v[i] = 0.0
    return expected


def toml_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    return str(v)


def case_toml(name: str, deck_file: str, source: str, fields: dict) -> str:
    expected = snapped(fields["expected"])
    out = [f'title = "{fields["title"]}"', f'source = "{source}"', 'units = "mm-MPa"', "", "[mesh]", f'deck = "../decks/{deck_file}"', "", "[expected]",
           f"tolerance = {toml_value(expected['tolerance'])}"]
    for group, rows_ in expected.items():
        if group == "tolerance":
            continue
        if group == "ply_stress_local":
            for element, plies in rows_.items():
                out.append(f'[expected.{group}."{element}"]')
                out += [f'"{ply}" = {toml_value(v)}' for ply, v in plies.items()]
            continue
        out.append(f"[expected.{group}]")
        out += [f'"{label}" = {toml_value(v)}' for label, v in rows_.items()]
    return "\n".join(out) + "\n"


def convergence() -> None:
    """The centre deflection and the centre-element moment of the three plates on 8, 16 and 32 elements a side, against the closed forms."""
    import tempfile

    from anisotropy_fea.abaqus_reader import read_deck
    from anisotropy_fea.kernel import solve_deck

    a, q0 = 100.0, 0.01
    plates = []
    for h in (1.0, 0.1):
        D, H = isotropic_section(E_NOMINAL, NU_NOMINAL, h)
        section = f"*Shell Section, elset=All, material=Nominal-Alloy\n{h:g}, 5\n"
        material = f"*Material, name=Nominal-Alloy\n*Elastic\n{E_NOMINAL:g}, {NU_NOMINAL:g}\n"
        plates.append((f"isotropic h/a = {h / a:g}, uniform", D, H, ("uniform", q0), section, material, -q0))
    D, H, _ = laminate_section([0.0, 90.0, 90.0, 0.0], IM7["ply"], IM7)
    section = ("*Orientation, name=Ori-1\n1., 0., 0., 0., 1., 0.\n3, 0.\n*Shell Section, elset=All, composite, orientation=Ori-1, layup=Layup-1, symmetric\n"
               + "".join(f"{IM7['ply']}, 3, IM7-8552, {angle:g}., Ply-{k}\n" for k, angle in enumerate((0.0, 90.0), start=1)))
    material = f"*Material, name=IM7-8552\n*Elastic, type=LAMINA\n{IM7['E1']}, {IM7['E2']}, {IM7['nu12']}, {IM7['G12']}, {IM7['G13']}, {IM7['G23']}\n"
    alpha = math.pi / a

    def sinusoidal(x0, x1, y0, y1):
        return -q0 * (math.cos(alpha * x0) - math.cos(alpha * x1)) / (alpha * (x1 - x0)) * (math.cos(alpha * y0) - math.cos(alpha * y1)) / (alpha * (y1 - y0))

    plates.append(("IM7/8552 [0/90]s, sinusoidal", D, H, ("sinusoidal", q0), section, material, sinusoidal))
    print("mesh      w centre: kernel, closed form, error      Mx at the centre element: kernel, closed form, error")
    for title, D, H, load, section, material, pressure in plates:
        print(title)
        for n in (8, 16, 32):
            text, centre, _, centre_element = plate_deck(n, n, a, a, section, material, ["convergence run"], pressure)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "plate.inp"
                path.write_text(text, encoding="utf-8")
                deck = read_deck(path, "mm-MPa")
                solution = solve_deck(deck)
            xc = a / 2.0 + a / (2.0 * n)
            w_exact = navier_fields(D, H, a, a, load, a / 2.0, a / 2.0)["w"]
            m_exact = navier_fields(D, H, a, a, load, xc, xc)["Mx"]
            w_fe = solution.displacement[deck_node(deck, solution, "Plate-1", centre)][2] * 1e3
            m_fe = solution.moment[solution.mesh.element(("Plate-1", centre_element))][0]
            print(f"  {n:2d}x{n:<2d}  {w_fe:12.6g} {w_exact:12.6g} {(w_fe - w_exact) / w_exact * 100:+7.3f} %      "
                  f"{m_fe:12.6g} {m_exact:12.6g} {(m_fe - m_exact) / m_exact * 100:+7.3f} %")


def deck_node(deck, solution, instance: str, label: int) -> int:
    return solution.mesh.node((instance, label))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="rewrite the decks and the cases")
    parser.add_argument("--converge", action="store_true", help="print the convergence table of the three plates instead")
    args = parser.parse_args()
    if args.converge:
        convergence()
        return
    for name, (deck_file, text, source, fields) in build_cases().items():
        deck_path = paths.CHECK_DECKS / deck_file
        case_path = paths.CASES / f"{name}.toml"
        if args.write:
            deck_path.write_text(text, encoding="utf-8", newline="\n")
            case_path.write_text(case_toml(name, deck_file, source, fields), encoding="utf-8", newline="\n")
            print("written", deck_path.name, "and", case_path.name)
        if not case_path.is_file():
            print(name, ": no case written yet; run with --write")
            continue
        comparisons, problems = compare(load_case(case_path))
        worst = max((abs(c.engine - c.expected) / c.allowed for c in comparisons), default=0.0)
        print(f"{name}: {len(comparisons)} numbers, worst at {worst:.2f} of the tolerance" + (f"; problems: {problems}" if problems else ""))
        for c in comparisons:
            rel = (c.engine - c.expected) / c.expected * 100 if c.expected else float("nan")
            print(f"  {c.key:48s} closed form {c.expected:14.8g}  kernel {c.engine:14.8g}  {rel:+8.3f} %  {'ok' if c.agrees else 'OUTSIDE'}")


if __name__ == "__main__":
    main()
