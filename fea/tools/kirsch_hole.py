"""The Kirsch closed form at the probe elements of an open-hole spec, beside the kernel's values: the source of the Kirsch validation case.

    uv run python tools/kirsch_hole.py checks/open-hole-isotropic-kirsch/open-hole-isotropic-kirsch.toml
    uv run python tools/kirsch_hole.py checks/open-hole-isotropic-kirsch/open-hole-isotropic-kirsch.toml --element-size 1.5 --circumferential 72 --radial-layers 12

An infinite isotropic plate with a circular hole of radius a under a uniform far-field stress sigma along y has, in polar
components about the hole centre with theta measured from the loading axis (Timoshenko and Goodier, Theory of Elasticity,
chapter 4, the article on the effect of circular holes on stress distributions in plates; the article number is not
checked against a copy here):

    sigma_rr     = sigma/2 (1 - a^2/r^2) + sigma/2 (1 - 4 a^2/r^2 + 3 a^4/r^4) cos 2 theta
    sigma_thth   = sigma/2 (1 + a^2/r^2) - sigma/2 (1 + 3 a^4/r^4) cos 2 theta
    tau_rth      = -sigma/2 (1 + 2 a^2/r^2 - 3 a^4/r^4) sin 2 theta

so sigma_thth = 3 sigma beside the hole on the axis perpendicular to the load and -sigma at the top and bottom of the hole.
The far-field stress of a force-controlled spec is F / (w h) on the gross section. The plate's finite width and length are
not in the closed form; the spec keeps them small (d/w = 0.05, length 3 w) and the table shows what remains together with
the discretisation error of the bilinear element's centroid value. The mesh overrides serve the convergence study.
"""

from __future__ import annotations

import argparse
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.recovery import element_ply_states  # noqa: E402
from anisotropy_fea.spec import CouponSpec, SpecError, full_angles, parse_spec, spec_ply_thickness, to_si, validate_spec  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402


def kirsch_polar(sigma: float, a: float, r: float, theta: float) -> tuple[float, float, float]:
    """(sigma_rr, sigma_thth, tau_rth) at radius r and angle theta from the loading axis."""
    q2, q4 = (a / r) ** 2, (a / r) ** 4
    c, s = math.cos(2 * theta), math.sin(2 * theta)
    return (sigma / 2 * (1 - q2) + sigma / 2 * (1 - 4 * q2 + 3 * q4) * c,
            sigma / 2 * (1 + q2) - sigma / 2 * (1 + 3 * q4) * c,
            -sigma / 2 * (1 + 2 * q2 - 3 * q4) * s)


def kirsch_xy(sigma: float, a: float, x: float, y: float, centre: tuple[float, float]) -> tuple[float, float, float]:
    """(sigma_xx, sigma_yy, tau_xy) at the point (x, y) for the far-field stress sigma along y."""
    dx, dy = x - centre[0], y - centre[1]
    r, alpha = math.hypot(dx, dy), math.atan2(dy, dx)  # alpha from the x axis; the loading axis y is at alpha = 90 degrees
    rr, tt, rt = kirsch_polar(sigma, a, r, alpha - math.pi / 2)
    c, s = math.cos(alpha), math.sin(alpha)
    return (rr * c * c + tt * s * s - 2 * rt * s * c,
            rr * s * s + tt * c * c + 2 * rt * s * c,
            (rr - tt) * s * c + rt * (c * c - s * s))


def spec_with_mesh(text: str, path: str, element_size: float | None, circumferential: int | None, radial_layers: int | None,
                   growth: float | None) -> CouponSpec:
    spec = parse_spec(text, source_path=path)
    hole = spec.mesh.hole.model_copy(update={k: v for k, v in (("circumferential", circumferential), ("radial_layers", radial_layers), ("growth", growth)) if v is not None})
    mesh = spec.mesh.model_copy(update={"hole": hole, **({"element_size": element_size} if element_size is not None else {})})
    spec = spec.model_copy(update={"mesh": mesh})
    validate_spec(spec)
    return to_si(spec)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--element-size", type=float, default=None, help="in the spec's units")
    parser.add_argument("--circumferential", type=int, default=None)
    parser.add_argument("--radial-layers", type=int, default=None)
    parser.add_argument("--growth", type=float, default=None)
    args = parser.parse_args()
    try:
        spec = spec_with_mesh(args.spec.read_text(encoding="utf-8"), str(args.spec), args.element_size, args.circumferential, args.radial_layers, args.growth)
    except SpecError as exc:
        raise SystemExit(f"spec refused: {exc}") from None
    if spec.kind != "open_hole_tension" or spec.loading.control != "force" or spec.material.library is not None or spec.material.E1 != spec.material.E2:
        raise SystemExit("the Kirsch form needs an isotropic open_hole_tension spec with explicit constants under force control")
    units = spec.units
    model = build_model(spec)
    g = spec.geometry
    thickness = spec_ply_thickness(spec) * len(full_angles(spec))
    sigma = spec.loading.value / (g.width * thickness)  # Pa, gross section
    a, centre = g.hole_diameter / 2, (g.width / 2, g.length / 2)
    with tempfile.TemporaryDirectory() as folder:
        deck_path = Path(folder) / "kirsch.inp"
        deck_path.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
        deck = read_deck(deck_path, units)
    solution = solve_membrane(deck)
    field = element_ply_states(solution)
    centroids = model.mesh.centroids()
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    print(f"{spec.title}")
    print(f"mesh: {model.mesh.element_count} elements, {model.mesh.node_count} nodes (element_size {from_si(spec.mesh.element_size, 'length', units):g}, "
          f"circumferential {spec.mesh.hole.circumferential}, radial_layers {spec.mesh.hole.radial_layers}, growth {spec.mesh.hole.growth:g})")
    print(f"far-field stress sigma = F / (w h) = {stress(sigma):.6g}; hole radius a = {from_si(a, 'length', units):g}")
    rf = solution.reaction_of(deck.nsets["Grip-Bottom"])
    print(f"reaction at Grip-Bottom = [{from_si(rf[0], 'force', units):.6g}, {from_si(rf[1], 'force', units):.6g}] "
          f"(the applied force is {from_si(spec.loading.value, 'force', units):g}); largest free-dof residual {solution.free_residual:.3g} N")
    print(f"{'probe':12s} {'element':14s} {'centroid':24s} {'r/a':>7s} {'alpha':>7s}   {'Kirsch sxx syy txy':>32s}   {'kernel sxx syy txy':>32s}   {'(kernel - Kirsch) / sigma':>26s}")
    for name, index in model.probe_elements.items():
        x, y = centroids[index]
        label = f"{model.instance}.{index + 1}"
        r, alpha = math.hypot(x - centre[0], y - centre[1]), math.degrees(math.atan2(y - centre[1], x - centre[0]))
        reference = np.array(kirsch_xy(sigma, a, x, y, centre))
        kernel = field.stress_12[index][0]  # one ply at 0 degrees: material axes are the plate axes
        diff = (kernel - reference) / sigma
        fmt = lambda v: " ".join(f"{stress(c):10.4f}" for c in v)  # noqa: E731
        print(f"{name:12s} {label:14s} ({from_si(x, 'length', units):8.4f}, {from_si(y, 'length', units):8.4f}) {r / a:7.4f} {alpha:7.2f}   {fmt(reference)}   {fmt(kernel)}   "
              + " ".join(f"{100 * d:7.3f} %" for d in diff))
    print("\nTOML for the case (Kirsch values at the kernel's centroids, in the spec's stress units):")
    for name, index in model.probe_elements.items():
        x, y = centroids[index]
        reference = kirsch_xy(sigma, a, x, y, centre)
        print(f'[expected.ply_stress_local."{model.instance}.{index + 1}"]  # {name}: centroid ({from_si(x, "length", units):.6g}, {from_si(y, "length", units):.6g}), r/a {math.hypot(x - centre[0], y - centre[1]) / a:.5f}')
        print(f"1 = [{stress(reference[0]):.6g}, {stress(reference[1]):.6g}, {stress(reference[2]):.6g}]")


if __name__ == "__main__":
    main()
