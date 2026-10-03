# Changelog

Notable changes, newest first. Dates are YYYY-MM-DD. Engine versions follow `engine/pyproject.toml`.

## [Unreleased]

### Fixed

- Chat preview preserves signed, zero and decimal inputs for validation instead of converting negative values to positive values or retaining an earlier value. Explicit hole dimensions are not cleared by selecting D3039.

### Added

- LaTeX engine manual (`docs/manual/`), generated from the documentation, the engine source and engine results; built as a PDF on every pull request (ADR-0008).
- `anisotropy_engine.cases`: validation-case logic shared by the tests, the manual and the future API.
- Documentation in `docs/`: system overview, decision records ADR-0001 to ADR-0007, engine 0.1 verification report and risk register.
- `engine/docs/theory.md`: every equation the engine uses, with the function that computes it.
- Pull request template, and automated tests on every pull request (engine and website).
- Working rules for AI coding assistants in `AGENTS.md`.

### Changed

- Moved `AI_Documentation.md` to `docs/documentation-guide.md`.

## [Engine 0.1.0] - 2026-10-02

### Added

- Python laminate analysis engine: ply stiffness, rotation, A-B-D matrices, load response, first-ply failure by maximum stress and Tsai-Wu, and laminate engineering constants (pull requests #1 and #2).
- Validation cases from textbooks and answer keys, SI/US/psi unit systems, a laminate calculator and a coupon example (pull request #2).

## Website

- 2026-10-02: Materials library with sources and references.
- 2026-09-30: Website assets organized and repository cleaned.
- 2026-09-30: Initial Anisotropy AI website.
