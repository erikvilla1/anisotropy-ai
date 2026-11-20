# ADR-0127: The wing's references are three pages in our own words, design rules, test methods and allowables, searched by subject with the wing's theory, each section with the other words it is asked by

- Status: Proposed; read by the wing's chat and the MCP server's wing tools by [ADR-0128](ADR-0128-a-wings-chat-reads-a-change-of-plies-into-the-engines-form-and-previews-it-on-a-copy-answers-from-the-wings-report-and-the-reference-pages-and-the-wing-changes-only-on-the-engineers-apply.md)
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 ("in rag make sure it pulls in allowables, astm methods and design rules, ply drop ratios, max consecutive same anlge ply, 10% rule", his ask for the wing chat; then "Plan order: project, rules, caps, chat", his choice on the plan whose step 4 is three reference pages in our own words searched by word matching with other words per section). The places, the subject, the synonym lines and the wording are the drafter's | Drafted by: Claude Code
- Related: [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md), [ADR-0123](ADR-0123-a-layups-design-rules-are-judged-by-the-engine-on-the-stack-alone-as-warnings-with-their-limits-in-the-wing-file-and-change-no-number-of-the-analysis.md), [ADR-0125](ADR-0125-a-spar-cap-is-a-strip-of-each-skin-over-each-web-with-its-own-layup-any-layup-may-change-in-zones-along-the-span-and-the-hand-calculation-works-a-section-per-stretch.md), [ADR-0126](ADR-0126-a-wings-margins-use-the-b-basis-strengths-of-the-materials-public-qualification-report-kept-as-a-dataset-of-their-own-beside-its-means.md), `engine/docs/references/`, `api/src/anisotropy_api/theory.py` (`SUBJECT_OF`, `wing_sections`, `ALSO`), `api/tests/test_theory.py`, `tests/assistant-questions/wing.json`, the wing chat plan (Claude Doc "Wing chat: tools and references plan")
- Area: assistant, docs, api

## Context

- The founder asked that the wing's chat bring in allowables, test methods and design rules: ply drop ratios, plies of one angle in a row, the 10 % rule. The theory search (ADR-0102) reads three pages: laminate theory, finite element theory and the reasons behind a coupon's result. None explains a design rule's purpose, a test method or a basis value.
- The values themselves are already exact: the rule limits and results are the engine's (ADR-0123, ADR-0125), the strengths and their basis, table and page the material record's (ADR-0126). A text search can find the closest words, which may belong to another material or another rule, so a value never comes from a page.
- The wing's own theory sections are searched only by their subject, since adding them to every search changed how a coupon's questions rank (ADR-0102 amendment 1). Pages of design guidance would do the same.
- ASTM standards and CMH-17 are licensed references: a standard's number, never its text or figures (ADR-0018 amendment 1). MIL-HDBK-17-3F and FAA AC 20-107B are public.
- Sources read on 2026-11-20: FAA AC 20-107B with change 1 (paragraphs 6.d, 6.f, 6.g, 7.a, 7.e, 7.f, 8.a(4) and Appendix 2); NCAMP's statistical report for IM7/8552, NCP-RP-2009-028 Rev B (sections 1, 1.3, 1.4, 2.3, 2.5, 3.1, Tables 1-2, 1-3 and 3-1). Not read: MIL-HDBK-17-3F (everyspec.com refuses automated downloads; the founder was asked for a copy), a NASA contractor report of laminate design guidelines (contract NAS1-19347, 1997; not found on NASA's report server), the DLR report ADR-0123 cites, and 14 CFR 23.613 and 25.613. A search excerpt places the handbook's 10 % rule in Volume 3, Chapter 12 (Lessons learned).

## Options considered

1. **Three pages in our own words, `engine/docs/references/`, read by the theory search as the subject "references" and searched with the wing's theory only; each section names the other words it is asked by in a line `<!-- also: ... -->`** (chosen). A coupon's question ranks as before; the wing's chat (step 5) will search `wing_sections()`.
2. The pages searched with every question. Rejected: the same fault ADR-0102 amendment 1 fixed, every coupon question's ranking moved by sections no coupon chat needs today.
3. Meaning search with vectors. Rejected for now: the pages are a few dozen sections, the word ranking is exact and testable, and each answer can name its section. The plan keeps vectors for when the banks show questions missing their section.
4. Other words in the search's table of spellings (`SAME`). Rejected: that table maps one word to another on every page; "taper" is not "ply drop" everywhere. A section's own line keeps its other words beside it, where its author sees them.
5. Text taken from the handbooks or the standards. Rejected: ASTM and CMH-17 text is licensed, and the pages explain the rules in the terms the wing's page and checks use.

## Decision

- Three pages: `design-rules.md` (the 10 % rule, plies of one angle in a row, balance, symmetry, ply drops with their run-out, plies per place and the outside ply, spar caps and webs, ±45° plies outside, the angle between neighbouring plies), `test-methods.md` (each test behind a strength the wing uses, by its ASTM number and our own description, and where the number enters the wing; holes, bearing and impact as not checked yet) and `allowables.md` (mean, B-basis and A-basis; which basis where; values and estimates; normalized and as measured; environment; design values and the margin; which strengths a wing used).
- Each section ends with "Sources:", the source's paragraph or section and page where it was read, UNVERIFIED where it was only seen in a search excerpt. No page holds a value of a material; a rule's default limit appears as the rule's.
- `theory.py`: the pages are sources `rules`, `tests` and `allowables` of the subject "references" (`SUBJECT_OF`); `wing_sections()` gives the wing's and the references' sections; a section's `<!-- also: -->` line counts as words of its title, at the title's weight, and is never shown.
- `tests/assistant-questions/wing.json` watches the three pages and names this record. `api/tests/test_theory.py` pins the section that five of the bank's questions and eleven other wordings find first among `wing_sections()`, and that none is found by a coupon's search.

## As built (2026-11-20)

- `engine/docs/references/design-rules.md`, `test-methods.md`, `allowables.md`: 26 sections.
- `api/src/anisotropy_api/theory.py`: `SOURCES` with the three pages, `SUBJECT_OF`, `WING_SUBJECTS`, `ALSO`, `Section.also`, `split(..., of=)`, `wing_sections()`.
- `api/tests/test_theory.py`: the also line, the wing's questions and other wordings, the pages' sources, programs and values.
- `tests/assistant-questions/wing.json`: records and watches.

## Why (evidence)

- `cd api && uv run pytest tests/test_theory.py tests/test_assistant_questions.py`: 28 passed (2026-11-20), among them every banked question of every live bank finding what it found before, so a coupon's search is unchanged.
- Among the wing's sections: "what ply drop ratio should I use?" finds "Ply drops: How long the run-out is" first; "how many 0° plies can I stack together?" finds "Plies of one angle in a row"; "which ASTM test gives the compression allowable?" finds "Compression along the fibres"; "what allowables are you using for the spar caps?" finds "Which strengths a wing used"; "hot wet knockdown" finds "Environment: hot, wet and cold" (the test's tables).
- The sources' passages are as cited in Context; the unread ones are marked UNVERIFIED in the pages.

## Consequences

- No user sees the pages until the wing's chat is built (step 5), and the FEA assistant of a blank project does not search them; a question there about B-basis finds only the theory pages.
- The pages are drafts until the founder reviews them. Their unread sources (the handbook, the NASA guidelines, the DLR report, the regulation) must be read at their section and page, and a line corrected where it differs, as ADR-0123 asks.
- A rule or a strength added later brings its section, its other words and a line in the test's tables.

## How we will know it was wrong

- A question of the wing's bank finds the wrong section in the real-model check (ADR-0121) although the words are on the page: then the other words, or the search, are not enough.
- The pages grow past what word matching ranks well, or an engineer's words miss their section often: then the meaning search the plan keeps for later.
- A review finds a sentence its sources do not support.
