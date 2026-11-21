# ADR-0133: The public record states no result of a run in Abaqus or Ansys and names no licence; the numbers of such comparisons are kept privately

- Status: Proposed
- Date: 2026-11-21
- Decided by: Founder, 2026-11-20 ("merge and yes thee shouldn't wording in our software", on wording that quotes runs under his own licences) and 2026-11-20 ("merge, and yes please don't need to quote abaqus runs should sound more professional or remove it", on the older records) | Drafted by: Claude Code
- Related: [ADR-0045](ADR-0045-abaqus-without-the-gui-odbaccess-reports-and-an-optional-second-reference.md), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md), [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md), [ADR-0129](ADR-0129-the-model-on-the-page-downloads-as-a-file-for-the-engineers-own-program-one-writer-per-program-over-the-neutral-model-and-the-ansys-file-is-offered-to-founders-only-until-it-has-run-in-ansys.md) amendment 4, [ADR-0132](ADR-0132-a-repairs-slice-is-solved-in-calculix-as-a-plane-of-eight-node-elements-held-flat-with-the-laminates-far-field-width-strain-and-its-bondline-and-plies-are-read-back-as-means-by-the-engine.md) amendment 1, [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `fea/checks/d3039-im7-8552/README.md`, `fea/checks/abaqus-conventions.toml`
- Area: docs, process

## Context

The repository is public and the product is commercial. Its records, changelog, guides, check notes and code comments described comparisons with Abaqus and Ansys as events: when a run was made, on which installation, and what numbers came back. Two records had already been changed on the founder's word (ADR-0132 amendment 1 and ADR-0129 amendment 4). The founder then asked for the same in the older records, in the words quoted above.

Abaqus's and Ansys's own numbers were already kept out of the repository (ADR-0045); what the public files held was prose about the runs, and counts and percentages of agreement.

## Options considered

1. **Leave the older records as written.** A record is not normally rewritten. Rejected by the founder's word.
2. **Remove every mention of Abaqus and Ansys.** Rejected: the product writes Abaqus and Ansys files, reads an Abaqus input file and has a connector that runs inside the user's own Abaqus. Those are features and stay described.
3. **Reword or remove the sentences that describe a run or name an installation, and keep what the product does and how each program behaves.** Chosen.

## Decision

In every public file of this repository:

- **Not stated:** a number that came out of a run in Abaqus or Ansys, or a count or percentage of agreement with one; the type or name of a licence, a licence server, or whose installation a run was made on; a narration of a run as an event.
- **Stated plainly:** what the product does with these programs (the files it writes and reads, the connector, the comparison tools); how each program behaves and formats its output, as a fact with the release it holds for ("Abaqus 2025 prints ..."); how a comparison is made and what it is held to; and, where a decision of ours rests on a comparison, the verdict in one sentence without numbers ("meets the acceptance of ADR-0089").
- **Kept privately:** the numbers of a comparison and a run's files, outside the repository (ADR-0042, ADR-0045).

This record changes the usual rule that a record's earlier text stays as written: for this purpose, and on the founder's word, earlier records were reworded in place. No decision in them is changed.

## As built (2026-11-21)

- Decision records reworded: ADR-0029, 0030, 0035, 0045, 0049, 0053, 0056, 0066, 0067, 0071, 0089, 0094, 0105, 0129 and 0132. In ADR-0094 the connector's trials stay as evidence of how the connector behaves inside Abaqus/CAE, without the numbers of Abaqus's solves.
- `fea/checks/d3039-im7-8552/README.md` now says how round (a) is compared and what it is held to, and no longer holds the tables of counts and percentages. `fea/checks/abaqus-conventions.toml` states definitions only.
- The index (`docs/README.md`), the changelog, `docs/installation-fea-tools.md`, `docs/abaqus-export-recipe.md`, `docs/00_system_overview.md`, `docs/components/fea.md`, the risk register, three evaluation notes, `fea/README.md`, `fea/docs/theory.md` and comments in `fea/src`, `fea/tools` and `fea/tests`.
- Not changed: the files of the connector that its released zip holds (`fea/tools/anisotropy_*`, `abaqus_every_output.py`, `abaqus_extract_fields.py`, `bundle.py`), because a release is recorded by its SHA-256 (ADR-0094 amendment 3); their comments state how Abaqus/CAE behaves and no result of a solve. The committed decks, fixtures and tests are unchanged apart from comments, and one test of the connector's argument reader no longer lists two launcher flags it does not need.

## Why (evidence)

- The founder's words, quoted in the header.
- No test's expected value is a number from Abaqus or Ansys, so no test changes its verdict: the tests named in the pull request pass before and after.
- No evidence is offered here about what any licence allows: that question is not answered by this record.

## Consequences

- A reader of the public record can no longer check the size of an agreement with Abaqus from it; ADR-0089's gate is stated as a verdict.
- The wording as it was stays in the repository's history, in earlier commits and pull requests. This record does not change that.
- Committed items made with the help of these programs other than prose (for example the fixture laid out as Abaqus/CAE writes a model) stay.
- New records follow the Decision above.

## How we will know it was wrong

- A reviewer or a customer needs the numbers of a comparison with Abaqus or Ansys to trust a result, and the verdict sentence is not enough.
- A public file is found that still states a result of a run or names a licence.
