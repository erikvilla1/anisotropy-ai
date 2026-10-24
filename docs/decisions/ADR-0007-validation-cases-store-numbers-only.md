# ADR-0007: Validation cases store numbers and a source reference only

- Status: Accepted; cases from the course's answer keys leave the repository and its history by [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md)
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: `engine/validation/README.md`, pull request #2

## Context

Validation uses textbook problems, course answer keys and, later, our own lab measurements. Problem statements, solution files and textbook pages belong to their publishers and instructors, and this repository is hosted on GitHub.

## Options considered

1. Store the original problem text or solution file with each case. Self-contained, but copies material we do not own.
2. Store only the inputs, the expected values and a short source reference. Originals stay in `.local/`, which Git ignores.

## Decision

Option 2. Each case is a small TOML file in `engine/validation/cases/`.

## Why (evidence)

The rule follows from who owns the material, not from a test. The format itself works: five cases run as automated tests, and the runner is tested to report wrong values.

## Consequences

- Re-checking a case against its source means consulting the original offline.
- The same file format can later hold lab measurements with their metadata.

## How we will know it was wrong

If a reviewer or customer needs worked solutions in the repository, link to licensed sources rather than copying them.
