"""Fill Tectonic's cache at image build (ADR-0056), so a running container never downloads a TeX file.

Tectonic fetches each package, font and format file from its bundle the first time a document needs it. Inside the solver
container the network may be off, so this script builds the real thing once, at image build time: the public IM7/8552 coupon
(tests/fixtures/studio/values.json, the studio's values fixture; never a team coupon, ADR-0042) goes through
fea/tools/run_coupon.py to its package with the PDF, exactly as a job runs it, and every TeX file the coupon document asks
for lands in the cache. A hand-written warm-up document lagged the real one (the first try missed `\\boldsymbol`'s font), so
the real document is the warm-up. The coupon's files are removed afterwards: the image carries no run. The CI job `image` then
proves the cache is complete by running the same job with the network off (docker/check-image.py).

Run from the repository root with the fea environment: `uv run --project fea python docker/warm-tectonic.py`. It refuses to run
where `.local/` already exists (a laptop with its private workspace), because it deletes that folder when it is done.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
VALUES = ROOT / "tests" / "fixtures" / "studio" / "values.json"
RUNNER = ROOT / "fea" / "tools" / "run_coupon.py"


def cache() -> Path:
    """Where Tectonic keeps its bundle files on Linux: `tectonic` under $XDG_CACHE_HOME or ~/.cache (Tectonic 0.17 writes the
    lowercase name there; the capitalised one is checked too, as a later release may use it)."""
    root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return next((root / name for name in ("tectonic", "Tectonic") if (root / name).is_dir()), root / "tectonic")


def size(folder: Path) -> int:
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else 0


def main() -> None:
    if shutil.which("tectonic") is None:
        raise SystemExit("tectonic is not on PATH")
    if LOCAL.exists():
        raise SystemExit(f"{LOCAL} exists: this script is for the image build, where it does not; it would delete that folder")
    if not VALUES.is_file():
        raise SystemExit(f"{VALUES} is missing: .dockerignore must keep this one file of tests/ in the build context")
    try:
        subprocess.run([sys.executable, str(RUNNER), str(VALUES), "--run-by", "image build"], cwd=ROOT, check=True)
        pdfs = sorted((LOCAL / "fea").glob("*/documents/*/*.pdf"))
        if len(pdfs) != 1 or pdfs[0].stat().st_size == 0:
            raise SystemExit(f"expected one coupon PDF under {LOCAL / 'fea'}, found {[p.name for p in pdfs]}")
        print(f"warm-tectonic: {pdfs[0].name} is {pdfs[0].stat().st_size} bytes; the cache at {cache()} holds {size(cache()) / 1e6:.0f} MB")
    finally:
        shutil.rmtree(LOCAL, ignore_errors=True)


if __name__ == "__main__":
    main()
