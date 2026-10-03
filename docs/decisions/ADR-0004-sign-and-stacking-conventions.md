# ADR-0004: Engineering shear, counterclockwise angles, bottom-first stacking

- Status: Accepted
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: `engine/README.md`, `engine/validation/README.md`

## Context

Textbooks and courses use different conventions: tensor or engineering shear strain, ply 1 at the top or the bottom, z measured up or down. A convention mismatch gives answers that look plausible but are wrong.

## Options considered

1. Follow one textbook's conventions exactly.
2. Let every call choose its conventions.
3. Fix one set of conventions, documented, and translate other sources at the input.

## Decision

Option 3:

- Shear strain is engineering shear, gamma12 = 2 * epsilon12.
- The ply angle is positive counterclockwise from the laminate x axis to fiber axis 1.
- Plies are listed from the bottom face up; z is measured from the mid-plane, positive upward, so the first ply starts at z = -h/2.
- Compressive strengths are stored as positive magnitudes.

These follow Daniel and Ishai (2006), with shear written as engineering strain.

## Why (evidence)

- Work-invariance tests in `test_rotation.py` detect a factor-of-2 shear error.
- The homework validation case matches its answer key under these conventions.

## Consequences

- Problems from sources with other conventions must be translated at input, for example by reversing the layup list.
- `engine/validation/README.md` lists the convention checks to make when a case does not match.

## How we will know it was wrong

If most users' sources use top-first stacking or tensor shear, add explicit input options rather than changing the defaults.
