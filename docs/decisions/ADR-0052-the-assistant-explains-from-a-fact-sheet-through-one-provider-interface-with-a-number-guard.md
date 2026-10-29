# ADR-0052: The assistant explains a setup and a result from the engine's fact sheet through one provider interface: a template writer always on, Claude when a provider is named in the settings, and a number guard that withholds any draft whose numbers are not the engine's

- Status: Proposed
- Date: 2026-10-28
- Decided by: Founder, 2026-10-28 (on the four choices asked for the studio: "Deterministic checklist + template prose now, Claude provider behind a setting", the recommended option: the checklist and the explanation computed by the fea package, a provider interface with a template writer always on and an Anthropic Claude writer when `ANISOTROPY_ASSISTANT_*` is set, and a number guard that withholds model prose whose numbers are not in the fact sheet) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0027](ADR-0027-deployment-tiers-and-assistant-model-location.md) (item 2 of its order of work: this record), [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md) (step 3), [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), `api/src/anisotropy_api/assistant.py`, `api/src/anisotropy_api/settings.py`, `api/tests/test_assistant.py`, `fea/src/anisotropy_fea/explain.py`, risks R-10 and R-11

## Context

- ADR-0001: a language model may help draft inputs and explain results, never produce a number in a result. ADR-0027 item 2 asks for the assistant's own record covering one provider interface behind one setting, the guard that keeps the model from producing result numbers, what the model may see, evaluation against the validation cases, and a test that a full solve makes no outbound request when the setting is empty. ADR-0048 puts the assistant third, after one command per job and the job through the API, both built.
- The fea package now writes, beside every solve, a fact sheet of the solve's numbers and the template's sentences from it (`explain.py`, ADR-0051), and before every run a checklist of the setup (`checks.py`). The studio shows both.
- The founder's deployment model: the public tier may use our own model endpoint; a self-hosted customer names Claude on Bedrock in their own account or an open-weight model on their hardware; self-hosted builds ship with the assistant off (ADR-0027).
- The founder's machine holds no Anthropic credential today (checked 2026-10-28: no `ANTHROPIC_API_KEY`, no `ant` profile).

## Options considered

What the assistant explains from:
1. **The fact sheet and the template's sentences the fea package wrote.** Every number the model may use is already computed and printed; the model rephrases. Chosen.
2. **The whole package (the fields, the record, the PDF).** The model would read numbers the engine did not summarise and could combine them: a number nobody computed.
3. **The model drafting the inputs too.** ADR-0048's later tools; not in this phase.

How a draft is kept honest:
1. **A number guard: every number token in the draft must equal a fact at the precision it was written, else the whole draft is withheld and the template's sentences stand, with the offending tokens named.** Mechanical and testable; it allows a fact rounded to fewer digits and refuses a percentage, a margin or a ratio the sheet does not hold. Chosen.
2. **A prompt alone.** No proof the model obeyed.
3. **Structured output of numbers by reference (the model names the fact, the page fills the number).** Cleaner in principle; the prose then reads as a form, and the template already does that.

Where the model is called:
1. **In the API, by `POST /v1/coupon-jobs/{id}/explain`, behind the settings, with the run record naming the writer.** The browser never holds a credential; every explanation has its receipt. Chosen.
2. **In the browser.** A credential in the page.
3. **In the fea tool.** The tool would reach out while a job runs; the job's receipt would hide it.

Which writer when the assistant is off:
1. **The template, always on.** A self-hosted customer with the assistant off gets the same words the fea package wrote. Chosen.
2. **No explanation without a model.** Rejected: ADR-0027 ships self-hosted builds with the assistant off.

## Decision

- **Settings.** `ANISOTROPY_ASSISTANT_PROVIDER` names the provider (today `anthropic`); unset, the assistant is off. Named, `ANISOTROPY_ASSISTANT_MODEL` and one of `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` must be set, each refusal naming the variable (ADR-0003). The model is named by the deployment, never defaulted.
- **One interface.** `Assistant.explain_setup(checklist, template)` and `Assistant.explain_result(facts, template)` return a `Draft`: the sentences, the writer (`template` or the provider), the model, and when the model's draft was set aside, whether the guard withheld it and why. `TemplateAssistant` returns the fea package's sentences. `ClaudeAssistant` calls the Anthropic SDK (`client.beta.messages.create`, the model named in the settings, effort low, `fallbacks: "default"` so a declined request is re-run on Anthropic's recommended substitute, no sampling parameters), handles a refusal, a rate limit, a credential or a connection failure by returning the template's sentences with the reason, and passes its text through the guard.
- **The guard.** Every number in the draft (a number on its own, not the digits of a name such as `Coupon-1.1068`) must equal a number in the fact sheet, lists included, within half the unit of its last written digit: `16211` and `1.62e+04` stand for the reaction 16211.2, `16212` and a computed `10.4 %` do not. A draft that fails is withheld whole.
- **What the model sees.** The fact sheet as the fea package wrote it (numbers, the designation, the test, the criteria's words) and the template's sentences; for a setup, the checklist's items with the material's source cut to its kind, so a source the team named stays with the coupon (R-11). Never a file, a deck, a mesh or the team's constants.
- **The record.** Each explanation is one run record: the job, the kind and the digest of the facts seen as inputs, the answer as the response, and `llm_provider` and `llm_model_version` filled when a model's draft stands (the columns of ADR-0026, empty until now).
- **The studio** asks the endpoint once a job's explanation exists and shows the prose with who wrote it; a withheld draft shows its reason and the template's words.
- **No outbound request with the assistant off:** the SDK is imported only when a Claude writer is built, and a test runs a whole job and its explanation with every non-loopback connection refused.

## As built (2026-10-28)

`api/src/anisotropy_api/assistant.py`, the settings and the endpoint in `main.py`, `record_run`'s two new parameters, `ExplainRequest`, `ExplainReceipt` and `ExplainResponse`, `.env.example`'s three lines, the `anthropic` dependency (1.17.0), the studio's call in `components/studio/results-view.tsx` and `lib/studio-api.ts`. Tests: `api/tests/test_assistant.py` (the guard, the writers with a stub client, what the model sees, the endpoint on a stand-in job, the no-outbound run, the record with its writer) and the settings tests. Not built: the setup explanation shown in the studio before a run (the endpoint explains a job's checklist; a check without a job has none), a second provider, the model drafting inputs.

## Why (evidence)

- The founder's choice of 2026-10-28, quoted above.
- `cd api && uv run pytest -q tests/test_assistant.py tests/test_settings.py`: the counts are in the evaluation note `docs/evaluations/api/2026-10-28-assistant.md`.
- The SDK's own types, read on 2026-10-28 (`anthropic` 1.17.0): `fallbacks` takes a list or the literal `"default"`; `output_config`, `betas` and `system` are parameters of `client.beta.messages.create`. The request shape follows the Claude API reference of the same day.
- A live answer from Claude: no evidence yet (no credential on the founder's machine). UNVERIFIED until the founder sets the three variables and runs a job; the stub tests cover the code path either way.

## Consequences

- Easier: the explanation can be rephrased for the reader without a number ever being invented; a self-hosted customer runs with the template alone; every explanation has its receipt and names its writer.
- Harder: the guard refuses a correct derived number (a percentage, a margin) the sheet does not hold, so the sheet must grow when such a number is wanted; a provider's outage shows as the template's words with a reason, not as an error.
- Depends on: the `anthropic` SDK in the API's environment (unused with the assistant off); the fea package's fact sheet.

## How we will know it was wrong

- If drafts are withheld on most jobs, the sheet is too small or the guard too strict: widen the sheet before loosening the guard.
- If a reader needs the model to say something the sheet cannot support (a comparison with a test, a design margin), the explanation needs a new fact, not a freer model.
- If a customer needs a provider this interface cannot name (Bedrock in their account, an open-weight model), the interface, not the guard, is what to extend.
