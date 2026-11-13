# ADR-0028: Hermes and the founder's post-drafting tooling live outside the product repository and call the API as an outside client

- Status: Proposed; the facts the post-drafting workflow's assistants share may live in `docs/brain/` since amendment 2, confirmed by the founder on 2026-11-04 ([ADR-0057](ADR-0057-a-shared-brain-for-the-teams-agents-lives-in-docs-brain-the-one-folder-written-to-main-without-a-pull-request.md))
- Date: 2026-10-14
- Decided by: Founder, 2026-10-14; amendment 2: Founder, 2026-11-04 | Drafted by: Claude Code
- Related: ADR-0023 (agent skills; Hermes part superseded here), ADR-0026 (actor list), ADR-0027 (deployment tiers), `docs/agents/README.md`, `scripts/link-agent-dirs.ps1`, `api/src/anisotropy_api/records.py`

## Context

Hermes Agent (Nous Research) was planned as a second agent for this repository: it would read the skills in `docs/agents/skills/` through a junction (ADR-0023), run simulations through the API, and draft X and LinkedIn posts from run records (ADR-0025 and ADR-0026 name it as a consumer). The actor list in the `runs` table includes `hermes`.

On 2026-10-14 the founder stated that Hermes is for them alone: drafting posts and running simulations to post about. It is not part of the product. ADR-0027 decides that the product ships to customers as a self-hosted package; a marketing agent that reads run records has no place in a customer's deployment, and the founder does not want it in the repository or the code at all.

## Options considered

1. **Keep Hermes in the repository but exclude it from customer builds.** Needs a build switch and a test that the switch holds; the repository still carries tooling customers never receive and that has nothing to do with laminates.
2. **Move everything Hermes-specific out of the repository.** Hermes configuration, its skills and any post-drafting prompts live in the founder's own Hermes home (`~/.hermes/`) or a separate private repository. Hermes reaches the engine the way any outside client does: HTTP requests to the API with an actor header. The repository keeps nothing that names it.

For the `hermes` value in the actor list (a check constraint, so a migration either way):

1. Keep the string; it is only a label.
2. Replace it with a product-neutral name, `founder-agent`, by a new migration, so the API's public documentation and a customer's database do not name a tool they will never run.

## Decision

Option 2 for both. The follow-up chunk removes the `.agents/skills/` junction from `scripts/link-agent-dirs.ps1`, the Hermes rows and settings from `docs/agents/README.md` and the `project-rules` skill metadata, renames the actor by migration 0003 and updates the API README and tests. ADR-0023 stands for Claude Code and the Obsidian vault; its Hermes parts are superseded. Anything Hermes drafts stays in the founder's own storage and is never committed. Hermes may quote a number only when a run record backs it, as before, and it reads those records through the API from the founder's own deployment, never a customer's.

## Amendment 2026-10-15 (founder, review of this record)

Hermes stays in the plan as an internal tool for the founder's own use, later. When it is adopted and how it fits the founder's workflow is undecided: the founder wants to understand the tool first, and a separate decision record will cover its integration when that happens. Nothing about it enters the product repository or a customer deployment regardless of that timing; this record's decision stands.

## Why (evidence)

- The founder's instruction of 2026-10-14 (this record's context).
- Where Hermes is named in the repository today: `api/src/anisotropy_api/records.py` line 25, `api/tests/test_runs_api.py`, `api/README.md`, `docs/agents/README.md`, `scripts/link-agent-dirs.ps1`, `docs/agents/skills/project-rules/SKILL.md` metadata, ADR-0023, ADR-0025, ADR-0026 (grep on 2026-10-14).
- Hermes was never installed and never loaded a skill through the junction (ADR-0023 marks it UNVERIFIED), so nothing working is lost.
- Legal status of shipping such tooling to a customer: no evidence yet; the decision does not depend on it, since the founder does not want it there regardless.

## Consequences

Easier: the repository holds only the product and its documentation; customer builds carry nothing to strip; the actor list reads neutrally in a customer's database. Harder: Hermes's configuration is on one machine, outside version control, so the founder backs it up themselves; a new actor name is one more migration. The assistant actor (`assistant`) is unaffected: it is part of the product (ADR-0027).

## How we will know it was wrong

Revisit if Hermes needs repository files to work (then a separate private repository, not this one); if a second person needs to run the post-drafting workflow; or if the actor rename breaks a stored record's readability (it must not: a migration rewrites existing `hermes` rows to the new name, and the trigger that forbids updates is suspended for that migration only, which the migration test must show).

## Amendment 2, 2026-11-04 (the facts the workflow's assistants share may live in `docs/brain/`; confirmed by the founder)

**Context.** This record's revisit trigger, "a second person needs to run the post-drafting workflow", has fired. Kai Saucedo (growth engineering) runs the X posting workflow for Anisotropy with his own assistant, Christopher Valerio approves each post, and both assistants and the founder's Claude Code need the same company context. [ADR-0057](ADR-0057-a-shared-brain-for-the-teams-agents-lives-in-docs-brain-the-one-folder-written-to-main-without-a-pull-request.md) proposes that context as `docs/brain/`.

**Options.** (1) A separate private repository, the path this record named: rejected in ADR-0057 for a second clone on every machine and drift from the decisions it summarizes. (2) `docs/brain/` in this repository, public-safe facts only: chosen there.

**Decision.** This record's decision stands for everything it covers: the assistants' configuration, skills, prompts, scripts, credentials, page and channel ids, and the drafts themselves stay outside the repository, on the machine that runs them, and reach the engine as outside clients. One thing changes: the facts those assistants share (the company, the people, the voice, the posting rules and the log of what was posted) may live in `docs/brain/`, written in tool-neutral terms, so the product code and documentation still name no assistant outside the decision records. Proposed by Kai Saucedo on 2026-11-04. Founder's words: "Accept with changes" (a Claude Code review, 2026-11-04); the changes are ADR-0057 amendment 1.

**Evidence.** Kai's instruction of 2026-11-04 (ADR-0057, Context). No evidence yet that the split, facts in and tooling out, holds; ADR-0057's revisit triggers cover it.
