# Evaluation: one folder and one document per homework set (ADR-0040, chunk 2) | 2026-10-21

- **Scope.**
  - `.local/homework/{assignments,code}/<HW>/` becomes `.local/homework/<set>/{provided, ours, documents}`, with `course_audit.py` beside the sets.
  - New: `docs/problems/homework.py`, one document per set.
  - The local index, the readings, `docs/problems/README.md` and the workspace-layout skill (0.5.2) are updated.
- **Branch:** `feat/homework-folders`, stacked on `feat/coupon-document` (#72).

## Commands and captured output

The local move, checked against an inventory taken before it:

```text
{'moved, README edited': 6, 'moved unchanged': 40} | before 46 after 46 | problems []
```

That is, 40 files moved unchanged and 6 READMEs were edited on purpose: the paths in the five `ours/README.md` files and the set index.

`uv run --project fea python docs/problems/homework.py --all`:

```text
HW2: 6 problems, 51 of 51 values agree           -> .local/homework/HW2/documents/HW2.pdf
HW3: 6 problems, 128 of 128 values agree         -> .local/homework/HW3/documents/HW3.pdf (75 pages)
HW4: 5 problems, 110 of 110 values agree         -> .local/homework/HW4/documents/HW4.pdf
HW5: 3 problems, 36 of 36 values agree           -> .local/homework/HW5/documents/HW5.pdf
course-reader: 2 problems, 46 of 46 values agree -> .local/homework/course-reader/documents/course-reader.pdf
```

HW1 and PRACTICE have no engine case, so they have no document.

HW3's title page and its first problem chapter were checked by eye. The first build numbered the problems' chapters 1 to 6 on the title page; they are 2 to 7, after the physics chapter, and that is now fixed. Each problem chapter's labels carry its case name, and `fea/tests/test_homework_document.py` checks that no label repeats and that every reference points to a label.

`fea/tools/case_pages.py --local` lists, per set, its status, engine cases, `ours/` folder and document.

## Not changed

The per-problem documents of `docs/problems/build.py --all` and the CI artifact stay. Which problems are benchmarks is waiting for the founder's review.
