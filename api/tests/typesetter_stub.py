"""A stand-in for Tectonic, for the reports written on request (ADR-0064 amendment 3): a script that takes Tectonic's arguments
(`--outdir <folder> <file>.tex`) and writes <file>.pdf from the LaTeX it was given, or fails as Tectonic does on LaTeX it cannot set.
The tests then need no Tectonic."""

import sys
from pathlib import Path

SCRIPT = r'''#!{python}
import pathlib, sys, time
out, tex = pathlib.Path(sys.argv[sys.argv.index("--outdir") + 1]), pathlib.Path(sys.argv[-1])
text = tex.read_text(encoding="utf-8")
while "HOLD" in text and not (pathlib.Path(r"{folder}") / "release-typesetter").exists():
    time.sleep(0.02)
if "REFUSE" in text:
    sys.stderr.write("error: something Tectonic prints first\\nerror: Undefined control sequence\\n")
    sys.exit(1)
assert (tex.parent / "figures" / "model.png").is_file(), "the report names a figure its source does not hold"
(out / (tex.stem + ".pdf")).write_bytes(b"%PDF typeset from: " + text.encode("utf-8"))
'''


def stand_in_typesetter(folder: Path, monkeypatch) -> Path:
    """Put the stand-in in `folder` and make it the typesetter the API finds. A report whose LaTeX says HOLD waits for the file
    `release-typesetter` in `folder`; one that says REFUSE fails."""
    from anisotropy_api import coupon_jobs

    script = folder / "tectonic-stand-in"
    script.write_text(SCRIPT.format(python=sys.executable, folder=folder), encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setattr(coupon_jobs, "typesetter", lambda: str(script))
    return script
