"""Rewrite every deck from its spec, in its test folder's decks/ (ADR-0036): the checks' and, on the founder's machine, the coupon models'.

    uv run python tools/regenerate_decks.py                      # every spec under fea/checks/ and .local/fea/
    uv run python tools/regenerate_decks.py unnotched-im7-8552-nodal  # one spec, by name
    uv run python tools/regenerate_decks.py <coupon> --ccx       # also write a CalculiX deck it does not have yet

The Abaqus deck `decks/<spec>-abaqus.inp` is always written. The CalculiX deck `decks/<spec>-ccx.inp` (the spec promoted to
order 2, S8R) is rewritten when it exists, or written with --ccx. Prints each deck and whether its text changed. A deck that
changed invalidates the digests of any record that names it: re-run CalculiX and the record tool for those, unless the deck
changed in its output requests alone (`*Output`, `*Node Print`, `*El Print` and their data lines), which no solver's numbers depend
on: then `--refresh-digests` rewrites the record's digest of that deck and says so, and the record stands.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.case_pages import rel
from anisotropy_fea.compare import sha256_of
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import write_abaqus


def write(path, text: str) -> str:
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return "new" if old is None else ("unchanged" if old == text else "CHANGED")


OUTPUT_KEYWORDS = ("*output", "*element output", "*node output", "*node print", "*el print", "*node file", "*el file", "*restart")


def without_output_requests(text: str) -> str:
    """The deck without its output requests and their data lines, and without its comments (`**`, such as the header naming the spec's
    digest): what every solver's numbers depend on."""
    kept, skipping = [], False
    for line in text.splitlines():
        if line.startswith("**"):
            continue
        if line.startswith("*"):
            skipping = line.lower().startswith(OUTPUT_KEYWORDS)
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


def refresh_digests(changed: dict[Path, str]) -> list[str]:
    """For every record naming a deck in `changed` (deck path -> its text before this run): rewrite the record's digest of that deck
    when the deck changed in its output requests alone, else say the record needs a new run. A line per record and deck."""
    lines = []
    for record_path in paths.all_records():
        record = tomllib.loads(record_path.read_text(encoding="utf-8"))
        text = record_path.read_text(encoding="utf-8")
        for key in ("deck_kernel", "deck_reference"):
            deck = (record_path.parent / record[key]).resolve()
            if deck not in changed:
                continue
            if without_output_requests(changed[deck]) != without_output_requests(deck.read_text(encoding="utf-8")):
                lines.append(f"{'needs run':9}  {rel(record_path)}: {deck.name} changed beyond its output requests; re-run the solver and the record tool")
                continue
            digest = sha256_of(deck)
            text, n = re.subn(rf'^{key}_sha256 = "[0-9a-f]+"$', f'{key}_sha256 = "{digest}"', text, flags=re.M)
            lines.append(f"{'refreshed' if n == 1 else 'NOT FOUND':9}  {rel(record_path)}: {key}_sha256 of {deck.name}, output requests only")
        if text != record_path.read_text(encoding="utf-8"):
            record_path.write_text(text, encoding="utf-8", newline="\n")
    return lines


def regenerate(spec_path, ccx: bool, writer=write, changed: dict[Path, str] | None = None) -> list[str]:
    """One spec's decks, written through `writer(path, text)`: a line per deck saying whether it is new, unchanged or changed, or
    why the CalculiX deck was skipped (a spec with couplings has none; its -nodal twin carries it). With `changed`, a dict, every
    deck whose text changed is added to it with its text before the write, for `refresh_digests`."""
    spec = load_spec(spec_path)
    abaqus = paths.deck_path(spec_path, "abaqus")
    before = abaqus.read_text(encoding="utf-8").replace("\r\n", "\n") if abaqus.exists() else None
    status = writer(abaqus, write_abaqus(build_model(spec)))
    if changed is not None and status == "CHANGED" and before is not None:
        changed[abaqus.resolve()] = before
    lines = [f"{status:9}  {rel(abaqus)}"]
    target = paths.deck_path(spec_path, "ccx")
    if target.exists() or ccx:
        from anisotropy_fea.write_calculix import CalculixWriterError, write_calculix

        order2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
        try:
            text = write_calculix(build_model(order2))
        except CalculixWriterError as exc:
            lines.append(f"{'skipped':9}  {rel(target)}: {exc}")
        else:
            before_ccx = target.read_text(encoding="utf-8").replace("\r\n", "\n") if target.exists() else None
            status_ccx = writer(target, text)
            if changed is not None and status_ccx == "CHANGED" and before_ccx is not None:
                changed[target.resolve()] = before_ccx
            lines.append(f"{status_ccx:9}  {rel(target)}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="spec names (file stems); default every committed spec")
    parser.add_argument("--ccx", action="store_true", help="also write CalculiX decks that do not exist yet")
    parser.add_argument("--refresh-digests", action="store_true",
                        help="rewrite the digests of records naming an Abaqus deck that changed in its output requests alone")
    args = parser.parse_args()
    specs = [paths.spec_path(name) for name in args.names] if args.names else paths.all_specs()
    changed: dict[Path, str] = {}
    for spec_path in specs:
        for line in regenerate(spec_path, args.ccx, changed=changed):
            print(line)
    if args.refresh_digests:
        for line in refresh_digests(changed):
            print(line)


if __name__ == "__main__":
    main()
