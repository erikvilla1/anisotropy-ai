# ADR-0048: The assistant drives tested jobs and never computes; one command per job and an API job come first, machine learning last

- Status: Proposed
- Date: 2026-10-26
- Decided by: Founder, 2026-10-26 ("i am settled with the order above", on the order: one command per job with an end-to-end test, the job through the API, the assistant, then machine learning) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0027](ADR-0027-deployment-tiers-and-assistant-model-location.md) (its order of work is extended here), [ADR-0047](ADR-0047-a-read-only-peer-review-subagent-for-generated-documents.md), [ADR-0049](ADR-0049-one-command-takes-a-coupon-from-its-input-form-to-its-package.md), [system overview](../00_system_overview.md)

## Context

- Tested code computes every number; a language model may draft inputs and explain results, never produce a number in a result (ADR-0001). The system overview plans the assistant as a general model with tool access, tested on the validation cases, and machine learning later, rechecked by the engine.
- ADR-0027 orders the work after the finite element phase: the assistant's own decision record (provider interface, the guard on result numbers, what the model may see, evaluation), then the assistant, then customer datasets and authentication, then containers.
- On 2026-10-26 the founder ran a hand-written spec through one of the seven coupon steps and got part of the outputs: no first-ply-failure lines in the summary, no file PrePoMax opens, and a crash when the output was piped. The full chain from the input form worked when its seven steps were run one by one, but each step was typed by hand with placeholders filled in, and no test ran the chain end to end.
- An assistant calling these tools would face the same seven steps.

## Options considered

1. **Build the assistant now on the existing scripts.** The quickest to show. It inherits the hand-filled placeholders and the steps that stop without a clear message, and its failures cannot be told apart from the tools'.
2. **One command per job first, then the job through the API, then the assistant, then machine learning.** The assistant gets a few tools with checked inputs, and the website and the assistant call the same job. The visible assistant comes later.
3. **A model trained on our cases that produces results.** Refused by ADR-0001: not reproducible, not auditable.

## Decision

Option 2, in this order:

1. One command per job, with a test that runs it end to end. The coupon job is ADR-0049.
2. The job through the API, writing a run record per run (ADR-0026), so the website and the assistant call the same thing.
3. The assistant, as ADR-0027 requires it (its own decision record first). Its tools are the jobs: draft a form or spec, check it, run the job, read the record, explain the result. It never writes a number in a result (ADR-0001), its inputs pass the same checks as anyone's (ADR-0003), and it is graded on the validation cases and the example forms.
4. Machine learning, once run records and coupon tests accumulate; every prediction rechecked by the engine.

ADR-0027's later items, customer datasets with authentication and then containers, keep their place after the assistant.

## Why (evidence)

- The founder's run of 2026-10-26: `.local/questions/my-coupon.toml` through `fea/examples/build_model.py` alone; PrePoMax refused the Abaqus deck; the pipe crash and the guide are fixed in the same pull request as this record.
- The seven steps run one by one from the example form in a scratch copy on 2026-10-26 each exited 0 and wrote the package; ADR-0049 turns that into one command and a test.
- For steps 2 to 4: no evidence yet.

## Consequences

- Easier: each AI step stands on a tested job; a failure of the assistant can be told apart from a failure of the tools.
- Harder: the assistant comes later; every job needs its one-command form and test before the assistant may call it.
- Depends on: CalculiX on the machine that runs a coupon job; the run records of ADR-0026.

## How we will know it was wrong

If the assistant, once built, mostly needs tools that are not jobs (free calculation, reading arbitrary files), the job boundary is wrong. If a demonstration of the assistant is needed before step 2 is done, the order is wrong.
