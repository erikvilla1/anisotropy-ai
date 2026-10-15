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
| How do I run my own problem through the engine? | [Engine cheat sheet](engine-cheat-sheet.md) and the [engine card](components/engine.md) |
| How do I send a whole case over HTTP? | [Case endpoint note](api-case-endpoint-2026-10-11.md) and the [API card](components/api.md) |
| What happened this week? | [Weekly briefs](weekly/) |
| How does the API call the engine? | [Chunk 1 walkthrough](../api/README.md) and [API component card](components/api.md) |
| How does the website call the API? | [Chunk 2 walkthrough](walkthroughs/chunk-2-calculator.md) and [calculator component card](components/calculator.md) |
| How do we solve for moments under a curvature constraint? | [Chunk 3 walkthrough](walkthroughs/chunk-3-constrained-analysis.md) and [analysis card](components/prescribed-curvature.md) |
| What do AI agents read before working here? | [Agent skills](agents/README.md) |
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
| [0009](decisions/ADR-0009-calculator-inputs-in-case-files.md) | Calculator inputs reuse explicit TOML cases |
| [0010](decisions/ADR-0010-public-citations-local-page-evidence.md) | Publish property citations; keep textbook page scans local |
| [0011](decisions/ADR-0011-local-laminate-api.md) | Separate synchronous API with explicit SI-base inputs |
| [0012](decisions/ADR-0012-browser-calculator.md) | Static calculator page calls Python API with explicit boundary conversions |
| [0013](decisions/ADR-0013-prescribed-curvature-analysis.md) | Dedicated prescribed-curvature operation with required inputs and forward verification |
| [0014](decisions/ADR-0014-explicit-temperature-change.md) | Thermal analysis in separate functions with an explicit temperature change |
| [0015](decisions/ADR-0015-course-inputs-and-several-materials.md) | Cases read course Excel inputs and describe several materials per laminate |
| [0016](decisions/ADR-0016-mixed-load-deformation-conditions.md) | One general solver for mixed load and deformation conditions |
| [0017](decisions/ADR-0017-failure-with-fixed-and-variable-loads.md) | First-ply failure holds fixed loads and thermal stress constant and scales the rest |
| [0018](decisions/ADR-0018-source-rights-classes.md) | Every cited source carries a rights class that decides what the website shows |
| [0019](decisions/ADR-0019-physics-library-mirrors-engine-theory.md) | The physics library presents every equation the engine implements, naming its function and source |
| [0020](decisions/ADR-0020-material-library-as-engine-input.md) | The engine loads materials from the website's cited library through one exported JSON file |
| [0021](decisions/ADR-0021-maximum-strain-and-tsai-hill.md) | Maximum strain and Tsai-Hill join the failure criteria; strain limits are explicit or derived only by stated choice |
| [0022](decisions/ADR-0022-plate-buckling.md) | Plate buckling: Navier closed form for specially orthotropic laminates, Ritz sine series otherwise, simply supported edges |
| [0023](decisions/ADR-0023-agent-skills-in-the-docs-vault.md) | Agent skills live in `docs/agents/skills`, and `docs/` is the Obsidian vault (proposed) |
| [0024](decisions/ADR-0024-api-exposes-the-case-format.md) | The API exposes the engine's case format as one endpoint instead of one contract per operation |
| [0025](decisions/ADR-0025-run-records-in-local-postgresql.md) | Run records go in PostgreSQL, run locally in Docker, reached through SQLAlchemy and Alembic (proposed) |
| [0026](decisions/ADR-0026-run-record-contents-and-startup-policy.md) | A run record is immutable, keeps rejected runs, names its actor; the API refuses to start without the database (proposed) |
| [0027](decisions/ADR-0027-deployment-tiers-and-assistant-model-location.md) | Regulated customers run the whole stack inside their own boundary; the assistant's model is a per-deployment setting, off until configured (proposed) |
| [0028](decisions/ADR-0028-founder-tooling-outside-the-repository.md) | Hermes and post-drafting tooling live outside the repository and call the API as an outside client (proposed) |
| [0029](decisions/ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md) | Finite elements start with our own laminate membrane kernel solving the team's Abaqus decks on their mesh, numbers-only comparison records against their runs; Gmsh and our deck writer later (proposed, amended 2026-10-15) |

New decisions use the [template](decisions/_template.md).

## Material data documents

Latest checks: [Hermes out, actor renamed](evaluations/api/2026-10-14-hermes-out.md), [calculator endpoints recorded](evaluations/api/2026-10-14-run-records-calculator.md), [run records written and read back](evaluations/api/2026-10-14-run-records-write.md), [run records table and startup policy](evaluations/api/2026-10-14-run-records-table.md), [run records database](evaluations/api/2026-10-14-run-records-database.md), [engine, 11 October](evaluations/2026-10-11-criteria-buckling-loader.md), [API case endpoint](evaluations/api/2026-10-11-case-endpoint.md), [engine inputs](evaluations/2026-10-03-input-validation.md), [website inputs and citations](evaluations/website/2026-10-03-input-validation.md) and [source rights](evaluations/website/2026-10-10-source-rights.md). Website-only evaluations live in their subdirectory so the generated engine manual selects engine evidence.

| Document | Contents |
| --- | --- |
| [textbook-material-release-2026-10-01.md](textbook-material-release-2026-10-01.md) | Textbook material release |
| [textbook-review-daniel-ishai-2006.md](textbook-review-daniel-ishai-2006.md) | Review of the Daniel and Ishai textbook as a source |
| [material-research-audit-2026-10-01.md](material-research-audit-2026-10-01.md) | Material library reference audit |
| [qualification-records-2026-10-01.md](qualification-records-2026-10-01.md) | First carbon and glass engineering-reference records |
| [material-property-expansion-2026-10-02.md](material-property-expansion-2026-10-02.md) | Material property expansion |
| [physics-foundations-2026-10-02.md](physics-foundations-2026-10-02.md) | Physics reference foundation for the website library |
| [physics-library-completion-2026-10-10.md](physics-library-completion-2026-10-10.md) | Physics library completion: a card for every engine operation (ADR-0019) |
| [material-loader-2026-10-10.md](material-loader-2026-10-10.md) | Material loader: the engine, API and calculator take cited library datasets by name (ADR-0020) |
| [api-case-endpoint-2026-10-11.md](api-case-endpoint-2026-10-11.md) | The API solves whole cases: every engine operation over HTTP in one call (ADR-0024) |
| [engine-cheat-sheet.md](engine-cheat-sheet.md) | How to put a problem into the engine and read the answer: units, applied forms, failure search, expected keys |
| [material-research-public-sources-2026-10-10.md](material-research-public-sources-2026-10-10.md) | Public data sources the website may show: NCAMP reports, MIL-HDBK-17F, NASA, open-access papers, datasheets |
| [material-release-im7-8552-2026-10-10.md](material-release-im7-8552-2026-10-10.md) | Hexcel 8552 / IM7 record from the NCAMP 2019 reports |
| [material-release-ncamp-5320-1-bt250e-6-2026-10-10.md](material-release-ncamp-5320-1-bt250e-6-2026-10-10.md) | Solvay 5320-1 / T650 and TenCate BT250E-6 / IM7 records from the NCAMP 2017 reports |
| [material-release-ncamp-tc380-ep2190-2026-10-10.md](material-release-ncamp-tc380-ep2190-2026-10-10.md) | Toray TC380 / T1100GC and Syensqo EP2190 / IMS65 records from the NCAMP 2025 reports |
| [material-release-nasa-im7-8552-2026-10-10.md](material-release-nasa-im7-8552-2026-10-10.md) | NASA 2023 IM7 / 8552 characterization as a second dataset of the IM7 / 8552 record |
| [material-release-library-completion-2026-10-10.md](material-release-library-completion-2026-10-10.md) | Three NCAMP plain weave records and two MIL-HDBK-17-2F historical records; close-out of the public-sources research |

## Added when the parts exist

From the documentation guide, these wait until the parts they describe are built: component cards for the language model and the report generator, and the per-run provenance record (run records, next). The weekly brief started on 2026-10-11 in `weekly/`; the engine has a [component card](components/engine.md). The local API now has a [component card](components/api.md) and [evaluation](evaluations/api/2026-10-03-api-chunk-1.md).
