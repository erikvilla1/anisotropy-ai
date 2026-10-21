# Model comparison documents (LaTeX)

One typeset document per finite element model comparison, separate from the engine manual ([ADR-0031](../decisions/ADR-0031-one-generated-document-per-model-comparison.md)). Each document is the complete argument for one model: what was modelled, the classical laminate theory hand check, the kernel's equations with the code that computes them, what the reference solver ran and how its element differs, how the numbers were mapped and judged, every compared number with its error, and the reading.

## Build one

From the repository root, with [Tectonic](https://tectonic-typesetting.github.io/) installed (the same as for the manual):

```sh
uv run --project fea python docs/models/build.py fea/validation/records/unnotched-im7-8552-nodal-calculix.toml
uv run --project fea python docs/models/build.py --all        # every committed record
uv run --project fea python docs/models/build.py .local/fea/abaqus/tension-coupon/comparison/tension-test-abaqus.toml
```

| Record | Document goes to | Committed? |
| --- | --- | --- |
| `fea/validation/records/<name>.toml` | `docs/models/build/<name>/<name>.pdf` | No: rebuilt from sources, like the manual; CI uploads the PDFs as the `model-documents` artifact |
| anything under `.local/` (a record at `.local/fea/<tool>/<test>/comparison/<name>.toml`) | `report/<name>/<name>.pdf` beside the record | Never: the material may not be public (R-16) |

Options: `--no-pdf` writes the LaTeX only; `--no-theory` leaves out the kernel theory and code section (about 20 pages, the same in every document); `--full-tables` prints every compared number even for records with more than 400 of them (otherwise each group shows its twenty numbers closest to the limit). Without Tectonic the `.tex` is still written and is self-contained.

## The short comparison for the team (ADR-0035)

When the team built the model in Abaqus, `docs/models/team.py` writes a short document for them and a folder they can open. The document says, in order: here is the team's model and here is ours, the same item by item; our material comes from the library, and this is its source and page; here are the results side by side. The results cover stress at named points, agreement over the coupon, maps, reaction force and first-ply failure. Each test needs a manifest at `.local/fea/abaqus/<test>/comparison/team-comparison.toml` (format in `Manifest` in the script) and a reading `team-comparison.md` beside it.

```sh
uv run --project fea python docs/models/team.py .local/fea/abaqus/tension-coupon/comparison/team-comparison.toml
```

The document goes to `comparison/report/<test>-comparison/`. The share folder goes to `.local/fea/share/<test>/`, zipped as `<test>.zip`. It holds the PDF, the team's deck, our Abaqus and CalculiX decks, the spec, the material record, and our S11, S22 and Mises in the layout of the team's own field reports with their element numbers. It also holds an element-by-element table and every ply's stress. Both stay local because they carry the team's results. The script replaces only a share folder it wrote itself.

The numbers come from `anisotropy_fea.equivalence` (the two decks matched node by node and item by item) and `anisotropy_fea.side_by_side` (the team's reports paired with our kernel). The hand check and first-ply failure come from the engine.

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
| Rebuild guide | `docs/models/rebuild.py` on `report.model_facts`, the team's report template and the PrePoMax 2.6.0 manual |
| Reading | `<record>.md` beside the record, written by a person: what the numbers show, what explains each difference, what is verified and UNVERIFIED, what would settle it. Without it the section says so; the build never invents one |
| Appendix | The record file itself (its first 40 lines when it is long) and, when there are at most 400 numbers or `--full-tables` is given, the full comparison table |

## The rebuild guide (Section 4 of every document)

A step-by-step guide to recreating the model by hand, in Abaqus/CAE and in PrePoMax, generated by `docs/models/rebuild.py` from the deck's facts (`anisotropy_fea.report.model_facts`: extents, partition lines where the node-row spacing changes or a gripped group ends, seeds by number, element bands, sets with their coordinate ranges, reference points, couplings, boundary conditions, loads, step, the ply table as entered and the expanded stack with z positions, ply fractions, edge-length range, output requests). It follows the team's FEA model report template (local copy under `.local/fea/abaqus/tension-coupon/team/template/`, 2026-10-18): document control, evidence tags, a summary card, then one subsection per modelling step with a settings table, the GUI steps for both tools, and the input-file keywords quoted from the decks.

Every value carries an evidence tag: `[INP]` read from the deck, `[INP-derived]` computed from it, `[SPEC]` from the spec, `[CALC]` computed by the generator, `[CAE-CHECK]` an Abaqus/CAE click path the deck does not store, `[MANUAL p.N]` a PrePoMax click path quoted from page N of the PrePoMax 2.6.0 manual, `[GUI-SEEN]` a PrePoMax step this project has performed on the model, `[ASSUMED]`, `[OPEN]`. A value that cannot carry a tag is written `[OPEN]` and listed at the end of the guide; the generator never fills one from memory.

PrePoMax 2.6 has no composite layup and no orthotropic material dialog (manual pages 30 and 31), so the guide gives two routes: route A, import the generated CalculiX deck (File > New, File > Import), which is what this project does; route B, build what the GUI offers and add the material and composite section through Model > Edit CalculiX Keywords, pasting the keyword blocks the guide quotes.

## Adding a model

1. Make the record with `fea/tools/record_from_dat.py` (CalculiX) or `fea/tools/record_from_report.py` (Abaqus field reports). `fea/tests/test_records.py` checks that the kernel reproduces every committed record.
2. Write the reading note `<record>.md` beside it. Quote numbers from the record or an evaluation note; never from memory.
3. Build the document and read it. Anything the reading claims that the tables do not show is a defect in the reading.

The Markdown subset the reading may use is the manual's: paragraphs, `##` and `###` headings, bullet and numbered lists, pipe tables, inline code, bold, italic, links, and `$`...`$` inline math written as `` $`...`$ ``.
