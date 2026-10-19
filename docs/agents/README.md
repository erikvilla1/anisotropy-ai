# Agent skills

This folder holds the skills that AI coding agents read when working in this repository; today that is Claude Code. A skill is a folder with a `SKILL.md` file in the [agentskills.io](https://agentskills.io) format: a short frontmatter with `name` and `description`, then instructions.

The `docs/` folder is also the Obsidian vault, so these files can be read and edited in Obsidian (ADR-0023).

## Layout

| Path | Contents |
| --- | --- |
| `skills/project-rules/` | The repository's rules and where each kind of content goes. Every agent loads it first. |
| `skills/workspace-layout/` | Where the team's and our finite element files go, test by test under each tool, and where course homework and the code that solves it go (ADR-0032). |
| `skills/<name>/` | One folder per workflow skill. |

## How the agent finds the skills

Claude Code scans `.claude/skills/`. `scripts/link-agent-dirs.ps1` points it at this folder with a local junction that git ignores. Run the script once after cloning:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1
```

## Changing a skill

Skills change through pull requests, like code. An agent may draft a new or changed skill, and a person reviews and merges it.

The `project-rules` skill tells every agent to read `AGENTS.md`, which stays the single source of the rules.

## What does not live here

Tooling that is not part of the product, such as the founder's agent that drafts posts about simulations, lives outside this repository and reaches the engine the way any outside client does: HTTP requests to the API with an actor header (ADR-0028).
