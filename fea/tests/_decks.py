"""Deck text generators for tests: the fixture coupons on any mesh, so refinement can be checked."""

from __future__ import annotations

LAYERS = "\n".join(f"0.18288, 3, IM7-8552, {angle}, Ply-{i}" for i, angle in enumerate(("0.", "45.", "-45.", "45.", "0."), start=1))
MATERIAL = "*Material, name=IM7-8552\n*Elastic, type=LAMINA\n162095.74, 8963.18, 0.316, 4688.43, 4688.43, 3000.\n*Fail Stress\n2558.51, -1731.48, 64.05, -285.72, 91.15, 0.\n"


def _grid(nx: int, ny: int, width: float, height: float) -> tuple[list[str], list[str], list[int], list[int]]:
    label = lambda i, j: 1 + i + (nx + 1) * j
    nodes = [f"{label(i, j)}, {width * i / nx:.10g}, {height * j / ny:.10g}, 0." for j in range(ny + 1) for i in range(nx + 1)]
    elements = [f"{1 + i + nx * j}, {label(i, j)}, {label(i + 1, j)}, {label(i + 1, j + 1)}, {label(i, j + 1)}"
                for j in range(ny) for i in range(nx)]
    bottom = [label(i, 0) for i in range(nx + 1)]
    top = [label(i, ny) for i in range(nx + 1)]
    return nodes, elements, bottom, top


def edge_coupon(nx: int, ny: int, pull_mm: float = 0.8, width: float = 10.0, height: float = 80.0) -> str:
    """The free-lateral-edge coupon: bottom edge held in y, corner held in x, top edge moved pull_mm in y."""
    nodes, elements, bottom, top = _grid(nx, ny, width, height)
    return (
        "*Heading\n*Part, name=Coupon\n*Node\n" + "\n".join(nodes) + "\n*Element, type=S4R\n" + "\n".join(elements) + "\n"
        f"*Elset, elset=All, generate\n1, {nx * ny}, 1\n*Orientation, name=Ori-1\n1., 0., 0., 0., 1., 0.\n3, 0.\n"
        "*Shell Section, elset=All, composite, orientation=Ori-1, layup=Layup-1, symmetric\n" + LAYERS + "\n*End Part\n"
        "*Assembly, name=Assembly\n*Instance, name=Coupon-1, part=Coupon\n*End Instance\n"
        f"*Nset, nset=Bottom, instance=Coupon-1\n{', '.join(map(str, bottom))}\n"
        f"*Nset, nset=Top, instance=Coupon-1\n{', '.join(map(str, top))}\n"
        "*Nset, nset=Corner, instance=Coupon-1\n1,\n*End Assembly\n" + MATERIAL +
        f"*Step, name=Step-1, nlgeom=NO\n*Static\n1., 1., 1e-05, 1.\n*Boundary\nBottom, 2, 2\n*Boundary\nCorner, 1, 1\n"
        f"*Boundary\nTop, 2, 2, {pull_mm}\n*End Step\n"
    )


def gripped_coupon(nx: int, ny: int, pull_mm: float = 0.8, width: float = 10.0, height: float = 80.0) -> str:
    """The team's structure: both end edges coupled to reference nodes; bottom encastre, top pulled pull_mm in y."""
    nodes, elements, bottom, top = _grid(nx, ny, width, height)
    return (
        "*Heading\n*Part, name=CFRP-Coupon\n*Node\n" + "\n".join(nodes) + "\n*Element, type=S4R\n" + "\n".join(elements) + "\n"
        f"*Elset, elset=CompositeLayup-1-1, generate\n1, {nx * ny}, 1\n*Orientation, name=Ori-1\n1., 0., 0., 0., 1., 0.\n3, 0.\n"
        "*Shell Section, elset=CompositeLayup-1-1, composite, orientation=Ori-1, layup=CompositeLayup-1, symmetric\n" + LAYERS + "\n*End Part\n"
        "*Assembly, name=Assembly\n*Instance, name=CFRP-Coupon-1, part=CFRP-Coupon\n*End Instance\n"
        f"*Node\n1, {width / 2:.10g}, {height:.10g}, 0.\n*Node\n2, {width / 2:.10g}, 0., 0.\n"
        "*Nset, nset=RF-Top\n1,\n*Nset, nset=RF-Bottom\n2,\n*Nset, nset=Set-Encastre\n2,\n*Nset, nset=Set-TopFix\n1,\n*Nset, nset=Set-TopPull\n1,\n"
        f"*Nset, nset=s_Top, instance=CFRP-Coupon-1\n{', '.join(map(str, top))}\n"
        f"*Nset, nset=s_Bottom, instance=CFRP-Coupon-1\n{', '.join(map(str, bottom))}\n"
        "*Surface, type=NODE, name=s_Top_CNS_, internal\ns_Top, 1.\n*Surface, type=NODE, name=s_Bottom_CNS_, internal\ns_Bottom, 1.\n"
        "*Coupling, constraint name=Grip-Top, ref node=RF-Top, surface=s_Top_CNS_\n*Kinematic\n"
        "*Coupling, constraint name=Grip-Bottom, ref node=RF-Bottom, surface=s_Bottom_CNS_\n*Kinematic\n*End Assembly\n" + MATERIAL +
        "*Step, name=Step-1, nlgeom=NO\n*Static\n1., 1., 1e-05, 1.\n*Boundary\nSet-Encastre, ENCASTRE\n*Boundary\n"
        "Set-TopFix, 1, 1\nSet-TopFix, 3, 3\nSet-TopFix, 4, 4\nSet-TopFix, 5, 5\nSet-TopFix, 6, 6\n"
        f"*Boundary\nSet-TopPull, 2, 2, {pull_mm}\n*End Step\n"
    )
