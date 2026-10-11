# ADR-0023: Agent skills live in docs/agents/skills, and docs/ is the Obsidian vault

- Status: Proposed
- Date: 2026-10-11
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: `docs/agents/README.md`, `docs/agents/skills/project-rules/SKILL.md`, `scripts/link-agent-dirs.ps1`

## Context

The founder plans to use two agents: Claude Code and Hermes Agent by Nous Research. They want the project's rules (what to document, what goes into the engine and the material library, what never enters the repository) to reach both agents. They also want to read and edit those files in Obsidian. The rules exist today only as prose in `AGENTS.md` and `docs/documentation-guide.md`.

Facts that constrain the choice:

- Hermes reads project skills from `<repo>/.hermes/skills/` and `<repo>/.agents/skills/` in the agentskills.io `SKILL.md` format. Its documentation does not mention `AGENTS.md`.
- Claude Code reads project skills from `.claude/skills/` in the same format.
- Obsidian does not show folders whose names start with a dot, and indexes every Markdown file under the vault root.
- The repository root contains `node_modules/`, which holds thousands of Markdown files.
- The PDF manual is generated from files in `docs/` (ADR-0008). Obsidian wikilinks (`[[note]]`) are not standard Markdown.
- Hermes does not run natively on Windows; it runs inside WSL2.

## Options considered

1. Vault at the repository root, skills in `.agents/skills/`. The agents find the skills directly, but Obsidian hides them and indexes `node_modules/`.
2. A vault outside the repository, synced into it. Keeps the repository clean of vault files, but skills would change outside pull requests and could drift from the code.
3. `docs/` as the vault, skills in the visible folder `docs/agents/skills/`, and local junctions from `.claude/skills/` and `.agents/skills/` to it. Skills are visible in Obsidian, change through pull requests, and are written once for both agents. Costs one setup script, and Hermes in WSL2 may not follow a Windows junction.
4. Option 3, but Hermes reads the folder through `skills.external_dirs` in its config instead of a junction. Works regardless of junction support, but needs per-machine Hermes configuration.

## Decision

Option 3, with option 4 as the fallback for Hermes if it does not follow the junction. Obsidian uses Markdown links, not wikilinks. Vault settings (`docs/.obsidian/`) and the junctions are ignored by git. `AGENTS.md` stays the single source of the rules; the `project-rules` skill tells each agent to read it.

## Why (evidence)

- Hermes project skill folders and the `skills.write_approval` setting: [Hermes skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills).
- Hermes on Windows requires WSL2: [Hermes WSL2 guide](https://hermes-agent.nousresearch.com/docs/user-guide/windows-wsl-quickstart).
- `scripts/link-agent-dirs.ps1` created both junctions on 2026-10-11, listed `project-rules` through each, and a second run reported both as already in place; `git status` shows neither junction.
- Claude Code loading a skill through the junction: UNVERIFIED until a new session lists `project-rules`.
- Hermes following the junction from WSL2: UNVERIFIED; Hermes is not installed yet.
- Obsidian hiding dot-folders: no evidence recorded beyond the founder's planned use; check in the vault.

## Consequences

Skills are written once and reviewed like code. Obsidian shows the skills, decisions and reports in one place. Each clone needs the setup script once. Two agents now depend on the same files, so a skill change affects both. The manual build is unaffected because it reads named files and the decision records only.

## How we will know it was wrong

Revisit if Claude Code or Hermes fails to load a skill through the junction and the `external_dirs` fallback does not fix Hermes, if Obsidian rewrites links in a way that breaks the manual build, or if an agent changes a skill without a pull request.
