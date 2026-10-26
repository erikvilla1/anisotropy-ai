# Documentation

Where to find what Anisotropy AI has built, why, and how we know it works.

## Start here

| Question | Read |
| --- | --- |
| What have we built? | [System overview](00_system_overview.md) |
| Why was it built this way? | [Decision records](decisions/) |
| How do we read the team's Abaqus decks, solve them, and what do we refuse? | [Finite element card](components/fea.md), [finite element theory](../fea/docs/theory.md), [what the team exports](abaqus-export-recipe.md) |
| How does the team hand us a coupon to model? | [ADR-0046](decisions/ADR-0046-coupon-intake-by-an-excel-input-form.md): the coupon input form, written by `fea/tools/coupon_form.py` and read by `fea/tools/coupon_from_form.py` |
| How do we build our own coupon models, and which tools do they need? | [ADR-0030](decisions/ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), one folder per test under `fea/checks/` and, for our models of the team's coupons, `.local/fea/<coupon>/` (ADR-0036, ADR-0042), [installing the tools](installation-fea-tools.md) |
| Does it work, and how do we know? | [Evaluation reports](evaluations/) and [validation cases](../engine/validation/) |
| What problems has the engine solved, and how, step by step? | [Solved problem documents](problems/), one per validation case, with `index.md` as the list |
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
| Where do the team's FEA files, our models, and the homework files go? | [ADR-0036](decisions/ADR-0036-one-folder-per-fea-test.md) for FEA, [ADR-0032](decisions/ADR-0032-local-workspace-layout-by-tool-and-test.md) for homework, and the [workspace-layout skill](agents/skills/workspace-layout/SKILL.md) |
| All of the above as one typeset PDF | [Engine manual](manual/) |
| The complete argument for one finite element model comparison: model, theory, code, reference solver, every number and its error | [Model comparison documents](models/), one per record |
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
| [0030](decisions/ADR-0030-models-from-a-spec-calculix-as-reference-solver.md) | Coupon models are generated from a parametric spec; CalculiX is the independent reference solver, Abaqus (a teaching licence) an optional second one since ADR-0045 (proposed) |
| [0031](decisions/ADR-0031-one-generated-document-per-model-comparison.md) | Every model comparison gets its own generated LaTeX document, separate from the manual (proposed) |
| [0032](decisions/ADR-0032-local-workspace-layout-by-tool-and-test.md) | Local finite element files sit test by test under each tool with team, ours and comparison folders; homework assignments and the code that solves them share folder names (proposed) (FEA layout superseded by 0036) |
| [0033](decisions/ADR-0033-one-generated-document-per-solved-problem.md) | Every solved problem gets its own generated document; the manual keeps one summary table (proposed) |
| [0034](decisions/ADR-0034-micromechanics-models-stated-by-the-caller.md) | Lamina constants from fiber and matrix: rule of mixtures, series models, Halpin-Tsai and the square-array combination model, each named by the caller (proposed) |
| [0035](decisions/ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md) | Our models reproduce the team's node for node; each team test gets a short comparison document and a share folder (proposed) |
| [0036](decisions/ADR-0036-one-folder-per-fea-test.md) | One folder per finite element test: `fea/models/<test>/` and `fea/checks/` in the repository, `.local/fea/<test>/` locally; supersedes the FEA layout of 0032; the coupon models are local since ADR-0042 (proposed) |
| [0037](decisions/ADR-0037-every-private-file-under-local-by-purpose.md) | Every private file lives under `.local/`, in a folder named for its purpose; `References/` and `output/` folded in (proposed) |
| [0038](decisions/ADR-0038-coupon-identity-card-and-designation.md) | Every coupon model carries an identity card and a name of the form material-test-layup, such as X840PW-UNT-L1 (proposed) |
| [0039](decisions/ADR-0039-case-pages-attempt-history-and-one-index.md) | Case pages, attempt history and one index, inside the existing layout; result tables and indexes generated from the records (proposed) |
| [0040](decisions/ADR-0040-one-folder-per-problem-named-for-it.md) | One folder per problem, named for it, with everything inside: coupons as `fea/models/<coupon>/` and `.local/fea/<coupon>/{from-team, our-runs, comparison, documents}`, no share folder; since ADR-0042 the models sit in `.local/fea/<coupon>/` too; since amendment 3 in three parts, `team/`, `ours/`, `documents/` (proposed) |
| [0041](decisions/ADR-0041-one-document-per-coupon-in-chapters.md) | One document per coupon, in chapters (problem, physics, building the part in our engine and in Abaqus/CAE, results, verification), and one zip, replaced by a package folder in 0043; `docs/models/coupon.py` (proposed) |
| [0042](decisions/ADR-0042-course-keys-and-team-models-stay-off-the-repository.md) | The course's answer keys, the homework readings and our models of the team's coupons leave the repository and its history, in chunks with one rewrite at the end; the X840-Z60 material record stays (proposed) |
| [0043](decisions/ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md) | Every coupon delivery is audited against one fixed rubric (`docs/audit/rubric.toml`): a chapter in the PDF and an Excel form, sent as one package folder per delivery, which replaces the zip of 0041 (proposed; rubric 0.2 confirmed by the founder, amendment 1; one package layout, amendment 2; no findings sheet, a failed row names its cause, amendment 3; rubric 0.3, evidence as the claim to verify and our values where the team's are missing, amendment 4) |
| [0044](decisions/ADR-0044-audit-form-summary-rule-verdict-formula-and-numbers-as-values.md) | The audit form carries its own summary, the rule's verdict as a formula that follows the auditor's entries, and the numbers behind our rows as values on a Results sheet and a Compared values sheet; formulas only for what the auditor changes (proposed; form v0.3, the cover says what is audited and which files are compared, the build record on its own sheet, amendment 1) |
| [0045](decisions/ADR-0045-abaqus-without-the-gui-odbaccess-reports-and-an-optional-second-reference.md) | Abaqus results come from a script under `abaqus python` that writes CAE's field-report CSV, and a headless runner solves our decks; Abaqus is an optional second reference under the UCSD teaching licence, for the course and the team comparison only, CalculiX stays the reference (proposed; the rule for S12, amendment 1; every generated deck runs in Abaqus/Standard as written, amendment 2) |
| [0046](decisions/ADR-0046-coupon-intake-by-an-excel-input-form.md) | A coupon enters as an Excel input form the team fills in, read into the spec by a tool that names every problem by its row; the team's own constants are user-supplied and stay local (proposed) |
| [0047](decisions/ADR-0047-a-read-only-peer-review-subagent-for-generated-documents.md) | A read-only subagent, `document-reviewer`, peer-reviews each generated document before it is sent, today the coupon package PDF; defined in `docs/agents/subagents/` and linked into `.claude/agents/` like the skills (proposed) |

New decisions use the [template](decisions/_template.md).

## Material data documents

Latest checks: [.local by purpose](evaluations/2026-10-21-local-by-purpose.md), [model comparison documents](evaluations/fea/2026-10-18-model-comparison-documents.md), [CalculiX first comparison](evaluations/fea/2026-10-15-calculix-first-comparison.md), [models from a spec](evaluations/fea/2026-10-15-models-from-a-spec.md), [manual covers the finite element layer](evaluations/fea/2026-10-15-manual-covers-fea.md), [ply recovery and first-ply failure](evaluations/fea/2026-10-15-ply-recovery-failure.md), [membrane kernel](evaluations/fea/2026-10-15-membrane-kernel.md), [Abaqus deck reader](evaluations/fea/2026-10-15-deck-reader.md), [Hermes out, actor renamed](evaluations/api/2026-10-14-hermes-out.md), [calculator endpoints recorded](evaluations/api/2026-10-14-run-records-calculator.md), [run records written and read back](evaluations/api/2026-10-14-run-records-write.md), [run records table and startup policy](evaluations/api/2026-10-14-run-records-table.md), [run records database](evaluations/api/2026-10-14-run-records-database.md), [engine, 11 October](evaluations/2026-10-11-criteria-buckling-loader.md), [API case endpoint](evaluations/api/2026-10-11-case-endpoint.md), [engine inputs](evaluations/2026-10-03-input-validation.md), [website inputs and citations](evaluations/website/2026-10-03-input-validation.md) and [source rights](evaluations/website/2026-10-10-source-rights.md). Website-only evaluations live in their subdirectory so the generated engine manual selects engine evidence.

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
