# Copy style guide: what the workspace says

How every word a customer reads in `/workspace` is written: the chat, the setup panels, the run, the results, the files, the errors and the report's file names. The decision is [ADR-0091](decisions/ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md). The words that turn the pipeline's names into the product's are in `lib/studio-copy.ts`; the browser test `the customer's workspace never names a tool…` in `tests/browser/studio.spec.ts` fails if a banned term reaches the page.

The reader is an outside engineer. The bar is Ansys Workbench or Abaqus/CAE: clear, short, confident.

## The rules

1. **Write for the customer.** No team language ("for the team", "ours", "the founder"), no job ids, file paths, script or record names (`.py`, `.toml`), decision numbers or names of people.
2. **The software speaks for itself.** Never say that a model, an AI, Anthropic or Claude wrote something. The explanation is the product's output. Who wrote it stays in the run record (`writer`, `model`) and in the `data-writer` attribute, never on the screen.
3. **No internal tools.** Do not name Abaqus, PrePoMax, CalculiX, SPOOLES or our comparison tools; the one exception is the customer's solver file, "Abaqus input file (.inp)", named so on the site and in the workspace (ADR-0091 amendment 2). The second solver is "the reference solver". Verification is one line: "Verified against reference solver: 57 of 57 values within 3 %", and only when every value agrees; otherwise "Reference solver check: 71 of 73 values within 3 %", not styled as a pass. One exception (ADR-0094 part 7): the card for the user's own Abaqus on a finished run names Abaqus and its script, because there it is the user's program and not a tool of ours. Its root carries `data-names-abaqus`, and it may say "Abaqus" and ".py" and no other banned term (`ABAQUS_CARD_ALLOWS`).
4. **States, not machinery.** A run is Queued, Meshing, Solving, Post-processing, Report ready, shown as a five-step stepper. Not "a free solver", "the attempt", "the decks", "our engine", "the engine", "the case runner".
5. **Fewer words.** One headline and at most two short sentences per block. Secondary detail goes under "Details". No repeated caveats, no hedging, no asides in brackets.
6. **The same terms everywhere.** σ₁, σ₂, τ₁₂ for ply stresses in fibre axes; εx, εy, γxy for laminate strains; ply, laminate, first-ply failure, R; criteria as Maximum stress, Maximum strain, Tsai-Hill, Tsai-Wu. Ply labels read "Ply 3 · −45°", on one line, with no plus sign.
7. **Verbs on buttons.** "Run analysis", "Check setup", "Show", "Export CSV", "Open results in a new window".
8. **Errors say what happened and what to do.** "The analysis stopped while solving. Run it again; if it stops again, contact us." No stack traces, exit codes, environment variables or paths. A check item whose own words cannot be shown still says what to do ("Fill in the inputs listed.").
9. **Empty states help.** Say what will appear and when: "Files appear here when the analysis finishes."

## Tables and numbers

- A table sits in a `.studio-table-scroll` box: it scrolls inside its panel and is never covered by the chat.
- The first column is a `<th scope="row">` and stays put (`.studio-table-sticky`).
- Numbers are right-aligned in tabular figures (`.studio-table-num` or `.studio-num`), at the four significant figures `printed()` gives.
- Every number follows one rule (`lib/number-format.ts`, ADR-0091 amendment 1): four significant figures, plain digits from 0.001 up to a million ("320700"), "3.207 × 10⁶" outside, and the minus sign (−), never "1e+05". A table column keeps its zeros ("3.220" beside "3.474"); a readout or a sentence drops them. Arithmetic noise is shown as 0.
- Units go in the heading, "Reaction (N)", not in every cell. Headings stay on one or two lines: group a family of columns under one heading ("Stress, fibre axes (MPa)" over σ₁ σ₂ τ₁₂).
- Tables keep their CSV export where they have one.

## Downloads

| Key | Asked for as | Label | Saved as | Offered to |
| --- | --- | --- | --- | --- |
| `document` | `document` | Report (PDF) | `D3039_[0,90]2s_report.pdf` | the customer |
| `abaqus_deck` | `solver_input` | Abaqus input file (.inp) | `D3039_[0,90]2s_solver.inp` | the customer |
| `package` | `package` | Full package (ZIP) | `D3039_[0,90]2s_package.zip` | the development view |
| `prepomax_deck` | `reference_input` | Reference solver input (.inp) | `D3039_[0,90]2s_reference.inp` | the development view |
| `prepomax_results` | `reference_results` | Reference solver results (.frd) | `D3039_[0,90]2s_reference.frd` | the development view |

The name is the standard (or the test) and the layup, its plies parted by commas; the API hands the file out under it (`?name=`, letters, digits and `_ . , ( ) [ ] + -` only). A customer gets the report and the solver input; the package and the reference solver's files are the team's verification material, offered only with `ANISOTROPY_ALL_TESTS=on` (ADR-0091 amendment 2). The page asks for a solver file by what it is (`solver_input`), never by a program's name, and the solver input comes with a neutral header.

## Text from the backend

The pipeline and the API keep their own names (stage names, output keys): tests and stored jobs depend on them. The page maps them in `lib/studio-copy.ts`. Text written for display at the source follows these rules too: the API's queued message and error details, the setup check's lines and item labels, the refusal of a test not offered yet, the explanation templates, the tension screen's reasons and the model's prompts (`VOICE` in `api/src/anisotropy_api/assistant.py`). A message that still carries a banned term, a file or folder path, an id or an exit code is replaced on the page by its plain state (`customerText`, `checkText`); a check item that falls back names its inputs. The page shows the API's own words only for a refusal the user can act on (400, 409, 422, 429); a job that is gone reads "These results are no longer available. Run the analysis again from your project."; any 5xx, the outage line, said once; any other failure says what failed and what to do (`FAILED_WORDS`, "The analysis could not be started. Reload the page; if it happens again, contact us.").

## Before you merge

- `npm test` and `npm run test:studio` pass; the banned-term tests cover the product view (the tension screen) from a fresh start to a finished and a stopped run, and every workspace route (the chooser, the coupon and laminate workspaces, the viewer with and without a job) with its title, meta description and links, the service up and down.
- New words a customer reads are in the voice above. When a banned term is needed in a developer-only view (`ANISOTROPY_ALL_TESTS=on`), it stays there.
