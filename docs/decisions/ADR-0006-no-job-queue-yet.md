# ADR-0006: No job queue until analyses are slow

- Status: Accepted; its trigger fired with coupon jobs (ADR-0050), and the queue comes after the hosted tier's closed beta by [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md)
- Date: 2026-10-02
- Decided by: Founder | Drafted by: Claude Code
- Related: v1 technical specification and v2 architecture (Celery and Redis workers)

## Context

Earlier architecture drafts include a job queue (Celery workers with a Redis broker) for long-running analyses. A laminate analysis takes milliseconds.

## Options considered

1. **A job queue from the start.** Ready for slow jobs. Adds two services to deploy, monitor and secure before any job needs them.
2. **A synchronous API** that returns results in the same request, with workers added when slow analyses arrive.

## Decision

Option 2.

## Why (evidence)

The full engine test suite, 148 tests covering hundreds of laminate analyses, runs in under one second.

## Consequences

- Simpler deployment for the first release.
- Finite element analysis, optimization over many layups, and report compilation will need workers when they are added.

## How we will know it was wrong

If any request routinely takes more than about two seconds, or when finite element analysis is added.
