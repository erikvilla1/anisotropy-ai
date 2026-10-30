# ADR-0049: One command takes a coupon from its input form to its package, and the CalculiX record keeps the gauge probes

- Status: Proposed
- Date: 2026-10-26
- Decided by: Founder, 2026-10-26 ("i am settled with the order above": step 1 of ADR-0048, one command per job with an end-to-end test) | Drafted by: Claude Code
- Related: [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), `fea/tools/run_coupon.py`, `fea/tests/test_run_coupon.py`, `fea/src/anisotropy_fea/intake.py` (`gauge_probes`, `next_commands`)

## Context

- A read form (ADR-0046) leaves a case page whose Rebuild section lists six commands. Four placeholders are filled by hand (`attempt-NN_<date>`, `--run-by`, `--machine`, `--notes`), and the attempt's row in the log is written by hand (ADR-0039).
- The case page's record command recorded every probe. In a scratch run of the example form on 2026-10-26, 96 of 108 recorded values agreed with CalculiX; all 12 others sat at the near-grip element, where the two element types are known to differ (the committed IM7/8552 record's UNVERIFIED region).
- The founder's coupon records were made with the gauge probes only, and say why in their notes (for example `.local/fea/X840PW-UNT-L1/ours/verification/X840PW-UNT-L1-calculix.toml`); so was the committed open-hole check record (`--element-probes far --node-probes gauge`, [evaluation](../evaluations/fea/2026-10-19-gmsh-open-hole.md)).

## Options considered

1. **A shell script with the six commands.** Simple. Two shells to keep on two systems, nothing checked before the first write, and the attempt folder parsed from a printed line.
2. **A Python tool that does every step in-process.** The kernel step's figures and VTK file are written by scripts in `fea/examples/`, not by the package, so it would import scripts.
3. **A Python tool that calls the package for the folder steps (form, decks, attempt, case page) and the document, and runs the documented scripts for the solves and the record.** The commands are the ones the case page lists, with their own messages. The document is built in-process because `docs/models/coupon.py` reads a coupon from `.local/fea/` whatever its `--root`, which moves only its outputs.
4. **Move every step into the package first.** The right shape for the API job (ADR-0048 step 2); larger than this step.

Within option 3:
- Input: a filled form, or a coupon that has its specs. A free-standing spec is not taken: it has no twin, no name and no case page, and the form makes all three.
- Probes: the gauge probes only (option a), or every probe (option b, the case page's command until now). Option b lets a known formulation difference read as disagreement.
- A failed run: its row is written with the step it stopped at (the log keeps failed tries), or no row.

## Decision

Option 3, with the gauge probes and a row for every run.

`uv run python tools/run_coupon.py <filled form>.xlsx --run-by "<name>"` (or `<coupon>` instead of the form) refuses before writing anything when CalculiX is missing, a spec is missing, or the attempt log is behind its folders. Then it reads the form, writes the decks, starts the attempt, runs our engine and the CalculiX twin, writes the record with the gauge probes and the reason in its notes, and builds the package. It adds the attempt's row (on failure, the step it stopped at), refreshes the case page's result, and lists the files to open in Abaqus/CAE, PrePoMax and ParaView. `--machine` defaults to the operating system and the CalculiX version, recorded and printed.

`intake.gauge_probes` names the probes a record keeps: the centre node and element, or for an open hole the gauge node and far element. The case page's record command uses it too.

## As built (2026-10-26)

- `fea/tools/run_coupon.py`; `gauge_probes` and a `kind` argument to `next_commands` in `fea/src/anisotropy_fea/intake.py`; `fea/tools/coupon_from_form.py` prints the one command; `fea/tools/regenerate_decks.py` prints paths outside the repository as they are.
- `fea/tests/test_run_coupon.py`: the public IM7/8552 form to its package under a temporary root (CalculiX needed; CI installs it), a failed step's row, the refusals without CalculiX and with a lagging log, and the record's tolerance and probes against the case page's command.
- Not in this step: the record's reading (`<record>.md`, written by a person, ADR-0031; the tool says so, and until it exists `test_every_test_folder_has_the_same_shape` names the record on that machine); the Abaqus run (`tools/run_abaqus.py` needs the teaching licence and stays a separate command); a failure-index output request in the Abaqus deck (waits for the founder); the case page text written by `intake.case_page` (it still lists the six commands; `coupon_from_form.py` prints the one command).

## Why (evidence)

- `cd fea && uv run pytest -q -ra tests/test_run_coupon.py tests/test_intake.py`: 37 passed (2026-10-26).
- Rehearsals in a scratch copy on 2026-10-26, from the command line: the example form gave exit 0 in 57 s with the PDF, 57 of 57 recorded values agreeing; a form filled with the founder's own coupon gave exit 0, with the same kernel reaction and first-ply failure as `build_model.py` on the hand-written spec.

## Consequences

- Easier: a demonstration is one command; the attempt log fills itself; the API job can call `run()`.
- Harder: the tool depends on the scripts' options, so a change in one breaks it; the end-to-end test catches that wherever CalculiX is installed. A coupon whose gauge probe has another name is refused by `record_from_dat.py`.

## How we will know it was wrong

If coupons the form describes are still run step by step, or the end-to-end test is skipped on CI because CalculiX is missing.
