# Risk register | last reviewed 2026-10-03

Functions follow the NIST AI Risk Management Framework: Govern, Map, Measure, Manage. Review monthly, and whenever a risk changes.

| ID | Risk | Area | NIST function | Likelihood | Impact | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 | A unit-entry mistake gives a wrong result | Engineering | Measure | High: two mistakes on 2026-10-02 | High | SI inside the engine (ADR-0002); calculator screens implausible moduli; local API requires SI_BASE and unit-labelled material inputs (ADR-0011). Declaring units does not prove the entered scale is correct | Engineer | Partly mitigated |
| R-02 | First-ply failure is unconservative without curing residual stresses | Engineering | Map | Medium | High | Stated in the overview, the reports and the code; add temperature and moisture effects before design use | Engineer | Open |
| R-03 | A result is used as ultimate strength or a design allowable | Engineering | Govern | Medium | High | First-ply failure labelled as the onset of cracking; engine not approved for design decisions | Founder | Open |
| R-04 | Material values are typed wrongly or taken from the wrong dataset | Data | Measure | Medium | High | Material loader reading the cited library (planned); dataset recorded with every run (planned) | Engineer | Open |
| R-05 | The public website shows scanned textbook pages | Legal | Govern | Low after cleanup | Medium | `/sources` shows citations and recorded values; images and rendering output stay under ignored `.local/`. Unit/browser checks prevent public scans (ADR-0010). No redistribution-rights claim | Founder | Mitigated in proposed change |
| R-06 | Course problem statements or solutions are committed to the repository | Legal | Govern | Low | Medium | Validation cases store numbers only (ADR-0007) | Both | Mitigated |
| R-07 | Ownership of lab test data is unclear | Legal and data | Govern | Medium | High | Written ownership or license before data is used in reports or models | Founder | Open |
| R-08 | Export control (ITAR or EAR) applies to aerospace data or customers | Legal | Govern | Low now | High | Classify data and software before accepting controlled data; make no compliance claims | Founder | Open |
| R-09 | Changes reach `main` without review | Process | Govern | High: seven direct commits on 2026-10-02 | Medium | Branch and pull request for every change; pull request template; automated tests on every pull request. Branch protection on a private repository needs GitHub Pro or Team | Both | Partly mitigated |
| R-10 | A language model invents numbers or references, once added | AI | Measure | Medium | High | The language model never produces numbers (ADR-0001); citations only from stored source records | Engineer | Not yet applicable |
| R-11 | Customer or lab data is sent to an external AI service | AI and data | Manage | Low | High | No raw data to external services without approval; zero-retention terms | Founder | Open |
| R-12 | Two implementations of laminate math drift apart | Engineering | Manage | Medium | Medium | Python engine is the single source; the TypeScript kernels become a cross-check or are removed | Engineer | Open |
