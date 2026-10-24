# ADR-0031: Every model comparison gets its own generated LaTeX document, separate from the manual

- Status: Proposed
- Date: 2026-10-18
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0008 (the manual is generated from sources), ADR-0029, ADR-0030 (comparison records), `docs/models/build.py`, `docs/models/README.md`, `fea/src/anisotropy_fea/report.py`, `fea/tests/test_report.py`

## Context

The founder asked, on 2026-10-18, for documentation of each finite element model comparison that is separate from the manual: the mathematics, the analysis, the code, the data and the error between the reference solver (Abaqus, CalculiX) and our kernel, in LaTeX, one document per model, because these documents are the argument in our analysis. Two comparisons exist: the generated unnotched IM7/8552 coupon against CalculiX 2.22 (committed record) and a team coupon against its Abaqus/CAE field reports (local record, ADR-0042). The manual already prints the kernel theory with code listings and the finite element validation tables, and `compare.py` already judges every record against the kernel in the tests.

## Options considered

1. **A section per model inside the manual.** One build, one PDF. The manual grows by twenty to forty pages per model, local records cannot appear in it at all, and a reader who wants one model's argument gets the whole manual.
2. **A hand-written LaTeX report per model.** Full control of the prose. Numbers, code listings and figures are copied by hand and drift from the record and the code; the rule of ADR-0008 would be broken for exactly the documents meant as evidence.
3. **A generated, self-contained LaTeX document per record**, built by a script that reuses the manual's converters: the spec and deck headers, the kernel's solution and figures, the engine's classical laminate theory hand check, the theory with code listings, the reference solver's provenance and conventions, the mapping and judging code, every compared number with its error in several forms, and a Markdown reading note beside the record for the human argument. Costs a second build script and a numbers module.
4. **Markdown or HTML instead of LaTeX.** Cheaper to render, but the founder asked for LaTeX and the manual's typesetting, code style and equation handling already exist.

Where the output lives:

1. Commit the PDFs: readable without a build, but binary diffs and a stale copy whenever the code or the record changes.
2. **Build output only** (`docs/models/build/`, git-ignored), uploaded by CI as an artifact, like the manual; local records build to `.local/model-reports/`.

## Decision

Option 3 with the output as build output only. `fea/src/anisotropy_fea/report.py` assembles the numbers (every compared value as a row with its difference, relative difference, fraction of the allowed difference and group scale; per-group statistics; element positions; the laminate-theory check from the deck's section and gripped node rows). `docs/models/build.py` loads `docs/manual/build.py` as a module for the Markdown, code-listing and number converters, pastes `docs/models/preamble.tex` into each document so a `.tex` is self-contained, draws two figures (every number against its allowed difference; the largest error per element on the mesh when the record covers at least twenty elements), and compiles with Tectonic when present. The reading is `<record>.md` beside the record; when it is missing the document says so rather than inventing one. The long comparison tables (more than 400 numbers) show the twenty numbers closest to the limit per group unless `--full-tables` is given, and the record itself is listed in an appendix.

## Why (evidence)

- The committed record builds to a 35-page PDF, 59 of 59 numbers agreeing, with the laminate-theory check beside the kernel and CalculiX (reaction: theory 16128 N, kernel 16212 N, CalculiX 16162 N; evaluation note of this chunk).
- The local Abaqus record builds to its document under `.local/model-reports/` with the element error map over the 300 gauge elements (numbers in the local note, not here).
- `fea/tests/test_report.py`: the rows equal the record comparison one for one, the group statistics are consistent, the laminate-theory check reproduces the kernel to 1e-9 on the one-element free-edge coupon where both must coincide, and the generator writes a LaTeX file for the committed record that names every section. Output in the evaluation note.
- CI builds every committed record's document in the manual job (UNVERIFIED until the first run of this pull request's checks).

## Consequences

Easier: one file per model to hand to a reviewer, with the equations, the code, the data and the error in one place; a new record gets its document for the cost of a reading note; local records get the same document without leaving `.local/`. Harder: two build scripts share converters through a module load, so a change to the manual's helpers can change these documents; the theory section repeats in every document (about twenty pages; `--no-theory` drops it); the reading note is the only hand-written part and must be kept true to the record.

## How we will know it was wrong

If reviewers read the summary and the reading but never the theory section, drop it to a reference to the manual. If the two build scripts keep diverging in what they need from the converters, move the converters into a small package both import. If a reading note is found to contradict its tables, add a test that quotes numbers from the record into the note instead of letting it be free text.

## Amendment 1, 2026-10-18 (the rebuild guide follows the team's report template)

**Context.** The founder asked, the same day, for a step-by-step guide in each document so that an engineer can recreate the model in Abaqus/CAE and in PrePoMax with every setting, and supplied the team's FEA model report template (a Word file: document control, evidence tags, a summary card, then part geometry, material, composite layup with the expanded stack, assembly, step, interactions, boundary conditions, mesh, job and outputs, each with a settings table, GUI steps and the input-file keywords). The template's rule, "a value is never written unless it can carry an evidence tag", is the same rule as this repository's.

**Options.** (1) Generate the guide from the deck in the template's structure, with evidence tags, Abaqus/CAE steps and PrePoMax steps cited to the PrePoMax 2.6.0 manual by page; the template stays a local team file. (2) Fill the Word template by hand per model: rejected, the manual-copy drift ADR-0008 forbids. (3) Abaqus steps only: rejected, PrePoMax is the tool this project runs.

**Decision.** Option 1: `docs/models/rebuild.py` renders Section 4 of every document from `anisotropy_fea.report.model_facts` (extents, partition lines from gripped groups and from changes in node-row spacing, seeds by number, element bands, sets with coordinate ranges, reference points, couplings, boundaries, loads, step, the ply table and the expanded stack with z positions, ply fractions, output requests). Tags: INP, INP-derived, SPEC, CALC, CAE-CHECK, MANUAL p.N, GUI-SEEN, ASSUMED, OPEN. PrePoMax 2.6 has no composite layup or orthotropic material dialog (manual pages 30 and 31; the executable's resource strings have no such dialog either), so the guide gives route A, import the generated CalculiX deck (the route this project has performed, recorded in PrePoMax's own history file), and route B, the GUI as far as it goes plus Model > Edit CalculiX Keywords with the quoted blocks.

**Evidence.** A team deck's partition lines and seeds are recovered from its mesh exactly as the team's template states them by hand (numbers in a local note (ADR-0042)); `fea/tests/test_report.py` covers the facts of the generated coupon and of the coupled-grips fixture and checks that the generated document carries the tags; the PrePoMax click paths are quoted from the manual downloaded on 2026-10-18 (v1.0.0 of 6 September 2026). Evaluation note of the chunk.
