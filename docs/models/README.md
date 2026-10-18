# Model comparison documents (LaTeX)

One typeset document per finite element model comparison, separate from the engine manual ([ADR-0031](../decisions/ADR-0031-one-generated-document-per-model-comparison.md)). Each document is the complete argument for one model: what was modelled, the classical laminate theory hand check, the kernel's equations with the code that computes them, what the reference solver ran and how its element differs, how the numbers were mapped and judged, every compared number with its error, and the reading.

## Build one

From the repository root, with [Tectonic](https://tectonic-typesetting.github.io/) installed (the same as for the manual):

```sh
uv run --project fea python docs/models/build.py fea/validation/records/unnotched-im7-8552-nodal-calculix.toml
uv run --project fea python docs/models/build.py --all        # every committed record
uv run --project fea python docs/models/build.py .local/abaqus/comparisons/tension-test-abaqus.toml
```

| Record | Document goes to | Committed? |
| --- | --- | --- |
| `fea/validation/records/<name>.toml` | `docs/models/build/<name>/<name>.pdf` | No: rebuilt from sources, like the manual; CI uploads the PDFs as the `model-documents` artifact |
| anything under `.local/` | `.local/model-reports/<name>/<name>.pdf` | Never: the material may not be public (R-16) |

Options: `--no-pdf` writes the LaTeX only; `--no-theory` leaves out the kernel theory and code section (about 20 pages, the same in every document); `--full-tables` prints every compared number even for records with more than 400 of them (otherwise each group shows its twenty numbers closest to the limit). Without Tectonic the `.tex` is still written and is self-contained.

## Where the content comes from

| In the document | Comes from |
| --- | --- |
| Title page, verdict, summary table | The record, and the kernel run on the record's deck during the build (`anisotropy_fea.compare`, `anisotropy_fea.report`) |
| The spec, the model figure, the deck header | `fea/validation/specs/`, `anisotropy_fea.femodel`, `fea/examples/plot_model.py` |
| What the kernel read, the solution figure | `anisotropy_fea.abaqus_reader`, `fea/examples/plot_deck.py` |
| Classical laminate theory hand check | The engine (`abd_matrices`, `mixed_response`, `ply_surfaces`, `engineering_constants`), from the deck's section and gripped node rows |
| Equations and code listings | `fea/docs/theory.md` and the `fea` source, through the manual's converters in `docs/manual/build.py` |
| Reference solver, known differences, conventions | The record's `[solver]` and `[known_differences]` tables; `fea/validation/records/_calculix-conventions.toml` |
| How numbers were mapped and judged | `compare.py`, `calculix.py` or `abaqus_report.py`, and the record tool, listed with line numbers |
| Every compared number | The record (reference) and the kernel (computed during the build) |
| Reading | `<record>.md` beside the record, written by a person: what the numbers show, what explains each difference, what is verified and UNVERIFIED, what would settle it. Without it the section says so; the build never invents one |
| Appendix | The record file itself (its first 40 lines when it is long) and, when there are at most 400 numbers or `--full-tables` is given, the full comparison table |

## Adding a model

1. Make the record with `fea/tools/record_from_dat.py` (CalculiX) or `fea/tools/record_from_report.py` (Abaqus field reports). `fea/tests/test_records.py` checks that the kernel reproduces every committed record.
2. Write the reading note `<record>.md` beside it. Quote numbers from the record or an evaluation note; never from memory.
3. Build the document and read it. Anything the reading claims that the tables do not show is a defect in the reading.

The Markdown subset the reading may use is the manual's: paragraphs, `##` and `###` headings, bullet and numbered lists, pipe tables, inline code, bold, italic, links, and `$`...`$` inline math written as `` $`...`$ ``.
