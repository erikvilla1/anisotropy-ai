# ADR-0105: A model brought in as an Abaqus input file is read as it stands, solved by our kernel and asked about; nothing in it is changed, and nothing of it is kept

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 ("do MCP last", after a plan of a live test, the MCP server and the import of an Abaqus .inp: the draft read it as import next, and said so); the scope of the first import was put on a card ("Open, solve, ask questions" recommended, over "Also edit loads by talking" and "Show me a written plan first") that was not answered when this was built, so every choice below is the draft's proposal | Drafted by: Claude Code
- Related: [ADR-0003](ADR-0003-reject-invalid-input.md); [ADR-0029](ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md); [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md); [ADR-0053](ADR-0053-plate-bending-by-an-mitc4-flat-shell-with-five-dofs-on-the-laminates-a-b-d-and-transverse-shear-stiffness.md); [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md); [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md); [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md); [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md); [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md); [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md); `fea/src/anisotropy_fea/imported.py`, `fea/tools/studio_tool.py`, `api/src/anisotropy_api/live.py`, `api/src/anisotropy_api/main.py`, `components/workspace/import-rail.tsx`, `components/studio/imported-stage.tsx`
- Area: fea, api, website, assistant

## Context

- The FEA workspace builds every model itself, from a coupon's rows. An engineer who already has a model built elsewhere could not bring it in.
- The fea package already reads an Abaqus input deck: `abaqus_reader` takes the subset in `fea/README.md` (flat S4, S4R and S4R5 shells, composite or one-material shell sections, lamina or isotropic elasticity, `*Fail Stress`, one linear static step, `*Boundary`, `*Cload`, `*Dload` with P, kinematic couplings) and refuses anything else with its line. `kernel.solve_deck` solves what is read, and `fields.field_data` writes the fields, the answer (ADR-0085) and the working.
- Until now those were used on decks the package wrote itself, in the two unit systems it writes (mm-MPa, m-Pa).
- A deck carries no units.
- A deck is somebody's own work. Runs and jobs are their owner's alone since ADR-0104; uploads from Abaqus are stored for their owner (ADR-0094).
- The hosted site offers one workflow to customers and every test to the founders (ADR-0089 amendment 5).
- The assistant answers questions about the results on the page (ADR-0099, ADR-0100, ADR-0102, ADR-0103) and edits a coupon's rows by talking (ADR-0088, ADR-0101).

## Options considered

What is read:

1. The deck through the reader as it is: its subset, and a refusal with the line for anything outside it. Nothing new to trust.
2. A wider reader first (more element types, several steps, included files). The kernel solves none of those today, so the file would be read and then not solved.
3. Turn the deck into a coupon's rows, so it could be edited like one. A deck states no test, no regions and no mesh seeds; the rows would be guesses (ADR-0003).

What may be done with it:

4. Open it, solve it, ask about it. Nothing in it is changed.
5. Also change its loads and supports by talking. Needs the deck's sets offered as regions and a way to write the change back; a later record.

The units:

6. The engineer states one of the four systems a coupon may be stated in; nothing is inferred; a modulus outside 1 to 1000 GPa after converting is warned beside the choice.
7. Infer the system from the magnitudes. A guess, and wrong units make every result wrong.
8. Only the two systems the package writes. An inch model could not be brought in.

Where it is solved:

9. By the live solve's warm workers (ADR-0086), in the request, within their 30 s limit. No queue, no new process to run.
10. As a queued job, like a full run. Takes large models; needs the deck stored while it waits.

What is kept:

11. Nothing of the deck. It is written to a folder of its own for the answer and removed; the run record keeps its name, size, SHA-256, what was read in counts and names, and the answer's summary.
12. The deck stored for its owner, as uploads are. A model could be reopened; needs retention, deletion and consent words that do not exist for it.

Who is offered it:

13. Where every test is offered (ADR-0089): the local API with the switch on, and a founder's sign-in on the hosted site.
14. Every signed-in person. The import reads files nobody here has seen, and its answer has no second solver behind it.

Where it is on the page:

15. In the FEA workspace, over the coupon: its own panels on the left, its model in the centre, the assistant answering from it; "Back to the coupon" returns to the rows, which it never touched.
16. A page or a project kind of its own. A project is stored and reopened; with nothing of the deck kept there is nothing to reopen.

The file's name:

17. In a request header, percent-encoded. It stays out of the address and so out of the logs that keep addresses.
18. In the query string, beside the units.

## Decision

Options 1, 4, 6, 9, 11, 13, 15 and 17.

- A model is brought in as an Abaqus input file (.inp). `abaqus_reader` reads it; what is outside its subset is refused with the reader's line, and a file that is not text or is over 20 MB is refused before it is read. Nothing is repaired, guessed or filled in.
- The engineer states the unit system the file is written in, one of mm-MPa, m-Pa, in-psi and in-ksi; the results come back in it. A modulus far from any material's is warned.
- The answer has one of three states: `refused` (with why and the line), `read` (taken, but our kernel could not solve it as it stands, with why) or `solved`.
- A file that was taken comes with its reading: the counts of nodes, elements by type, sets and couplings, the layup, the materials, the step, the supports and loads, the reader's notes, and every keyword that was skipped (output and print requests, which change no result).
- A solved model has the fields, the answer and the working that a live solve has, from the same functions. It is labelled as solved as the file states it: no mesh study and no second solver.
- Nothing in the model can be changed. The assistant answers questions about its results and says once that nothing is changed by talking; the coupon's rows behind it are not touched.
- Nothing of the file is kept. The run record holds its name, size and digest, the state, the reading and the summary, and is its owner's alone (ADR-0104).
- It is offered where every test is offered, and refused with 403 elsewhere.

## As built (2026-11-16)

- `fea/src/anisotropy_fea/imported.py`: `import_model(content, name, units)` (the three states), `decoded` (the size limit, a NUL byte, UTF-8 then cp1252), `read_text` (the reader, `validate_deck`, `to_si`), `reading`, `model_preview` (the deck in the shape of `preview.preview_data`: its own sets by mesh index, each support once per set with its directions, a load on a coupling's reference point shown on the coupled surface, a pressure stated element by element as one load with its range), `plain` (a message without this repository's file names).
- `fea/src/anisotropy_fea/model.py`: `to_si(deck, units, any_system=False)`; a deck of ours is still stated in a deck system only.
- `fea/src/anisotropy_fea/abaqus_reader.py`: the `generate` lines of one deck may name 5,000,000 labels in all (`MAX_GENERATED`); past that the deck is refused at the line, before the range is built. The reader is otherwise unchanged.
- `fea/tools/studio_tool.py`: the command `import <file> --units <system> [--name <name>] --out <folder>` (import.json, preview.json, fields.json, summary.json, explanation.json, timings.json; exit 0 whatever the state), and `serve` answers a request that carries `deck`.
- `api/src/anisotropy_api/live.py`: `LiveSolver.read_model`, on the same workers and limits as a live solve. `api/src/anisotropy_api/main.py`: `POST /v1/imported-models?units=`, the body the file, the header `X-Anisotropy-Model-Name` its name; 403 where not every test is offered, 413 past 20 MB, 422 for no body, units outside the four or a solve past the time limit, 429 when every worker stays busy, 503 when none can run. A refused file is recorded as a rejection.
- The page: `lib/studio-api.ts` (`importModel`, `readImportedModel`), `components/studio/use-imported-model.ts` (the state, and `resultsOnPage`, what the stage shows and the assistant answers from), `components/workspace/import-rail.tsx`, `components/studio/imported-stage.tsx`, "Import a model" on the rail's head, and in `components/studio/coupon-chat.tsx` the announcement, the answers from the imported results and the one line for anything else.
- The page's words (ADR-0091): the panels may name Abaqus, as the card of the engineer's own Abaqus does (ADR-0094 part 7), since the file is theirs; a reader's message is shown only when it holds nothing else that is banned (`importText`, `importProblemWords`).
- Difference from the plan: none. Not built: anything of option 5.

## Why (evidence)

- The founder's words on the order, quoted above. No evidence yet that the scope is the one he wants: the card was not answered.
- `cd fea && uv run pytest -q tests/test_imported.py`: 27 passed on 2026-11-16. They cover: each of the eleven public check decks is read and solved; the answer equals `read_deck`, `solve_deck` and `field_data` on the same deck; the reading's counts and skipped keywords; the preview's supports and loads through couplings; a `*Include`, a solid element type, `nlgeom=YES`, a letter and an empty file each refused with the line the reader names; a file with a NUL byte, one over the size and an unknown unit system refused; a generated set of four billion labels refused at its line; the same digits read in in-psi give the same first-ply failure factors and the unit warning; a deck with no support is `read` with the kernel's reason and still drawn; the tool's files; the warm worker.
- Seconds on the eleven decks, one run in a cloud container on 2026-11-16: 0.00 to 0.35 s up to 256 shell elements, 1.6 s for 1024 shell elements (`plate-ss-32x32-cross-ply-im7-8552.inp`).
- `cd api && uv run pytest -q tests/test_imported_models_api.py`: 9 passed on 2026-11-16, with a stand-in for the tool: the answer passed on as written; the folder with the deck removed after a warm and a cold answer; 403 where not every test is offered, with nothing written; the name taken from the header as a file's name; 413, 422; the record holds the digest and the summary and never the deck or the arrays; a refused file recorded as a rejection.
- The whole API suite with a test database: 646 passed, 1 skipped. `npm test`: 377 passed. `npm run typecheck`: clean.
- `tests/browser/import.spec.ts`: 2 passed (the file and units sent, the reading, the results, three questions, the refusal, back to the coupon; no import where one workflow is offered).
- By hand on 2026-11-16, the local API and page in a headless browser: the gripped coupon solved and asked about; a solid-element file refused with line 15; a deck with no support read and drawn with the kernel's reason; the 1024-element pressure plate stated in in-psi solved in 1.9 s with the unit warning shown.
- UNVERIFIED: not tried on the hosted site. No deck written by Abaqus/CAE for a model of a customer's has been tried; the eleven decks are our own check decks, two of them in the form CAE writes. How large a model the 30 s limit takes is not measured beyond 1024 shell elements.

## Consequences

- An engineer with a flat shell laminate model in Abaqus can see our answer on it, and ask the assistant about it, without retyping it as a coupon.
- Most real models will be refused at first: curved shells, solids, several steps, contact, included files and parts placed by a translation are all outside the reader. The refusal names the line.
- The places in the answer are worded by the same rules as a coupon's. A model that is not a coupon can be told its failure is "at the edge of a gripped tab" when its supports look like grips.
- One laminate per model: elements that carry different ply counts are refused by the kernel.
- An imported model cannot be reopened; the file is chosen again.
- The import shares the live solve's workers: a model that takes 20 s holds one worker for 20 s.
- The reader now reads files from outside. It was written for our own decks: the size limit, the refusal of `*Include` (it never opens another file) and the count of generated labels are its guards; it has not been reviewed line by line against a hostile file, which matters before option 14.
- A founder's sign-in must be named in `ANISOTROPY_FOUNDER_EMAILS` for the import to show on the hosted site.

## Not in this record

- Changing an imported model's loads, supports or mesh, by talking or by hand (option 5).
- Storing an imported model, or a project made from one (option 12, option 16).
- CalculiX beside an imported model, a mesh study on it, or a report of it.
- A wider reader.
- Offering the import to customers (option 14).

## How we will know it was wrong

- A file is taken and its answer differs from Abaqus on the same deck by more than the tolerances of `fea/checks/cases`: then the import stops until the difference is explained.
- Something in a file changes the result and was listed as skipped, not refused.
- More than half of the first ten real decks tried are refused: then the reader is widened before anything else is built on the import.
- Engineers ask to change the load of an imported model more often than they ask about it: then option 5.
- A deck, or any line of one, is found on the machine or in a record after its answer was read.
