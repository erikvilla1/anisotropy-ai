# Changelog

Notable changes, newest first. Dates are YYYY-MM-DD. Engine versions follow `engine/pyproject.toml`.

## [Unreleased]

### Fixed

- The course handout "SE143AB Appendix F: Material Properties" was being served from the website's public assets and linked from exported analysis packets. It now stays in ignored local storage, is never served or linked, and the website's asset test expects a 404 for its former URL (ADR-0018).

- Chat preview preserves signed, zero and decimal inputs for validation instead of converting negative values to positive values or retaining an earlier value. Explicit hole dimensions are not cleared by selecting D3039.
- Engine input checks reject non-finite stress/strain vectors, malformed vectors, unknown model fields and invalid safety-factor inputs (ADR-0003). Zero-stress infinite ratios remain supported.
- Corrected the sign in the Tsai-Wu numerical-stability explanation; the equation is unchanged.

### Added

- Maximum strain and Tsai-Hill ply failure criteria, including the fixed-and-variable load form, in the engine and the calculator. Strain limits are five explicit magnitudes or, by the case's stated choice `strain_limits = "from-strengths"`, strength divided by modulus; the engine never derives them silently. Two validation cases: an analytical biaxial lamina where maximum strain and maximum stress differ through Poisson coupling, and the textbook's 45° shear strength by Tsai-Hill (ADR-0021). The calculator prints B of a symmetric laminate as zeros instead of roundoff.
- Engine cheat sheet (`docs/engine-cheat-sheet.md`): units per system, the applied-load forms, what fixed and variable mean in a failure search, how to read the printout and which expected keys exist. The theory document's gap list now names maximum strain, Tsai-Hill and buckling.
- Material loader: the website library is exported to `engine/src/anisotropy_engine/data/material-library.json` (`npm run export:library`, drift-guarded by a test) and the engine loads a cited dataset by name as a `Lamina` in SI with the page of every value used. Case files accept `[material] library = "im7-8552"`; the API gains `GET /v1/materials`, `GET /v1/materials/{id}` and a `material: {library_id, dataset_id}` request form with `material_provenance` in the response; the calculator gets a library picker and a material source block (ADR-0020).
- Physics library completion: nine cards for the operations the engine implements and the textbook states but the library did not show (ABD inverse compliance, prescribed curvature, mixed load and deformation conditions, Hashin–Rotem as printed, first-ply failure load, strength ratio with fixed and variable loads, thermal resultants, residual ply stress, laminate expansion coefficients), each naming its engine function, textbook or NASA location, units and typeset form; the engineering-constants card now covers general laminates. 38 cards; a test checks every card has a typeset equation and that every engine theory section has a card (ADR-0019).
- Library completion: three NCAMP plain weave records (8552S / AS4, 5320-1 / T650, TC250 / HTS40) with measured warp, fill, shear and physical entries, and two public-domain historical records from the canceled MIL-HDBK-17-2F (T650-35 / 976 tape and 7781 / EA 9396 wet lay-up fabric) sourced from the official DLA ASSIST copy with its cancellation notice, each value keeping the handbook data class as its basis. 25 materials in the public library; the public-sources research is closed out.
- NASA 2023 IM7 / 8552 characterization (NASA/TM-20230001560) as a second dataset of the IM7 / 8552 record, selectable beside the NCAMP data: 24 room-temperature entries including through-thickness moduli and strengths, printed psi values kept as source values, publisher fingerprint, rights evidence and a monitor adapter. The material count is unchanged.
- Toray TC380 / T1100GC and Syensqo EP2190 / IMS65 unidirectional records from the NCAMP 2025 qualification reports: 20 measured room-temperature entries each. EP2190 was tested at ambient condition and its compression measured directly; the record and its keys say so.
- Solvay 5320-1 / T650 and TenCate BT250E-6 / IM7 unidirectional records from the NCAMP 2017 qualification reports: 19 measured room-temperature entries each with page references, publisher-confirmed fingerprints, rights evidence and one-record-per-report monitor adapters.
- Hexcel 8552 / IM7 unidirectional record from the NCAMP 2019 qualification reports: 21 measured room-temperature entries with page references, fingerprints, rights evidence and monitor adapters; the first entry from the public-sources research.
- Research record of public material data sources the website may show (`docs/material-research-public-sources-2026-10-10.md`): 20 NCAMP-qualified systems with room-temperature means for 12 of them, four systems from the public-domain MIL-HDBK-17-2F, and NASA, open-access and manufacturer sources, each with its rights evidence. No values entered yet.
- Source rights classes: every cited source records whether it is public domain, open publisher data, a licensed reference or user supplied, with evidence. One policy table decides what the website shows for each class; the library displays the class beside each dataset and explains the classes on the references panel. Tests check that every public dataset has a class, that nothing copied is served and that no PDF exists under public assets (ADR-0018).
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

- The founder accepted ADR-0016 (mixed load and deformation conditions), ADR-0017 (first-ply failure with fixed and variable loads) and ADR-0018 (source rights classes) on 2026-10-10.
- The founder accepted ADR-0019 (the physics library presents every equation the engine implements) on 2026-10-10.
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
