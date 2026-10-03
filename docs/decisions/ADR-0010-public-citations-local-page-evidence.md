# ADR-0010: Keep page scans local and publish property citations

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Codex
- Related: AGENTS.md data rules; risk R-05; `tests/textbook-materials.test.ts`

## Context

The unfinished source viewer put four Daniel and Ishai page images in public assets. AGENTS.md forbids committing textbook pages; R-05 already records this issue. No evidence of redistribution permission is recorded.

## Options considered

1. Publish the scans. Conflicts with the repository rule; no evidence of permission.
2. Remove the whole viewer. Loses useful property-specific source locations and unit comparisons.
3. Publish citation details and recorded values, keeping the source scans local.

## Decision

Option 3. Retain table/page and dataset/property links, source-unit values and displayed conversions. The viewer links to the publisher and tells readers to consult their copy. Move existing images into ignored `.local/textbook-evidence/`; make the renderer write only there.

## Why (evidence)

The policy is explicit in AGENTS.md. Unit tests check that public scans are absent; browser tests check citations, conversions, invalid links and a 404 for the old scan URL. Results are recorded in the [evaluation](../evaluations/website/2026-10-03-input-validation.md).

## Consequences

The website cannot display scanned source pages. Reviewers retain local evidence and fingerprints. This does not assert broader redistribution or commercial-use rights for source material.

## How we will know it was wrong

Revisit if the repository policy changes with documented rights for a specific source. Do not infer permission from access to a supplied PDF.
