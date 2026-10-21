# ADR-0036: One folder per finite element test, in the repository and on the founder's machine

- Status: Proposed
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (test first locally, the repository too, superseded local files deleted, no `.frd` in the zips) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/paths.py`, `fea/tools/regenerate_decks.py`, [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0032](ADR-0032-local-workspace-layout-by-tool-and-test.md) (its FEA layout superseded; its homework layout stands), [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [evaluation](../evaluations/fea/2026-10-21-one-folder-per-test.md)

## Context

The founder found the finite element files hard to follow. One test was spread over up to eight places:

- **In git:** `fea/validation/specs/`, `decks/generated/` and `records/`, with documents in `docs/models/build/`.
- **Locally:** `.local/fea/abaqus/<test>/`, `.local/fea/calculix-prepomax/<test>/`, `.local/fea/share/<test>/` and `share/our-models/<n>-<test>/`.

The committed folders were sorted by file kind. Team models, the IM7/8552 regression models, the Kirsch plate and two twins per test shared one flat `specs/` folder. The local folders were sorted by tool first (ADR-0032), so every test name appeared twice. About 18 test files and several tools each hard-coded the `validation/...` paths.

## Options considered

1. **Sort by file kind in git and by tool locally**, as before. This was rejected: finding everything about one test meant visiting every folder.
2. **One folder per test, everywhere.** In git, `fea/models/<test>/` (specs at the root, `decks/`, `records/`, README) holds the team models. `fea/checks/` holds the proofs that are not team models: `cases/`, `decks/`, the conventions file, and the IM7/8552 and Kirsch test folders in the same shape. Locally, `.local/fea/<test>/` holds `team/<date>/`, `runs/<solver>/` and `comparison/`. One module states every location. Chosen.
3. **Reorganize only the local folders.** This was rejected by the founder: the repository was equally hard to follow.

## Decision

Option 2.

- **Paths.** `anisotropy_fea.paths` is the only place that says where things are (`MODELS`, `CHECKS`, `CASES`, `CHECK_DECKS`, `CONVENTIONS`, `LOCAL`, `all_specs`, `all_records`, `spec_path`, `deck_path`). Tests, tools and document builders take their paths from it.
- **Names.** The team-build specs drop the material and grip type from their names: `tension-coupon.toml` and `tension-coupon-nodal.toml`. The material lives in the spec, and a second material for a test becomes a new test name, such as `tension-coupon-t700`. The IM7/8552 and Kirsch files keep their names.
- **Decks.** `tools/regenerate_decks.py` rewrites every committed deck from its spec. The deck tests loop over every spec, so a new test folder is checked with no list to edit.
- **Records.** The record tool defaults to the spec's own decks and writes the conventions file as a relative path.

This supersedes the finite element layout of ADR-0032; its homework layout stands. It amends ADR-0030 (where specs, decks and records live) and ADR-0035 (the share step, in the local chunk that follows).

## Why (evidence)

- Regenerating every deck changed only header comment lines: the spec file name, and the conventions path that the CalculiX writer prints. Every geometry, material and load line is identical.
- The five CalculiX records were re-run on those decks. Every recorded value is unchanged to 6e-8. The exceptions are lateral displacements of order 1e-13 mm at nodes where symmetry makes them zero; those are solver roundoff that varies between identical runs.
- From `fea/`, `uv run pytest -q`: 281 passed. Output is in the evaluation note.

## Consequences

- **Adding a test** means adding one folder in git and one folder locally, with the same name.
- **Moving things later** means changing `paths.py`.
- **History.** Evaluation notes and ADRs written before this one cite the old paths.
- **CI.** It uses the same commands; `docs/models/build.py --all` finds the records through `paths.all_records()`.

## How we will know it was wrong

Revisit if a test needs files that fit neither `decks/` nor `records/`, such as meshes from another tool or a second solver's runs committed. Revisit too if the founder still cannot find a test's files from its name.
