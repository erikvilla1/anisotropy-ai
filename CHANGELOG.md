# Changelog

Notable changes, newest first. Dates are YYYY-MM-DD. Engine versions follow `engine/pyproject.toml`.

## [Unreleased]

### Fixed

- Chat preview preserves signed, zero and decimal inputs for validation instead of converting negative values to positive values or retaining an earlier value. Explicit hole dimensions are not cleared by selecting D3039.
- Engine input checks reject non-finite stress/strain vectors, malformed vectors, unknown model fields and invalid safety-factor inputs (ADR-0003). Zero-stress infinite ratios remain supported.
- Corrected the sign in the Tsai-Wu numerical-stability explanation; the equation is unchanged.

### Added

- First-ply failure with fixed and variable loads: residual thermal stress and loads held fixed stay constant while the rest scale, in closed form for maximum stress and Tsai-Wu (Daniel and Ishai Section 9.8). Course Homework 5 Problem 1 part D (Nx at failure, ply and location) is now a validation case (ADR-0017).
- Mixed load and deformation conditions: give one known quantity per load/deformation pair, with or without a temperature change, and the engine solves and verifies the rest. Course Homework 2 Problem 1 and Course Reader Problems 3.8 and 5.13 are now validation cases (ADR-0016).
- Course inputs and answer-key comparison: the calculator reads the course Excel input template, cases can describe several materials and ply thicknesses, new results cover S, Q-bar, S-bar, the inverse ABD blocks and every ply face, and the calculator ends with an answer-key table. 17 new validation cases from course Homeworks 2 to 5 agree with 313 answer-key values (ADR-0015).
- Thermal analysis: expansion coefficients, a uniform temperature change, thermal force and moment resultants, and residual ply stresses in the engine, case files and terminal calculator. Two validation cases reproduce the Course Reader 5.9 answer key (ADR-0014).
- Prescribed-curvature analysis computes required laminate moments from explicit forces and curvature, checks the full forward response, and exposes a dedicated API operation with analytical cases and a chunk 3 walkthrough (ADR-0013).
- Calculator page connects an editable GPa/mm laminate form to the Python API, displays engine stiffness/deformation, and handles invalid inputs, cancellation and outdated results; includes browser integration tests and a learning walkthrough (ADR-0012).
- Local FastAPI endpoint for one-material laminate stiffness and deformation, with explicit SI-base inputs, integration tests and a chunk-by-chunk learning walkthrough (ADR-0011).
- Property-specific textbook citation viewer with source units, conversions and exact table/page references. Original page scans and their rendering output remain local (ADR-0010).
- Analytical practice case for a zero-degree AS4/3501-6 ply under 100 MPa tension, with independently calculated strains and maximum-stress ratio.
- LaTeX engine manual (`docs/manual/`), generated from the documentation, the engine source and engine results; built as a PDF on every pull request (ADR-0008).
- `anisotropy_engine.cases`: validation-case logic shared by the tests, the manual and the future API.
- Documentation in `docs/`: system overview, decision records ADR-0001 to ADR-0007, engine 0.1 verification report and risk register.
- `engine/docs/theory.md`: every equation the engine uses, with the function that computes it.
- Pull request template, and automated tests on every pull request (engine and website).
- Working rules for AI coding assistants in `AGENTS.md`.

### Changed

- The founder accepted ADR-0014 (thermal analysis) and ADR-0015 (course inputs, several materials). The thermal theory now cites its Daniel and Ishai Chapter 8 equations, and ADR-0014 records the course validation.
- The founder accepted ADR-0009 to ADR-0013 (calculator cases, citations, local API, browser calculator, prescribed curvature).
- The calculator reads explicit TOML cases using the existing validation format; personal inputs no longer require code edits. It displays input units, requires review of implausible moduli and does not assume a Tsai-Wu interaction coefficient (ADR-0009).
- Case inputs reject unknown fields, partial strengths and malformed applied vectors before solving.
- Moved `AI_Documentation.md` to `docs/documentation-guide.md`.

## [Engine 0.1.0] - 2026-10-02

### Added

- Python laminate analysis engine: ply stiffness, rotation, A-B-D matrices, load response, first-ply failure by maximum stress and Tsai-Wu, and laminate engineering constants (pull requests #1 and #2).
- Validation cases from textbooks and answer keys, SI/US/psi unit systems, a laminate calculator and a coupon example (pull request #2).

## Website

- 2026-10-02: Materials library with sources and references.
- 2026-09-30: Website assets organized and repository cleaned.
- 2026-09-30: Initial Anisotropy AI website.
