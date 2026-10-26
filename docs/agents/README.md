# Agent skills

This folder holds the skills that AI coding agents read when working in this repository; today that is Claude Code. A skill is a folder with a `SKILL.md` file in the [agentskills.io](https://agentskills.io) format: a short frontmatter with `name` and `description`, then instructions.

It also holds the subagents: an agent the session hands one task to, which starts with an empty context and returns one reply. A subagent is one Markdown file in [Claude Code's format](https://code.claude.com/docs/en/sub-agents): a frontmatter with `name`, `description`, `tools`, `model` and the skills it preloads, then its instructions (ADR-0047).

The `docs/` folder is also the Obsidian vault, so these files can be read and edited in Obsidian (ADR-0023).

## Layout

| Path | Contents |
| --- | --- |
| `skills/project-rules/` | The repository's rules and where each kind of content goes. Every agent loads it first. |
| `skills/workspace-layout/` | Where the team's and our finite element files go, test by test under each tool, and where course homework and the code that solves it go (ADR-0032). |
| `skills/decision-records/` | How to write and amend a decision record: new record or amendment, numbering, the header lines, the amendment heading, evidence, the index row and the changelog line. |
| `skills/<name>/` | One folder per workflow skill. |
| `subagents/document-reviewer.md` | A read-only peer reviewer for a generated document, today the coupon package PDF. It returns findings by page and section with where each fix goes; it never edits a file or computes a number (ADR-0047). |

## How the agent finds them

Claude Code scans `.claude/skills/` for skills and `.claude/agents/` for subagents. `scripts/link-agent-dirs.ps1` points them at `skills/` and `subagents/` here with local junctions that git ignores. Run the script once after cloning and in every new worktree:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/link-agent-dirs.ps1
```

A session started before `.claude/agents/` existed lists no subagent; start a new session once.

## Using a subagent

Name it in a request, for example `@document-reviewer review <package folder>`. Its reply comes back in the session; it writes nothing.

## Changing a skill or a subagent

Skills and subagents change through pull requests, like code. An agent may draft a new or changed one, and a person reviews and merges it.

The `project-rules` skill tells every agent to read `AGENTS.md`, which stays the single source of the rules.

## What does not live here

Tooling that is not part of the product, such as the founder's agent that drafts posts about simulations, lives outside this repository and reaches the engine the way any outside client does: HTTP requests to the API with an actor header (ADR-0028).
