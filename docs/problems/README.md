# Solved problem documents (LaTeX)

One typeset document per solved problem, separate from the engine manual ([ADR-0033](../decisions/ADR-0033-one-generated-document-per-solved-problem.md)). Each document is the complete argument for one problem: what the problem was as the validation case states it, every step the engine took with the equation from the theory and the function that computes it, the numbers of each step, the source's answers next to the engine's with their differences, how the inputs were read and judged, and the reading.

## Build

From the repository root, with [Tectonic](https://tectonic-typesetting.github.io/) installed (the same as for the manual):

```sh
uv run --project fea python docs/problems/build.py engine/validation/cases/se142-hw3-p3a-boron-symmetric.toml
uv run --project fea python docs/problems/build.py --all        # every committed case, and index.md
uv run --project fea python docs/problems/build.py .local/homework/code/course-reader/cr-5-9-as4.toml
```

| Case | Document goes to | Committed? |
| --- | --- | --- |
| `engine/validation/cases/<name>.toml` | `docs/problems/build/<name>/<name>.pdf`, and `docs/problems/build/index.md` with `--all` | No: rebuilt from sources, like the manual; CI uploads the PDFs and the index as the `problem-documents` artifact |
| anything under `.local/` | `report/<name>/<name>.pdf` beside the case | Never |

Options: `--no-pdf` writes the LaTeX only; `--no-theory` leaves out the theory text and code listings of every step. Without Tectonic the `.tex` is still written and is self-contained.

## Where the content comes from

| In the document | Comes from |
| --- | --- |
| Title page, verdict, summary | The case file and the engine's case runner, run during the build (`anisotropy_engine.cases`) |
| The problem: materials, plies with z positions, loading, failure settings | The case file, with library citations when a material comes from the engine's library |
| The steps: ply stiffness, rotation, ABD and its inverse, thermal resultants, the response, every ply face, first-ply failure, engineering constants, buckling | The matching section of `engine/docs/theory.md` through the manual's converters, the function listings with line numbers, and the engine's numbers for this problem |
| Every compared number | The case file (source) and the engine (computed during the build) |
| How the inputs were read and judged | `anisotropy_engine/cases.py`, listed |
| Reading | A note under `docs/problems/readings/` whose file name is a prefix of the case's name (one note covers a homework set), or `<case>.md` beside the case; written by a person, quoting numbers from the case. Without one the section says so; the build never invents a reading |
| Appendix | The case file itself |

## The index

`--all` writes `docs/problems/build/index.md`: one row per problem with its title, source, how many values the source states and how many the engine reproduces. It is the answer to "what problems has the engine solved", with the documents behind each row.

## Adding a problem

1. Add the case under `engine/validation/cases/` (see `engine/validation/README.md`): inputs and the source's numbers only, never the problem text.
2. Write or extend the reading note for its set under `readings/`.
3. Build the document and read it. Anything the reading claims that the tables do not show is a defect in the reading.

The Markdown subset a reading may use is the manual's: paragraphs, `##` and `###` headings, bullet and numbered lists, pipe tables, inline code, bold, italic, links, and `$`...`$` inline math written as `` $`...`$ ``.
