# Coupon documents (LaTeX)

**One document per coupon** ([ADR-0041](../decisions/ADR-0041-one-document-per-coupon-in-chapters.md)), written for engineers and investors: what was solved, the physics our engine uses, how the part is built in our engine and in Abaqus/CAE, our results, and how they compare with other solvers. It is separate from the engine manual and built by `docs/models/coupon.py`. Every number is computed from the committed spec, decks and record while it is built; nothing is typed in.

## Build it

From the repository root, with [Tectonic](https://tectonic-typesetting.github.io/) installed (the same as for the manual):

```sh
uv run --project fea python docs/models/coupon.py <coupon>             # one coupon
uv run --project fea python docs/models/coupon.py --all                 # every coupon model under .local/fea/ (none on CI, ADR-0042)
uv run --project fea python docs/models/coupon.py --all --check         # before merging an engine change (ADR-0043)
```

The LaTeX is written to the coupon's `.local/fea/<coupon>/ours/latex/` (ADR-0040 amendment 3): `<coupon>.tex` with the `figures/` it uses. What goes to the team is the package, one folder per delivery, `.local/fea/<coupon>/documents/<date>_<coupon>/` (ADR-0043), copied to them as it is. It holds:
- the PDF, compiled straight into it, so there is one copy;
- the audit form, `<date>_<coupon>-audit.xlsx`;
- the Abaqus deck to import, the CalculiX deck, both specs and the material record;
- when the team built the coupon, their deck and our results in the layout of their field reports.

It holds no CalculiX results, since the team runs our decks. A package folder is replaced only when this project wrote it; earlier packages stay, because a returned audit form names its package. What comes back, a filled-in form or a deck rebuilt from the guide, goes in `team/<date>/`.

Options:
- `--no-pdf` writes the LaTeX and the package without its PDF;
- `--no-theory` leaves out the equations and code of Chapter 2, about 25 pages that are the same in every document;
- `--full-tables` prints every compared CalculiX number;
- `--root <folder>` writes somewhere other than `.local/fea/`;
- `--check` builds nothing to keep: it scores each coupon again in a scratch folder and fails when a row our tools passed in the newest returned audit no longer passes.

## The chapters, and where each comes from

| Chapter | Comes from |
| --- | --- |
| Title page: the coupon card and the verdict | the spec's `[coupon]` card (ADR-0038); our engine's reaction and first-ply failure; the CalculiX record; the team comparison when there is one |
| 1 The problem | the card; the material record of our library with the page of every value (the team's values beside them when they built it); the grips and loading of the spec; the model figure (`fea/examples/plot_model.py`) |
| 2 The physics: how our engine solves it | `engine/docs/theory.md` sections 1 to 3 (ply stiffness, rotation, laminate stiffness) and 5 (failure), and `fea/docs/theory.md` (the finite element kernel), each equation followed by the code that computes it with its real line numbers, through the manual's converters; the laminate-theory hand check for this coupon |
| 3 Building the part in our engine | the spec as committed; the lines in which the CalculiX twin differs; the generated deck's header and what our deck reader reads back; the commands that rebuild it |
| 4 Building the part in Abaqus/CAE | what the team built, item by item against our deck (`anisotropy_fea.equivalence`), when they did; the step-by-step guide (`docs/models/rebuild.py`, Abaqus/CAE steps only) |
| 5 Results from our engine | our kernel on the generated deck: the solution figure, the reaction, the centre element's strains and every ply's stress, first-ply failure by each criterion of the spec |
| 6 Verification against other solvers | the CalculiX record against our kernel (summary, the solver and its deck, every compared number); the team's Abaqus side by side when they built it (`anisotropy_fea.side_by_side`) |
| 7 What this shows and what it does not | the readings written by a person (`ours/verification/<coupon>-calculix.md`, and `team-comparison.md` beside the team manifest); what is not shown yet |
| 8 The audit | the rubric `docs/audit/rubric.toml`, scored by `anisotropy_fea.audit.score` from the same computations; the rows the auditor judges, with what our tools can show them (`docs/models/audit.py`) |
| Appendices | how the CalculiX numbers were mapped and judged, with the code; the record; the files in the package |

## The team comparison (ADR-0035)

It is not a document of its own. When `.local/fea/<coupon>/ours/verification/team-comparison.toml` exists, `docs/models/team.py` supplies four things:
- the team's sections of Chapters 1, 4, 6 and 7;
- their files in the package;
- the comparison in figures, in `.local/fea/<coupon>/ours/verification/<coupon>-team-summary.toml`. It holds no value from the team's files and feeds the case page's result table (ADR-0039). It stays local with the model (ADR-0042); then run `fea/tools/case_pages.py`.

The manifest's format is `Manifest` in `team.py`, and a reading `team-comparison.md` sits beside it. Everything stays local, because it carries the team's results (R-16).

## The rebuild guide (Chapter 4)

`docs/models/rebuild.py` generates the guide from the deck's facts (`anisotropy_fea.report.model_facts`):
- extents, and partition lines where the node-row spacing changes or a gripped group ends;
- seeds by number and element bands;
- sets with their coordinate ranges, reference points and couplings;
- boundary conditions, loads, the step and the output requests;
- the ply table as entered, the expanded stack with z positions, ply fractions and the edge-length range.

It follows the team's FEA model report template (local copy in the tension coupon's `team/<date>/template/`): document control, evidence tags, a summary card, then one subsection per modelling step with a settings table, the GUI steps and the input-file keywords quoted from the decks.

Every value carries an evidence tag; a value that cannot is written `[OPEN]` and listed at the end, and the generator never fills one from memory. The tags:
- `[INP]`: read from the deck;
- `[INP-derived]`: computed from it;
- `[SPEC]`: from the spec;
- `[CALC]`: computed by the generator;
- `[CAE-CHECK]`: an Abaqus/CAE click path the deck does not store;
- `[ASSUMED]` and `[OPEN]`.

The coupon document asks for the Abaqus/CAE steps only (`Helpers.tools`). The guide can also write the PrePoMax steps, citing the PrePoMax 2.6.0 manual.

## The audit (ADR-0043)

Every package is audited against one rubric, `docs/audit/rubric.toml`. Our tools score the rows they can judge; Chapter 8 and the form show the same rows. The auditor fills in the form's open cells (their rows, the findings, name, date and verdict) and sends it back. Then:

```sh
cd fea && uv run python tools/read_audit.py <coupon> <returned form>.xlsx
```

The tool refuses a form that is incomplete, inconsistent or not this package's, and names every reason. A form it accepts goes to `team/<date>/`, and the case page's audit block lists it. The case line is written by hand; the tool says what it suggests. A deck an auditor rebuilt from the guide goes in `team/<date>/rebuilt/`, and the next package scores it as row E2.

## Record documents (checks)

`docs/models/build.py` builds one document per comparison record (ADR-0031). It is used for the checks under `fea/checks/` (the IM7/8552 regression set): `--all` builds those into `docs/models/build/<record>/`, and CI uploads them. A coupon's own CalculiX record is a chapter of its coupon document, so `--all` leaves it out. Given explicitly, a record under `.local/` goes to `report/<record>/` beside it.

## Adding a coupon

1. Make its record with `fea/tools/record_from_dat.py` (CalculiX); `fea/tests/test_records.py` checks that the kernel reproduces every committed record.
2. Write the reading note `ours/verification/<coupon>-calculix.md`. Quote numbers from the record or an evaluation note, never from memory.
3. Build the coupon document and read it. Anything a reading claims that the tables do not show is a defect in the reading.

The Markdown subset a reading may use is the manual's: paragraphs, `##` and `###` headings, bullet and numbered lists, pipe tables, inline code, bold, italic, links, and inline math written as `` $`...`$ ``.
