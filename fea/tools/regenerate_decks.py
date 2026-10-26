"""Rewrite every deck from its spec, in its test folder's decks/ (ADR-0036): the checks' and, on the founder's machine, the coupon models'.

    uv run python tools/regenerate_decks.py                      # every spec under fea/checks/ and .local/fea/
    uv run python tools/regenerate_decks.py unnotched-im7-8552-nodal  # one spec, by name
    uv run python tools/regenerate_decks.py <coupon> --ccx       # also write a CalculiX deck it does not have yet

The Abaqus deck `decks/<spec>-abaqus.inp` is always written. The CalculiX deck `decks/<spec>-ccx.inp` (the spec promoted to
order 2, S8R) is rewritten when it exists, or written with --ccx. Prints each deck and whether its text changed. A deck that
changed invalidates the digests of any record that names it: re-run CalculiX and the record tool for those.
"""

from __future__ import annotations

import argparse

from anisotropy_fea import paths
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import write_abaqus


def write(path, text: str) -> str:
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return "new" if old is None else ("unchanged" if old == text else "CHANGED")


def regenerate(spec_path, ccx: bool, writer=write) -> list[str]:
    """One spec's decks, written through `writer(path, text)`: a line per deck saying whether it is new, unchanged or changed, or
    why the CalculiX deck was skipped (a spec with couplings has none; its -nodal twin carries it)."""
    spec = load_spec(spec_path)
    abaqus = paths.deck_path(spec_path, "abaqus")
    lines = [f"{writer(abaqus, write_abaqus(build_model(spec))):9}  {abaqus.relative_to(paths.ROOT).as_posix()}"]
    target = paths.deck_path(spec_path, "ccx")
    if target.exists() or ccx:
        from anisotropy_fea.write_calculix import CalculixWriterError, write_calculix

        order2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
        try:
            text = write_calculix(build_model(order2))
        except CalculixWriterError as exc:
            lines.append(f"{'skipped':9}  {target.relative_to(paths.ROOT).as_posix()}: {exc}")
        else:
            lines.append(f"{writer(target, text):9}  {target.relative_to(paths.ROOT).as_posix()}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="spec names (file stems); default every committed spec")
    parser.add_argument("--ccx", action="store_true", help="also write CalculiX decks that do not exist yet")
    args = parser.parse_args()
    specs = [paths.spec_path(name) for name in args.names] if args.names else paths.all_specs()
    for spec_path in specs:
        for line in regenerate(spec_path, args.ccx):
            print(line)


if __name__ == "__main__":
    main()
