# ADR-0138: A robot asks the question banks on the live site in a browser as a customer, grades each answer by fixed checks then a small model, and opens an issue only when one fails

- Status: Proposed
- Date: 2026-11-24
- Decided by: Founder, 2026-11-24 ("Is there a way to create an automatic agent that goes through the website and goes through quesitons to make sure the output we are getting is good?" and "let's do it let me know what you need", on the robot; "make sure it doesn't create any risks on data, impose any data leaks, no hacking leaks, needs to be safe", on its safety; "doesn't have to be every night i'd do 1$ a run but every 4 days", on how often and at what cost) | Drafted by: Claude Code
- Related: [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md), [ADR-0114](ADR-0114-ci-lints-the-python-runs-every-browser-spec-in-three-engines-and-on-a-phone-pins-its-actions-and-checks-the-site-after-each-deploy.md), [ADR-0120](ADR-0120-each-call-to-the-language-model-is-kept-as-a-row-with-who-asked-what-for-the-tokens-billed-and-their-cost-read-through-three-views.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0136](ADR-0136-a-repairs-chat-reads-one-change-into-the-engines-form-and-previews-it-on-a-copy-and-a-sweep-names-the-smallest-repair-whose-adhesive-stays-elastic-at-a-load-with-that-pick-solved-as-a-slice.md); `scripts/site-check/`, `scripts/site-check-judge.py`, `.github/workflows/site-check.yml`, `api/src/anisotropy_api/main.py` (`_cost_header`), `tests/site-check.test.ts`, `docs/agents/skills/chat-answer-quality/SKILL.md`
- Area: assistant, process, website, api, hosting

## Context

The assistant is held to 331 questions in 17 banks (`tests/assistant-questions/`, ADR-0121). Check 1 asks them free on every pull request, but of the page's functions and a harness that repeats how the components put an answer together, on fixtures. Check 2 asks the model's questions of the API's readers with real models, by hand before a feature merges. Neither uses the site a customer uses: a deployed page, its real setup screens, the API's own answers and what the chat finally shows. On 2026-11-17 four of ten answers the founder got on the hosted site were poor though every number was right (the `chat-answer-quality` skill), and nothing would have said so until he asked.

The site sits behind Cloudflare Access. The Deploy workflow's check already reaches it with a service token held in two repository secrets (ADR-0114); a service token carries no email, so the site shows it what a customer sees, with no founder features. The repository is public: a run's log, summary and artifacts can be read by anyone signed in to GitHub.

## Options considered

1. **Check 2 on a schedule.** It asks the API's readers, not the page: it never sees the setup screen, the page's own answers, a sweep's final words or the time an answer takes. Rejected.
2. **An agent with a browser that explores and judges freely.** It finds what nobody wrote a question for, but each run differs, its verdicts cannot be held to a bank, and it costs far more per run. Kept for later as the source of new questions (see Consequences), not as the check.
3. **A robot that asks the banks' questions on the live site in a real browser, grades by fixed checks first and a small model second, and tells the founder only when an answer fails.** Repeatable, cheap, and graded against the same criteria and expectations as checks 1 and 2. Chosen.

## Decision

A robot (`scripts/site-check/run.ts`, Playwright) opens anisotropy.dev as a customer, through Access with the deploy check's service token, and brings each page a bank names to its state by the page's own buttons with the public example coupon IM7/8552 [45/0/-45/90]s (ADR-0042): the FEA start, a blank coupon, one given its material and layup on the customer's setup screen, one checked, one solved, a past analysis opened, the example wing with and without spar caps, and the example repair worked by hand, solved, and bonded on top. It types each question into the chat and reads the answer as shown: its heading, its text, what is folded under Details (a table read cell by cell), and the first answer when the page then works and replaces it (a sweep, a solve). A plate and an imported model are set up on a founder's sign-in only and are left out with the reason.

Each answer is graded in two layers (`grade.ts`):

1. **Fixed checks, no model.** An answer appeared, and no outage sentence; the time from Enter (aim 5 s and at most 20 s for the page's own answer, 20 s and 60 s when a model read it); no tool, vendor or model name (`lib/studio-copy.ts`); a heading of 60 characters at most; a question never offers to change the model; every number traces to one the API sent the page, one the page prints outside the chat or one in the question, to its printed digits, in SI or the US units the page converts to (`numbers.ts`): a number that does not is weak in the page's answer and fails in words a model wrote (ADR-0052, ADR-0102); the bank's expected words where the page answers itself, as in check 1, with numbers left out because they are of another coupon; a page that opens another must open the one the bank names; a repair's answer never calls the repair strong enough, safe, a margin or restored unless it says it is not (ADR-0136); the same question back twice fails (criterion 11); a script error on the page fails.
2. **The judge.** Only the answers that pass every fixed check go to the small model (`claude-haiku-5-5`) with the eleven criteria of the skill and what the bank says a good answer holds, with the judge and instructions of check 2 (`scripts/assistant_live_common.py`). A grade is kept under the exact request, so an answer shown word for word as before costs nothing.

Where a page's state on the live site differs from the bank's example of it by design (the customer's setup screen previews first-ply failure and takes the geometry from the standard; spar caps added by their button have no ply drop), a mismatch with the bank's words is weak and the judge is told the difference. Where a yes-or-no question quotes numbers of the bank's example that this result does not hold, the bank's "Yes" is not held, and the judge grades the answer on its own numbers.

**When, and at what cost.** After each deploy of main that succeeded, a quick run asks only the questions the page answers itself: nothing is spent on the site, and the judge costs cents, nothing for answers graded before. Every four days a full run asks every question, the model's too, for at most $1 a run and $20 a month, the site's model and the judge together. The site's spend is read from a new response header, `X-Anisotropy-Model-Cost`, which the API adds only to a request with no signed-in email (ADR-0120's priced calls); a run stops asking the model's questions before its cap, keeps a share for the judge, and asks the ones it left first next time. The month's spend and the time each question was last asked are kept between runs in the workflow's cache.

**Telling the founder.** A run that finds an answer that fails, other than a known gap the bank marks, or a page it could not set up, opens one GitHub issue labelled `site-check` and assigned to the repository's owner, or comments on the one open; the first run that asks those questions again and finds them holding closes it. A run that passes says nothing. The issue names the questions and why they failed, and links the run; the report on the run's page has the counts, the spend, every answer that did not hold and a picture of its chat. `results.json` (`anisotropy-site-check/1`) is written for the founders' QA page to read later.

**Safety** (the founder's words above). The token's two headers go on the site's own requests only, never to the file bucket or anywhere else. The browser records no trace, video, network log or storage, which would hold the token or the Access cookie. The API's answers are read for their numbers in memory and never written. Every text written is scrubbed of the run's secrets, email addresses, signed links and tokens (`scrub.ts`). The robot's requests carry the actor `test`, as the deploy check's do, so its runs and model calls are told from people's. The workflow never runs on a pull request; its actions are pinned to commits; the job that holds the token cannot write to the repository, and the job that writes the issue and holds the judge's key never sees the token. No text from a page or a bank enters a shell line.

## As built (2026-11-24)

- `api/src/anisotropy_api/main.py`: `_cost_header` adds `X-Anisotropy-Model-Cost: <dollars>; calls=<n>; unpriced=<n>` to an answer that called the model for a request with no email; `api/tests/test_model_costs.py` holds it to a service token's request and keeps it off a signed-in person's.
- `scripts/site-check/`: `run.ts` (the robot), `pages.ts` (each page's setup), `chat.ts` (asking and reading), `plan.ts` (what a quick or full run asks, rotated under the cap), `numbers.ts`, `grade.ts`, `budget.ts`, `scrub.ts`, `record.ts`, `report.ts`, `issue.ts`; `scripts/site-check-judge.py`; the judge's request moved into `scripts/assistant_live_common.py` unchanged, so check 2's stored grades still match.
- `.github/workflows/site-check.yml`: after Deploy on main, a schedule every four days (`23 15 */4 * *`), and by hand with the mode, the banks and the cap.
- `tests/site-check.test.ts`: 16 tests of the reading of numbers, the fixed checks, the plan, the cap, the scrubbing and the report.
- A grade no run has used for 45 days is dropped from the store.

## Why (evidence)

- The robot run on a local copy of the site (the API and the built site on this machine, 2026-11-24) asked 87 questions of six banks on seven page states with every page set up. Before the fixes in this record it raised seven false alarms, each traced to a cause: a fold's table read as one string ran its numbers together ("74", "12.85", "233.5" read as 7412.85233), a sweep's and a solve's first answer were replaced by their result, a yes-or-no question quoted the bank example's 16,220 N where this coupon gives 16,210 N, the customer's setup screen and spar caps differ from the bank's examples, and a question asked before the setup's preview arrived was answered otherwise than one asked after it (the robot now waits for the page to settle). The first four have tests in `tests/site-check.test.ts`.
- The same run found what checks 1 and 2 cannot see, each confirmed by the picture of the chat: on the customer's setup screen, with "Everything is stated" and the geometry "from the standard", "how wide is it?" is answered "No width yet" (criteria 2 and 9); after "solve the slice" on the repair, the answer's heading is 69 characters (criterion 8); once a sweep with no quantity named is worked, the answer no longer says that the step length was taken for it and how to sweep another (criterion 2). These are reported, not fixed, here.
- `npx tsx --test tests/site-check.test.ts`: 16 passed. `cd api && uv run pytest tests/test_model_costs.py`: 12 passed, 5 skipped.
- The cost of a full run on the hosted site is not measured yet: no run has reached anisotropy.dev, since the token is a repository secret that only the workflow holds. UNVERIFIED until the first run; the cap holds it to $1 whatever the measure.

## Consequences

- An answer that goes wrong on the live site is found within a deploy for the page's own answers and within four days for the model's, without anyone asking.
- The banks now serve three checks. A question whose expected words hold only for the bank's fixture shows up as a mismatch on the live site; the fix is in the bank or in `LIVE_DIFFERS`, never in loosening the check.
- A number that traces by coincidence to some value of thousands the result's field holds passes the number check: it catches numbers that come from nowhere, not every wrong one. The judge is told not to grade numbers.
- Each run solves one coupon through the queue, under the actor `test`, and counts against the daily cap of jobs with no email, as the deploy check does.
- Invented questions (an agent that writes new questions each full run and proposes the ones that fail for the banks, by pull request) are left for a later amendment.

## How we will know it was wrong

- More than one issue in a month that the founder closes as a false alarm: the fixed checks or the judge are too strict, and the record is amended.
- An answer the founder finds poor on the live site that a full run asked within the four days before and passed.
- A month whose spend passes $20, or a run that passes $1.
- Any secret, email address or signed link found in a run's log, summary, artifact or issue: the run's output is taken down and the robot stops until it is fixed.
