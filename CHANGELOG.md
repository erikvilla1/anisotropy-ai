# Changelog

Notable changes, newest first. Dates are YYYY-MM-DD. Engine versions follow `engine/pyproject.toml`.

## [Unreleased]

### Fixed

- Engine input checks reject non-finite stress/strain vectors, malformed vectors, unknown model fields and invalid safety-factor inputs (ADR-0003). Zero-stress infinite ratios remain supported.
- Corrected the sign in the Tsai-Wu numerical-stability explanation; the equation is unchanged.

### Added

- Analytical practice case for a zero-degree AS4/3501-6 ply under 100 MPa tension, with independently calculated strains and maximum-stress ratio.
- LaTeX engine manual (`docs/manual/`), generated from the documentation, the engine source and engine results; built as a PDF on every pull request (ADR-0008).
- `anisotropy_engine.cases`: validation-case logic shared by the tests, the manual and the future API.
- Documentation in `docs/`: system overview, decision records ADR-0001 to ADR-0007, engine 0.1 verification report and risk register.
- `engine/docs/theory.md`: every equation the engine uses, with the function that computes it.
- Pull request template, and automated tests on every pull request (engine and website).
- Working rules for AI coding assistants in `AGENTS.md`.

### Changed

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
