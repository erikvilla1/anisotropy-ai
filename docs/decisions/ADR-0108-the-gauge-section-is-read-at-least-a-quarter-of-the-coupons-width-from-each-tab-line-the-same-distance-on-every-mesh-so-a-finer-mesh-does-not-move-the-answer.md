# ADR-0108: The gauge section is read at least a quarter of the coupon's width from each tab line, the same distance on every mesh, so a finer mesh does not move the answer

- Status: Proposed
- Date: 2026-11-16
- Decided by: Founder, 2026-11-16 (the decision card "Choose what I build next now that the assistant plan is done": "Fix the gauge-section answer"; then the card "Choose where the gauge-section answer is read from": "A quarter width from the tabs", over "One width from the tabs" and "Mid-length of the gauge only") | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/fields.py` (`gauge_reading`, `gauge_elements`, `gauge_failures`, `verdict_of`), `fea/src/anisotropy_fea/explain.py`, `fea/docs/theory.md` (section 7), `lib/result-question.ts` (`gaugeSection`), `mcp-server/src/anisotropy_mcp/results.py` (`gauge_section`), [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md) (the answer is read over the gauge section), [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md) (the study that showed the gauge factor moving, and its open item), [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md) (the clamped edge's peaks are reported apart), [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md) (the page looks an extreme up over the gauge section), [ADR-0107](ADR-0107-an-mcp-client-reaches-anisotropy-through-a-local-server-over-stdio-that-calls-the-api-it-solves-a-preview-and-starts-no-full-run-and-the-clients-model-writes-the-words.md) (the MCP server does the same)
- Area: fea, website, assistant

## Context

- A coupon's answer, fails or holds and at what loading, is read over its gauge section (ADR-0085). Until this record the gauge section was the deck's `Gauge` element set less the elements with a gripped node: one row of elements beside each tab line.
- The grips hold every node of a tab. Where a tab line meets a free edge the boundary changes from held to free at one point, and the model's stress has no finite value there: every refinement reads it higher. A row of elements is thinner on a finer mesh, so the nearest element left in the gauge section moved toward that corner as the mesh was refined.
- ADR-0068's study had shown it ("the gauge-section FPF factor also moves") and left "a gauge-section failure factor read away from the clamped edge" open.
- On 2026-11-16, in a live test on the hosted site, "finer mesh" (2 mm to 1 mm, ADR-0088 amendment 2) turned the same coupon under the same loading from holds (factor 1.04) to fails (0.9435), the first failure moving to the corner beside a tab line.
- Three places read the gauge section, each by its own copy of the rule: the fea package, the page (`lib/result-question.ts`) and the MCP server (`results.py`).

## Options considered

1. **Leave the rule.** Rejected: the answer is a function of the element size (the table below), and it falls without limit.
2. **Leave out a number of element rows beside each tab line**, two or three in place of one. Rejected: a count of rows is still a distance that shrinks with the mesh.
3. **Read the gauge section at least one width from each tab line.** ASTM D3039 names a failure "within one width of a tab or grip" apart from one in the gauge (`fea/src/anisotropy_fea/standards/astm_d3039.py`, §12.2, as the repository records it). Rejected on the founder's card: a compression coupon's gauge is about as long as it is wide (13 mm on 12 mm in `fea/checks/compression-im7-8552`), so no point is one width from both tabs and a second rule would be needed; and it leaves out a zone where the factor has settled.
4. **Read the answer at mid-length only**, the element of ADR-0066's validation quantities. Rejected on the founder's card: it never moves with the mesh, but it misses what is real in the gauge: a hole, and the restraint of the grips on a laminate that narrows much when pulled ([30/-30]2s: 0.993 past the stand-off against 1.119 at mid-length, on every mesh).
5. **Read the gauge section at least a quarter of the coupon's width from each tab line.** Chosen.
6. **Take the corner out of the model**: tabs with their own stiffness, or grips that let the tab narrow. Not chosen here: it is another model of the grip and a later record. A kinematic coupling of the tab to a reference node does not remove it (`unnotched-im7-8552-coupling`: 1.0236, 0.9284, 0.8114, 0.6943 by the rule before).
7. **Find the zone from the run's own convergence study**: read where two meshes agree. Rejected for now: the live preview solves one mesh, and its answer has to be the run's.

## Decision

- **The rule.** The gauge section is read at the elements of the `Gauge` set that touch no gripped node and whose centroid is at least the stand-off from each tab line, the innermost row of gripped nodes at each end. The stand-off is a quarter of the coupon's width.
- **A short gauge.** The stand-off is a quarter of the smaller of the width and the length between the tab lines, so the middle half of a gauge shorter than the coupon is wide is still read. The result says which length set it. (My choice; the founder's card names the quarter width.)
- **What is read there.** The first ply to fail per criterion (`summary.fpf_gauge`), the verdict (ADR-0085), the largest ply stresses (`summary.ply_extremes`), the strength the test method predicts and the convergence study's gauge factor.
- **What is left out stays visible.** The whole model's first failure, at the clamped edge of a grip or inside the stand-off, is still reported beside the answer as `outside_earlier`, never as the answer. A failure inside the stand-off that touches no gripped node is marked `near_tab`.
- **One reading, written once.** The package writes where the gauge section is read (`summary.gauge_reading`: the stand-off, its fraction, the length it is a fraction of, the tab lines, the counts) and the elements read (`mesh.gauge_elements`, null for a model without a gauge section). The page and the MCP server take that list and derive none. A result written before this record holds no list and is read by the rule it was written by.
- **Said to the engineer.** The package's sentences, the answer card and the coupon document say "the gauge section is read at least 6.25 mm from each tab line, a quarter of the width".

## As built (2026-11-16)

- `fea/src/anisotropy_fea/fields.py`: `GAUGE_STAND_OFF = 0.25`; `gauge_reading(deck, solution)` returns the elements read, the elements left out, the stand-off, `of` ("width" or "gauge length"), the tab lines and the width, in SI; `gauge_elements` and `gauge_failures` read it; `field_data` writes `summary.gauge_reading`, `mesh.gauge_elements` and `near_tab` on each first-ply-failure entry; `verdict_of` carries `near_tab` on `outside_earlier`. The width is the mesh's extent across the coupon, the wide end of a dog-bone. A centroid on the line itself is read (a slack of a millionth of the gauge length).
- `fea/src/anisotropy_fea/explain.py`: the facts `gauge_stand_off`, `gauge_stand_off_of` and `outside_near_tab`; one sentence on where the gauge section is read; the sentence for a failure inside the stand-off.
- `docs/models/coupon.py`: the coupon document's sentence names the stand-off. `fea/docs/theory.md` section 7 and `engine/docs/reasons.md` say the rule.
- Page: `lib/studio-api.ts` (`GaugeReading`, `mesh.gauge_elements`, `near_tab`), `lib/result-question.ts` (`gaugeSection` takes the written list), `components/studio/results-view.tsx` (the line under the answer's table; "Beside a tab line" for a failure marked `near_tab`).
- MCP server: `results.gauge_section` takes the written list; `solve_coupon`'s answer carries `gauge_section_read`.
- The stored results the page's tests use (`tests/fixtures/studio*/`) gained the new keys and nothing else: on their meshes of about 5 mm the elements read are the same 130 and 156 as before.
- Not changed: the convergence study's code (its gauge factor now settles because `gauge_failures` reads the new section); the whole-model table `summary.fpf`; every ply's peak with its `touches_grip` mark (ADR-0066).

## Why (evidence)

The gauge section's Tsai-Hill factor on four meshes, each element split in two along both axes from one mesh to the next (about 2, 1, 0.5 and 0.25 mm rows on the tension coupon), by the rule before and by `gauge_reading`, with our kernel on 2026-11-16. The tension coupon is `fea/checks/d3039-im7-8552` (250 by 25 mm, 56 mm tabs, 1 mm pull); the other laminates are the same coupon with its layup replaced; the compression coupon is `fea/checks/compression-im7-8552` as its spec states it.

| Coupon | Before | Read past the stand-off | Largest step |
| --- | --- | --- | --- |
| Tension, [45/0/-45/90]s | 1.0218, 0.9274, 0.8088, 0.6910 | 1.0335, 1.0334, 1.0334, 1.0334 | 0.00 % |
| Compression, 13 mm gauge, 12 mm wide | 1.2304, 1.0823, 0.9297, 0.7891 | 1.3032, 1.3030, 1.3031, 1.3031 | 0.01 % |
| Tension, [45/-45]2s | 1.2087, 1.1451, 0.8725, 0.6597 | 1.2087, 1.1887, 1.1827, 1.1814 | 1.68 % |
| Tension, [30/-30]2s | 0.9985, 0.8652, 0.6701, 0.5167 | 0.9985, 0.9938, 0.9929, 0.9926 | 0.47 % |
| Tension, [0]8 | 1.9815, 1.9019, 1.8046, 1.6782 | 2.1191, 2.1100, 2.1049, 2.1082 | 0.43 % |
| Tension, [90]8 | 0.9829, 0.9783, 0.9661, 0.9409 | 0.9850, 0.9851, 0.9851, 0.9851 | 0.00 % |
| Tension, [0/90]2s | 0.9888, 0.9868, 0.9786, 0.9649 | 0.9904, 0.9904, 0.9904, 0.9904 | 0.01 % |

- By the rule before, the first row crosses 1.0 between the first two meshes: the same coupon holds, then fails.
- Past the stand-off the steps shrink with each refinement. The largest, [45/-45]2s from the first mesh to the second (1.68 %), is followed by 0.51 % and 0.11 %: the mesh error of a value that exists, not a value that grows.
- Why a quarter and not less: with the stand-off as a fraction of the width, the tension coupon's factor still moved at 0.15 (1.0335, 1.0334, 1.0270, 1.0297) and was the same to four figures from 0.2 on; [30/-30]2s still fell at 0.1 (0.9985, 0.9361, 0.9221, 0.8971) and settled from 0.15 on. A quarter is the next round fraction past the worst case found. Measured with a script kept outside the repository; the table above is by the package's own functions.
- Tests: `cd fea && uv run pytest -q tests/test_convergence.py tests/test_fields.py` (40 passed): the public tension coupon on three meshes holds its gauge factor within 0.2 % while the whole model's falls by more than a tenth; three more layups move by less than 1 % from the second mesh to the third; the reading's elements, stand-off and tab lines; a gauge shorter than the width; the mark and the sentences.
- The whole suites: `cd fea && uv run pytest -q -ra tests ../engine/tests`: 1623 passed, 43 skipped, 3 failed and 1 error; the same four fail on main unchanged in the container this was drafted in, where Gmsh is not installed. `cd api && uv run pytest -q` with a database: 662 passed, 1 skipped. `cd mcp-server && uv run pytest -q`: 39 passed. `npm test`: 378 pass, 1 skipped, 0 fail. `npm run typecheck`: clean. The studio browser suite: 48 passed, the answer card's new line among them.
- UNVERIFIED: no test coupon's failure load has been compared with either number. The open-hole coupon (a Gmsh mesh) was not run here: Gmsh is not installed in the container the record was drafted in. No result on the hosted site has been looked at.

## Consequences

- A coupon's answer no longer depends on the element size past ordinary mesh error. "Finer mesh" by talking refines the stresses and leaves the verdict.
- A result solved on a fine mesh before this record reads differently when solved again: the tension coupon at 1 mm rows goes from 0.93 (fails) to 1.03 (holds). Stored results are not rewritten; each keeps its own rule and its own numbers.
- The largest ply stresses "in the gauge section", in the summary and in the assistant's answers, are read over the same narrower section.
- The page and the MCP server no longer hold a copy of the rule for new results; they keep the old one only to read old results.
- A fields file grows by one list of element numbers.
- The answer still includes what the grips do inside the gauge: on [30/-30]2s it is 11 % below the mid-length value. An engineer who wants the laminate's own strength reads the mid-length element (ADR-0066's validation table).
- The model is a shell: it has no stress between plies at a free edge. A real coupon can start to fail at a free edge or at a tab for reasons the model does not hold; the answer does not speak to them.
- The quarter rests on our own runs with rigid grips over a tab. Another grip model or a much longer or shorter coupon may want another fraction; the constant is one line.

## How we will know it was wrong

- A run's convergence study reports the gauge factor as not settled (its last refinement moves it by 1 % or more) on a coupon of a standard we offer.
- A laminate or a geometry is found where the corner sets the smallest strength ratio further than a quarter width from the tab line.
- A test coupon that breaks in its gauge does so at a loading nearer the value at the tab line than the value read past the stand-off.
- An engineer reads "the gauge section" as the whole length between the tabs and is misled by the answer.
