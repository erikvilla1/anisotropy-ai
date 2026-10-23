<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Working in this repository

These rules apply to AI coding assistants and to people. `next dev` rewrites only the block above; keep project rules below it.

## Changes

- Deliver work in small, reviewable chunks. After each chunk, explain what was implemented, what its functions and libraries do, how data flows between components, how it was checked, and what remains. Stop for the founder's walkthrough before starting the next chunk.
- Work on a branch and open a pull request. Do not commit to `main` directly.
- Before opening a pull request, run the tests that cover the change: `cd engine && uv run pytest` for the engine; `npm test` and `npm run typecheck` for the website.

## Documentation

The full method is in `docs/documentation-guide.md`; the index is `docs/README.md`.

1. If a change chooses between alternatives (a library, algorithm, data format, architecture, units or conventions), add a decision record in `docs/decisions/` from `_template.md`. List the rejected options and link real evidence. Never invent evidence; write "no evidence yet" instead.
2. Add a line to `CHANGELOG.md` under Unreleased.
3. If engine physics changes, update `engine/docs/theory.md` and add or update cases in `engine/validation/cases/`.
4. Never claim a test passed without its output. Mark anything unchecked as UNVERIFIED.
5. State what was decided and what supports it. Do not present your own reasoning as fact.
6. Keep entries short.
7. The PDF manual in `docs/manual/` is generated from these documents and the code. Edit the sources, never `docs/manual/generated/`. When `theory.md` says a function computes something, add a `<!-- code: name -->` marker where its listing belongs.

## Agent skills

- Skills for AI agents live in `docs/agents/skills/` (ADR-0023). Read `project-rules` first. Change a skill only through a pull request.

## Engine rules

- The engine computes every number in a result (ADR-0001).
- SI units inside the engine; convert only where values enter and leave (ADR-0002).
- Reject invalid input; never add silent defaults (ADR-0003).
- Engineering shear strain, angles counterclockwise from x to the fibers, plies listed from the bottom face up (ADR-0004).

## Data and sources

Do not commit course problem statements, solutions or answer-key numbers, homework readings, textbook pages, customer data, unapproved lab data, the team's coupon models and the numbers compared with them, or secrets (ADR-0042). Store public numbers with a source reference; keep everything else, and all originals, in `.local/`.
