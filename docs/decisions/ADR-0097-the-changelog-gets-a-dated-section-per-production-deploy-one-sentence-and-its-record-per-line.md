# ADR-0097: The changelog gets a dated section per production deploy, one sentence and its record per line

- Status: Proposed
- Date: 2026-11-13
- Decided by: Founder, 2026-11-12 ("accept", on the audit's recommendation "give each production deploy a dated section with one-sentence entries") | Drafted by: Claude Code
- Related: [ADR-0096](ADR-0096-the-repository-is-all-rights-reserved-by-anisotropy-and-third-party-values-keep-their-owners-terms.md), `CHANGELOG.md`, `docs/documentation-guide.md`, `.github/workflows/deploy.yml`

## Context

`CHANGELOG.md` keeps every change since the start under one Unreleased heading, with several Added, Changed and Fixed blocks and lines of a hundred words or more. A merge to `main` deploys to production once its Tests pass (`.github/workflows/deploy.yml`), so Unreleased mixes what is live with what is not. The professional audit of 2026-11-12 found it hard to read (finding documents-37).

## Options considered

1. One Unreleased section with one Added, Changed and Fixed block: rejected, because it still does not say what each deploy shipped.
2. A dated section per production deploy, one sentence and its record per line: chosen.
3. Numbered releases: rejected, because the site deploys from `main` on every merge and has no release step to number.

## Decision

Option 2. A pull request adds one line under `## [Unreleased]`, in its Added, Changed or Fixed block: one sentence saying what changed for a reader, then its decision record. The next change to `CHANGELOG.md` after a production deploy moves the lines that deploy shipped to `## [YYYY-MM-DD]`, the deploy's date; deploys on one day share a section. Each section has at most one Added, one Changed and one Fixed block, in that order. The rule starts with the first deploy after the 2026-11-12 audit's pull requests have merged, and that change also sorts the current Unreleased lines into dated sections. `docs/documentation-guide.md` carries the rule.

## Why (evidence)

The founder's decision D30 of 2026-11-12, answered on the audit's findings page. No evidence yet that the cadence is kept.

## Consequences

Every pull request still adds one line, as before. The first sorting of the existing lines is one larger change to `CHANGELOG.md`, made when no other pull request is open against it.

## How we will know it was wrong

If dated sections fall behind the deploys, or lines keep growing past one sentence, the rule is not being followed and a check in CI, or a simpler rule, is needed.
