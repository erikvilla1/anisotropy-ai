"""The team comparison: the team's Abaqus model against ours, item by item and side by side (ADR-0035, ADR-0041).

Not a document of its own: its sections are chapters of the coupon document (docs/models/coupon.py) and its files go in the
coupon's package folder. The manifest `.local/fea/<coupon>/ours/verification/team-comparison.toml` (format in `Manifest` below; every key
required, paths relative to the manifest) names the team's deck and field reports, our spec, the CalculiX record of our
twin, and the bands and points to compare. Every number is computed while the document is built: the equivalence from both
parsed decks (`anisotropy_fea.equivalence`), our results from the kernel on our generated deck, the pairing from the team's
reports (`anisotropy_fea.side_by_side`), the hand check from the engine. The reading beside the manifest
(`<manifest stem>.md`) is written by a person; without it the section says so. Everything stays under `.local/`: it carries
the team's results, which are theirs to publish (ADR-0035).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import math
import shutil
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, PositiveFloat, ValidationError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREAMBLE = (HERE / "preamble.tex").read_text(encoding="utf-8")
README_MARK = "Anisotropy AI share folder"  # first line of every README.txt in our packages; only such a package is ever replaced


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manual = load_module("anisotropy_manual_build", ROOT / "docs/manual/build.py")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm  # noqa: E402

from anisotropy_engine.library import library_material  # noqa: E402
from anisotropy_fea import paths as fea_paths  # noqa: E402  where the files live (ADR-0036)
from anisotropy_fea import __version__ as fea_version  # noqa: E402
from anisotropy_fea.abaqus_reader import parse_deck, read_deck  # noqa: E402
from anisotropy_fea.abaqus_report import FieldReport, read_field_report, write_field_report  # noqa: E402
from anisotropy_fea.equivalence import DeckEquivalence, deck_equivalence  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.model import expanded_layers, to_si  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, strength_ratios  # noqa: E402
from anisotropy_fea.report import laminate_check  # noqa: E402
from anisotropy_fea.side_by_side import Agreement, PairedValue, agreement, kernel_difference, pair_reports, ply_values  # noqa: E402
from anisotropy_fea.spec import coupon_card, load_spec, spec_material  # noqa: E402
from anisotropy_fea.units import from_si, to_si as value_to_si  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402

escape, code, inline, number = manual.escape, manual.code, manual.inline, manual.number
UNITS = {"mm-MPa": ("mm", "MPa", "N"), "m-Pa": ("m", "Pa", "N")}
QUANTITY_TITLE = {"S11": "S11, the ply stress along material direction 1 (across the width for these 0-degree plies)",
                  "S22": "S22, the ply stress along material direction 2 (along the pull for these 0-degree plies)",
                  "S12": "S12, the in-plane shear stress of the ply", "Mises": "The von Mises stress of the ply"}
SIGN_FLOOR = 1e-6  # a value below this share of the largest magnitude does not decide whether a map is one-signed (the rigid tabs carry roundoff)
INK, MUTED, GRID, EMPTY = "#1C1F22", "#5D636A", "#D9DCE0", "#F6F7F5"
SEQUENTIAL = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list("blue_grey_red", ["#1c5cab", "#86b6ef", "#f0efec", "#ec9b9a", "#c4302f"])


# --------------------------------------------------------------------------------------------- manifest

class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TeamSide(Record):
    deck: str  # the team's Abaqus deck
    solver: str  # what ran it, as the team states it
    run_by: str
    run_date: str
    reports: list[str]  # Abaqus/CAE field reports (CSV), one quantity each


class OurSide(Record):
    spec: str  # the spec our generator builds the model from
    calculix_record: str  # the committed CalculiX record of our twin (an independent second solver)


class Manifest(Record):
    name: str  # the coupon's name, as its folder; the title comes from the coupon card of our spec
    units: str  # the unit system of the team's deck and reports, and of the document
    node_tolerance: PositiveFloat  # length: a node of ours counts as at the team's position within this
    agreement: PositiveFloat  # fraction of a quantity's largest magnitude in a band within which two values "agree"
    edge_band: PositiveFloat  # length beside each tab line left out of the inner band (the tab-line corners are singular)
    map_layer: int  # the layer the maps show, 1 at the bottom
    locations: dict[str, tuple[float, float]]  # named points (x, y) at which the stress table compares
    team: TeamSide
    ours: OurSide


def load_manifest(path: Path) -> Manifest:
    try:
        manifest = Manifest(**tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise SystemExit(f"{path}: {exc}") from None
    if manifest.units not in UNITS:
        raise SystemExit(f"{path}: units must be one of {list(UNITS)}")
    if not manifest.locations:
        raise SystemExit(f"{path}: give at least one location")
    return manifest


def resolve(base: Path, relative: str, what: str) -> Path:
    path = (base / relative).resolve()
    if not path.exists():
        raise SystemExit(f"{what} not found: {path}")
    return path


# --------------------------------------------------------------------------------------------- small helpers

def sha256(path_or_text: Path | str) -> str:
    data = path_or_text.read_bytes() if isinstance(path_or_text, Path) else path_or_text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def git_commit() -> str:
    try:
        commit = manual.run("git", "rev-parse", "--short", "HEAD")
        if manual.run("git", "status", "--porcelain", "--untracked-files=no"):
            commit += " + local changes"
        return commit
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def source_text(lib) -> str:
    """The library's citation, led by the authors when the record names them."""
    return f"{lib.authors}, {lib.citation}" if lib.authors else lib.citation


def pct(fraction: float, digits: int = 2) -> str:
    return f"{100 * fraction:.{digits}f}" + r"\,\%"


def table(header: list[str], rows: list[list[str]], spec: str, size: str = r"\small") -> str:
    head = " & ".join(r"\textbf{" + h + "}" for h in header) + r" \\"
    body = [" & ".join(cells) + r" \\" for cells in rows]
    return "\n".join(["{" + size, rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", head, r"\midrule", r"\endhead",
                      *body, r"\bottomrule", r"\end{xltabular}", "}"])


def figure(path: Path, caption: str, width: str = r"\linewidth") -> str:
    return "\n".join([r"\begin{figure}[H]", r"\centering", rf"\includegraphics[width={width}]{{figures/{path.name}}}",
                      rf"\caption{{{caption}}}", r"\end{figure}"])


def style(ax) -> None:
    ax.set_aspect("equal")
    ax.tick_params(colors=MUTED, labelsize=7)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


# --------------------------------------------------------------------------------------------- the computation

class Comparison:
    """Everything the document and the package print, computed once."""

    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path.resolve()
        base = self.manifest_path.parent
        m = self.manifest = load_manifest(self.manifest_path)
        self.units = m.units
        self.length_unit, self.stress_unit, self.force_unit = UNITS[m.units]
        self.team_deck_path = resolve(base, m.team.deck, "team deck")
        self.report_paths = [resolve(base, r, "team field report") for r in m.team.reports]
        self.spec_path = resolve(base, m.ours.spec, "our spec")
        self.calculix_record_path = resolve(base, m.ours.calculix_record, "CalculiX record")
        self.reading_path = self.manifest_path.with_suffix(".md")
        self.package: Path | None = None  # set by docs/models/coupon.py to the package folder before the files section is written

        # the two models
        self.spec = load_spec(self.spec_path)
        self.card = dict(coupon_card(self.spec))
        if not self.card:
            raise SystemExit(f"{rel(self.spec_path)} has no [coupon] table: a team comparison names the coupon it compares (ADR-0038)")
        self.headline = f"{self.card['Coupon']}, {self.card['Test']}"
        self.our_text = write_abaqus(build_model(self.spec))
        self.committed_deck = fea_paths.deck_path(self.spec_path, "abaqus")
        if self.committed_deck.exists() and self.committed_deck.read_text(encoding="utf-8").replace("\r\n", "\n") != self.our_text:
            raise SystemExit(f"{rel(self.committed_deck)} is not what the generator writes from {rel(self.spec_path)} today; regenerate it first")
        self.team_deck = read_deck(self.team_deck_path, units=m.units)
        self.our_deck = to_si(parse_deck(self.our_text, source_path=f"{self.spec_path.stem}-abaqus.inp"), m.units)
        self.equivalence: DeckEquivalence = deck_equivalence(self.team_deck, self.our_deck, value_to_si(m.node_tolerance, "length", m.units), m.units)

        # the results
        self.team_kernel = solve_membrane(self.team_deck)
        self.ours = solve_membrane(self.our_deck)
        self.kernel_both = kernel_difference(self.team_kernel, self.ours, self.equivalence, m.units)
        self.reports: list[FieldReport] = [read_field_report(p) for p in self.report_paths]
        self.paired: list[PairedValue] = pair_reports(self.reports, self.team_deck, self.ours, self.equivalence, m.units)
        self.quantities = [r.quantity for r in self.reports]
        g = self.spec.geometry
        L = lambda v: from_si(v, "length", m.units)  # noqa: E731
        self.width, self.length, self.tab = L(g.width), L(g.length), L(g.tab_length or 0.0)
        free = (self.tab, self.length - self.tab)
        inner = (self.tab + m.edge_band, self.length - self.tab - m.edge_band)
        if inner[0] >= inner[1]:
            raise SystemExit("edge_band leaves no inner band between the tab lines")
        self.bands = {"free length": free, "inner": inner}
        self.agreements: dict[tuple[str, str], Agreement] = {
            (q, band): agreement(self.paired, q, band, rng, m.agreement) for q in self.quantities for band, rng in self.bands.items()}

        # the material, from our library
        material = self.spec.material
        if material.library is None:
            raise SystemExit("the comparison document cites a library material; this spec gives explicit constants")
        self.library = library_material(material.library, material.dataset)
        self.material = spec_material(self.spec)

        # reaction: kernel, CalculiX twin, laminate theory
        self.clt = laminate_check(self.our_deck, self.ours)
        self.calculix = tomllib.loads(self.calculix_record_path.read_text(encoding="utf-8"))
        rf = self.calculix["expected"]["rf"]
        top = [k for k in rf if "top" in k.lower()]
        if len(top) != 1:
            raise SystemExit(f"{rel(self.calculix_record_path)}: expected one top-grip reaction, found {list(rf)}")
        self.calculix_reaction = float(rf[top[0]][1])
        self.calculix_deck_path = (self.calculix_record_path.parent / self.calculix["deck_reference"]).resolve()

        # first-ply failure, ours only: the team's deck states no strengths
        f12 = deck_f12_star(self.our_deck)
        self.fpf = {criterion: strength_ratios(self.ours, criterion, f12) for criterion in self.spec.output.fpf_criteria}
        self.inverse = {ours: team for team, ours in self.equivalence.element_map.items()}

    # lookups ---------------------------------------------------------------------------------------
    def team_element_near(self, point: tuple[float, float]) -> int:
        centroids = self.reports[0].centroids
        return min(centroids, key=lambda e: math.dist(centroids[e], point))

    def value(self, quantity: str, element: int, layer: int) -> PairedValue:
        for p in self.paired:
            if p.quantity == quantity and p.reference_element == element and p.layer == layer:
                return p
        raise KeyError((quantity, element, layer))

    def layers(self) -> list[int]:
        return sorted({p.layer for p in self.paired})


# --------------------------------------------------------------------------------------------- figures

def mesh_figure(c: Comparison, path: Path) -> None:
    """The team's mesh and ours, side by side, with the gripped tabs shaded and the reference points marked."""
    fig, axes = plt.subplots(1, 2, figsize=(5.6, 6.4), constrained_layout=True)
    fig.patch.set_facecolor("white")
    for ax, deck, title in ((axes[0], c.team_deck, "The team's deck"), (axes[1], c.our_deck, "Our generated deck")):
        part = next(iter(deck.parts.values()))
        xy = from_si(part.nodes.xyz[:, :2], "length", c.units)
        index = {int(label): k for k, label in enumerate(part.nodes.labels)}
        polys = [xy[[index[int(n)] for n in row]] for row in part.elements.connectivity]
        centre_y = np.array([p[:, 1].mean() for p in polys])
        tab = (centre_y < c.tab) | (centre_y > c.length - c.tab)
        ax.add_collection(PolyCollection(polys, facecolors=np.where(tab[:, None], np.array([[0.80, 0.89, 0.98, 1.0]]), np.array([[1, 1, 1, 1.0]])),
                                         edgecolors=MUTED, linewidths=0.25))
        ref = from_si(deck.assembly_nodes.xyz[:, :2], "length", c.units)
        ax.plot(ref[:, 0], ref[:, 1], linestyle="none", marker="o", markersize=6, color=INK, markerfacecolor="white", markeredgewidth=1.2, clip_on=False)
        ax.autoscale()
        style(ax)
        ax.set_title(f"{title}\n{len(part.nodes.labels)} nodes, {len(part.elements.labels)} {part.elements.element_type}", fontsize=8, color=INK, loc="left")
        ax.set_xlabel(f"x ({c.length_unit})", fontsize=7, color=INK)
    axes[0].set_ylabel(f"y ({c.length_unit})", fontsize=7, color=INK)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def map_figure(c: Comparison, quantity: str, path: Path) -> tuple[float, float]:
    """Team, ours and the difference for one quantity at the map layer, on our mesh (the same elements, matched one to one).
    Returns the colour cap of the difference panel and the largest difference, both in the stress unit."""
    layer = c.manifest.map_layer
    mesh = c.ours.mesh
    xy = from_si(mesh.xy, "length", c.units)
    polys = [xy[nodes] for nodes in mesh.connectivity[:, :4]]
    position = {key: i for i, key in enumerate(mesh.element_keys)}
    instance = mesh.element_keys[0][0]
    team = np.full(len(polys), np.nan)
    ours = np.full(len(polys), np.nan)
    for p in c.paired:
        if p.quantity == quantity and p.layer == layer:
            k = position[(instance, p.our_element)]
            team[k], ours[k] = p.reference, p.ours
    if np.isnan(team).all():
        raise SystemExit(f"no {quantity} values at layer {layer} in the team's reports; choose map_layer from {c.layers()}")
    difference = ours - team
    lo, hi = float(np.nanmin([team, ours])), float(np.nanmax([team, ours]))
    floor = SIGN_FLOOR * max(abs(lo), abs(hi))
    if lo < -floor and hi > floor:  # both signs: blue below zero, red above, grey at zero
        bound = max(-lo, hi)
        value_norm, value_cmap = TwoSlopeNorm(vmin=-bound, vcenter=0.0, vmax=bound), DIVERGING
    elif hi > floor:  # positive only: light near zero, dark at the largest value
        value_norm, value_cmap = Normalize(vmin=0.0, vmax=hi), SEQUENTIAL
    else:  # negative only: dark at the most negative value
        value_norm, value_cmap = Normalize(vmin=lo, vmax=0.0), SEQUENTIAL.reversed()
    inner = c.bands["inner"]
    centre_y = np.array([p[:, 1].mean() for p in polys])
    in_inner = (centre_y >= inner[0]) & (centre_y <= inner[1]) & ~np.isnan(difference)
    largest = float(np.nanmax(np.abs(difference)))
    cap = float(np.max(np.abs(difference[in_inner]))) if in_inner.any() else largest
    cap = max(cap, 1e-12)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 5.4), constrained_layout=True)
    fig.patch.set_facecolor("white")
    panels = ((axes[0], team, value_norm, value_cmap, "Team (Abaqus)"), (axes[1], ours, value_norm, value_cmap, "Ours (engine kernel)"),
              (axes[2], difference, TwoSlopeNorm(vmin=-cap, vcenter=0.0, vmax=cap), DIVERGING, "Ours minus team"))
    for ax, values, norm, cmap, title in panels:
        shown = ~np.isnan(values)
        ax.add_collection(PolyCollection([p for p, s in zip(polys, shown) if not s], facecolors=EMPTY, edgecolors=GRID, linewidths=0.2))
        collection = PolyCollection([p for p, s in zip(polys, shown) if s], edgecolors="none", cmap=cmap, norm=norm)
        collection.set_array(np.clip(values[shown], norm.vmin, norm.vmax))
        ax.add_collection(collection)
        ax.autoscale()
        style(ax)
        ax.set_title(title, fontsize=8, color=INK, loc="left")
        ax.set_xlabel(f"x ({c.length_unit})", fontsize=7, color=INK)
        bar = fig.colorbar(collection, ax=ax, orientation="horizontal", fraction=0.04, pad=0.06, extend="both" if values is difference and largest > cap else "neither")
        bar.ax.tick_params(colors=MUTED, labelsize=6)
        bar.set_label(f"{quantity} ({c.stress_unit})" if values is not difference else f"difference ({c.stress_unit}), capped at ±{cap:.3g}", fontsize=7, color=INK)
    axes[0].set_ylabel(f"y ({c.length_unit})", fontsize=7, color=INK)
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return cap, largest


# --------------------------------------------------------------------------------------------- sections

def verdict(c: Comparison) -> str:
    judged = [i for i in c.equivalence.items if i.same is not None]
    same = sum(bool(i.same) for i in judged)
    inner = [c.agreements[(q, "inner")] for q in c.quantities]
    free = [c.agreements[(q, "free length")] for q in c.quantities]
    worst_inner = max(inner, key=lambda a: a.worst_fraction)
    worst_free = max(free, key=lambda a: a.worst_fraction)
    lo, hi = c.bands["inner"]
    model = (rf"\textbf{{Same model.}} {same} of {len(judged)} physical items agree; every node of ours sits at the team's position "
             rf"(largest offset {number(from_si(c.equivalence.largest_node_offset, 'length', c.units), 2)} {c.length_unit}) and all "
             rf"{len(c.equivalence.element_map)} elements match one to one." if c.equivalence.same_model else
             rf"\textbf{{Not the same model.}} {len(judged) - same} of {len(judged)} physical items differ (Section~\ref{{sec:models}}).")
    stress = (rf" \textbf{{Stress.}} Away from the tab lines (y {lo:g} to {hi:g} {c.length_unit}) every compared value agrees within "
              rf"{pct(worst_inner.worst_fraction)} of its quantity's largest value (" + ", ".join(f"{a.quantity} {pct(a.worst_fraction)}" for a in inner) + "). "
              rf"Over the whole free length the largest difference is {pct(worst_free.worst_fraction)} ({worst_free.quantity}, team element "
              rf"{worst_free.worst.reference_element} beside a tab line), where the corner is singular (Section~\ref{{sec:reading}}).")
    return model + stress


def title_block(c: Comparison) -> str:
    m = c.manifest
    lib = c.library
    facts = [
        ("Team's deck", escape(f"{c.team_deck_path.name} (sha256 {sha256(c.team_deck_path)[:16]}), {m.team.solver}, run by {m.team.run_by} on {m.team.run_date}")),
        ("Our model", escape(f"{c.spec_path.name} built by anisotropy-fea {fea_version} (deck sha256 {sha256(c.our_text)[:16]}), solved by our engine's "
                             "finite element kernel (four-node membrane element on the engine's laminate stiffness)")),
        ("Material source", escape(f"our library record {lib.material_id}, dataset {lib.dataset_id}: {source_text(lib)}")),
        ("Compared", escape(f"{len(c.paired)} values ({', '.join(c.quantities)} at layers {', '.join(map(str, c.layers()))}) from the team's field reports")),
        ("Built", escape(f"{date.today().isoformat()}, commit {git_commit()}, by docs/models/team.py")),
    ]
    return "\n".join([
        r"\begin{center}", r"{\sffamily\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} THE TEAM'S MODEL AND OURS}\par\medskip",
        rf"{{\sffamily\fontsize{{20}}{{26}}\selectfont\bfseries\color{{ink}} {escape(c.card['Coupon'])}}}\par\smallskip",
        rf"{{\sffamily\large\color{{ink}} {escape(c.card['Test'].capitalize())} coupon}}\par\smallskip",
        r"{\sffamily\color{muted} What the team built in Abaqus, what we built with our engine, where our material comes from, and the results side by side}",
        r"\end{center}", r"\medskip",
        r"{\sffamily\bfseries\small The coupon}\par\smallskip",
        r"{\small\begin{tabular}{@{}p{2.6cm}p{\dimexpr\linewidth-3.1cm}@{}}",
        *[rf"{label} & {escape(value)} \\[0.3ex]" for label, value in c.card.items() if label not in ("Coupon", "Test")], r"\end{tabular}}\par", r"\medskip",
        r"{\sffamily\bfseries\small The comparison}\par\smallskip",
        r"{\small\begin{tabular}{@{}p{2.6cm}p{\dimexpr\linewidth-3.1cm}@{}}", *[rf"{label} & {value} \\[0.3ex]" for label, value in facts], r"\end{tabular}}\par",
        r"\medskip", rf"\verdict{{{verdict(c)}}}",
    ])


def models_section(c: Comparison, figures: Path) -> str:
    mesh_figure(c, figures / "meshes.png")
    rows = []
    for item in c.equivalence.items:
        mark = {True: r"\textcolor{passgreen}{same}", False: r"\textcolor{accent}{\textbf{differs}}", None: r"\textcolor{muted}{listed}"}[item.same]
        rows.append([escape(item.item), escape(item.team), escape(item.ours), mark])
    difference, largest = c.kernel_both
    return "\n\n".join([
        rf"The team built the coupon in Abaqus/CAE ({code(c.team_deck_path.name)}). We built it from a spec ({code(c.spec_path.name)}) with our model "
        r"generator, which writes an Abaqus deck from it. Both decks were read by the same reader and compared item by item below. Nodes and "
        r"elements are numbered differently in the two decks, so nodes are matched by position and elements by their corner nodes. "
        r"Names read ``same'' when they match; a name that differs is only ``listed'', because names do not change the solution. "
        r"Strengths are always listed: a linear solve does not read them.",
        table(["Item", "Team", "Ours", ""], rows, r">{\raggedright\arraybackslash}p{3.2cm}YY>{\raggedright\arraybackslash}p{1.1cm}", r"\footnotesize"),
        rf"Our kernel solved both decks. Over all {len(c.equivalence.element_map)} elements and every ply, the stress from the team's deck and from ours "
        rf"differs by at most {number(difference, 3)} {c.stress_unit}, against a largest stress of {number(largest, 5)} {c.stress_unit}: the node "
        rf"offsets of at most {number(from_si(c.equivalence.largest_node_offset, 'length', c.units), 2)} {c.length_unit} are the only difference.",
        figure(figures / "meshes.png", r"The two meshes. Shaded: the gripped tabs, coupled to the reference points (circles). The rows change "
               r"spacing at the team's partition lines, which our spec reproduces.", r"0.5\linewidth"),
    ])


def material_section(c: Comparison) -> str:
    lib, mat = c.library, c.material
    team_material = c.team_deck.materials[expanded_layers(next(iter(c.team_deck.parts.values())).sections[0])[0].material]
    team_values = {"E1": team_material.elastic.E1, "E2": team_material.elastic.E2, "G12": team_material.elastic.G12, "nu12": team_material.elastic.nu12}
    rows = []
    for v in lib.values:
        if v.role == "tply":
            continue
        shown = from_si(v.value, "stress", c.units) if v.unit == "Pa" else v.value
        unit = c.stress_unit if v.unit == "Pa" else ""
        if v.role in team_values:
            team = team_values[v.role]
            team_shown = from_si(team, "stress", c.units) if v.unit == "Pa" else team
            same = abs(team - v.value) <= 1e-9 * max(abs(v.value), 1e-300)
            team_cell = f"{number(team_shown, 6)} " + (r"\textcolor{passgreen}{same}" if same else r"\textcolor{accent}{\textbf{differs}}")
        else:
            team_cell = r"\textcolor{muted}{not in the deck}"
        page = f"{v.page}" + (f" (printed {v.printed_page})" if v.printed_page else "")
        rows.append([escape(v.role), f"{number(shown, 6)} {unit}", escape(page), team_cell])
    for name, value, team in (("G13", mat.G13, team_material.elastic.G13), ("G23", mat.G23, team_material.elastic.G23)):
        same = team is not None and abs(team - value) <= 1e-9 * value
        rows.append([name, f"{number(from_si(value, 'stress', c.units), 6)} {c.stress_unit}", r"stated in our spec",
                     f"{number(from_si(team, 'stress', c.units), 6)} " + (r"\textcolor{passgreen}{same}" if same else r"\textcolor{accent}{\textbf{differs}}")
                     if team is not None else "--"])
    not_given = "; ".join(lib.not_provided) or "nothing listed"
    return "\n\n".join([
        rf"Our model does not type its material in. The spec names a record of our material library, {code(lib.material_id)} "
        rf"(dataset {code(lib.dataset_id)}, record {escape(lib.record_revision or 'unrevised')}), and the generator writes its values, with "
        r"their source and page, into the deck header. The record's source:",
        rf"\begin{{quote}}{escape(source_text(lib))}.\end{{quote}}",
        rf"Rights class {code(lib.rights)}: the values are cited by table and page and the source itself is not reproduced. The table lists "
        r"every value the model uses, the page it comes from, and the value the team typed into their deck.",
        table(["Property", "Our library", "Source page", "Team's deck"], rows, r">{\raggedright\arraybackslash}p{2cm}>{\raggedright\arraybackslash}p{2.8cm}Y>{\raggedright\arraybackslash}p{3.6cm}"),
        rf"The strengths are what let our engine predict first-ply failure (Section~\ref{{sec:fpf}}); the team's deck has none. "
        rf"What the record does not give: {escape(not_given)}. The deck states the ply thickness itself "
        rf"({number(from_si(c.clt.thickness_m / len(c.clt.plies), 'length', c.units), 3)} {c.length_unit}).",
    ])


def results_section(c: Comparison, figures: Path) -> str:
    m, u = c.manifest, c.stress_unit
    layer = m.map_layer
    parts = [
        rf"The team exported {', '.join(c.quantities)} from Abaqus at every element centroid for layers {', '.join(map(str, c.layers()))} "
        r"(the outer plies; Abaqus numbers layers from the bottom). S11 and S22 are in each ply's material axes; for these 0-degree plies "
        r"direction 1 is the global x axis, across the width, and direction 2 the loading axis y. Our kernel gives the same quantities at "
        rf"the same centroids. Differences are ours minus the team's. Layers 1 and 10 carry the same values in both, so tables show layer {layer}.",
        r"\subsection{Stress at named points}",
    ]
    rows = []
    team_instance = next(iter(c.team_deck.instances))
    for name, point in m.locations.items():
        element = c.team_element_near(point)
        our_element = c.equivalence.element_map[(team_instance, element)][1]
        for q in c.quantities:
            p = c.value(q, element, layer)
            scale = c.agreements[(q, "free length")].largest
            rows.append([escape(name), f"{element} / {our_element}", escape(q), number(p.reference, 6), number(p.ours, 6), number(p.difference, 3),
                         pct(abs(p.difference) / scale if scale else 0.0)])
    for q in c.quantities:
        lo, hi = c.bands["free length"]
        members = [p for p in c.paired if p.quantity == q and p.layer == layer and lo <= p.y <= hi]
        if q == "Mises" and members:
            team_peak = max(members, key=lambda p: p.reference)
            our_peak = max(members, key=lambda p: p.ours)
            rows.append([r"Largest Mises, team", f"{team_peak.reference_element} / {team_peak.our_element}", "Mises", number(team_peak.reference, 6),
                         number(team_peak.ours, 6), number(team_peak.difference, 3), pct(abs(team_peak.difference) / c.agreements[(q, "free length")].largest)])
            rows.append([r"Largest Mises, ours", f"{our_peak.reference_element} / {our_peak.our_element}", "Mises", number(our_peak.reference, 6),
                         number(our_peak.ours, 6), number(our_peak.difference, 3), pct(abs(our_peak.difference) / c.agreements[(q, "free length")].largest)])
    parts.append(rf"Element numbers are the team's, then ours. The last column is the difference as a share of the quantity's largest team value "
                 rf"over the free length. Points (x, y) in {c.length_unit}: " + "; ".join(f"{escape(n)} ({x:g}, {y:g})" for n, (x, y) in m.locations.items()) + ".")
    parts.append(table(["Where", "Elements", "", f"Team ({u})", f"Ours ({u})", f"Difference ({u})", "Share"], rows,
                       r">{\raggedright\arraybackslash}p{3.3cm}>{\raggedright\arraybackslash}p{1.5cm}>{\raggedright\arraybackslash}p{1cm}YYYY", r"\footnotesize"))

    parts.append(r"\subsection{Over the coupon}")
    rows = []
    for band, (lo, hi) in c.bands.items():
        label = "Free length" if band == "free length" else f"Away from the tab lines (more than {m.edge_band:g} {c.length_unit})"
        for q in c.quantities:
            a = c.agreements[(q, band)]
            if a.count == 0:
                continue
            rows.append([escape(f"{label}, y {lo:g} to {hi:g}"), escape(q), str(a.count), number(a.largest, 6), f"{a.within} of {a.count}",
                         pct(a.worst_fraction), escape(f"{a.worst.reference_element} at ({a.worst.x:g}, {a.worst.y:g})")])
    parts.append(rf"Every compared value in a band, both layers. ``Agree'' means a difference of at most {pct(m.agreement, 0)} of the quantity's largest "
                 r"team value in that band.")
    parts.append(table(["Band", "", "Values", f"Largest ({u})", "Agree", "Largest difference", "At team element (x, y)"], rows,
                       r">{\raggedright\arraybackslash}p{3.6cm}>{\raggedright\arraybackslash}p{1cm}>{\raggedright\arraybackslash}p{1cm}YY>{\raggedright\arraybackslash}p{1.6cm}Y", r"\footnotesize"))

    parts.append(r"\subsection{Maps}")
    for q in c.quantities:
        path = figures / f"map-{q}.png"
        cap, largest = map_figure(c, q, path)
        note = (rf" The difference colours are capped at the largest difference away from the tab lines, {number(cap, 3)} {u}; the cells beside the "
                rf"tab lines reach {number(largest, 3)} {u}." if largest > cap else "")
        parts.append(figure(path, rf"{escape(QUANTITY_TITLE.get(q, q))} at layer {layer}: the team's Abaqus values, ours on the same elements, and the "
                                  rf"difference.{note}"))

    parts.append(r"\subsection{Reaction force and displacement}")
    reaction = c.clt.kernel_reaction_N
    applied = from_si(c.clt.applied, "length", c.units) if c.clt.control == "displacement" else c.clt.applied
    solver = c.calculix["solver"]
    rows = [
        ["Pull at the top grip", *[f"{number(applied, 6)} {c.length_unit} (prescribed)"] * 3, "--"],
        ["Reaction along the pull", r"\textcolor{muted}{not exported}", f"{number(reaction, 6)} {c.force_unit}",
         f"{number(c.calculix_reaction, 6)} {c.force_unit}", f"{number(c.clt.reaction_N, 6)} {c.force_unit}"],
    ]
    parts.append(table(["", "Team (Abaqus)", "Ours (kernel)", escape(f"Ours in CalculiX {solver['version']}"), "Laminate theory"], rows,
                       r">{\raggedright\arraybackslash}p{3.2cm}YYYY", r"\footnotesize"))
    parts.append(rf"CalculiX is an independent solver run on our twin of the coupon with the grips written as direct constraints on the tab nodes "
                 rf"({escape(solver['element_type'])} elements; record {code(c.calculix_record_path.name)}). The laminate theory column is the engine's "
                 rf"classical laminate theory for a uniaxial test over the {number(from_si(c.clt.free_length_m, 'length', c.units), 4)} {c.length_unit} "
                 r"free length with free lateral edges; the coupled tabs stop the width from contracting at the ends, which is why the models carry a little more "
                 r"force. The team's export has no reaction force, so that cell stays open (Section~\ref{sec:open}).")

    parts.append(r"\subsection{First-ply failure, ours}\label{sec:fpf}")
    rows = []
    free_length = from_si(c.clt.free_length_m, "length", c.units)
    for criterion, field in c.fpf.items():
        team_element = c.inverse.get(field.element, (None, "--"))[1]
        pull = field.factor * applied
        rows.append([escape(criterion.replace("_", " ")), number(field.factor, 4), f"{number(pull, 4)} {c.length_unit}",
                     pct(pull / free_length), f"{team_element} / {field.element[1]}", f"{field.ply}", escape(field.governing_mode)])
    parts.append(r"With the strengths from our library the engine finds the first ply to fail. The analysis is linear, so the factor scales the "
                 r"applied pull: the first ply fails at that share of it. The team's deck carries no strengths, so Abaqus reports no failure index to set beside this.")
    parts.append(table(["Criterion", "Factor", "Pull at failure", "Nominal strain", "Elements", "Ply", "Mode"], rows,
                       r">{\raggedright\arraybackslash}p{2cm}YYYY>{\raggedright\arraybackslash}p{0.8cm}Y", r"\footnotesize"))
    return "\n\n".join(parts)


def reading_section(c: Comparison) -> str:
    if not c.reading_path.exists():
        return rf"No reading has been written yet ({code(c.reading_path.name)} beside the manifest)."
    return manual.convert(c.reading_path.read_text(encoding="utf-8"))


def files_section(c: Comparison) -> str:
    rows = [[code(path), escape(what)] for path, what in share_contents(c)]
    return "\n\n".join([
        rf"Everything is in the package folder {code(c.package.name)}, which goes to the team as it is. It holds no CalculiX results: run our "
        rf"decks to get them. Numbers in the files are in {c.length_unit}, {c.stress_unit} and {c.force_unit}.",
        table(["File", "What it is and how to open it"], rows, r">{\raggedright\arraybackslash}p{6.4cm}Y", r"\footnotesize"),
    ])


def open_section(c: Comparison) -> str:
    return "\n".join([
        r"\begin{itemize}",
        r"\item The reaction force and displacement at the two reference points: Abaqus has them (RF and U), the export does not.",
        r"\item The inner plies and the shear stress S12: the export holds only the outer layers and no S12. The 45-degree plies would also confirm "
        r"which axes Abaqus reports S11 and S22 in, which the 0-degree plies cannot show.",
        r"\item Strains and section forces.",
        r"\end{itemize}",
        r"To settle them, export from the same output database: Report, Field Output, with S (all components) and E at all section points, and RF and U "
        r"at both reference points. Our file \texttt{4-results/ours-all-plies.csv} already holds every ply for that comparison.",
    ])


# --------------------------------------------------------------------------------------------- the package for the team

def share_contents(c: Comparison) -> list[tuple[str, str]]:
    stem = c.spec_path.stem
    return [
        ("README.txt", "this list, as plain text"),
        (f"{c.manifest.name}.pdf", "this document"),
        (f"{c.package.name}-audit.xlsx", "the audit form: our tools' results locked; the auditor's results, observations and verdict to fill in (ADR-0043)"),
        (f"1-team-model/{c.team_deck_path.name}", "the team's deck, as we received it"),
        (f"2-our-model/abaqus/{stem}-abaqus.inp", "our deck of the same coupon, for Abaqus. Abaqus/CAE: File, Import, Model, choose the .inp file "
                                                  "(this click path is not checked by us); or run it as a job from the command line"),
        (f"2-our-model/calculix/{c.calculix_deck_path.name}", "our twin for CalculiX, with the grips as direct constraints. PrePoMax: File, Import, then run it"),
        (f"2-our-model/spec/{c.spec_path.name}", "the spec our generator builds the deck from: every dimension, the seeds, the layup, the material record"),
        (f"3-material/{c.library.material_id}.csv", "the material from our library: every value, its unit, basis and source page, and the source"),
        *[(f"4-results/ours-{q}.csv", f"our {q} in the layout of the team's {q} field report: same columns, the team's element numbers, "
                                      "the same layers and faces. Open the two side by side") for q in c.quantities],
        ("4-results/team-vs-ours.csv", "every compared value: team element, our element, x, y, layer, quantity, team, ours, difference, share of the largest"),
        ("4-results/ours-all-plies.csv", "our S11, S22, S12 and Mises for every ply of every element, with the team's element numbers"),
    ]


def write_material_csv(path: Path, lib, material, units: str) -> None:
    """The library record a model uses: every value with its unit, basis and source page, the source and its rights class."""
    length_unit, stress_unit, _ = UNITS[units]
    # utf-8-sig: the citation holds characters beyond ASCII (a section sign, middle dots); the byte-order mark makes Excel read them
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["material", lib.material_id, lib.name])
        writer.writerow(["dataset", lib.dataset_id, lib.dataset])
        writer.writerow(["record revision", lib.record_revision or ""])
        writer.writerow(["source", source_text(lib)])
        writer.writerow(["rights class", lib.rights, "values cited by table and page; the source is not reproduced"])
        writer.writerow([])
        writer.writerow(["property", f"value ({units})", "unit", "value as the source gives it", "source unit", "basis", "source page (PDF)", "printed page", "link"])
        for v in lib.values:
            shown = from_si(v.value, "stress", units) if v.unit == "Pa" else (from_si(v.value, "length", units) if v.unit == "m" else v.value)
            unit = stress_unit if v.unit == "Pa" else (length_unit if v.unit == "m" else v.unit)
            writer.writerow([v.role, f"{shown:.10g}", unit, f"{v.source_value:.10g}", v.source_unit, v.basis, v.page, v.printed_page or "", v.reference_url])
        for name, value in (("G13", material.G13), ("G23", material.G23)):
            writer.writerow([name, f"{from_si(value, 'stress', units):.10g}", stress_unit, "", "", "stated in our spec", "", "", ""])


def write_all_plies(path: Path, solution, deck, units: str, inverse: dict | None = None) -> None:
    """Our S11, S22, S12 and Mises for every ply of every element, with the team's element numbers where a comparison maps them
    (`inverse`: our element key -> (instance, team label)); blank otherwise."""
    length_unit, stress_unit, _ = UNITS[units]
    values = ply_values(solution, units)
    mesh = solution.mesh
    angles = [layer.angle_deg for layer in expanded_layers(next(iter(deck.parts.values())).sections[0])]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["team element", "our element", f"x ({length_unit})", f"y ({length_unit})", "ply (1 = bottom)", "angle (deg)",
                         f"S11 ({stress_unit})", f"S22 ({stress_unit})", f"S12 ({stress_unit})", f"Mises ({stress_unit})"])
        for index, key in enumerate(mesh.element_keys):
            x, y = from_si(mesh.xy[mesh.connectivity[index, :4]].mean(axis=0), "length", units)
            team = (inverse or {}).get(key, (None, ""))[1]
            for k, angle in enumerate(angles):
                writer.writerow([team, key[1], f"{x:.9g}", f"{y:.9g}", k + 1, f"{angle:g}"] + [f"{values[q][index, k]:.9g}" for q in ("S11", "S22", "S12", "Mises")])


def package_folder(documents: Path, name: str) -> Path:
    """The package under today's date, `documents/<YYYY-MM-DD>_<name>/`, so each package sent out says when it was built (ADR-0043)."""
    return documents / f"{date.today().isoformat()}_{name}"


def package_is_ours(folder: Path) -> bool:
    """True when the folder's README.txt starts with README_MARK: a package this project wrote, safe to replace."""
    try:
        return (folder / "README.txt").read_text(encoding="utf-8").startswith(README_MARK)
    except OSError:
        return False


def write_package(folder: Path, fill) -> Path:
    """An empty package folder filled by `fill(folder)`. One that exists is replaced only when this project wrote it
    (`package_is_ours`); earlier packages, under other dates, are kept, because a returned audit form names its package."""
    if folder.exists():
        if not package_is_ours(folder):
            raise SystemExit(f"{folder} exists and was not written by this project; choose another name")
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    fill(folder)
    return folder


def fill_share(c: Comparison, share: Path) -> None:
    """Every file of the package except the PDF, which is compiled into the folder afterwards, and the audit form."""
    for sub in ("1-team-model", "2-our-model/abaqus", "2-our-model/calculix", "2-our-model/spec", "3-material", "4-results"):
        (share / sub).mkdir(parents=True, exist_ok=True)
    stem = c.spec_path.stem
    shutil.copy2(c.team_deck_path, share / "1-team-model" / c.team_deck_path.name)
    (share / "2-our-model/abaqus" / f"{stem}-abaqus.inp").write_text(c.our_text, encoding="utf-8", newline="\n")
    shutil.copy2(c.calculix_deck_path, share / "2-our-model/calculix" / c.calculix_deck_path.name)
    shutil.copy2(c.spec_path, share / "2-our-model/spec" / c.spec_path.name)

    write_material_csv(share / "3-material" / f"{c.library.material_id}.csv", c.library, c.material, c.units)

    odb, step, frame = f"anisotropy-fea {fea_version} kernel on {stem}-abaqus.inp (no .odb)", "Step-1", "linear static solve"
    our_instance = next(iter(c.our_deck.instances))
    section = f"ASSEMBLY_{our_instance}_{next(iter(c.our_deck.parts.values())).sections[0].elset}".upper()  # as Abaqus/CAE names it in a report
    for report in c.reports:
        # rows in the order of the team's own report (its first block), so the two files line up row by row
        ours_of = {(p.reference_element, p.layer): p for p in c.paired if p.quantity == report.quantity}
        rows = [(element, layer, report.faces[(element, layer)], ours_of[(element, layer)].x, ours_of[(element, layer)].y, ours_of[(element, layer)].ours)
                for element, layer in report.values]
        write_field_report(share / "4-results" / f"ours-{report.quantity}.csv", report.quantity, rows, odb, step, frame, report.instance, section,
                           c.material.name)
    with (share / "4-results" / "team-vs-ours.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["team element", "our element", f"x ({c.length_unit})", f"y ({c.length_unit})", "layer", "quantity", f"team ({c.stress_unit})",
                         f"ours ({c.stress_unit})", f"ours - team ({c.stress_unit})", "share of the largest team value in the free length"])
        for p in c.paired:
            scale = c.agreements[(p.quantity, "free length")].largest
            writer.writerow([p.reference_element, p.our_element, f"{p.x:.9g}", f"{p.y:.9g}", p.layer, p.quantity, f"{p.reference:.9g}", f"{p.ours:.9g}",
                             f"{p.difference:.6g}", f"{abs(p.difference) / scale:.6g}" if scale else ""])
    write_all_plies(share / "4-results" / "ours-all-plies.csv", c.ours, c.our_deck, c.units, c.inverse)

    lines = [README_MARK, f"{c.headline}: the team's Abaqus model and ours", "",
             *[f"{label + ':':14} {value}" for label, value in c.card.items()], "",
             f"Built {date.today().isoformat()} by docs/models/coupon.py (anisotropy-fea {fea_version}, commit {git_commit()}).",
             "Start with the PDF. Numbers in the files are in " + f"{c.length_unit}, {c.stress_unit} and {c.force_unit}.", ""]
    width = max(len(path) for path, _ in share_contents(c))
    lines += [f"{path.ljust(width)}  {what}" for path, what in share_contents(c)]
    (share / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------------------------- summary

def toml_value(value) -> str:
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    return f"{value:.9g}" if isinstance(value, float) else str(value)


def write_team_summary(c: Comparison) -> Path:
    """The comparison in figures, committed beside our model's records (ADR-0039): the equivalence counts and the agreement per
    quantity and band. Derived numbers only; no value from the team's deck or reports is written."""
    path = fea_paths.team_summary(c.spec_path.parent)
    judged = [i for i in c.equivalence.items if i.same is not None]
    lines = [
        "# The team comparison in figures, written by docs/models/coupon.py (ADR-0039, ADR-0041). Derived from the team's deck and field reports,",
        "# which stay local; no value of theirs is in this file. The case page's result table is generated from it (fea/tools/case_pages.py).",
        f"coupon = {toml_value(c.card['Coupon'])}",
        f"units = {toml_value(c.units)}",
        f"built = {toml_value(date.today().isoformat())}",
        f"commit = {toml_value(git_commit())}",
        "",
        "[team]",
        f"deck = {toml_value(c.team_deck_path.name)}",
        f"deck_sha256 = {toml_value(sha256(c.team_deck_path))}",
        f"solver = {toml_value(c.manifest.team.solver)}",
        f"run_date = {toml_value(c.manifest.team.run_date)}",
        f"reports = {toml_value([p.name for p in c.report_paths])}",
        "",
        "[equivalence]",
        f"items = {len(judged)}",
        f"same = {sum(bool(i.same) for i in judged)}",
        f"elements_matched = {len(c.equivalence.element_map)}",
        f"largest_node_offset = {toml_value(from_si(c.equivalence.largest_node_offset, 'length', c.units))}  # {c.length_unit}",
    ]
    for band, (lo, hi) in c.bands.items():
        for q in c.quantities:
            a = c.agreements[(q, band)]
            lines += ["", "[[agreement]]", f"band = {toml_value(band)}", f"y = {toml_value([float(lo), float(hi)])}  # {c.length_unit}",
                      f"quantity = {toml_value(q)}", f"values = {a.count}", f"agree = {a.within}",
                      f"within = {toml_value(a.fraction)}  # of the quantity's largest team value in the band",
                      f"largest_difference = {toml_value(a.worst_fraction)}  # the same fraction, for the worst value"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


# --------------------------------------------------------------------------------------------- no document of its own

def main() -> None:
    raise SystemExit("The team comparison is a set of chapters of the coupon document (ADR-0041): "
                     "uv run --project fea python docs/models/coupon.py <coupon>")


if __name__ == "__main__":
    main()
