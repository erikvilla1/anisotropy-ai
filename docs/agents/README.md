# Agent skills

This folder holds the skills that AI agents working in this repository read: Claude Code and Hermes Agent (Nous Research). A skill is a folder with a `SKILL.md` file in the [agentskills.io](https://agentskills.io) format: a short frontmatter with `name` and `description`, then instructions.

The `docs/` folder is also the Obsidian vault, so these files can be read and edited in Obsidian (ADR-0023).

## Layout

| Path | Contents |
| --- | --- |
| `skills/project-rules/` | The repository's rules and where each kind of content goes. Every agent loads it first. |
| `skills/<name>/` | One folder per workflow skill. |

## How the agents find the skills

Each agent scans its own hidden folder. `scripts/link-agent-dirs.ps1` points both at this one:

| Agent | Scans | Points to |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `docs/agents/skills/` |
| Hermes Agent | `.agents/skills/` | `docs/agents/skills/` |

The links are local and ignored by git. Run the script once after cloning:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1
```

Hermes runs inside WSL2 on Windows. Whether it follows these Windows junctions is UNVERIFIED; if it does not, set `skills.external_dirs` in `~/.hermes/config.yaml` to this folder's WSL path instead.

## Changing a skill

Skills change through pull requests, like code. An agent may draft a new or changed skill, and a person reviews and merges it. Hermes is configured with `skills.write_approval: true`, so the skills it writes wait for approval instead of taking effect.

Hermes does not read `AGENTS.md`. The `project-rules` skill tells every agent to read it, so `AGENTS.md` stays the single source of the rules.
