"""A model sent from Abaqus beside a run of ours: check its bundle, compare it, or pack one from files (ADR-0094, step 1).

    uv run python tools/abaqus_upload.py check <bundle>.zip [--json <file>]
    uv run python tools/abaqus_upload.py compare <bundle>.zip --ours <package>/4-results/ours-every-output.csv --our-deck <our deck>.inp
        [--json <file>] [--pairs <file>.csv]
    uv run python tools/abaqus_upload.py pack --deck <job>.inp --every-output <job>-every-output.csv [--rf <job>-every-output-RF.csv]
        [--provenance <job>-every-output.json] [--journal <job>.jnl] [--model <model>.json] --units mm-MPa --out <bundle>.zip
    uv run python tools/abaqus_upload.py connector --out anisotropy-connector.zip

`check` reads a bundle (`anisotropy_fea.bundle`, version 1) and says what it holds and whether it is in scope: a deck our reader
reads (flat S4 or S4R shells, one linear static step) and every element and ply in `tools/abaqus_every_output.py`'s columns.

`compare` puts the bundle beside a run of ours, from that run's own files: our every-output file with its JSON, and our deck. Nothing is
solved here. The model is compared item by item (`anisotropy_fea.equivalence`), after moving a coupon drawn elsewhere onto ours. The
results are compared by the rules of `tools/compare_every_output.py`, the comparison the team's engineers run themselves (ADR-0089
amendment 3): paired by element number or by position, judged by zone, the reaction and the gauge within 1 %, the free length within
3 %. A model on another mesh cannot be paired element by element: then the model is compared without its mesh, each of its gauge
elements stands beside ours nearest its centroid, the reaction is compared, the free length is reported and not judged, and the result
says so. A bundle in the other deck system is converted to ours first.

Exit 0: agrees. 1: differs, or something that should be judged could not be. 2: refused (the bundle breaks the format, or is out of
scope), with every reason. `--json` writes the result in each case: the page's card is drawn from it in a later step.

`pack` writes a bundle from files that already exist, the output of `abaqus python tools/abaqus_every_output.py` and the deck that ran:
what `tools/anisotropy_connector.py` does in one command under the user's Abaqus (step 2). `connector --out <zip>` writes that
connector's files as one zip to hand over.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import compare_every_output as team  # noqa: E402  the comparison the team's engineers run: one set of rules for both

from anisotropy_fea import __version__  # noqa: E402
from anisotropy_fea.abaqus_reader import read_deck  # noqa: E402
from anisotropy_fea.bundle import EPOCH, BundleRefused, open_bundle, write_bundle  # noqa: E402
from anisotropy_fea.equivalence import EquivalenceError, deck_equivalence, equivalence_without_mesh, outline  # noqa: E402
from anisotropy_fea.model import DeckError, expanded_layers  # noqa: E402
from anisotropy_fea.units import DECK_UNIT_SYSTEMS, UNIT_LABEL, from_si, to_si  # noqa: E402

STRESSES = team.QUANTITIES[:9]  # the rest are strains, numbers without a unit
RF_COLUMNS = ("Node", "X", "Y", "RF1", "RF2")


class OutOfScope(Exception):
    """The bundle is well formed and this comparison does not take it; `problems` says why."""

    def __init__(self, problems):
        self.problems = tuple(problems)
        super().__init__("; ".join(self.problems))


def bundle_facts(bundle) -> dict:
    m = bundle.manifest
    return {"sha256": bundle.sha256, "bundle_version": m["bundle_version"], "created": m["created"], "units": m["units"],
            "written_by": m["written_by"], "job": m.get("job"), "coupon": m.get("coupon"), "results": m.get("results"),
            "files": {role: dataclasses.asdict(entry) for role, entry in bundle.files.items()}}


def deck_facts(path: Path, units: str):
    """(the deck in SI, its facts) or (None, {"read": False, "reason"}): whether our reader takes it."""
    try:
        deck = read_deck(path, units)
    except (DeckError, ValueError) as exc:
        return None, {"read": False, "reason": str(exc)}
    facts = {"read": True, "parts": len(deck.parts), "steps": [step.name for step in deck.steps], "notes": list(deck.notes)}
    if len(deck.parts) == 1:
        part = next(iter(deck.parts.values()))
        facts.update(nodes=len(part.nodes), elements=len(part.elements) if part.elements is not None else 0,
                     element_type=part.elements.element_type if part.elements is not None else None)
        if len(part.sections) == 1:
            layers = expanded_layers(part.sections[0])
            facts.update(plies=len(layers), layup="/".join(f"{layer.angle_deg:g}" for layer in layers))
    return deck, facts


def read_reactions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in RF_COLUMNS if name not in (reader.fieldnames or ())]
        if missing:
            raise team.Refused(f"{path.name} has no column {', '.join(missing)}: is it what abaqus_every_output.py wrote?")
        try:
            return [{"Node": int(row["Node"]), **{name: float(row[name]) for name in RF_COLUMNS[1:]}} for row in reader]
        except ValueError as exc:
            raise team.Refused(f"{path.name}: {exc}") from None


MODEL_FORMAT = 1
MODEL_GROUPS = ("parts", "materials", "sections", "steps", "boundary_conditions", "loads", "constraints", "field_output_requests",
                "history_output_requests")


def plies_of(layup: dict) -> int:
    """A layup's plies through the thickness: the connector states it, a symmetric layup listing half of them."""
    stated = layup.get("plies_through_thickness")
    return stated if isinstance(stated, int) and not isinstance(stated, bool) else len(layup.get("plies") or [])


def model_facts(path: Path) -> dict:
    """What the connector read from the `.cae` (the bundle's `model` role), counted. It is listed and never judged: the comparison is
    made on the deck Abaqus solved, and what this file adds is how the model was built."""
    try:
        model = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return {"read": False, "reason": f"{path.name} is not JSON: {exc}"}
    if not isinstance(model, dict) or model.get("model_format") != MODEL_FORMAT:
        found = model.get("model_format") if isinstance(model, dict) else type(model).__name__
        return {"read": False, "reason": f"{path.name} is not a model of format {MODEL_FORMAT} (found {found!r})"}
    groups = {name: len(model[name]) for name in MODEL_GROUPS if isinstance(model.get(name), list)}
    parts = [part for part in model.get("parts") or [] if isinstance(part, dict)]
    layups = [layup for part in parts for layup in part.get("layups") or [] if isinstance(layup, dict)]
    not_read = model.get("not_read")
    return {"read": True, "model": model.get("model"), "read_by": model.get("read_by"), "groups": groups,
            "layups": [{"name": layup.get("name"), "plies": plies_of(layup)} for layup in layups],
            "not_read": [str(entry) for entry in not_read] if isinstance(not_read, list) else []}


def check(bundle_path: Path) -> dict:
    """What a bundle holds, and whether the comparison takes it. Raises `BundleRefused` when it breaks the format."""
    bundle = open_bundle(bundle_path)
    result = {"bundle": bundle_facts(bundle)}
    with tempfile.TemporaryDirectory() as folder:
        files = bundle.extract(folder)
        _, result["deck"] = deck_facts(files["deck"], bundle.units)
        try:
            rows = team.read_rows(files["every_output"], False)
            result["every_output"] = {"read": True, "rows": len(rows), "elements": len({key[0] for key in rows}),
                                      "layers": len({key[1] for key in rows})}
        except team.Refused as exc:
            result["every_output"] = {"read": False, "reason": str(exc)}
        if "reactions" in files:
            try:
                result["reactions"] = {"read": True, "nodes": len(read_reactions(files["reactions"]))}
            except team.Refused as exc:
                result["reactions"] = {"read": False, "reason": str(exc)}
        else:
            result["reactions"] = None
        result["model"] = model_facts(files["model"]) if "model" in files else None
    result["in_scope"] = bool(result["deck"]["read"] and result["every_output"]["read"]
                              and (result["reactions"] is None or result["reactions"]["read"]))
    return result


def in_our_units(rows: dict, reactions: list[dict] | None, theirs: str, ours: str):
    """Their values in our deck system: lengths, stresses and forces converted, strains as they are."""
    if theirs == ours:
        return rows, reactions
    factor = lambda kind: DECK_UNIT_SYSTEMS[theirs][kind] / DECK_UNIT_SYSTEMS[ours][kind]  # noqa: E731
    length, stress, force = factor("length"), factor("stress"), factor("force")
    converted = {key: {name: value * (length if name in ("X", "Y") else stress if name in STRESSES else 1.0) for name, value in values.items()}
                 for key, values in rows.items()}
    moved = None if reactions is None else [
        {"Node": r["Node"], "X": r["X"] * length, "Y": r["Y"] * length, "RF1": r["RF1"] * force, "RF2": r["RF2"] * force} for r in reactions]
    return converted, moved


def moved_deck(deck, shift_si: tuple[float, float]):
    """The deck with every node moved by the shift, so that a coupon drawn elsewhere is compared in our place."""
    add = np.array([shift_si[0], shift_si[1], 0.0])
    parts = {name: dataclasses.replace(part, nodes=dataclasses.replace(part.nodes, xyz=part.nodes.xyz + add)) for name, part in deck.parts.items()}
    return dataclasses.replace(deck, parts=parts, assembly_nodes=dataclasses.replace(deck.assembly_nodes, xyz=deck.assembly_nodes.xyz + add))


def items_of(items) -> list[dict]:
    return [{"item": i.item, "yours": i.team, "ours": i.ours, "same": i.same} for i in items]


# Abaqus/CAE writes an input file's material lines to six significant digits, whatever the model holds (Abaqus 2025: 162095.744 in the
# model, 162096. in the file it solved). A model sent back from Abaqus/CAE therefore states our constants to six digits, and two
# constants that are one number at six digits are the same here, said as such on the item (ADR-0094).
MATERIAL_DIGITS = 6


def compare_models(their_deck, our_deck, shift: tuple[float, float], units: str, tolerance: float, same_mesh: bool) -> dict:
    """The two models: item by item when their meshes are one mesh, else without the mesh; and why, when it is the second."""
    reason = "the two meshes differ"
    if same_mesh:
        shift_si = (to_si(shift[0], "length", units), to_si(shift[1], "length", units))
        try:
            eq = deck_equivalence(moved_deck(their_deck, shift_si), our_deck, to_si(tolerance, "length", units), units, MATERIAL_DIGITS)
            return {"compared": "item by item", "same": eq.same_model, "items": items_of(eq.items),
                    "largest_node_offset": from_si(eq.largest_node_offset, "length", units)}
        except EquivalenceError as exc:
            reason = str(exc)
    try:
        items = equivalence_without_mesh(their_deck, our_deck, units, MATERIAL_DIGITS)
    except EquivalenceError as exc:
        return {"compared": "not compared", "same": None, "items": [], "reason": str(exc)}
    return {"compared": "without the mesh", "same": all(i.same is not False for i in items), "items": items_of(items), "reason": reason}


def zone_by_centroid(y: float, lines: dict):
    """A centroid's zone along the coupon, by our lines; None in the tabs and within one width of a tab line, which are not compared
    on another mesh."""
    low, high = lines["tab_length"] + lines["width"], lines["length"] - lines["tab_length"] - lines["width"]
    if lines["gauge_from"] <= y <= lines["gauge_to"]:
        return "gauge"
    return "free length" if low <= y <= high else None


def compare_by_position(ours_rows: dict, your_rows: dict, lines: dict, shift: tuple[float, float], floor: float):
    """On two meshes: each of their gauge and free-length elements beside ours nearest its centroid. Returns the tables by zone as
    `compare_every_output.compare` gives them, every pair's differences, the pairs, our values beside each of theirs, and our element
    for each of theirs."""
    ours_at, yours_at = team.centroids(ours_rows), team.centroids(your_rows)
    our_labels = sorted(ours_at)
    tree = cKDTree(np.array([ours_at[label] for label in our_labels]))
    reach = max(team.mean_size(ours_at), team.mean_size(yours_at))
    nearest, zones = {}, {}
    for label, (x, y) in yours_at.items():
        zone = zone_by_centroid(y + shift[1], lines)
        if zone is None:
            continue
        distance, index = tree.query((x + shift[0], y + shift[1]))
        if distance > reach:
            raise team.Refused(f"your element {label} at ({x:g}, {y:g}) has no element of ours within {reach:g}: not the same coupon")
        nearest[label], zones[label] = our_labels[int(index)], zone
    if not nearest:
        raise team.Refused("none of your elements lies between the tabs of our coupon: not the same coupon, or it lies along another axis")
    beside = {(label, layer): dict(ours_rows[(nearest[label], layer)], zone=zones[label]) for (label, layer) in your_rows if label in nearest}
    yours = {key: your_rows[key] for key in beside}
    tables, differences, pairs = team.compare(beside, yours, {label: label for label in nearest}, floor)
    for table in tables.values():
        for q in team.QUANTITIES:
            table[q]["our_element"] = nearest[table[q]["your_element"]]
    return tables, differences, pairs, beside, nearest


def reaction_of(reactions: list[dict] | None, meta: dict, shift: tuple[float, float]):
    """Their RF2 summed over the nodes at or above our top tab line, beside ours: `compare_every_output.reaction`'s rule."""
    if not reactions:
        return None
    top = meta["reaction"]["top_from"]
    tolerance = 1e-6 * max(1.0, abs(top))
    rows = [r for r in reactions if r["Y"] + shift[1] >= top - tolerance]
    if not rows:
        raise team.Refused(f"no reaction at or above the top tab line, Y = {top:g} {meta['length_unit']}")
    yours, ours = sum(r["RF2"] for r in rows), meta["reaction"]["ours"]
    return {"nodes": len(rows), "yours": yours, "ours": ours, "difference": (ours - yours) / abs(yours) if yours else float("inf")}


def compare(bundle_path: Path, ours_csv: Path, our_deck_path: Path, pairs_out: Path | None = None) -> dict:
    """The bundle beside a run of ours. Raises `BundleRefused` or `OutOfScope`; otherwise the result, with its verdict."""
    bundle = open_bundle(bundle_path)
    meta_path = ours_csv.with_suffix(".json")
    if not meta_path.is_file():
        raise OutOfScope([f"no {meta_path.name} beside {ours_csv.name}: both come from the run's 4-results folder"])
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    units = meta["units"]
    with tempfile.TemporaryDirectory() as folder:
        files = bundle.extract(folder)
        problems = []
        their_deck, their_facts = deck_facts(files["deck"], bundle.units)
        if their_deck is None:
            problems.append(f"our reader does not take the bundle's deck: {their_facts['reason']}")
        try:
            your_rows = team.read_rows(files["every_output"], False)
        except team.Refused as exc:
            problems.append(str(exc))
        try:
            reactions = read_reactions(files["reactions"]) if "reactions" in files else None
        except team.Refused as exc:
            problems.append(str(exc))
        if problems:
            raise OutOfScope(problems)
    ours_rows = team.read_rows(ours_csv, True)
    our_deck = read_deck(our_deck_path, units)
    your_rows, reactions = in_our_units(your_rows, reactions, bundle.units, units)
    layers, your_layers = sorted({key[1] for key in ours_rows}), sorted({key[1] for key in your_rows})
    if layers != your_layers:
        raise OutOfScope([f"your model has plies {your_layers} and ours {layers}: not the same layup"])

    result = {"bundle": bundle_facts(bundle), "units": units, "converted_from": bundle.units if bundle.units != units else None,
              "ours": {key: meta[key] for key in ("coupon", "written_by", "element", "elements", "layers")},
              "floor": meta["floor"], "acceptance": meta["acceptance"]}
    tolerance = team.PAIRING * team.mean_size(team.centroids(ours_rows))
    try:
        mapping, how, shift = team.pair(ours_rows, your_rows)
        same_mesh = True
    except team.Refused as exc:
        same_mesh, why_not = False, str(exc)

    if same_mesh:
        result["model"] = compare_models(their_deck, our_deck, shift, units, tolerance, True)
        tables, differences, pairs = team.compare(ours_rows, your_rows, mapping, meta["floor"])
        result["pairing"] = {"same_mesh": True, "how": how, "elements": len(mapping), "moved_by": list(shift)}
        rf = reaction_of(reactions, meta, shift)
        criteria = [{"criterion": c, "met": met, "evidence": evidence, "judged": True} for c, met, evidence in team.verdict(tables, rf, meta["acceptance"])]
        if pairs_out is not None:
            team.write_pairs(pairs_out, ours_rows, your_rows, pairs, differences)
    else:
        try:
            (tx, ty, _, _), (ox, oy, _, _) = outline(their_deck), outline(our_deck)
        except EquivalenceError as exc:
            raise OutOfScope([f"{why_not}; and the two coupons cannot be placed on each other: {exc}"]) from None
        shift = (from_si(ox - tx, "length", units), from_si(oy - ty, "length", units))
        result["model"] = compare_models(their_deck, our_deck, shift, units, tolerance, False)
        outline_item = next((i for i in result["model"]["items"] if i["item"] == "Outline"), None)
        if outline_item is None or outline_item["same"] is not True:
            tables, rf = {}, None
            said = "not compared: the two coupons are not the same size" if outline_item else f"not compared: {result['model'].get('reason')}"
            criteria = [{"criterion": c, "met": None, "evidence": said, "judged": True}
                        for c in ("Reaction within 1 %", "Gauge: every value within 1 %")]
            result["pairing"] = {"same_mesh": False, "how": said, "elements": 0, "moved_by": list(shift), "why_not_element_by_element": why_not}
        else:
            tables, differences, pairs, beside, nearest = compare_by_position(ours_rows, your_rows, meta["lines"], shift, meta["floor"])
            result["pairing"] = {"same_mesh": False, "elements": len(nearest), "moved_by": list(shift), "why_not_element_by_element": why_not,
                                 "how": "by position on two meshes: each of your elements in the gauge and the free length beside ours nearest its centroid"}
            rf = reaction_of(reactions, meta, shift)
            criteria = []
            for c, met, evidence in team.verdict(tables, rf, meta["acceptance"]):
                reported = c.startswith("Free length")
                criteria.append({"criterion": c, "met": None if reported else met, "judged": not reported,
                                 "evidence": f"reported, not judged on another mesh: {evidence}" if reported else evidence})
            if pairs_out is not None:
                team.write_pairs(pairs_out, beside, your_rows, pairs, differences)
    result["reaction"], result["zones"], result["criteria"] = rf, tables, criteria
    judged = [c["met"] for c in criteria if c["judged"]] + [result["model"]["same"]]
    result["verdict"] = "differs" if any(v is False for v in judged) else "incomplete" if any(v is None for v in judged) else "agrees"
    result["summary"] = summary_of(result)
    return result


def summary_of(result: dict) -> dict:
    """The comparison as the page's card and the terminal say it first, so that neither counts for itself (ADR-0001): how many items
    of the model were judged and how many differ, each zone's count of values with its worst quantity and where that is, the number
    of places that differ (items of the model, and criteria judged and not met), and the units' names."""
    items = result["model"]["items"]
    zones = {}
    for zone, table in result["zones"].items():
        worst = max(team.QUANTITIES, key=lambda q: table[q]["worst"])
        zones[zone] = {"elements": table.get("elements"), "values": sum(table[q]["values"] for q in team.QUANTITIES), "quantity": worst,
                       **{key: table[worst].get(key) for key in ("worst", "your_element", "our_element", "layer", "yours", "ours")}}
    different = sum(1 for i in items if i["same"] is False)
    labels = UNIT_LABEL[result["units"]]
    return {"places": different + sum(1 for c in result["criteria"] if c["judged"] and c["met"] is False),
            "model": {"items": len(items), "judged": sum(1 for i in items if i["same"] is not None), "different": different},
            "zones": zones, "labels": {kind: labels[kind] for kind in ("length", "stress", "force")}}


WORDS = {"agrees": "Agrees with ours", "differs": "Differs from ours", "incomplete": "Not every part could be compared"}


def print_comparison(result: dict) -> None:
    b, model, pairing = result["bundle"], result["model"], result["pairing"]
    solver = f" ({b['written_by']['abaqus']})" if b["written_by"].get("abaqus") else ""
    print(f"{WORDS[result['verdict']]}: {b['job'] or 'the model sent'}{solver} beside {result['ours']['coupon']} ({result['ours']['written_by']})")
    if result["converted_from"]:
        print(f"your values were written in {result['converted_from']} and are shown in {result['units']}")
    said = result["summary"]
    different = [i for i in model["items"] if i["same"] is False]
    if model["compared"] == "not compared":
        print(f"\nThe model: not compared ({model['reason']})")
    else:
        how = model["compared"] + ("" if model["compared"] == "item by item" else f", because {model['reason']}")
        print(f"\nThe model ({how}): " + (f"the same as ours on every one of {said['model']['judged']} items" if not different
                                           else f"{said['model']['different']} of {said['model']['judged']} items differ"))
        for i in different:
            print(f"  {i['item']}: yours {i['yours']}; ours {i['ours']}")
    print(f"\nThe results: {pairing['elements']} elements paired {pairing['how']}")
    for zone, t in said["zones"].items():
        print(f"  {zone}: {t['values']} values, the worst {100 * t['worst']:.4g} % ({t['quantity']}, your element "
              f"{t['your_element']} ply {t['layer']}: yours {t['yours']:.6g}, ours {t['ours']:.6g})")
    print("\nVerdict")
    for c in result["criteria"]:
        state = "met" if c["met"] else "NOT MET" if c["met"] is False else "not judged"
        print(f"  {state}: {c['criterion']} ({c['evidence']})")


def print_check(result: dict) -> None:
    b = result["bundle"]
    print(f"bundle version {b['bundle_version']}, {b['units']}, written {b['created']} by {b['written_by']['connector']}"
          + (f" under {b['written_by']['abaqus']}" if b["written_by"].get("abaqus") else ""))
    for role, entry in b["files"].items():
        print(f"  {role}: {entry['path']}, {entry['bytes']} bytes, SHA-256 matches")
    deck = result["deck"]
    if deck["read"]:
        print(f"the deck: our reader takes it: {deck.get('elements', '?')} {deck.get('element_type') or 'elements'}, {deck.get('nodes', '?')} nodes"
              + (f", {deck['plies']} plies [{deck['layup']}]" if "plies" in deck else ""))
    else:
        print(f"the deck: our reader does not take it: {deck['reason']}")
    every = result["every_output"]
    print(f"every output: {every['rows']} rows, {every['elements']} elements by {every['layers']} plies" if every["read"]
          else f"every output: not read: {every['reason']}")
    rf = result["reactions"]
    print("the reactions: none in the bundle, so the pull force cannot be compared" if rf is None
          else f"the reactions: {rf['nodes']} nodes" if rf["read"] else f"the reactions: not read: {rf['reason']}")
    model = result.get("model")
    if model is None:
        print("the model as built: not in the bundle (the connector adds it with --cae)")
    elif not model["read"]:
        print(f"the model as built: not read: {model['reason']}")
    else:
        counted = ", ".join(f"{count} {name.replace('_', ' ')}" for name, count in model["groups"].items())
        plies = "; ".join(f"layup {layup['name']}: {layup['plies']} plies" for layup in model["layups"])
        print(f"the model as built: {model['model']}: {counted}" + (f"; {plies}" if plies else ""))
        for entry in model["not_read"]:
            print(f"  not read from the .cae: {entry}")
    print("in scope: the comparison takes this bundle" if result["in_scope"] else "out of scope: the comparison does not take this bundle")


def pack(args) -> int:
    results, abaqus = None, None
    if args.provenance:
        results = json.loads(args.provenance.read_text(encoding="utf-8"))
        abaqus = results.get("solver")
    files = {"deck": args.deck, "every_output": args.every_output}
    for role, path in (("reactions", args.rf), ("journal", args.journal), ("model", args.model)):
        if path:
            files[role] = path
    bundle = write_bundle(args.out, files, args.units, connector=f"anisotropy-fea {__version__} (tools/abaqus_upload.py pack)", abaqus=abaqus,
                          job=args.job or args.deck.stem, coupon=args.coupon, results=results)
    print(f"{args.out}: bundle version {bundle.manifest['bundle_version']}, {len(bundle.files)} files, SHA-256 {bundle.sha256}")
    return 0


CONNECTOR_FILES = {"anisotropy_connector.py": TOOLS, "abaqus_every_output.py": TOOLS, "abaqus_extract_fields.py": TOOLS,
                   "bundle.py": TOOLS.parent / "src" / "anisotropy_fea", "anisotropy_menu.py": TOOLS, "anisotropy_plugin.py": TOOLS}
CONNECTOR_README = """The Anisotropy connector: one command under your own Abaqus that turns a finished job into one file to send.

Keep these files together in one folder. Nothing is sent anywhere unless you ask: the command writes <job>-anisotropy.zip beside your ODB.

The results and the input file Abaqus solved (no seat of Abaqus/CAE is used):

    abaqus python anisotropy_connector.py <job>.odb --units mm-MPa

The same, with the model as built read from your .cae and its journal. Your .cae is not opened: a copy in a
temporary folder is. Put the .odb first. Abaqus/CAE ends with exit code 0 whatever happened, so read the line the
command prints: the bundle's path, or "refused:" with the reason. It also writes its own abaqus.rpy where you start it.

    abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units mm-MPa --cae <model>.cae

--units states the system your model is written in, mm-MPa or m-Pa: an Abaqus model carries none.
The job must ask for S and E at each ply's middle section point, and RF, as the package's input file does.

To send the bundle as well, add  --send https://<the site>/api  to either command. It goes with the upload token you
created on the site: put the token in a file and name it with --token-file, or set ANISOTROPY_UPLOAD_TOKEN. Never put the
token on the command line. The upload is yours alone, and the command prints whether it agrees with our run.
Read the line it prints, "sent:" or "not sent:" with the reason: Abaqus ends with exit code 0 either way.

To send every job as it finishes, leave this running in a terminal; it ends with Ctrl+C:

    abaqus python anisotropy_connector.py --watch <the folder your jobs run in> --units mm-MPa --send https://<the site>/api --token-file <file>

It takes a job when its .sta says the analysis completed. Jobs that had finished before it started are left alone
(add --existing to take them too). What it did for each job is in anisotropy-watch.json in that folder, so no ODB is
sent twice. Without --send it writes each <job>-anisotropy.zip and sends nothing.

A menu in Abaqus/CAE (Abaqus 2024 or later): copy this whole folder into a folder named abaqus_plugins in your home
directory (create it if it is not there) and start Abaqus/CAE again. Under Plug-ins > Anisotropy you then have

    Open from Anisotropy...   builds the coupon from the build script you downloaded from a run's page
    Send to Anisotropy...     writes the file from a finished job, with the model open in the session, and sends it

Each asks in a small box and answers in the message area under the viewport. Your .cae and your ODB are not changed.
"""


def connector_zip(out: Path) -> list[str]:
    """The connector's files and a note of its two commands in one zip to hand over, the same bytes for the same files."""
    names = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in [(n, (folder / n).read_bytes()) for n, folder in CONNECTOR_FILES.items()] + [("README.txt", CONNECTOR_README.encode())]:
            archive.writestr(zipfile.ZipInfo(f"anisotropy-connector/{name}", EPOCH), data, zipfile.ZIP_DEFLATED)
            names.append(name)
    return names


def plain(value):
    """The result as JSON takes it: a number that is not finite (a difference from a reaction of zero) becomes null."""
    if isinstance(value, dict):
        return {key: plain(v) for key, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json(path: Path | None, result: dict) -> None:
    if path is not None:
        path.write_text(json.dumps(plain(result), indent=1, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("check", help="what a bundle holds, and whether the comparison takes it")
    c.add_argument("bundle", type=Path)
    c.add_argument("--json", type=Path, default=None)
    c = commands.add_parser("compare", help="a bundle beside a run of ours")
    c.add_argument("bundle", type=Path)
    c.add_argument("--ours", type=Path, required=True, help="ours-every-output.csv of the run, its .json beside it")
    c.add_argument("--our-deck", type=Path, required=True, help="our deck of the same run (.inp)")
    c.add_argument("--json", type=Path, default=None)
    c.add_argument("--pairs", type=Path, default=None, help="write every pair and quantity to this CSV")
    c = commands.add_parser("pack", help="write a bundle from a deck and the files abaqus_every_output.py wrote")
    c.add_argument("--deck", type=Path, required=True)
    c.add_argument("--every-output", type=Path, required=True)
    c.add_argument("--rf", type=Path, default=None)
    c.add_argument("--provenance", type=Path, default=None, help="<job>-every-output.json, where the results were read in the ODB")
    c.add_argument("--journal", type=Path, default=None)
    c.add_argument("--model", type=Path, default=None)
    c.add_argument("--units", required=True, choices=sorted(DECK_UNIT_SYSTEMS))
    c.add_argument("--job", default=None)
    c.add_argument("--coupon", default=None)
    c.add_argument("--out", type=Path, required=True)
    c = commands.add_parser("connector", help="write the connector's files as one zip to hand to a user of Abaqus")
    c.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "connector":
            print(f"{args.out}: {', '.join(connector_zip(args.out))}")
            return 0
        if args.command == "pack":
            return pack(args)
        if args.command == "check":
            result = check(args.bundle)
            write_json(args.json, result)
            print_check(result)
            return 0 if result["in_scope"] else 2
        result = compare(args.bundle, args.ours, args.our_deck, args.pairs)
    except (BundleRefused, OutOfScope, team.Refused) as exc:
        problems = list(exc.problems) if hasattr(exc, "problems") else [str(exc)]
        write_json(getattr(args, "json", None), {"verdict": "refused", "problems": problems})
        print("refused:\n" + "\n".join(f"  {p}" for p in problems), file=sys.stderr)
        return 2
    write_json(args.json, result)
    print_comparison(result)
    return 0 if result["verdict"] == "agrees" else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
