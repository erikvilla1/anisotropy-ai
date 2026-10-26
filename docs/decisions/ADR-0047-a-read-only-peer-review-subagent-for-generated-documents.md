# ADR-0047: A read-only subagent peer-reviews each generated document before it is sent, defined in the docs vault beside the skills

- Status: Proposed
- Date: 2026-10-25
- Decided by: Founder, 2026-10-25 ("ok let's do it", on the plan "a read-only peer-review subagent for the coupon package PDF") | Drafted by: Claude Code
- Related: `docs/agents/subagents/document-reviewer.md`, `scripts/link-agent-dirs.ps1`, [ADR-0023](ADR-0023-agent-skills-in-the-docs-vault.md), [ADR-0041](ADR-0041-one-document-per-coupon-in-chapters.md), [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md)

## Context

- The PDF of a coupon package (ADR-0041, ADR-0043) goes to the team, who build in Abaqus/CAE and do not read our code. The founder asked for a reviewer that reads it the way they will and says what is wrong before it is sent.
- The tests check the document's structure: chapters, labels, the coupon's name, the package's folders (`fea/tests/test_coupon_document.py`). No test reads the text, figures or tables as a reader does: whether a sentence agrees with the table beside it, whether a figure has units, whether an engineer can follow a chapter.
- The session that builds a document would review it with the builder's assumptions, and a whole PDF takes much of that session's context.
- Claude Code runs subagents. A subagent is defined in one Markdown file (name, description, tools, model, skills to preload, then its instructions), starts with an empty context and returns one reply. Claude Code reads them from `.claude/agents/` and loads a new folder there after a restart of the session ([Claude Code subagents](https://code.claude.com/docs/en/sub-agents), read 2026-10-25).

## Options considered

1. **A read-only subagent defined in `docs/agents/subagents/` and linked into `.claude/agents/` by a junction, as the skills are (ADR-0023).** It reads the document fresh, in its own context, with the same checklist every time, and it changes through pull requests and is visible in the vault. It costs a second junction and one restart. Chosen.
2. **A skill run in the main session.** No new folder, but the session that built the document would review it, and the PDF would fill its context.
3. **A subagent in the founder's `~/.claude/agents/`.** No repository change, but it would change outside pull requests and the vault, on one machine only.
4. **Tests only.** Deterministic, and they stay: they check structure. They cannot judge the text or whether a reader can follow it, so the reviewer adds to them rather than replacing them.

## Decision

Option 1.

- `docs/agents/subagents/document-reviewer.md` defines `document-reviewer`: tools Read, Grep and Glob only; model `opus`, so every review runs on the same model; the `project-rules` and `workspace-layout` skills preloaded.
- It reads the whole PDF of a coupon package, its figures and its `README.txt`, and checks seven things: the text against its own tables and figures, claims, conventions, figures and tables, the reader, the package's files, and typesetting. It lists the questions a peer would ask about the engineering apart from the findings.
- It returns at most 20 findings, most serious first. Each has its page and section, a severity (Must fix, Should fix, Minor) and the code in `docs/models/` where the fix goes. The review ends with a readiness: Ready to send, Send after fixes or Not ready. These words differ from the audit's Pass and Fail on purpose; this review is not the audit.
- It never computes a number or checks one against a record (ADR-0001). It never writes a file: the review is its reply, with no per-run notes (ADR-0039). It never proposes editing the generated `.tex` or PDF.
- It runs only when the founder asks; its description does not invite automatic delegation. Its findings are input to the founder's reading, not a gate.
- `scripts/link-agent-dirs.ps1` links `.claude/agents/` to `docs/agents/subagents/` beside the skills; git ignores both junctions.
- Coupon packages come first. The engine manual and the homework documents follow, each when asked.

## Why (evidence)

- The format, read on 2026-10-25 in [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): the fields used here (`name`, `description`, `tools` as a comma-separated string, `model`, `skills` as a YAML list), `.claude/agents/` as the project folder, a restart after the first file in a new folder, and an `@` mention to run a named subagent.
- The link script in a new worktree, 2026-10-25: the first run printed `created  .claude\skills -> docs\agents\skills` and `created  .claude\agents -> docs\agents\subagents`, and the second `ok` for both; `.claude\agents` listed `document-reviewer.md`; `git status` showed neither junction.
- The trial on one local coupon package: UNVERIFIED until the founder runs it. Then the counts of findings by kind, and how many the founder judged real, go here. The coupon's numbers and text stay out of this record (ADR-0042).
- Whether the Read tool in a subagent shows the figures of a PDF: UNVERIFIED until the trial.

## Consequences

- Easier: every package gets a second reading before it goes out, at the cost of one request, and the checklist changes through a pull request like code.
- Harder: each clone and each worktree needs the link script, and a session started before the folder existed sees no subagent until it is restarted. A review costs tokens on the largest model. The findings can be wrong or incomplete, so the founder still reads the package.
- We now depend on Claude Code's subagent format; if it changes, one file changes.

## How we will know it was wrong

- In two reviews running, the founder judges fewer than half of the findings real.
- The team reports a problem in a document that the reviewer read and did not flag.
- The founder stops asking for a review before sending a package.
