"""Ask Abaqus which output requests our composite deck may carry, before the deck asks for them (ADR-0066 amendment 2, ADR-0089 part 7a).

    uv run python tools/abaqus_detect.py --out ../.local/fea/checks/d3039-im7-8552/runs/abaqus-detect         # write the decks only
    uv run python tools/abaqus_detect.py --out <folder> --run                                                 # and run them (Abaqus + licence)

Writes, from the public D3039 check's spec, our Abaqus deck with one more request per candidate, each in a deck of its own so that one
refusal cannot hide the others:

- `field-points`: `*Element Output` with the middle section point of every layer listed first, so CAE contours show every ply;
- `sinv`, `sp`, `tshr`, `cfailure`, `ep`: one `*El Print` table each at the centre element, every section point of every layer
  (`SINV` Mises, Tresca, pressure; `SP` the principal stresses; `TSHR` the transverse shear stress of a shell; `CFAILURE` the failure
  indices of `*Fail Stress`; `EP` the principal strains).

With --run it runs `abaqus datacheck` on each, then a full run of those the datacheck accepts, and prints per deck: accepted or the
error Abaqus gave, and the columns of each printed table (read with `anisotropy_fea.abaqus_dat`). Nothing is concluded here: the person
running it copies what it printed into `fea/checks/abaqus-conventions.toml`. Which identifiers exist, where a section-point list goes under
`*Element Output`, the order of the principal stresses at a shell section point and whether CFAILURE is 1/R or 1/R squared are UNVERIFIED
until this has run. Needs Abaqus (ANISOTROPY_ABAQUS or `abaqus` on PATH) and a licence seat (the founder's, over the UCSD VPN).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.abaqus import find_abaqus
from anisotropy_fea.abaqus_dat import AbaqusDatError, parse_abaqus_dat
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import SECTION_POINTS, write_abaqus

SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
PROBE = "Probe-centre"


def every_point(layers: int) -> str:
    return ", ".join(str(p) for p in range(1, SECTION_POINTS * layers + 1))


def middles(layers: int) -> str:
    return ", ".join(str(SECTION_POINTS * k + (SECTION_POINTS + 1) // 2) for k in range(layers))


def candidates(layers: int) -> dict[str, list[str]]:
    """Each candidate's lines, inserted before `*End Step`."""
    printed = lambda variable: [f"*El Print, elset={PROBE}, position=CENTROIDAL", every_point(layers), variable]  # noqa: E731
    return {
        "field-points": ["*Output, field", "*Element Output, directions=YES", middles(layers), "S, E, SF, SE"],
        "sinv": printed("SINV"),
        "sp": printed("SP"),
        "tshr": printed("TSHR"),
        "cfailure": printed("CFAILURE"),
        "ep": printed("EP"),
    }


def decks(out: Path) -> dict[str, Path]:
    model = build_model(load_spec(SPEC))
    base = write_abaqus(model)
    if "*End Step" not in base:
        raise SystemExit("our deck has no *End Step; the writer changed")
    layers = len(model.section.plies)
    written = {}
    out.mkdir(parents=True, exist_ok=True)
    for name, lines in candidates(layers).items():
        text = base.replace("*End Step", "\n".join(lines) + "\n*End Step", 1)
        path = out / f"detect-{name}.inp"
        path.write_text(text, encoding="utf-8", newline="\n")
        written[name] = path
    return written


def run(abaqus: Path, deck: Path, datacheck: bool) -> tuple[bool, str]:
    job = deck.stem + ("-dc" if datacheck else "")
    command = [str(abaqus), f"job={job}", f"input={deck.name}", "interactive"] + (["datacheck"] if datacheck else [])
    done = subprocess.run(command, cwd=deck.parent, capture_output=True, text=True, shell=sys.platform == "win32", timeout=900)
    dat = deck.parent / f"{job}.dat"
    text = dat.read_text(encoding="utf-8", errors="replace") if dat.is_file() else ""
    errors = re.findall(r"\*\*\*ERROR:[^\n]*(?:\n(?!\s*\*\*\*)[^\n]*){0,3}", text)
    message = "; ".join(" ".join(e.split()) for e in errors)
    if not message and done.returncode != 0:
        tail = (done.stdout + done.stderr).strip().splitlines()
        message = tail[-1] if tail else f"exit code {done.returncode}"
    return done.returncode == 0 and not errors, message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="a run folder under .local (Abaqus writes its files there)")
    parser.add_argument("--run", action="store_true", help="run datacheck and then a full run of each deck (needs Abaqus and a licence seat)")
    parser.add_argument("--read", action="store_true", help="run nothing: read the .dat each deck's earlier run left in --out")
    parser.add_argument("--only", nargs="+", default=None, help="these candidates only, by name")
    args = parser.parse_args(argv)
    written = decks(args.out)
    if args.only:
        unknown = sorted(set(args.only) - set(written))
        if unknown:
            parser.error(f"no candidate {', '.join(unknown)}; the candidates are {', '.join(written)}")
        written = {name: path for name, path in written.items() if name in args.only}
    for name, path in written.items():
        print(f"written    {path}")
    if not (args.run or args.read):
        return 0
    abaqus = find_abaqus() if args.run else None
    if args.run and abaqus is None:
        print("abaqus_detect: Abaqus not found (ANISOTROPY_ABAQUS or abaqus on PATH)", file=sys.stderr)
        return 2
    for name, deck in written.items():
        if args.run:
            accepted, why = run(abaqus, deck, datacheck=True)
            if not accepted:
                print(f"{name:13} datacheck REFUSED: {why or 'see ' + deck.stem + '-dc.dat'}")
                continue
            solved, why = run(abaqus, deck, datacheck=False)
            if not solved:
                print(f"{name:13} run FAILED: {why or 'see ' + deck.stem + '.dat'}")
                continue
        dat_path = deck.parent / f"{deck.stem}.dat"
        if not dat_path.is_file():
            print(f"{name:13} no {dat_path.name} to read")
            continue
        try:
            dat = parse_abaqus_dat(dat_path.read_text(encoding="utf-8", errors="replace"))
        except AbaqusDatError as exc:  # one deck's .dat that does not read stops none of the others
            print(f"{name:13} accepted, but its .dat does not read: {exc}")
            continue
        tables = [f"{t.kind} {t.set_name}: {', '.join(t.columns)} ({len(t.rows)} rows)" for t in dat.tables]
        print(f"{name:13} accepted; printed tables: " + (" | ".join(tables) or "none"))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
