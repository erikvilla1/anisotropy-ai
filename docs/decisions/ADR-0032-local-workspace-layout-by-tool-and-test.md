# ADR-0032: Local finite element files are laid out by tool and test with team, ours and comparison folders; homework assignments and their code share folder names

- Status: Proposed
- Date: 2026-10-19
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0029, ADR-0030, ADR-0031 (what the files are), ADR-0023 (skills), `docs/agents/skills/workspace-layout/SKILL.md`, `.local/fea/README.md`, `.local/homework/README.md`, `fea/tests/test_local_tension_deck.py`

## Context

The team's first Abaqus coupon and our twin of it were spread over seven local folders sorted by file kind: `.local/abaqus/` (team deck, exports, records, notes), `.local/calculix/` (runs), `.local/fea-models/` (generated decks), `.local/specs/`, `.local/model-reports/`, `.local/fea-plots/`, `.local/fea-vtk/`. Comparing one test meant opening five of them. Course homework was split the same way: the provided PDFs and Excel files under `output/Problems_Solutions/`, our corrected inputs and scripts under `.local/homework/` and `.local/practice/`. More team tests (compression, shear, bending) and the FEA training are coming, each with files from the team and files we generate. The founder asked on 2026-10-19 for one FEA folder with an Abaqus folder and a CalculiX/PrePoMax folder, a sub-folder per test with the same name under both, the files we compare against separate from the files we create, and for homework an assignments folder beside a code folder that makes the link between the two obvious.

Everything involved is git-ignored: team decks may carry proprietary materials (R-16) and course material is never committed (AGENTS.md).

## Options considered

1. By tool, then test, then origin: `.local/fea/<abaqus|calculix-prepomax>/<test>/{team,ours,comparison}/`. Pro: what the founder asked for; one `cd` reaches everything about one test in one solver; the same test name under both tools gives the cross-solver comparison. Con: a test with files in both solvers has two folders.
2. By test, then tool: `.local/fea/<test>/<tool>/...`. Pro: one folder per test. Con: not the layout asked for; browsing all PrePoMax files, which is how the FEA training proceeds, crosses every test folder.
3. Keep sorting by file kind (status quo). Con: five folders per comparison; new tests multiply that.

For homework: (a) `assignments/<HW>/` and `code/<HW>/` with the same names, or (b) one folder per homework holding both. (a) was chosen because it mirrors the FEA rule (provided files in one tree, ours in another, joined by the name) and keeps the provided files visibly untouched.

## Decision

Option 1 and (a). `team/` holds what we compare against, including a team deck we converted to another solver; `ours/` what our generator wrote; `comparison/` the record, its reading note, notes, figures and the generated document in `report/<record>/`. Regenerable output of committed fixtures goes to `.local/fea/scratch/`. `docs/models/build.py` writes a local record's document beside the record instead of to `.local/model-reports/`. The committed side is unchanged: `fea/validation/{specs,decks,records}` for public materials, `engine/validation/cases/se142-*` for homework numbers. The `workspace-layout` skill states the rules and the filing procedure for agents.

## Why (evidence)

No measured evidence yet. The move itself: 7 local folders became 2 trees; the one real comparison (tension coupon) now reads as `abaqus/tension-coupon/{team,ours,comparison}` and `calculix-prepomax/tension-coupon/{team,ours,comparison}`. Tests and the document builder were pointed at the new paths; their output is in the pull request.

## Consequences

Easier: finding every file of one test, mirroring a team test with our own, and adding a new test or homework by following one procedure. Harder: paths in the evaluation reports of 2026-10-15 to 18 are now historical; they are left as written and the skill names the current ones. We now depend on everyone (people and agents) filing by the rule; the skill and the two local READMEs are the only enforcement, since the trees are not in git.

## How we will know it was wrong

A test's files end up in a fourth folder outside `team/`, `ours/` and `comparison/`, or the same files have to be moved again within six months.
