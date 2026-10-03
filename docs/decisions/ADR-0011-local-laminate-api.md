# ADR-0011: A separate synchronous FastAPI adapter with an explicit SI-base contract

- Status: Accepted
- Date: 2026-10-03
- Decided by: Founder | Drafted by: Codex
- Related: [API walkthrough](../../api/README.md), [evaluation](../evaluations/api/2026-10-03-api-chunk-1.md), [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0006](ADR-0006-no-job-queue-yet.md)

## Context

The website is a static export; the standalone Python engine already computes laminate stiffness and response. The founder requested small implementation chunks with explanations after each. FastAPI was planned in the system overview.

## Options considered

1. Put HTTP code and dependencies inside the engine. Fewer packages; couples the standalone solver to the web layer.
2. Implement the calculation endpoint in Next.js. Requires a server beyond the current static export and a way to invoke Python, or duplicated equations.
3. Add a separate Python API package that imports the engine. Adds a second environment/lockfile; retains the solver's existing boundary.
4. Accept calculator display units or default absent loads to zero. Shorter requests; risks confusing GPa with Pa or an omitted component with an intentional zero.

## Decision

Option 3, with one synchronous endpoint for stiffness and deformation. Require `SI_BASE` and all six load components, explicit unit suffixes on material moduli/thickness, one material with a caller-supplied reference, and a bottom-first ply list. Return finite matrices/vectors, accepted inputs and engine package version. Keep persistence, material lookup and assistant orchestration for later chunks. Use HTTPX2 for the current Starlette test client.

## Why (evidence)

- [FastAPI request-body documentation](https://fastapi.tiangolo.com/tutorial/body/) describes Pydantic validation and generated API schemas.
- [The existing solver](../../engine/src/anisotropy_engine/response.py) already exposes `midplane_response`; the adapter calls it directly.
- [API tests](../../api/tests/test_api.py) compare a constructed axial case to independent compliance equations and a coupled stack to direct engine calls. Actual output is recorded in the evaluation.
- The installed Starlette 1.7.0 `testclient.py` imports HTTPX2 first and deprecates HTTPX. Package versions are pinned in [api/uv.lock](../../api/uv.lock).
- Comparative framework performance, deployment capacity and physical coupon agreement: no evidence yet (UNVERIFIED).

## Consequences

The API is locally runnable and inspectable at `/docs`. It performs no unit conversions and does not authenticate callers or validate citation provenance. There are two Python lockfiles; the engine must also be tested under the API environment. A declared package version alone does not fingerprint source changes.

## How we will know it was wrong

Revisit if requests routinely exceed the existing roughly two-second threshold in ADR-0006, if mixed-material laminates are needed, or if integration evidence shows this contract cannot represent supported requests without losing information.
