# Engine manual (LaTeX)

A typeset PDF that collects the engine documentation into one readable document: what was built, every equation with the code that computes it, validation results, the finite element layer with its own theory and cases, decisions, limits and risks, and a worked example.

## Get the PDF

- **Without installing anything:** open the repository's Actions tab on GitHub, choose the latest "Tests" run, and download the `engine-manual` file. Every pull request and every merge to `main` builds it.
- **On your computer:** install [Tectonic](https://tectonic-typesetting.github.io/), then from the repository root run:

  ```sh
  uv run --project fea python docs/manual/build.py
  ```

  The build runs from the `fea` environment because it holds both packages: the finite element layer and, as an editable dependency, the engine. The PDF is written to `docs/manual/build/anisotropy-engine-manual.pdf`.

## Where the content comes from

The manual is generated, so it cannot drift from the repository ([ADR-0008](../decisions/ADR-0008-manual-generated-from-sources.md), extended to the finite element layer by [ADR-0029](../decisions/ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md)):

| In the manual | Comes from |
| --- | --- |
| What we built, known limitations | `docs/00_system_overview.md` |
| Equations and explanations | `engine/docs/theory.md` and `fea/docs/theory.md` |
| Code listings with line numbers | The engine and `fea` source, at the places marked `<!-- code: name -->` in each theory file |
| Validation tables | Running the engine on every case in `engine/validation/cases`, and the kernel on every case in `fea/validation/cases` |
| Verification reports | The newest file in `docs/evaluations` (engine) and in `docs/evaluations/fea` (finite element layer) |
| Decisions | `docs/decisions/ADR-*.md` |
| Risk register | `docs/risks/risk_register.md` |
| Worked example | Running the engine during the build |
| Versions, commit, test counts | `engine/pyproject.toml`, `fea/pyproject.toml`, Git and both test runs |

To change the manual, edit those sources. Only the layout and the short framing text live in `main.tex`. Files in `generated/` and `build/` are rebuilt every time and are not committed.

## Rules the build enforces

- The engine tests and the finite element tests must pass, or the manual is not built.
- Every validation case, engine and finite element, must reproduce its source.
- Every function that a theory file says "computes" or "checks" something must have a code marker, and every marker needs that sentence. `fea/tests/test_theory_markers.py` checks the finite element file on every test run as well.

## Markdown the converter understands

Headings, paragraphs, bullet and numbered lists, tables, `**bold**`, `*italic*`, inline code, links, inline math written as $`...`$, and display math in ```` ```math ```` blocks. Keep to these in the source documents.
