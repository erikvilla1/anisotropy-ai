# ADR-0027: Regulated customers run the whole stack inside their own boundary, and the assistant's model is a per-deployment setting that is off until configured

- Status: Proposed; order of work extended by [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md): one command per job and an API job come before the assistant, machine learning after it; item 2 of its order of work, the assistant's record, is [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md)
- Date: 2026-10-14
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0011 (API has no authentication), ADR-0018 (user-supplied rights class), ADR-0020 (one bundled material file), ADR-0025 (hosting deferred), ADR-0026 (run records), ADR-0028 (founder-only tooling), [system overview](../00_system_overview.md), risk R-14

## Context

The founder asked how the software can be sold to a company that tests coupons in its own laboratory and will not let its data leave (a defense prime was the example). Such data may be export controlled under ITAR. Facts about the stack today:

- The engine is a plain Python package with no network calls; the API is FastAPI; run records are standard PostgreSQL reached by one `DATABASE_URL`; the website is a static export that calls the API (ADR-0011, ADR-0012, ADR-0025).
- The API has no authentication, and the actor header is a short checked list, not an identity (ADR-0011, ADR-0026).
- The engine reads one bundled material file exported from the public library; a customer's own allowables can only be typed as raw constants per case, with no provenance (ADR-0020).
- ADR-0018 defines a "user supplied" rights class whose policy is "nothing public, private workspace only", but no private workspace exists.
- The language-model assistant is planned and would send a drafted case to a model provider (system overview). No provider is chosen.
- Legal review of the rights classes has not happened (ADR-0018); none has happened for export control either.

## Options considered

Where the product runs for a customer:

1. **Multi-tenant hosted service run by us.** One deployment, simplest to operate. Every customer's inputs and run records sit in our database; we become a recipient of any controlled data, and the customer's security review must approve our hosting. Unsuitable for export-controlled work.
2. **Single-tenant hosted, one isolated cloud account per customer, in their region, under a data-processing agreement.** Keeps tenants apart; we still operate the machines and hold the data.
3. **Self-hosted: versioned container images for the API, the database and the static site, run by the customer on their premises or in their own cloud account, with an offline license.** We never receive the data. Costs packaging, offline installation and an upgrade path; support is harder without access.

Where the assistant's model runs, when a deployment turns the assistant on:

1. **Our account at a public model endpoint.** Simplest. The customer's case text passes through a vendor account they do not control.
2. **A frontier model inside the customer's own cloud boundary**, for example Claude on Amazon Bedrock in AWS GovCloud under the customer's account.
3. **An open-weight model served on the customer's own hardware** (vLLM, Ollama or similar). Nothing leaves the network; smaller models draft cases less reliably.
4. **No assistant.** The engine, the cited library, run records and reports are complete without it; the assistant only drafts inputs and explains results (ADR-0001).

## Decision

Option 3, self-hosted, is the deployment for regulated and secretive customers and is built first. Option 1 remains the plan for the public tier: students, professors and research groups, small shops, anyone working with public data. In that tier the assistant is a main feature, not an extra, because its users are learning the method or exploring problems rather than running a qualified test program. Option 2 is not pursued until a customer asks for it.

The assistant is off unless a deployment names a model endpoint in its configuration; starting with the assistant requested and no endpoint named is refused with the variable named (ADR-0003). Self-hosted builds ship with it off. Which of model options 2 and 3 a customer uses is their choice and is recorded per deployment; option 1 is allowed only in the public tier.

The product makes no outbound network connection except to its own database and, when configured, the named model endpoint. Customer data is never used for shared training; the "by default" qualifier in the system overview is removed.

Order of work (founder, 2026-10-14): the assistant comes before the self-hosted plumbing, because the assistant is the one component that sends data outside the deployment, and its shape must be right from the first line. (1) Hermes removal (ADR-0028). (2) The assistant's own decision record: one provider interface behind one setting, the guard that keeps the model from producing result numbers, what the model may see, evaluation against the validation cases. That record must require the interface and a test that a full solve makes no outbound request when the setting is empty; neither is optional. (3) The assistant, built for the public tier against that interface, so the self-hosted variant is a setting. (4) Customer material datasets loaded from a file outside the repository with the same provenance and rights handling as the public library, and authentication with per-user attribution in run records, when the first proprietary customer is in sight. (5) Container images, a software bill of materials and an offline install, when that customer is ready to deploy.

Amended the same day (founder, 2026-10-14): the finite element phase (ADR-0029) comes before the assistant. Items 2 to 5 keep their order after it; the assistant's requirements above are unchanged.

Amended 2026-10-15 (founder, review of this record): the self-hosted tier is delivered as a forward-deployed engagement, not a self-service download. Our engineers deploy the stack inside the customer's ecosystem, configure it against their data and test program, validate it against their coupons, and support it there. The packaging work (item 5) serves that engagement: images and an offline install that our engineer brings in, not a product the customer installs alone. Consequences: the first regulated customers need our time inside their network; contract and licensing terms for such engagements: no evidence yet.

## Why (evidence)

- The components are already separable: the API depends only on `DATABASE_URL` (ADR-0025, "any host works with a changed `DATABASE_URL`"), and the website needs only a configured API address (ADR-0012).
- No authentication in the API: ADR-0011 consequences.
- Claude models are offered on Amazon Bedrock inside AWS GovCloud (US) regions: [AWS announcement, 2026-07-23](https://aws.amazon.com/about-aws/whats-new/2026/07/claude-sonnet-5-govcloud/); [Amazon Bedrock in AWS GovCloud (US) user guide](https://docs.aws.amazon.com/govcloud-us/latest/UserGuide/govcloud-bedrock.html). Which model versions and which compliance authorizations apply at purchase time: UNVERIFIED, check at that time.
- Whether a given deployment satisfies ITAR or a customer's security policy: no evidence yet. Export-control counsel has not reviewed any of this; the design goal is that we never receive controlled data, and counsel confirms whether that is sufficient.
- Customer demand for any tier, and the reliability of an open-weight model at drafting cases: no evidence yet. The validation cases are the planned test (system overview).

## Consequences

Easier: a strict customer can be sold to without us holding their data, and the assistant is never an accidental leak because it does not run until a provider is chosen. Harder: releases must be packaged and installable offline; support happens without access to the customer's machine; a second material load path and authentication are needed before the first sale. The public tier and the self-hosted tier share one codebase, so features that only make sense in one must be configuration, not forks.

## How we will know it was wrong

Revisit if a customer's security review rejects self-hosting and asks us to host instead; if the two tiers need different code rather than different configuration; if counsel finds that shipping software to a customer who processes controlled data with it still makes us a recipient; or if the assistant off by default turns out to be the reason a regulated customer does not buy.
