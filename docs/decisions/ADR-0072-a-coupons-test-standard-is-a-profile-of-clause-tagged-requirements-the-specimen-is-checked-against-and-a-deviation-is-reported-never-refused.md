# ADR-0072: A coupon's test standard is a profile of clause-tagged requirements the specimen is checked against, and a deviation is reported, never refused

- Status: Proposed
- Date: 2026-11-08
- Decided by: Founder, 2026-11-08 ("what my cofounder wanted was that the user is able to select the type of standard to test based off the standards ... the geometry and the interface will also change based off the type of testing"; asked to choose, the founder picked: ASTM D4018 as a tow calculator with no finite element model, in a later part; ASTM C1869 now, offered for any material with a scope warning, and ASTM D5766 once its copy is in hand; the profiles in the public repository as individual values cited by clause in our own words; the Test row first and a Standard list filtered by the test after it) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/standards/`, `fea/src/anisotropy_fea/spec.py`, `fea/src/anisotropy_fea/intake.py`, `fea/src/anisotropy_fea/checks.py`, `fea/tools/export_form_definition.py`, `fea/tools/migrate_standard.py`, `fea/tests/test_standards.py`, [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0018](ADR-0018-source-rights-classes.md) (amendment 1), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (amendment 7), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0065](ADR-0065-coupon-ply-angles-are-counted-from-the-coupons-length-axis.md), risks R-24 and R-25

## Context

Until form 0.7 the coupon form's Standard row took any text, "none" by default. It was copied to the spec's card, the deck heading and the document, and checked nowhere; the chat wrote "ASTM D3039" into it from a typed message. The founder asked that the engineer pick the test, then the ASTM standard for it, and that the rows, the geometry and the checks follow the standard, because companies will want to see the model built to it.

Three standards were supplied as copies licensed to UC San Diego, each stamped "No further reproductions authorized":

- **ASTM D3039/D3039M-17**, tension of polymer matrix composites. The copy is stamped as superseded; the publisher lists D3039/D3039M-17(2025), a reapproval, as active.
- **ASTM C1869-18 (reapproved 2023)**, open-hole tension of ceramic matrix composites, with Specimen A (a 6 mm hole in a 36 mm wide strip) and Specimen B (a 3 mm hole in a 10 mm wide strip).
- **ASTM D4018-23**, tension of a resin-impregnated carbon fibre tow.

Every material in our library has a polymer matrix (`family` in `engine/src/anisotropy_engine/data/material-library.json`). The polymer open-hole standard, ASTM D5766/D5766M, was not supplied. A spec is loaded by every naming of a new coupon (`intake.existing_coupons`), so a stricter rule in `spec.validate_spec` stops every older spec from loading.

## Options considered

1. **Keep the free text and add help.** Nothing would be checked; one code would carry several meanings. Rejected.
2. **Lock the rows to the standard's values.** The page would fill and freeze the size. Rejected: both standards allow a variation that the report states (D3039 §11.2.1 and §14.1.4, C1869 §9.2.6 and §15.1), and an engineer studying a variant would have to leave the standard to model it.
3. **Refuse a coupon that misses a mandatory clause.** Rejected for the same reason: the run is still worth having, and the standards ask that the deviation be reported, not that the specimen go untested.
4. **Judge conformance in the spec's rules.** Rejected: an older or a nonconforming spec would stop loading, and with it the naming of every new coupon.
5. **A profile per standard, judged by the setup check, with deviations reported.** Chosen.
6. **Keep the profiles private.** Rejected by the founder in favour of the licensed-reference rule (ADR-0018 amendment 1).

## Decision

Option 5.

- **Profiles.** Each standard is a `Profile` in `fea/src/anisotropy_fea/standards/`. It holds the designation and the edition read, the tests it covers, the specimens or classes it names with their sizes, and its requirements. Each `Requirement` has a clause, a level and a text in our words; only the laboratory's clauses have no rule.
  - The levels are `scope`, `mandatory`, `recommended`, `note` and `lab`.
  - A rule reads a `Subject`, the coupon as the spec states it in SI. It returns the coupon's value and what the clause asks, both in the coupon's units.
- **Judgement.** `standards.conformance` judges each requirement as one of:
  - met;
  - deviation (a scope or mandatory miss);
  - advisory (a recommendation not followed);
  - note (a caution that applies);
  - the laboratory's;
  - not applicable.
- **The setup check.** A new item, Test standard, lists every judged requirement. It warns on a deviation and never fails. Only the form's own refusals block: a standard that does not cover the test, a word not on the list, or a row a standard needs left blank.
- **The spec.** It carries three tables: `[test_method] id, variant`, `[strain] device, gauge_length` and `[tabs] thickness, bevel, material`. `validate_spec` checks their structure only. The deck heading names them only when they are given, so no existing deck or record digest changes.
- **The form** goes to 0.8 (ADR-0046 amendment 7). The page reads the profiles from the `standards` block of `lib/coupon-form-definition.json` and judges nothing.
- **What a model claims.** The check judges the specimen definition, never the test, and never says "conforms". A coupon that meets every requirement a model can meet is "checked against" the standard. The clauses of the procedure stay the laboratory's: specimens, conditioning, speed, alignment, measurement, failure mode.
- **Systems.** D3039 states its SI and inch-pound values separately (§1.2), so a coupon stated in inches is held to the bracketed inch values. C1869 is SI only (§1.8), so its values are converted exactly.
- **Our readings, recorded as readings.** Each is written in the profile's docstring:
  - D3039 Table 1's "gripping" in the minimum length is both gripped lengths together; Table 2's lengths allow that.
  - A stated size inside a tolerance band of C1869's tables meets the size.
  - D3039's Table 2 class is read from the layup and the library record's architecture. The team's own constants are taken as a tape.
  - "Balanced" and "symmetric" follow the definitions C1869 A2 quotes from D3878. A fabric ply is counted by its stated angle.
- **Not in this record:**
  - D4018 (a later part: a tow calculator in the engine);
  - D5766, D6641, D3518 and D7264 (each once its copy is read);
  - the test quantities from the solved model (gross and net area, chord modulus, the virtual extensometer), a later part;
  - the studio's list by test, the size presets and the conformance view, a later part.

## As built (2026-11-08)

The registry:
- `fea/src/anisotropy_fea/standards/__init__.py`: the registry, `STANDARD_WORDS`, `profile_of_word`, `profiles_for`.
- `profile.py`: the data model, with the balanced and symmetric definitions.
- `astm_d3039.py`: 14 judged requirements and 12 laboratory clauses, with the three Table 2 classes in SI and inch-pound.
- `astm_c1869.py`: 17 judged requirements and 9 laboratory clauses, with Specimens A and B.
- `conformance.py`: `subject_of`, `judge`, `conformance`.

Where the standard enters the existing tools:
- `spec.py`: `StandardRef`, `Strain`, `Tabs`; card rows Specimen, Tabs and Strain measurement.
- `femodel.CARD_IN_HEADING`.
- `intake.py`: form 0.8, `READ_VERSIONS`, `ROWS_ADDED`, and a Test standards group on the Definitions sheet.
- `checks.py`: the `standard` item, which carries `requirements`.
- The exporter's `standards` block.

On the website side:
- `lib/source-rights.ts` gains `testStandardReferences`.
- `fea/tools/migrate_standard.py`.
- The page:
  - Specimen shows only for a standard that names specimens;
  - the tab and strain rows are hidden for bending and a plate;
  - the chat writes the listed designation.

Part 2, the studio (2026-11-08):
- `lib/studio-form.ts`: `wordsFor`, `withTest`, `withStandard`, `mergeRows`, `presetsOf`, `presetRows`.
- `components/studio/standard-card.tsx`, `requirement-table.tsx` (a list, to fit the rail) and `components/workspace/panels/standard-size.tsx`.
- The checklist item opens the judged requirements; the sketch draws bonded tabs and the strain measurement (`lib/studio-sketch.ts`, `components/studio/sketch-canvas.tsx`). The hole stays an outline on the sketch, not a cut.
- Evidence: `tests/studio-standards.test.ts` (6 passed), `npm test` 174 passed and 1 skipped, `npm run test:studio` 16 passed with the new scenario, `tests/browser/expansion.spec.ts` 6 passed; screenshots in `.local/website/screenshots/standards-*.png`.

## Why (evidence)

- **The public IM7/8552 coupon under D3039:**
  - 4 of 4 requirements a model can meet are met;
  - Table 2's 2.5 mm thickness against its 1.46 mm is an advisory.
- **The same laminate as C1869 Specimen B:**
  - the polymer matrix (§1.1, §1.4) and the 1.46 mm thickness (§9.2, 2 to 10 mm) are two deviations;
  - the run is still ready.

  Both are in `fea/tests/test_standards.py`, which also holds:
  - D3039's inch values;
  - each refusal by its row;
  - the spec's structural rules;
  - the round trip;
  - a 0.7 values file and Excel form.
- **The baseline before this change**, `cd fea && uv run pytest -q -ra tests ../engine/tests` on 2026-11-08: 1133 passed, 7 skipped, 1 failed. The failure was `test_abaqus`, which needs the Abaqus licence. With this change, on 2026-11-08:
  - fea and engine: 1179 passed, 7 skipped, the same one failed;
  - `cd api && uv run pytest` with the test database: 350 passed, 1 skipped;
  - `npm test`: 168 passed, 1 skipped; `npm run typecheck` is clean;
  - `npm run test:studio` after `npm run build`: 15 passed;
  - `tools/export_form_definition.py --check` reports the definition current.
- **The 14 local coupon specs:** `uv run python tools/migrate_standard.py --dry-run` found none that needed restating.
- **The publisher's pages:** https://store.astm.org/d3039_d3039m-17r25.html and https://store.astm.org/c1869-18.html (2026-11-08).
- **Not yet checked:**
  - that the 2025 reapproval of D3039 leaves the text of the 2017 copy unchanged: UNVERIFIED;
  - a legal review of holding individual values from a paid standard: no evidence yet.

## Consequences

- **Easier:**
  - A standard is added as one module and its tests.
  - The page, the Excel form and the chat take it from the definition.
  - A customer sees each clause with this coupon's value beside it.
- **Harder:**
  - A form version moves whenever a standard needs a row.
  - Every edition a profile names must be watched for revisions.
  - An older coupon whose Standard text is not on the list reopens in the studio only after `migrate_standard.py` or a pick from the list.
- **We now depend on** the team's licensed copies being read clause by clause, and on the "individual values" position (R-25).

## How we will know it was wrong

- A customer or reviewer reads "checked against" as conformance of a test (R-24).
- ASTM, or counsel, objects to the values held in the public repository (R-25).
- A deviation should have stopped a run because the results would mislead: for example, a hole far outside a standard's sizes still labelled with it.
- A standard asks something a `Subject` cannot carry, so a rule has to read past the spec.
