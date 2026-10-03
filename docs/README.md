# Documentation

Where to find what Anisotropy AI has built, why, and how we know it works.

## Start here

| Question | Read |
| --- | --- |
| What have we built? | [System overview](00_system_overview.md) |
| Why was it built this way? | [Decision records](decisions/) |
| Does it work, and how do we know? | [Evaluation reports](evaluations/) and [validation cases](../engine/validation/) |
| What changed, and when? | [Changelog](../CHANGELOG.md) and merged pull requests |
| What could go wrong? | [Risk register](risks/risk_register.md) |
| How is each result calculated? | [Engine theory](../engine/docs/theory.md) |
| How does the API call the engine? | [Chunk 1 walkthrough](../api/README.md) and [API component card](components/api.md) |
| How does the website call the API? | [Chunk 2 walkthrough](walkthroughs/chunk-2-calculator.md) and [calculator component card](components/calculator.md) |
| How do we solve for moments under a curvature constraint? | [Chunk 3 walkthrough](walkthroughs/chunk-3-constrained-analysis.md) and [analysis card](components/prescribed-curvature.md) |
| All of the above as one typeset PDF | [Engine manual](manual/) |
| Where do material values come from? | The material data documents below |

## How we document

We follow the [documentation guide](documentation-guide.md). In short:

- Documents live in this repository and change through pull requests, like code.
- Record decisions and evidence. Any claim that something works links to a test or a report.
- AI tools may draft documents; a person reviews and merges them.
- Document what exists. A planned component gets its document when it is built.

Rules for AI coding assistants are in [AGENTS.md](../AGENTS.md).

## Engineering credibility

The guide covers software and AI governance (NIST AI RMF). Engineering results also need evidence that the physics model is credible:

| Evidence | Meaning | Where |
| --- | --- | --- |
| Theory | The equations and their assumptions | [engine/docs/theory.md](../engine/docs/theory.md) |
| Verification | The code solves those equations correctly | Engine tests and [evaluation reports](evaluations/) |
| Validation | The equations match independent results: textbooks and answer keys now, our coupon tests later | [engine/validation/cases](../engine/validation/cases/) |
| Applicability | Where the model may and may not be used | "Known limitations" in the [system overview](00_system_overview.md) |

NASA-STD-7009A (models and simulations) and ASME V&V 10 (computational solid mechanics) are the reference practices for this kind of evidence.

## Decision records

| ADR | Decision |
| --- | --- |
| [0001](decisions/ADR-0001-deterministic-engine.md) | A tested Python engine computes every number |
| [0002](decisions/ADR-0002-si-units-inside-the-engine.md) | SI units inside the engine; convert only at inputs and outputs |
| [0003](decisions/ADR-0003-reject-invalid-input.md) | Reject invalid input; never substitute defaults |
| [0004](decisions/ADR-0004-sign-and-stacking-conventions.md) | Engineering shear, counterclockwise angles, bottom-first stacking |
| [0005](decisions/ADR-0005-engineering-constants-from-full-abd.md) | Laminate engineering constants from the full ABD inverse |
| [0006](decisions/ADR-0006-no-job-queue-yet.md) | No job queue until analyses are slow |
| [0007](decisions/ADR-0007-validation-cases-store-numbers-only.md) | Validation cases store numbers and a source reference only |
| [0008](decisions/ADR-0008-manual-generated-from-sources.md) | The LaTeX manual is generated from the repository's sources |
| [0009](decisions/ADR-0009-calculator-inputs-in-case-files.md) | Calculator inputs reuse explicit TOML cases (proposed) |
| [0010](decisions/ADR-0010-public-citations-local-page-evidence.md) | Publish property citations; keep textbook page scans local (proposed) |
| [0011](decisions/ADR-0011-local-laminate-api.md) | Separate synchronous API with explicit SI-base inputs (proposed) |
| [0012](decisions/ADR-0012-browser-calculator.md) | Static calculator page calls Python API with explicit boundary conversions (proposed) |
| [0013](decisions/ADR-0013-prescribed-curvature-analysis.md) | Dedicated prescribed-curvature operation with required inputs and forward verification (proposed) |

New decisions use the [template](decisions/_template.md).

## Material data documents

Latest checks: [engine inputs](evaluations/2026-10-03-input-validation.md) and [website inputs and citations](evaluations/website/2026-10-03-input-validation.md). Website-only evaluations live in their subdirectory so the generated engine manual selects engine evidence.

| Document | Contents |
| --- | --- |
| [textbook-material-release-2026-10-01.md](textbook-material-release-2026-10-01.md) | Textbook material release |
| [textbook-review-daniel-ishai-2006.md](textbook-review-daniel-ishai-2006.md) | Review of the Daniel and Ishai textbook as a source |
| [material-research-audit-2026-10-01.md](material-research-audit-2026-10-01.md) | Material library reference audit |
| [qualification-records-2026-10-01.md](qualification-records-2026-10-01.md) | First carbon and glass engineering-reference records |
| [material-property-expansion-2026-10-02.md](material-property-expansion-2026-10-02.md) | Material property expansion |
| [physics-foundations-2026-10-02.md](physics-foundations-2026-10-02.md) | Physics reference foundation for the website library |

## Added when the parts exist

From the documentation guide, these wait until the parts they describe are built: component cards for the language model and the report generator; the per-run provenance record; and the weekly brief. The local API now has a [component card](components/api.md) and [evaluation](evaluations/api/2026-10-03-api-chunk-1.md).
