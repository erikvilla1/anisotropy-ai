---
name: project-rules
description: Rules for any work in the Anisotropy AI repository (composite laminate engine, material library, website, docs). Load before writing code, documents, data or skills here, and whenever deciding whether something belongs in the engine, the material library, the docs, or nowhere in the repository.
version: 0.1.0
---

# Project rules

## When to use

Before any change in this repository, and whenever you must decide where content belongs.

## Procedure

1. Read `AGENTS.md` at the repository root and follow it. It is the authority. If this skill and `AGENTS.md` disagree, `AGENTS.md` wins; report the disagreement.
2. Read `docs/documentation-guide.md` before writing a decision record, a report or a changelog entry.
3. Decide where the content goes with the table below. If nothing in the table fits, stop and ask the founder.
4. Work on a branch and open a pull request. Never commit to `main`.

## Where content goes

| Content | Where | Rule |
| --- | --- | --- |
| Any number in an analysis result | Computed by the engine, `engine/src/anisotropy_engine/` | ADR-0001 |
| An equation the engine uses | `engine/docs/theory.md`, plus a card in the website physics library (`lib/physics*.ts`) | ADR-0019 |
| A validation case | `engine/validation/cases/*.toml`: inputs, expected numbers and a source reference only | ADR-0007 |
| A material value from a public-domain or open-publisher source (MIL-HDBK-17F, NASA, NCAMP, datasheets) | The website material library in `lib/`, with a rights class and evidence; then `npm run export:library` so the engine sees it | ADR-0018, ADR-0020 |
| A value from a licensed reference (Daniel and Ishai, CMH-17, the course appendix) | Individual values with table and page only. Never scans, text, tables or PDFs | ADR-0010, ADR-0018 |
| User-supplied or customer data | Nothing public; private workspace only | ADR-0018 |
| Course problem statements or solutions, textbook pages, PDFs, unapproved lab data, secrets | `.local/` only. Never committed, never under `public/` | AGENTS.md |
| A choice between alternatives (library, algorithm, format, architecture, units) | A decision record in `docs/decisions/` from `_template.md` | AGENTS.md |
| Every change | One line in `CHANGELOG.md` under Unreleased | AGENTS.md |
| A new or changed agent skill | `docs/agents/skills/<name>/SKILL.md`, through a pull request | ADR-0023 |

## Pitfalls

- A source's rights class decides what may be shown. When it is unknown, treat the source as a licensed reference until the founder decides.
- Never invent evidence. Write "no evidence yet".
- Never claim a test passed without its output. Mark anything unchecked UNVERIFIED.
- The engine uses SI units inside; convert only where values enter and leave (ADR-0002). Invalid input is rejected, never defaulted (ADR-0003).

## Verification

- `git status` shows no file under `.local/`, `References/`, `output/` or any `*.pdf`.
- The tests that cover the change pass, with their output shown: `cd engine && uv run pytest`, `npm test`, `npm run typecheck`.
