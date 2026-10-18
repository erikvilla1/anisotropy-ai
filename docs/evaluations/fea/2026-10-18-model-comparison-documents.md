# Evaluation: one generated LaTeX document per model comparison (ADR-0031) | 2026-10-18

- Scope: `fea/src/anisotropy_fea/report.py` (every compared number as a row with its error in four forms, per-group statistics, element positions, the classical laminate theory hand check computed by the engine from the deck's section and gripped node rows), `docs/models/build.py` and `docs/models/preamble.tex` (one self-contained LaTeX document per comparison record, compiled with Tectonic, reusing the manual's converters), `docs/models/README.md`, the reading-note convention `<record>.md` beside a record (committed for the CalculiX record; local for the team's Abaqus record), `fea/tests/test_report.py`, a CI step uploading the committed records' PDFs as `model-documents`, `docs/models/build/` git-ignored. `fea/examples/plot_deck.py` lays its six panels in one row for coupons longer than three times their width, with wrapped titles.
- Why: the founder asked for documentation of every model comparison, separate from the manual, that shows the mathematics, the analysis, the code and the error between the reference solver and our kernel, one document per model, as the argument for each analysis.
- Environment: Windows 11; Tectonic 0.17.0 at `%LOCALAPPDATA%\Programs\tectonic`; CalculiX not on this shell's PATH, so the solver tests skipped; `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run python -m pytest -q -ra tests ../engine/tests`

```text
613 passed, 6 skipped in 59.21s
```

(611 before this chunk plus 8 new tests in `test_report.py`; the 6 skips are the CalculiX runs, `ANISOTROPY_CCX` not set in this shell.)

From the repository root: `uv run --project fea python docs/models/build.py --all`

```text
59 numbers compared, 59 agree; LaTeX written to ...\docs\models\build\unnotched-im7-8552-nodal-calculix\unnotched-im7-8552-nodal-calculix.tex
Document written to ...\docs\models\build\unnotched-im7-8552-nodal-calculix\unnotched-im7-8552-nodal-calculix.pdf
```

32 pages, 604 KB. From the root: `uv run --project fea python docs/models/build.py .local/abaqus/comparisons/tension-test-abaqus.toml`

```text
1800 numbers compared, 1800 agree; LaTeX written to ...\.local\model-reports\tension-test-abaqus\tension-test-abaqus.tex
Document written to ...\.local\model-reports\tension-test-abaqus\tension-test-abaqus.pdf
```

29 pages; stays under `.local/` (material not public, R-16).

## What the documents hold (checked by rendering every page to PNG with PyMuPDF and reading them)

Title page with the verdict box (59 of 59 agree; the number closest to the limit is the centre element's shear strain at 0.594 of what is allowed), the summary table per group with the mean and largest error as a fraction of the group's largest magnitude, the figure of every number against its allowed difference, the spec listed verbatim with the model figure, the deck header and a table of what the kernel read, the kernel's solution figure, the hand check (for the committed record: laminate theory reaction 16127.5 N, kernel 16211.7 N, CalculiX 16162.2 N; centre strain within 0.52 %; every ply's stress in material axes in three columns), the theory with 15 code listings, the solver's provenance and the conventions file, the mapping and judging code with the record tool, every compared number, the reading note, and the record in the appendix. For the local record: the error map over the 300 gauge elements (largest error 0.16 % of the group's largest magnitude at the box edges), the twenty numbers closest to the limit per group (1200 ply stresses, 600 Mises), and the hand check against the team's deck (laminate theory reaction 105014 N, kernel 105993 N, 0.93 %, the whole-tab coupling preventing lateral contraction).

A defect found and fixed while reading the pages: the reaction of a coupled grip is carried by the coupling's reference node, which the first version of the hand check left out of the gripped group (it printed 0 N for the team's coupon). The reference node now joins its group by position; the committed free-edge patch test and the committed record's check cover both grip kinds.

## What the tests cover

`test_report.py`: every label shape parsed; the rows equal `compare_record` one for one (59 numbers, no `nan`); group statistics consistent with their rows and all within 0.3 % of each group's largest magnitude; element centroids in the record's units; the hand check equals the kernel to 1e-12 (strain) and 1e-9 (section force, reaction, ply stress) on the one-element free-edge coupon where both must coincide; on the committed record it sits within 1 % of the kernel's reaction and centre strain; a deck with no gripped rows is refused by name; the generator writes a LaTeX file for the committed record that starts and ends as a document, labels every section, states the verdict, lists the spec, prints the reading note and writes the two figures but no element map (one probe element).

## The rebuild guide (same day, ADR-0031 amendment 1)

- Scope: `anisotropy_fea.report.model_facts` (the deck's facts for a rebuild guide), `docs/models/rebuild.py` (Section 4 of every document in the team's template structure with evidence tags, Abaqus/CAE and PrePoMax 2.6 steps, keyword boxes quoted from both decks), the `\evidence` macro in the preamble, two more tests. The team's template is a local copy under `.local/abaqus/team-files/template/`; the PrePoMax 2.6.0 manual (v1.0.0, 6 September 2026) was downloaded from prepomax.fs.um.si and read for every PrePoMax step; the PrePoMax executable's resource strings were searched for a composite or layup dialog (none).
- From `fea/`: `uv run python -m pytest -q -ra tests ../engine/tests`

```text
615 passed, 6 skipped in 64.08s
```

- Both documents rebuilt and every page rendered and read: the committed record's document is now 44 pages (Section 4 on pages 8 to 20), the local one 40 pages. On the team deck the facts extractor recovers the four partition lines the template states by hand, 15, 35.97, 44.03 and 65 mm, from the changes in node-row spacing and the gripped groups, and the seeds by number 15, 21, 8, 21, 15; the expanded stack lists ten plies with z from -0.5 to 0.5 mm and names the 0.2 mm double layer at the midplane, as the template does.
- Defects found by reading the pages and fixed: a `%` inside an `\href` in a tabularx body comments out the rest of the row (the URL's `#` is now written `\#`); the spec's out-of-plane constants printed in Pa instead of the deck's MPa; a generated deck has no CAE job name and now cites the spec instead of OPEN; a hand-built deck's job and tool names are read from the heading comments.
- UNVERIFIED: every Abaqus/CAE click path (tagged CAE-CHECK, no CAE available) and every PrePoMax click path of route B (tagged MANUAL p.N, quoted from the manual but not performed here); route A is the one this project has performed (GUI-SEEN).

## Not run, UNVERIFIED

- CI: the new build step and artifact upload, until the first run of this pull request's checks.
- Remaining typesetting: four cells of the per-ply comparison tables in the committed document overrun their column by 3 to 10 pt (TeX warnings, visible as a slightly tight right margin); the equations, figures and other tables have no warnings.
- The document on a record that fails (a disagreeing number): the verdict and the table of failing numbers exist in the code but no such record exists to render them.
