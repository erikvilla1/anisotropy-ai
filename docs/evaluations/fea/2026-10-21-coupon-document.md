# Evaluation: one document per coupon, in chapters (ADR-0041) | 2026-10-21

- **Scope.**
  - New: `docs/models/coupon.py`.
  - Changed: `manual.theory` gains an `only` section filter, `rebuild.Helpers` gains `tools`, `build.py` gains `deck_facts()` with `--all` limited to the checks, and `team.py` becomes the team comparison's sections and files.
  - Removed: `docs/models/share.py`.
  - Each coupon's `documents/` now holds one PDF, its LaTeX and one zip.
- **Branch:** `feat/coupon-document`, stacked on `feat/coupon-folders` (#71).

## Commands and captured output

From the repository root:

```text
uv run --project fea python docs/models/coupon.py --all
X840PW-OHT-L1: document written to .local\fea\X840PW-OHT-L1\documents\X840PW-OHT-L1.pdf   zip 2026-10-21_X840PW-OHT-L1.zip
X840PW-UNC-L1: document written to .local\fea\X840PW-UNC-L1\documents\X840PW-UNC-L1.pdf   zip 2026-10-21_X840PW-UNC-L1.zip
X840PW-UNT-L1: document written to .local\fea\X840PW-UNT-L1\documents\X840PW-UNT-L1.pdf   zip 2026-10-21_X840PW-UNT-L1.zip
X840PW-UNT-L1: team comparison figures written to fea\models\X840PW-UNT-L1\records\X840PW-UNT-L1-team-summary.toml
```

The tension document has 79 pages and builds in 36 s. Its contents run:

- **1 The problem:** p. 4.
- **2 The physics:** p. 6. Ply stiffness, rotation and laminate stiffness; the finite element kernel; failure; the hand check on p. 28.
- **3 Building the part in our engine:** p. 31.
- **4 Building the part in Abaqus/CAE:** p. 35. What the team built, then the step-by-step guide.
- **5 Results from our engine:** p. 48.
- **6 Verification:** p. 50.
- **7 What this shows:** then the appendices.

Rendered pages were checked by eye: the title page, Chapter 1, the opening of Chapter 4 (the equivalence table, all "same"), and Chapter 5 with the first-ply-failure table.

Chapter 5 gives, on the team's build:
- the reaction, 105993 N;
- the centre element's strain, eps_y 0.20186;
- first-ply failure in ply 2 (45°) at 0.03819 of the 10 mm pull by maximum stress (in-plane shear, element 225), and at 0.03711 by Tsai-Hill.

So the 10 mm pull is about 26 times the load at first-ply failure, and the title page says the loading is past it.

The superseded documents were removed from each `documents/`: tension's three PDFs and two zips, the other coupons' PDF and model zip each, and their `latex/` folders. Each `documents/` now holds `<coupon>.pdf`, `latex/<coupon>/` and `<date>_<coupon>.zip`.

Tests from `fea/`:
- `uv run pytest -q tests/test_coupon_document.py` gives `5 passed`.
- `uv run pytest -q -ra tests ../engine/tests` gives `743 passed in 176.31s`, with none skipped.
- `tools/case_pages.py --check` reports all five pages current.

The first fixture run failed: the problem statement assumed tabs, and the fixture's coupling holds an end row without tabs. The statement now handles both.

## Not run, UNVERIFIED

- CI building `coupon.py --all` with Gmsh on Linux, and uploading `.local/fea/*/documents/*.pdf`.
