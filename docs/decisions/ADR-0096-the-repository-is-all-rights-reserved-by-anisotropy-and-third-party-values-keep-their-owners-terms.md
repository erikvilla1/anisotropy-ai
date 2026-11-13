# ADR-0096: The repository is all rights reserved by Anisotropy, and third-party values keep their owners' terms

- Status: Proposed
- Date: 2026-11-13
- Decided by: Founder, 2026-11-12 ("accept", on the audit's recommendation "State all rights reserved now, with a NOTICE that third-party values keep their owners' terms; revisit a source-available licence later") | Drafted by: Claude Code
- Related: [ADR-0018](ADR-0018-source-rights-classes.md) (source rights classes), [ADR-0010](ADR-0010-public-citations-local-page-evidence.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), [ADR-0081](ADR-0081-the-site-shows-uc-san-diegos-the-basement-mark-for-the-launchpad-cohort-the-team-is-part-of.md) (The Basement mark), `LICENSE`, `NOTICE`, `package.json`, `lib/source-rights.ts`, `README.md`

## Context

The repository is public (the About page says so, `app/about/page.tsx`). Until this record it had no `LICENSE`; `package.json`, `engine/pyproject.toml`, `fea/pyproject.toml` and `api/pyproject.toml` named no licence, and the README had no licence section (audit finding repository-8, 2026-11-12). A reader could not tell what they may do with the code, or which material in it belongs to others: every cited source carries a rights class (ADR-0018, `lib/source-rights.ts`), public domain (MIL-HDBK-17-2F), open publisher (NCAMP and NASA reports, manufacturer datasheets) or licensed reference (a textbook, CMH-17, ASTM test standards, cited value by value).

## Options considered

1. All rights reserved, stated in `LICENSE`, with a `NOTICE` that third-party material keeps its owners' terms. Nothing is granted beyond reading; every later choice stays open. Chosen.
2. A source-available licence such as BUSL-1.1 or PolyForm Noncommercial. It would let others use the code on stated terms, but needs terms the company has not chosen (which use is allowed, a change date). Deferred, not rejected: the founder's answer revisits it later.
3. An open-source licence, permissive or copyleft, such as Apache-2.0 or AGPL-3.0. It grants reuse, commercial reuse included, and cannot be withdrawn from a version once published. Rejected for now.

## Decision

Option 1. `LICENSE` states "Copyright (c) 2026 Anisotropy. All rights reserved.", names the site's company as the site's footer does, grants no right beyond the licence GitHub's Terms of Service (section D.5) give each GitHub user for a public repository (to use, display and perform it through GitHub and to reproduce it on GitHub, for example by forking), and points to `NOTICE`. `NOTICE` says that third-party values, requirements and references keep their owners' terms and are outside `LICENSE`, names the three rights classes the library uses with what each allows, and names the marks and media of others the site serves (The Basement mark of UC San Diego, ADR-0081). `package.json` says `"license": "UNLICENSED"`. The README links both files.

## As built (2026-11-13)

`LICENSE`, `NOTICE`, the `license` field in `package.json` and in the root entry of `package-lock.json`, and the README's opening section. The pyproject files of `engine/`, `fea/` and `api/` still carry no licence field: whether their build backend accepts a non-SPDX value is UNVERIFIED, and their packages are not published.

## Why (evidence)

- The founder's answer to decision D32 of the 2026-11-12 audit: "accept" (the decision list sits with the audit's working files, outside the repository).
- npm documents `"license": "UNLICENSED"` for a package whose owner grants no right to use it: https://docs.npmjs.com/cli/v11/configuring-npm/package-json#license
- GitHub's Terms of Service, section D.5, "License Grant to Other Users": making a repository public grants each GitHub user a licence to use, display and perform it through GitHub and to reproduce it on GitHub, for example by forking: https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#5-license-grant-to-other-users
- The rights classes and their sources: `lib/source-rights.ts`, `lib/curated-materials.ts`, `lib/qualification-references.json`.
- Whether option 2 would serve the company better: no evidence yet.
- Legal review of the LICENSE and NOTICE wording: no evidence yet.

## Consequences

Easier: the repository says who owns it and what is someone else's; a licence for later versions can still be chosen freely. Harder: an outside engineer may read the code but not reuse it, and an outside contribution needs a written agreement first. A new rights class, or a new kind of third-party material, needs a line in `NOTICE`.

## How we will know it was wrong

When a partner, customer or contributor asks to use or extend the code and the answer would be yes, revisit with option 2 or 3. Also when the company's legal name or form changes, so the copyright line names the right owner.
