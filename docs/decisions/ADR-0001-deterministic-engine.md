# ADR-0001: A tested Python engine computes every number

- Status: Accepted
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: pull requests #1 and #2, [engine 0.1 verification report](../evaluations/2026-10-02_engine-0.1-verification.md)

## Context

Every architecture draft (the v1 technical specification, the v2 diagram and the v3 roadmap) requires that solvers, not a language model, produce the numbers in a result. Until 2026-10-02 the repository had no analysis code; small TypeScript kernels in `lib/physics-reference-checks.ts` only reproduced three textbook examples.

## Options considered

1. **A language model computes results directly.** Quick to demonstrate. Not reproducible, and errors are hard to detect.
2. **Extend the TypeScript kernels inside the website.** One language across the product. The planned backend, the numerical libraries and future finite element tools are Python, so the core would later be rewritten.
3. **A standalone Python package with no web or database code**, tested on its own and imported by the future API.

## Decision

Option 3: the package in `engine/`.

## Why (evidence)

- 148 automated tests pass.
- The engine reproduces printed answers from Daniel and Ishai (Problem 7.11, Table 7.3), the conclusions of Sample Problems 6.1 and 9.1, and a past homework answer key.
- Deliberately planted bugs in every module were detected by the tests.

Details are in the verification report.

## Consequences

- Easier: every number traces to tested code, and the physics can be tested without the website.
- Harder: each new analysis needs a tested engine function before it can be offered.
- The TypeScript kernels now duplicate part of the engine. They should become a cross-check or be removed (risk R-12).

## How we will know it was wrong

If most user requests need analyses the engine does not provide, and writing engine functions becomes the main bottleneck.
