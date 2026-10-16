# Evaluation: the LaTeX manual covers the finite element layer (ADR-0008, ADR-0029 chunk 2b) | 2026-10-15

- Scope: `docs/manual/build.py` reads a second package: `fea/docs/theory.md` with its code markers, the finite element validation cases solved during the build, the newest report in `docs/evaluations/fea`, the `fea` tests and version. A "Finite element layer" section in `main.tex`. The build runs from the `fea` environment, which holds both packages.
- Environment: Windows 11, uv 0.13, Tectonic 0.17 at `%LOCALAPPDATA%\Programs\tectonic\tectonic.exe`, branch `feat/fea-manual` at `7f9e9dd` plus these changes.

## Commands and captured output

From the repository root: `uv run --project fea python docs/manual/build.py`

```text
Manual written to C:\Users\erikv\Documents\Composite_AI\docs\manual\build\anisotropy-engine-manual.pdf
```

(Tectonic also printed a Fontconfig warning about a missing default config file, as before; it does not affect the output.) The PDF is 609 KB.

`docs/manual/generated/meta.tex` after the build:

```text
\newcommand{\EngineVersion}{0.1.0}
\newcommand{\FeaVersion}{0.1.0}
\newcommand{\TestSummary}{411 passed}
\newcommand{\FeaTestSummary}{106 passed}
```

Both test suites ran inside the build and passed; a failure in either stops the build.

`generated/fea_theory.tex`: 15 code listings (`\codefrom`), one per marker in `fea/docs/theory.md`, each with the source file and real line numbers from the `fea` package.

`generated/fea_verification.tex`: "469 of 469 values from 5 cases agree with their sources within each case's tolerance", followed by the five case tables (reactions, displacements, strains, section forces, ten plies' stresses and strains, first-ply-failure factors), then the recorded report `docs/evaluations/fea/2026-10-15-ply-recovery-failure.md`.

`generated/verification.tex` (engine, unchanged behaviour): "426 of 426 values from 32 cases agree".

## Not checked

The PDF was produced but not opened on this machine (no PDF renderer available to the build session): page layout of the new section, the title-page line "Finite element layer 0.1.0, tests: 106 passed", and the typesetting of the finite element equations are UNVERIFIED until someone opens the file or downloads the `engine-manual` artifact from CI. Website suites: unaffected.
