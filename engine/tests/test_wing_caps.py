"""Spar caps and layups that change along the span (ADR-0125): the description refuses what cannot be built, the section with caps
is worked by hand on a flat-sided box and holds equilibrium on a curved one, the span is cut where a layup changes, and the beam,
the stations and the ply drop rules follow."""

import math

import numpy as np
import pytest

from anisotropy_engine.wing import analyze_wing, box_section, wing_from_dict, wing_report, wing_views
from anisotropy_engine.wing.analysis import BEAM_ELEMENTS, Stretch, _beam_nodes, aeroelastic_checks, bending_frequency, stations_of
from anisotropy_engine.wing.description import SpanSegment, span_segments
from anisotropy_engine.wing.wing_file import wing_rules
from anisotropy_engine.units import FOOT, LBF
from test_wing import example, flat_sided

CAPS = {"front_width": 0.045, "rear_width": 0.045, "half_stack": [0, 0, 45, -45, 0]}
SOLID_SKIN = {"skin.core": None, "skin.core_thickness": None}  # a skin of plies only, so the flat box can be summed by hand


def capped(caps: dict | None = None, **changes) -> dict:
    data = example(**changes)
    data["spar_caps"] = dict(CAPS if caps is None else caps)
    return data


def zoned(**zones) -> dict:
    """The example with spar caps and, for each part named, its zones: part=[(start, end, half_stack), ...]."""
    data = capped()
    for part, stretches in zones.items():
        table = data["spar_caps"] if part == "spar_caps" else data[part]
        table["zones"] = [{"start": a, "end": b, "half_stack": stack} for a, b, stack in stretches]
    return data


# ----------------------------------------------------------------------------------------------- the description

@pytest.mark.parametrize("data, message", [
    (zoned(skin=[(0.0, 0.5, [0, 45]), (0.4, 0.8, [0])]), "Two zones overlap: 0 to 0.5 and 0.4 to 0.8"),
    (zoned(skin=[(0.6, 0.4, [0])]), r"0 <= start < end <= 1; got 0.6 to 0.4"),
    (zoned(skin=[(0.0, 1.2, [0])]), r"0 <= start < end <= 1"),
    (zoned(skin=[(0.0, 0.4, [])]), "at least one ply"),
    (zoned(rib=[(0.0, 0.4, [0])]), "A rib stands at one station: it has no zones along the span"),
    (zoned(skin=[(0.0, "40 %", [0])]), "end is a fraction of the half span"),
    (capped({**CAPS, "front_width": 0.2, "rear_width": 0.18}), "The spar caps meet between the spars"),  # halves 0.19 m, the box 0.18 m
    (capped({**CAPS, "front_width": 0.3, "rear_width": 0.01}), "The front spar cap reaches the leading edge"),
    (capped({**CAPS, "front_width": 0.01, "rear_width": 0.33}), "The rear spar cap reaches the trailing edge"),
    (capped({**CAPS, "core": "divinycell-h45"}), r"\[spar_caps\] has unknown keys core"),
    (capped({"front_width": 0.045, "half_stack": [0]}), r"\[spar_caps\] is missing rear_width"),
])
def test_a_cap_or_zone_that_cannot_be_built_is_refused_by_name(data, message):
    with pytest.raises(ValueError, match=message):
        wing_from_dict(data)


def test_a_cap_too_wide_for_the_airfoil_where_it_lies_is_refused():
    wing, _ = wing_from_dict(capped({**CAPS, "front_width": 0.2, "half_stack": [0] * 80}))  # 29 mm thick, the nose 25 mm at its edge
    with pytest.raises(ValueError, match="The front spar cap reaches where the airfoil is thinner than the cap: make it narrower"):
        box_section(wing)


def test_a_layup_is_its_zones_and_its_own_stack_between_them_and_like_neighbours_are_one_stretch():
    wing, _ = wing_from_dict(zoned(skin=[(0.6, 0.8, [0, 45, -45]), (0.2, 0.4, [0, 0, 45, -45, 0]), (0.4, 0.6, [0, 45, -45, 0])]))
    assert [z.start for z in wing.skin.zones] == [0.2, 0.4, 0.6]  # kept in order from the root
    stretches = [(a, b, layup.half_stack_deg) for a, b, layup in wing.skin.stretches()]
    assert stretches == [(0.0, 0.2, (0, 45, -45, 0)), (0.2, 0.4, (0, 0, 45, -45, 0)), (0.4, 0.6, (0, 45, -45, 0)),
                         (0.6, 0.8, (0, 45, -45)), (0.8, 1.0, (0, 45, -45, 0))]
    assert all(not layup.zones and layup.core == wing.skin.core for _, _, layup in wing.skin.stretches())  # its core in every stretch
    same, _ = wing_from_dict(zoned(skin=[(0.0, 0.5, [0, 45, -45, 0])]))  # a zone of the part's own stack changes nothing
    assert len(same.skin.stretches()) == 1 and len(span_segments(same)) == 1


def test_the_span_is_cut_wherever_any_part_changes_and_nowhere_else():
    wing, _ = wing_from_dict(zoned(skin=[(0.0, 0.25, [0, 0, 45, -45, 0])], spar_caps=[(0.0, 0.5, [0, 0, 0, 45, -45, 0])],
                                   spar=[(0.0, 0.25, [45, -45, 0, 0, 0])]))
    segments = span_segments(wing)
    assert [(s.start_m, s.end_m) for s in segments] == [(0.0, 0.5), (0.5, 1.0), (1.0, 2.0)]  # metres: 25 % and 50 % of 2 m
    assert [s.skin.half_stack_deg for s in segments] == [(0, 0, 45, -45, 0), (0, 45, -45, 0), (0, 45, -45, 0)]
    assert [s.cap.half_stack_deg for s in segments] == [(0, 0, 0, 45, -45, 0)] * 2 + [(0, 0, 45, -45, 0)]
    plain, _ = wing_from_dict(example())
    assert [(s.start_m, s.end_m, s.cap) for s in span_segments(plain)] == [(0.0, 2.0, None)]


# ----------------------------------------------------------------------------------------------- the section with caps

def test_a_flat_box_with_caps_sums_by_hand_strip_by_strip():
    wing, _ = wing_from_dict(capped(**{"geometry.airfoil": flat_sided(), **SOLID_SKIN}))
    section = box_section(wing)
    skin, cap, spar = section.skin, section.cap, section.spar
    half = 0.06 * 0.45  # the airfoil's half height where the box is
    z_skin, z_cap = half - skin.thickness_m / 2, half - cap.thickness_m / 2  # each at its own mid-surface under the surface
    caps_width = 0.045 + 0.045  # each cap's full width, inside and outside the box, on each skin
    panel = 0.4 * 0.45 - caps_width / 2  # the skin between the caps' inner edges
    assert section.skin_panel_widths_m == pytest.approx((panel, panel), rel=1e-12)
    assert section.spar_heights_m == pytest.approx((2 * z_cap, 2 * z_cap), rel=1e-12)  # the webs run between the caps
    Et = {name: m.Ex * m.thickness_m for name, m in (("skin", skin), ("cap", cap), ("spar", spar))}
    EI = 2 * (Et["skin"] * panel * z_skin**2 + Et["cap"] * caps_width * z_cap**2) + 2 * Et["spar"] * (2 * z_cap) ** 3 / 12
    assert section.centroid_m == pytest.approx(0, abs=1e-12)
    assert section.EI == pytest.approx(EI, rel=1e-12)  # the steps between the cap and the skin carry no spanwise load
    # The cell: the caps' inner halves at their height, the skin at its, and a straight step between them at each cap's edge.
    area = 2 * (z_cap * caps_width / 2 + z_skin * panel)
    steps = 4 * abs(z_skin - z_cap)
    loop = (2 * caps_width / 2 / (cap.Gxy * cap.thickness_m) + 2 * panel / (skin.Gxy * skin.thickness_m) + steps / (skin.Gxy * skin.thickness_m)
            + 2 * (2 * z_cap) / (spar.Gxy * spar.thickness_m))
    assert section.enclosed_area_m2 == pytest.approx(area, rel=1e-12)
    assert section.GJ == pytest.approx(4 * area**2 / loop, rel=1e-12)
    density = wing.skin.material.density_kg_m3
    assert section.mass_caps_kg_m == pytest.approx(2 * caps_width * cap.thickness_m * density, rel=1e-12)
    assert section.mass_skins_kg_m == pytest.approx(2 * panel * skin.thickness_m * density, rel=1e-12)
    assert section.mass_spars_kg_m == pytest.approx(2 * (2 * z_cap) * spar.thickness_m * density, rel=1e-12)
    assert section.mass_core_kg_m == 0


def walk(section):
    """The cell's sets in the order of its axis with the steps between them put back (straight, the flow constant along them, as a
    step's laminate carries no spanwise load), then the flanges: (x, z, flow) of each."""
    cell = [s for s in section.point_sets if s.in_cell]
    pieces = []
    for k, s in enumerate(cell):
        pieces.append((s.x_m, s.z_m, s.flow_per_shear))
        after = cell[(k + 1) % len(cell)]
        if s.wall == after.wall and (s.x_m[-1], s.z_m[-1]) != (after.x_m[0], after.z_m[0]):
            pieces.append((np.array([s.x_m[-1], after.x_m[0]]), np.array([s.z_m[-1], after.z_m[0]]), np.full(2, s.flow_per_shear[-1])))
    return pieces + [(s.x_m, s.z_m, s.flow_per_shear) for s in section.point_sets if not s.in_cell]


@pytest.mark.parametrize("airfoil", ["naca-2412", "naca-0012"])
def test_the_shear_flow_with_caps_carries_the_shear_at_the_shear_center_and_vanishes_at_each_flanges_edge(airfoil):
    wing, _ = wing_from_dict(capped({**CAPS, "front_width": 0.05, "rear_width": 0.04}, **{"geometry.airfoil": airfoil}))
    section = box_section(wing)
    fx = fz = moment = 0.0
    for x, z, q in walk(section):
        dx, dz, mean = np.diff(x), np.diff(z), (q[1:] + q[:-1]) / 2
        fx, fz = fx + (mean * dx).sum(), fz + (mean * dz).sum()
        moment += (mean * (z[:-1] * dx - x[:-1] * dz)).sum()
    # The trapezoid rule on a flow that is quadratic along each piece: about 0.1 % here.
    assert fx == pytest.approx(0.0, abs=2e-3) and fz == pytest.approx(1.0, abs=2e-3)
    assert -moment == pytest.approx(section.shear_center_m, rel=2e-3)
    flanges = [s for s in section.point_sets if not s.in_cell]
    assert [s.label for s in flanges] == ["upper rear spar cap", "upper front spar cap", "lower front spar cap", "lower rear spar cap"]
    edges = [flanges[0].flow_per_shear[0], flanges[1].flow_per_shear[-1], flanges[2].flow_per_shear[0], flanges[3].flow_per_shear[-1]]
    assert edges == pytest.approx([0.0] * 4, abs=1e-12)  # no flow at a free edge


@pytest.mark.parametrize("airfoil", ["naca-2412", "naca-0012"])
def test_the_bending_load_with_caps_sums_to_the_moment_and_to_no_force(airfoil):
    section = box_section(wing_from_dict(capped(**{"geometry.airfoil": airfoil}))[0])
    force = moment_z = moment_x = 0.0
    for s in section.point_sets:  # the flanges carry their part too; the steps carry none
        length = np.hypot(np.diff(s.x_m), np.diff(s.z_m))
        n = s.load_per_moment

        def exact(g, n=n, length=length):  # both linear along each straight piece: the rule is exact
            return (length * (2 * n[:-1] * g[:-1] + n[:-1] * g[1:] + n[1:] * g[:-1] + 2 * n[1:] * g[1:]) / 6).sum()

        force += exact(np.ones_like(s.x_m))
        moment_z += exact(s.z_m - section.centroid_m)
        moment_x += exact(s.x_m - section.centroid_x_m)
    assert force == pytest.approx(0, abs=1e-9)
    assert moment_z == pytest.approx(-1, rel=1e-12)
    assert moment_x == pytest.approx(0, abs=1e-12)


def test_caps_stiffen_the_box_taller_webs_and_a_narrower_skin_panel():
    plain, with_caps = (box_section(wing_from_dict(data)[0]) for data in (example(), capped()))
    assert with_caps.EI > 1.3 * plain.EI  # two more 0° plies over the webs, where the bending strains most
    assert min(with_caps.spar_heights_m) > min(plain.spar_heights_m)  # a solid cap is thinner than the cored skin, so nearer the surface
    assert max(with_caps.skin_panel_widths_m) < max(plain.skin_panel_widths_m) - 0.04
    assert with_caps.skin_widths_m == pytest.approx(plain.skin_widths_m, rel=0.02)  # caps included, much the same length round the curve
    assert plain.cap is None and plain.mass_caps_kg_m == 0 and with_caps.mass_caps_kg_m > 0


# ----------------------------------------------------------------------------------------------- along the span

def test_a_wing_that_changes_along_the_span_has_a_section_per_stretch_and_its_stations_on_both_sides_of_each_change():
    result = analyze_wing(*wing_from_dict(zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])))
    assert [(s.segment.start_m, s.segment.end_m) for s in result.stretches] == [(0.0, 0.8), (0.8, 2.0)]
    assert result.stretches[0].section.EI > result.stretches[1].section.EI
    y, which = stations_of(result.stretches, 2.0, 51)
    assert y.size == 52 and list(y[which == 0][-1:]) == [0.8] and list(y[which == 1][:1]) == [0.8]  # the change twice, inboard first
    assert np.all(np.diff(y) >= 0)
    assert result.cases[0].stations.y.size == 52
    plain = analyze_wing(*wing_from_dict(example()))
    y, which = stations_of(plain.stretches, 2.0, 51)
    assert y == pytest.approx(np.linspace(0, 2, 51), abs=0) and not which.any()  # a uniform wing: the even stations exactly
    assert plain.mass_kg() == pytest.approx(plain.stretches[0].section.mass_per_length_kg_m * 2.0, rel=1e-12)
    assert result.mass_kg() == pytest.approx(sum(s.section.mass_per_length_kg_m * s.length_m for s in result.stretches), rel=1e-12)
    assert result.mass_kg("caps") + result.mass_kg("skins") + result.mass_kg("spars") + result.mass_kg("core") == pytest.approx(result.mass_kg())


def test_the_caps_plies_are_checked_where_they_are():
    result = analyze_wing(*wing_from_dict(capped({**CAPS, "half_stack": [45, -45]})))  # caps weaker than the skin along the span
    labels = {check.member for case in result.cases for check in case.checks[:1] if check.member}
    assert labels & {"upper front spar cap", "upper rear spar cap", "lower front spar cap", "lower rear spar cap"}


def test_the_beam_of_a_wing_cut_into_stretches_of_one_section_gives_the_closed_form():
    wing, _ = wing_from_dict(example())
    section = box_section(wing)
    for cut in (0.4, 0.37, 0.123456):
        a, b = SpanSegment(0.0, 2 * cut, wing.skin, wing.spar, None), SpanSegment(2 * cut, 2.0, wing.skin, wing.spar, None)
        beam = bending_frequency((Stretch(a, section), Stretch(b, section)), 2.0)
        assert beam == pytest.approx(section.first_bending_frequency_Hz, rel=2e-6)  # round-off of the eigenvalue, not the elements


def test_a_stiffer_root_raises_the_frequency_and_the_beam_keeps_no_sliver_of_an_element():
    plain = analyze_wing(*wing_from_dict(capped()))
    root = analyze_wing(*wing_from_dict(zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])))
    tip = analyze_wing(*wing_from_dict(zoned(spar_caps=[(0.6, 1.0, [0, 0, 0, 45, -45, 0])])))
    assert root.first_bending_frequency_Hz > plain.first_bending_frequency_Hz > tip.first_bending_frequency_Hz  # stiffness counts most at the root
    assert plain.first_bending_frequency_Hz == plain.section.first_bending_frequency_Hz
    for changes in ([0.8], [0.8, 0.80001], [0.123456, 0.5], [0.0051], [1.995]):
        nodes = _beam_nodes(changes, 2.0)
        assert nodes[0] == 0 and nodes[-1] == 2.0 and np.diff(nodes).min() >= 0.25 * 2.0 / BEAM_ELEMENTS
        assert changes[0] in nodes or changes[0] < 0.25 * 2.0 / BEAM_ELEMENTS or 2.0 - changes[0] < 0.25 * 2.0 / BEAM_ELEMENTS


def test_divergence_and_reversal_of_a_changing_wing_are_the_weakest_stretchs():
    result = analyze_wing(*wing_from_dict(zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])))
    each = [aeroelastic_checks(result.wing, result.envelope, s.section) for s in result.stretches]
    assert result.aeroelastic.divergence_dynamic_pressure_Pa == min(a.divergence_dynamic_pressure_Pa for a in each)
    assert result.aeroelastic.reversal_dynamic_pressure_Pa == min(a.reversal_dynamic_pressure_Pa for a in each)


# ----------------------------------------------------------------------------------------------- the file, the rules and the page

def test_a_wing_with_caps_and_zones_in_us_units_is_the_same_wing():
    si = analyze_wing(*wing_from_dict(zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])))
    data = zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])
    data["units"] = "US"
    inch = 0.0254
    data["geometry"] |= {"half_span": 2.0 / inch, "chord": 0.45 / inch, "rib_spacing": 0.5 / inch}
    data["skin"]["core_thickness"] = 6.0 / 25.4
    data["spar_caps"] |= {"front_width": 0.045 / inch, "rear_width": 0.045 / inch}
    data["envelope"] |= {"gross_weight": 3000.0 / LBF, "altitudes": [0.0, 3000.0 / FOOT]}
    data["envelope"]["aileron"] |= {"span_start": 1.2 / inch, "span_end": 1.9 / inch}
    data["envelope"]["gust"]["wing_area"] = 1.8 / inch**2
    us = analyze_wing(*wing_from_dict(data))
    assert [s.section.EI for s in us.stretches] == pytest.approx([s.section.EI for s in si.stretches], rel=1e-12)
    assert [c.governing.margin_ultimate for c in us.cases] == pytest.approx([c.governing.margin_ultimate for c in si.cases], rel=1e-9)
    rules = {(r["part"], r["rule"]): r for r in wing_rules(us.wing, "US") if r["at"] is not None}
    ratio = rules["cap", "drop_ratio"]
    assert ratio["detail"]["run_out_m"] == pytest.approx(20 * 2 * 0.18288e-3, rel=1e-12)  # 20 times the two plies that end
    assert ratio["words"] == "The plies ending at 40 % of the span need 0.288 in of run-out at 20 to 1; the thicker side runs 31.5 in."


def test_the_rules_come_for_each_stretch_of_each_part_and_at_each_change():
    wing, _ = wing_from_dict(zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])], skin=[(0.5, 1.0, [45, -45, 0])]))
    rules = wing_rules(wing)
    where = [(r["part"], tuple(r["span"]) if r["span"] else r["at"]) for r in rules]
    assert sorted(set(where), key=where.index) == [("skin", (0.0, 0.5)), ("skin", (0.5, 1.0)), ("skin", 0.5), ("spar", (0.0, 1.0)),
                                                   ("cap", (0.0, 0.4)), ("cap", (0.4, 1.0)), ("cap", 0.4), ("rib", (0.0, 1.0))]
    assert len(rules) == 6 * 4 + 2 * 3
    drop = {r["rule"]: r for r in rules if r["part"] == "cap" and r["at"] == 0.4}
    assert all(r["met"] for r in drop.values())
    assert drop["drop_ratio"]["words"] == "The plies ending at 40 % of the span need 7.32 mm of run-out at 20 to 1; the thicker side runs 800 mm."
    cut = {r["rule"]: r for r in rules if r["part"] == "skin" and r["at"] == 0.5}
    assert cut["drop_cover"]["met"] is False  # the skin's outside ply, a 0°, ends at 50 %: [0/45/-45/0] to [45/-45/0]
    assert "The outside ply ends at 50 % of the span" in cut["drop_cover"]["words"]


def test_the_report_and_the_drawings_of_a_wing_with_caps():
    data = zoned(spar_caps=[(0.0, 0.4, [0, 0, 0, 45, -45, 0])])
    result = analyze_wing(*wing_from_dict(data))
    report, views = wing_report(result, "SI", "m/s"), wing_views(result, "SI")
    design = report["design"]
    assert design["mass"] == pytest.approx(result.mass_kg()) and design["mass_caps"] == pytest.approx(result.mass_kg("caps"))
    assert design["first_bending_frequency"] == result.first_bending_frequency_Hz
    assert [(s["start"], s["end"]) for s in design["stretches"]] == [(0.0, 0.8), (0.8, 2.0)]
    assert design["cap_thickness"] == pytest.approx(result.section.cap.thickness_m * 1e3)  # mm, the root's
    assert report["rule_limits"] == {"min_percent": 10.0, "max_in_a_row": 4, "drop_ratio": 20.0, "max_dropped": 2}
    assert views["changes"] == [0.8]
    caps = {c["name"]: c for c in views["caps"]}
    front = result.wing.cap_edges_m[:2]
    assert min(caps["upper front spar cap"]["x"]) == pytest.approx(front[0], rel=1e-3)
    assert max(caps["upper front spar cap"]["x"]) == pytest.approx(front[1], rel=1e-3)
    assert all(np.all(np.diff(c["x"]) > 0) for c in views["caps"])  # fore to aft, the web's point once
    assert math.isfinite(report["aeroelastic"]["divergence_speed"])
