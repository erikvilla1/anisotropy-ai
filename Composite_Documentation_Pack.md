# Documentation Pack for an AI Engineering Startup

**Purpose:** give the founder visibility into what the engineer builds, why, whether it works, what changed, and what broke, without making documentation a burden.

> **Note on examples.** All filled-in examples below are **illustrative placeholders** written to show the format. They are not real decisions from your project. Replace them with your engineer's actual content.

---

## Part 1. The management logic

You are not trying to read the engineer's mind. You are trying to answer five questions at any time:

| # | Founder question | Document that answers it |
|---|---|---|
| 1 | What exactly have we built? | System Overview + Component Cards |
| 2 | Why was it built this way? | Decision Log (ADRs) |
| 3 | Does it work, and how do we know? | Verification and Evaluation Reports |
| 4 | What changed, and when? | Changelog + Provenance Log |
| 5 | What could go wrong, and who owns it? | Risk Register + Weekly Brief |

**Three design rules**

1. **Docs live in the code repository** (a `/docs` folder in GitHub/GitLab), as plain text files. They are versioned, dated, and attributed automatically.
2. **Record decisions and evidence, not "AI thinking."** An LLM's written explanation of its own reasoning can be plausible yet misleading (Turpin et al., 2023). So the record that matters is: what was decided, which alternatives were rejected, what test or source supports it, and what the result was. Tests and logs are the proof; narrative is the summary.
3. **Automate the drafting, keep humans on approval.** The AI coder drafts; the engineer reviews and merges; you read the summaries.

**Suggested repo layout**

```
/docs
  00_system_overview.md
  /decisions        (ADR-0001-....md, one file per decision)
  /components       (one card per component)
  /evaluations      (one report per release or major test)
  /risks            (risk_register.md)
  /weekly           (2026-10-09_brief.md ...)
CHANGELOG.md
/provenance         (auto-generated JSON run records)
AGENTS.md           (instructions to the AI coder; see Part 3)
```

---

## Part 2. The documents, with examples

### Document 1: System Overview (one page, you own it)

```markdown
# System Overview  | version 0.1 | last reviewed: 2026-10-02 | owner: Founder

## Key principle
The LLM never writes the final answer directly. Deterministic code computes; the LLM orchestrates and explains.

## Layers
| Layer | What it does | Deterministic? | Component card |
|---|---|---|---|
| Solver | Laminate analysis, FEA, unit handling | Yes | components/solver.md |
| Retrieval | Pulls only from the curated source library | Yes (index), No (ranking) | components/retrieval.md |
| Solution object | JSON: assumptions, inputs + source IDs, steps, results, checks, uncertainty | Yes | components/solution_object.md |
| Renderer | Fills LaTeX templates from the JSON; LLM writes prose into slots only | Mostly | components/renderer.md |
| Verification gate | Unit checks, limiting cases, second method, citation resolution | Yes | components/verification.md |
| Provenance log | Model, tool, data versions per run | Yes | components/provenance.md |

## External dependencies
- LLM API provider(s) and model version(s): [fill in]
- Source library location and owner: [fill in]
- Accounts and who holds credentials: [fill in]

## Known limitations (plain language)
- [e.g., Paywalled standards are not yet in the library, so answers cannot cite them.]
```

### Document 2: Decision Log, using ADRs (Architecture Decision Records)

ADRs are short text files that capture a decision with its context and consequences. The format was proposed by Michael Nygard and has since been widely adopted. Typical fields are title, context, decision, and consequences; superseded decisions are marked as superseded rather than deleted (UK Government Digital Service, "Documenting architecture decisions"). Mozilla's *bedrock* project is one team that records major architectural decisions this way.

**Template**

```markdown
# ADR-XXXX: [Decision, stated as a choice, not a problem]
- Status: Proposed | Accepted | Superseded by ADR-YYYY | Deprecated
- Date: YYYY-MM-DD
- Decided by: [engineer] | Reviewed by: [founder]
- Related: [PR link, test report, source IDs]

## Context
What situation forced a decision? Facts only.

## Options considered
1. Option A: pros / cons
2. Option B: pros / cons

## Decision
What we chose.

## Why (evidence)
Test results, source IDs, benchmarks, cost figures.

## Consequences
What becomes easier. What becomes harder. What we now depend on.

## How we will know it was wrong
A measurable trigger to revisit.
```

**Worked example (illustrative)**

```markdown
# ADR-0003: Run laminate analysis in deterministic code; the LLM never does arithmetic
- Status: Accepted
- Date: 2026-10-05
- Decided by: Engineer | Reviewed by: Founder
- Related: PR #14, evaluations/2026-10-05_laminate_check.md

## Context
In a 40-case test, the LLM returned plausible but wrong ABD-matrix values in 6 cases.

## Options considered
1. LLM computes directly. Fast to build; unacceptable error rate.
2. LLM writes code on the fly. Flexible; unreviewed code runs in production.
3. Fixed, unit-tested solver module; LLM only calls it. Slower to extend; reproducible.

## Decision
Option 3.

## Why (evidence)
Solver matches hand-calculated reference cases within 0.1%. See evaluation file.

## Consequences
New analysis types require writing and testing a solver function first.

## How we will know it was wrong
If more than 30% of user requests need an analysis the solver does not support.
```

### Document 3: Component Card (adapted from "model cards")

Model cards are short documents that accompany a trained model and disclose intended use, evaluation procedures, and performance across conditions (Mitchell et al., 2019). They complement "Datasheets for Datasets," which document the data feeding a model. Your system is a pipeline rather than one trained model, so use the same idea per component.

```markdown
# Component Card: Retrieval Layer | version 0.2 | updated 2026-10-12

## Purpose and intended use
Return citable passages from the curated library to support a solution.

## Out of scope / do not use for
Answering from sources not in the library; legal or certification claims.

## Inputs / outputs
In: query + filters. Out: passages with source ID, page, and metadata.

## Dependencies and versions
Embedding model: [name, version]. Index build date: [date]. Library version: [tag].

## Evaluation
Test set: 50 questions with known source passages. Recall@5: [x]. Report: evaluations/....

## Known limitations
No access to paywalled standards. Weak on tabular data in scanned PDFs.

## Failure modes seen
[date] Retrieved an outdated edition of a handbook; fixed by edition metadata (ADR-0006).

## Owner and contact
[engineer]
```

### Document 4: Changelog (what changed, for humans)

```markdown
# Changelog

## [0.3.0] - 2026-10-19
### Added
- Citation-resolution check in the verification gate.
### Changed
- Retrieval now filters by standard edition (ADR-0006).
### Fixed
- Unit conversion error in ply thickness (psi vs MPa) found by limiting-case test.
### Known issues
- Renderer retries LaTeX compilation up to 3 times; some figures still fail.
```

### Document 5: Evaluation / Verification Report

```markdown
# Evaluation Report 2026-10-05: Laminate solver vs reference cases
- Release tested: 0.2.1 (commit abc1234)
- Test set: 40 cases (source: textbook examples + own coupon data, data version v3)
- Method: solver output vs reference values, tolerance 1%

| Metric | Result | Threshold | Pass? |
|---|---|---|---|
| Cases within tolerance | 40/40 | 100% | Yes |
| Unit-check failures | 0 | 0 | Yes |
| Independent second method agreement | 38/40 | 95% | Yes |

## Failures and what we did
2 cases disagreed with the second method; traced to a sign convention (ADR-0004).

## Decision
Approved for internal use. Not approved for external users until citation check ships.
```

### Document 6: Provenance record (automatic, machine-written)

```json
{
  "run_id": "2026-10-05T14:22:10Z-0042",
  "llm_provider": "[provider]", "llm_model_version": "[exact version string]",
  "solver_version": "0.2.1", "retrieval_index_version": "lib-2026-10-01",
  "data_version": "coupons-v3",
  "git_commit": "abc1234",
  "verification": {"unit_check": "pass", "limiting_cases": "pass",
                   "second_method": "pass", "citations_resolved": "pass"},
  "output_files": ["answer.pdf", "answer.tex", "solution.json"]
}
```

This is what lets you trace a customer complaint back to an exact model, code, and data version.

### Document 7: Risk Register (adapted from NIST AI RMF)

The NIST AI Risk Management Framework organizes AI risk work into four functions: Govern, Map, Measure, and Manage (NIST, AI RMF 1.0, January 2023). It is voluntary, but government customers and partners often know it, so aligning early helps credibility. A lightweight register is a good first step.

| ID | Risk | NIST function | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| R-01 | LLM fabricates a reference | Measure | Med | High | Citations only from retrieved metadata; resolution check | Engineer | Mitigated |
| R-02 | Single LLM vendor change breaks outputs | Manage | Med | High | Pin model version; regression suite before upgrades | Engineer | Open |
| R-03 | Founder cannot reproduce a result | Govern | High | Med | Provenance log on every run | Both | Open |
| R-04 | Proprietary test data leaks into prompts | Manage | Low | High | Data-handling rule; no raw data to external APIs without approval | Founder | Open |

### Document 8: Weekly Founder Brief (15 minutes, the heart of your oversight)

```markdown
# Weekly Brief 2026-10-09 | prepared by: Engineer (AI-drafted) | read by: Founder

1. Shipped this week (3 bullets, plain language)
2. Decisions made (links to ADRs, one-line each)
3. Evidence: tests run, pass/fail, link to report
4. What broke or surprised us
5. Risks changed (links to register)
6. Next week plan and anything needing a founder decision
7. Spend: API cost this week vs. budget
```

---

## Part 3. Making it automatic

**A. Instruction file for the AI coder** (many AI coding assistants read a project instruction file such as `AGENTS.md` or `CLAUDE.md`; check your tool's convention).

```markdown
# Documentation rules for AI assistants working in this repository

When you make or propose any change, you must also:

1. If the change involves a choice between alternatives (library, model, algorithm,
   data format, architecture), draft an ADR in /docs/decisions using the template.
   Include options rejected and the evidence. Do not invent evidence: link real
   test output or sources, or write "no evidence yet".
2. Update CHANGELOG.md under "Unreleased".
3. If a component's behavior, inputs, outputs, or dependencies changed, update its card.
4. Record test results in /docs/evaluations. Never claim a test passed without output.
5. Mark anything uncertain as "UNVERIFIED".
6. Do not paraphrase your own reasoning as fact. State what was decided and what
   supports it.
Keep entries short. Prefer bullet points. A human will review before merge.
```

**B. Pull request template** (`.github/pull_request_template.md`)

```markdown
## What changed (plain language)
## Why
## Decision record: ADR link or "none needed"
## Tests run and results
## Changelog updated? [ ] Component card updated? [ ] Risks changed? [ ]
```

**C. Automatic checks (CI)**: a small script that fails a merge if CHANGELOG.md was not touched, or if a PR labeled "architecture" has no linked ADR.

**D. Provenance logging**: the pipeline writes the JSON record in Document 6 on every run, with no human effort.

**E. Weekly brief**: ask the AI coder to draft it from the week's merged PRs, ADRs, and test logs; the engineer edits for five minutes.

---

## Part 4. Your management cadence

| When | What | Time |
|---|---|---|
| Weekly | Read the brief; approve or question decisions | 15 min |
| Per decision | Review ADRs marked "Proposed" that affect cost, customers, or data | 5 to 10 min each |
| Monthly | Review risk register and evaluation trends | 45 min |
| Per release | Confirm evaluation report exists and thresholds passed | 15 min |
| Quarterly | Audit: pick one customer-style output and trace it back through provenance, ADRs, and tests | 1 hr |

**The audit test.** If you can pick any output and trace it to the exact code, model, data, and decision behind it in under 30 minutes, your documentation system works.

---

## Sources

- Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., Gebru, T. (2019). *Model Cards for Model Reporting.* FAT* '19. https://arxiv.org/abs/1810.03993
- Nygard, M. (2011). *Documenting Architecture Decisions.* Summarized and recommended in: UK Government Digital Service, "Documenting architecture decisions," https://gds-way.digital.cabinet-office.gov.uk/standards/architecture-decisions.html
- Mozilla *bedrock* architectural decision records: https://dokk.org/documentation/mozilla-bedrock/2021-12-22/architectural-decisions/
- NIST (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0),* NIST AI 100-1. https://www.nist.gov/news-events/news/2023/01/nist-risk-management-framework-aims-improve-trustworthiness-artificial
- Turpin, M., Michael, J., Perez, E., Bowman, S. R. (2023). *Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting.* https://arxiv.org/abs/2305.04388
- Gebru, T. et al., *Datasheets for Datasets* (referenced as a companion to model cards in Mitchell et al., 2019; not independently retrieved here).
