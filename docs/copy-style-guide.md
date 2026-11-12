# Copy style guide: what the workspace says

How every word a customer reads in `/workspace` is written: the chat, the setup panels, the run, the results, the files, the errors and the report's file names. The decision is [ADR-0091](decisions/ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md). The words that turn the pipeline's names into the product's are in `lib/studio-copy.ts`; the browser test `the customer's workspace never names a tool…` in `tests/browser/studio.spec.ts` fails if a banned term reaches the page.

The reader is an outside engineer. The bar is Ansys Workbench or Abaqus/CAE: clear, short, confident.

## The rules

1. **Write for the customer.** No team language ("for the team", "ours", "the founder"), no job ids, file paths, script or record names (`.py`, `.toml`), decision numbers or names of people.
2. **The software speaks for itself.** Never say that a model, an AI, Anthropic or Claude wrote something. The explanation is the product's output. Who wrote it stays in the run record (`writer`, `model`) and in the `data-writer` attribute, never on the screen.
3. **No internal tools.** Do not name Abaqus, PrePoMax, CalculiX or our comparison tools. The second solver is "the reference solver". Verification is one line: "Verified against reference solver: 57 of 57 values within 3 %".
4. **States, not machinery.** A run is Queued, Meshing, Solving, Post-processing, Report ready, shown as a five-step stepper. Not "a free solver", "the attempt", "the decks", "our engine".
5. **Fewer words.** One headline and at most two short sentences per block. Secondary detail goes under "Details". No repeated caveats, no hedging, no asides in brackets.
6. **The same terms everywhere.** σ₁, σ₂, τ₁₂ for ply stresses in fibre axes; εx, εy, γxy for laminate strains; ply, laminate, first-ply failure, R; criteria as Maximum stress, Maximum strain, Tsai-Hill, Tsai-Wu. Ply labels read "Ply 3 · -45°", on one line.
7. **Verbs on buttons.** "Run analysis", "Check setup", "Show", "Export CSV", "Open results in a new window".
8. **Errors say what happened and what to do.** "The analysis stopped while solving. Run it again; if it stops again, contact us." No stack traces, exit codes, environment variables or paths.
9. **Empty states help.** Say what will appear and when: "Files appear here when the analysis finishes."

## Tables and numbers

- A table sits in a `.studio-table-scroll` box: it scrolls inside its panel and is never covered by the chat.
- The first column is a `<th scope="row">` and stays put (`.studio-table-sticky`).
- Numbers are right-aligned in tabular figures (`.studio-table-num` or `.studio-num`), at the four significant figures `printed()` gives.
- Units go in the heading, "Reaction (N)", not in every cell. Headings stay on one or two lines: group a family of columns under one heading ("Stress, fibre axes (MPa)" over σ₁ σ₂ τ₁₂).
- Tables keep their CSV export where they have one.

## Downloads

| Key | Label | Saved as |
| --- | --- | --- |
| `document` | Report (PDF) | `D3039_[0-90]2s_report.pdf` |
| `package` | Full package (ZIP) | `D3039_[0-90]2s_package.zip` |
| `abaqus_deck` | Solver input (.inp) | `D3039_[0-90]2s_solver.inp` |
| `prepomax_deck` | Reference solver input (.inp) | `D3039_[0-90]2s_reference.inp` |
| `prepomax_results` | Reference solver results (.frd) | `D3039_[0-90]2s_reference.frd` |

The name is the standard (or the test) and the layup; the API hands the file out under it (`?name=`, letters, digits and `_ . , ( ) [ ] + -` only).

## Text from the backend

The pipeline and the API keep their own names (stage names, output keys): tests and stored jobs depend on them. The page maps them in `lib/studio-copy.ts`. Text written for display at the source follows these rules too: the API's queued message, the setup check's lines, the explanation templates, the tension screen's reasons and the model's prompts (`VOICE` in `api/src/anisotropy_api/assistant.py`). A message that still carries a banned term, a path or an exit code is replaced on the page by its plain state (`customerText`, `checkText`).

## Before you merge

- `npm test` and `npm run test:studio` pass; the banned-term test covers the product view (the tension screen) from a fresh start to a finished and a stopped run.
- New words a customer reads are in the voice above. When a banned term is needed in a developer-only view (`ANISOTROPY_ALL_TESTS=on`), it stays there.
