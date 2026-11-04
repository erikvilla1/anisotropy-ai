# ADR-0057: A shared brain for the team's agents lives in `docs/brain/`, the one folder an agent may write to `main` without a pull request

- Status: Proposed
- Date: 2026-11-04
- Decided by: Proposed by Kai Saucedo, growth engineering, 2026-11-04 ("docs/brain": a shared second brain for Anisotropy that he and the founder can use together, segregated from his personal one); the founder's decision is pending | Drafted by: Claude Code
- Related: [ADR-0023](ADR-0023-agent-skills-in-the-docs-vault.md) (`docs/` is the vault), [ADR-0028](ADR-0028-founder-tooling-outside-the-repository.md) (amendment 2), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `AGENTS.md`, `docs/brain/README.md`, `docs/agents/skills/project-rules/SKILL.md`

## Context

Two people now build Anisotropy with their own AI assistants: the founder with Claude Code in this repository, and Kai Saucedo (growth engineering since the kickoff of 2026-10-28) with Claude Code and a personal assistant that drafts and posts on X through an approval loop. Each assistant starts a session knowing nothing about the company unless someone re-explains it. Kai's personal assistant keeps a private memory vault for his own life, and he wants Anisotropy's context kept apart from it: an agent working on Anisotropy must read the company's memory, never his.

The first shared workflow is X posting: a draft in the team's Notion, a copy-editing pass, Christopher Valerio's approval in Discord, then the post. ADR-0028 keeps the founder's post-drafting tooling outside the repository and names as its revisit trigger "a second person needs to run the post-drafting workflow". That is now the case.

Facts that constrain the choice:

- `docs/` is already the Obsidian vault and changes through pull requests (ADR-0023; `AGENTS.md`).
- `AGENTS.md` forbids commits to `main`; every change goes through a pull request.
- The repository is public. Anything written here is readable by anyone.
- An agent writes memory during a session, many times a day. A pull request per fact is not workable.

## Options considered

1. **Notion only.** Memory in the team's Notion workspace. Pros: private, already shared, no repository change. Cons: not versioned or attributed the way the documentation guide asks; not beside the decision records and the rules it summarizes; needs a Notion token in every tool, including Claude Code sessions in this repository.
2. **A separate private repository**, the path ADR-0028 named for this case. Pros: private; agents commit freely; nothing in the product repository. Cons: a second clone on every machine and in every session; the brain drifts from the decisions and rules it summarizes; the founder's Claude Code sessions here do not see it without extra setup.
3. **`docs/brain/` in this repository, written directly to `main`, the only such folder.** Pros: one clone, one vault, beside the rules and the decision records; versioned and attributed by git; every agent working here finds it. Cons: public, so the brain holds only public-safe facts; one exception to the pull-request rule, limited to one folder and auditable by path and by commit prefix.
4. **`docs/brain/` through pull requests like everything else.** Rejected: an agent writes memory many times a day; a pull request per entry would stop it being written at all.

## Decision

Option 3. `docs/brain/` is the shared brain: `README.md` (the rules for any agent reading it), `company.md`, `people.md`, `voice.md` and `x.md` to start, one subject per note, dated entries under `## Log`. An agent pulls before reading and may commit and push changes inside `docs/brain/` to `main` directly, with a commit message that starts `brain:`. Everything else in the repository keeps changing through pull requests.

The brain holds facts: what the company is, who does what, where things live, how we write, what was decided and what was posted. It never holds secrets, customer or user data, contact details, personal facts beyond a role, pricing, contracts, fundraising or hiring before the founder makes it public, course material or the team's models (ADR-0042), nor drafts, prompts, page or channel ids, or any agent's configuration (ADR-0028). Those stay in Notion, in `.local/`, or on the machine that runs a workflow. The notes name no tool: they say "an assistant" and "the copy editor", so the repository's product code and documentation still name no assistant outside the decision records (ADR-0028).

Kai's assistant for Anisotropy is a separate profile of his assistant with its own memory pointing at this folder, never at his personal vault; his personal profile never reads this repository.

## Why (evidence)

- Kai's instruction of 2026-11-04 (this record's context): a shared second brain under `docs/`, segregated from his personal one.
- ADR-0028, "How we will know it was wrong": "if a second person needs to run the post-drafting workflow" ([ADR-0028](ADR-0028-founder-tooling-outside-the-repository.md)).
- `docs/` is the vault: ADR-0023, Decision. The pull-request rule: `AGENTS.md`, Changes.
- The repository is public: `gh api repos/erikvilla1/anisotropy-ai --jq .private` returned `false` on 2026-11-04.
- `main` has no branch protection: `gh api repos/erikvilla1/anisotropy-ai/branches/main/protection` returned 404 on 2026-11-04, so a direct push is possible today and this record is what limits it to one folder.
- The founder's review of this record: no evidence yet; pending.
- That agents keep the folder's rules (public-safe content, `brain:` commits only inside the folder): no evidence yet. The first month of `git log -- docs/brain/` is the test.

## Consequences

Easier: every agent working on Anisotropy, in any tool, reads the same company context; the founder sees what the agents know, in git, beside the decisions; Kai's two brains stay apart. Harder: the brain is public, so private context must live elsewhere and every writer must keep the folder's rules; one folder is exempt from the pull-request rule, so `git log -- docs/brain/` is the audit; a tool that writes here needs a clone and push rights. We now depend on git as the sync between machines: an agent that does not pull first gets its push refused as non-fast-forward, pulls and retries.

## How we will know it was wrong

Revisit if anything private lands in `docs/brain/` (then option 2, a private repository, at once, and the history rewritten); if a commit with the `brain:` prefix touches a file outside the folder; if the founder finds the brain's entries wrong or stale more than once a month; or if a third machine needs the brain and git sync conflicts weekly.
