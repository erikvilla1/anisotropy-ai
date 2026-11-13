"""Write the script that builds a coupon in Abaqus/CAE as a native model, from its spec (ADR-0094, step 3).

    uv run python tools/abaqus_build_script.py <coupon>.toml [--out <script>.py]

The script is what `anisotropy_fea.write_cae_script` writes from the same model the input deck is written from. In Abaqus/CAE it is run
with File > Run Script, or from a terminal with  abaqus cae noGUI=<script>.py -- save=<model>.cae . A coupon it cannot draw is refused
with every reason (exit 2).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import SpecError, load_spec
from anisotropy_fea.write_cae_script import CaeScriptError, cae_facts, write_cae_script


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path, help="the coupon's spec (.toml)")
    parser.add_argument("--out", type=Path, default=None, help="the script to write; default <model's name>-build.py beside the spec")
    args = parser.parse_args(argv)
    try:
        model = build_model(load_spec(args.spec))
        facts = cae_facts(model)
        text = write_cae_script(model)
    except CaeScriptError as exc:
        print("refused:\n" + "\n".join(f"  {problem}" for problem in exc.problems), file=sys.stderr)
        return 2
    except (SpecError, ValueError, OSError) as exc:
        print(f"refused:\n  {str(exc).splitlines()[0]}", file=sys.stderr)
        return 2
    out = args.out or args.spec.with_name(f"{facts['model']}-build.py")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{out}: builds model {facts['model']} in Abaqus/CAE, {sum(facts['rows']) * facts['columns']} {facts['element']} elements, units {facts['units']}")
    print(f"SHA-256 {hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
