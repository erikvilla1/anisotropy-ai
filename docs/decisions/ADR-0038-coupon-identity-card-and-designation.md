# ADR-0038: Every coupon model carries an identity card and a name of the form material-test-layup

- Status: Accepted; the folders carry the name too, by [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md) (option 4 taken after all)
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (the coupon's name, such as X840PW-UNT-L1, is the title, with the type of test; the team's tension coupon has the same name as ours); accepted 2026-10-26 ("FEA method (7)", choosing which groups of the proposed records to accept) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/spec.py` (`Coupon`, `coupon_card`), `fea/tests/test_coupon.py`, [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [ADR-0036](ADR-0036-one-folder-per-fea-test.md), local evaluation note `.local/notes/evaluations/fea/2026-10-21-coupon-identity.md` (ADR-0042)

## Context

The founder could not tell which coupon was being compared. Folders, specs and documents named only the kind of test: `tension-coupon`, "Tension coupon", "Tensile Coupon". What the files say:

- **The team's files.** Their deck, slides and Abaqus/CAE replay name a job, a model and a part, but no standard or specimen name appears anywhere (the details are local, ADR-0042).
- **The material.** The team's material is the "Fabric" row of Chen 2015, Table 3.1 (X840-Z60 plain weave). That row is our library record `x840-z60-pw`.
- **No test data.** Chen 2015 tested ENF, curved-beam and shear-tie compression coupons, but no flat tension, compression or open-hole coupon. The dissertation says that its lamina values came from the manufacturer (printed p. 79).
- **How a test report names coupons.** The NCAMP IM7/8552 material property data report (`.local/sources/ncamp/8552-IM7-MPDR.pdf`) names coupons by test and layup: UNT1 is "25/50/25" unnotched tension, OHT1 is open-hole tension in the same layup, and so on.

## Options considered

1. **An identity card in the spec, with a name of the form material-test-layup.** Test codes follow NCAMP's style. Chosen.
2. **Descriptive titles only, as before.** Rejected: this is what the founder found unhelpful.
3. **NCAMP's own names (UNT1, OHC2).** Rejected: NCAMP's layup numbers stand for its three layups (25/50/25, 10/80/10, 50/40/10), and the team's layup is none of them.
4. **Rename the test folders to the coupon names.** Not chosen: the founder asked for the name as the title, and ADR-0036 set the folder names a day earlier. Every title, document and zip folder carries the name instead.

## Decision

Option 1.

- **The card.** A `[coupon]` table in the spec has five keys: `designation`; `standard` (or "none"); `size_from` (where the dimensions come from); `team_model` (the team's own model of the coupon, or "not built yet"); and `test_data` (measured results to benchmark against, or "none" and why). All five are required when the table is present. Every spec under `fea/models/` has one; a check under `fea/checks/` may not.
- **The name.** It reads `<material code>-<test code>-<layup code>` in capitals.
  - The test code follows from `kind`: UNT unnotched tension, UNC unnotched compression, OHT open-hole tension, IPS in-plane shear, 3PB and 4PB bending. A name whose test code disagrees with `kind` is refused.
  - A material code names one library record, and a layup code names one stacking sequence.
  - `fea/tests/test_coupon.py` checks two things across the models: each code means one thing, and each thing has one code.
- **The title.** The spec's title starts with `<name>, <test>: `, so record titles and deck headings start with the name too.
- **One coupon, one name.** The team's build and its CalculiX twin share one card. The team's own model of the same coupon has the same name: X840PW-UNT-L1 is the team's tension coupon.
- **Where the name shows:**
  - every generated deck heading (the name, the test and the four entered keys);
  - the team comparison: its title, its card and its zip README;
  - `our-models.zip`: one folder per coupon name, and in the README each card and a key to the codes, built from the coupons zipped;
  - the title page of each record document.
- **No title in the manifest.** The team-comparison manifest loses its `title` key, so the name comes from the spec only.
- **The codes today:**
  - X840PW: X840-Z60 plain-weave fabric, `x840-z60-pw`;
  - UNT, UNC and OHT;
  - L1: the team's layup (the codes table is local, ADR-0042).

  This gives X840PW-UNT-L1, X840PW-UNC-L1 and X840PW-OHT-L1.

## Why (evidence)

- The findings above come from the team's deck, replay and slides and from the text of Chen 2015 (local copies). The commands are in the evaluation note.
- The three CalculiX twins were re-run after their deck headings changed. Every recorded number is unchanged to 1.4e-5 relative; the largest change is 8e-8 MPa on a 0.0057 MPa shear stress.
- The team comparison still finds every item the same and the same agreement in the gauge (numbers in a local note (ADR-0042)).
- `uv run pytest -q -ra tests ../engine/tests` passed 729 tests with none skipped.

## Consequences

- **What the name tells.** Every document and zip names the coupon, and the card states plainly that no coupon has a standard or test data yet. The comparison with the team stays solver against solver.
- **New codes.** A new material or layup needs a new code, listed in `fea/models/README.md`.
- **The decks changed** (their headings only), so the records were re-run.

## How we will know it was wrong

Revisit if two coupons with the same material, test and layup but different sizes are needed: the uniqueness test will refuse the second, and the name will need a size code. Revisit also if the team or the cofounder name the same coupons differently.

## Amendment 1, 2026-11-06 (a blank material code is derived, never asked for)

**Context.** The chat asked for the material code in its last step and the example form pre-filled `IM7`, so a new library material was refused with "this material has no code yet; give one" unless the engineer invented a code, and any other material with the pre-filled code was refused as a clash. The founder (2026-11-06): "The layup code, material code, is confusing, any user will just put anything, doesn't make sense for user to put that for no reason." The layup code was already automatic when blank.

**Options.** (1) Keep the codes as typed rows and explain them better: rejected, the row is work with no meaning to the engineer. (2) Drop the codes and name coupons by a number: rejected, the name would no longer say the material, the test and the layup, and every folder, deck heading and record carries the name. (3) Derive a blank material code as the layup code already is, keep both rows as optional overrides for the team: chosen.

**Decision.** `intake.designation_for` derives a blank material code with `derived_material_code`: the library record's id without its punctuation (`im7-8552` gives `IM78552`; an id that starts with a digit gets `M` in front) when that code is free, else the next free `M<n>`, which is also what a set of own constants gets. The reuse-first lookup runs before any derivation, so a material that already has a code (IM7, X840PW, AS4 on the founder's machine) keeps it, and a code still means one thing. The two rows stay on the form as optional overrides with the refusals of this record; the chat no longer asks for them, the example form no longer pre-fills one, and the workspace shows them on its Advanced panel only ([ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md)). A same-name variant (same material, test and layup, another size) is told apart by the project's name and its attempt number; a size code is still deferred, as "How we will know it was wrong" foresaw.

**Evidence.** `cd fea && uv run pytest -q tests/test_intake.py tests/test_checks.py tests/test_values_input.py tests/test_coupon.py tests/test_studio_tool.py` (2026-11-06): a coupon of AS4/8552 without a code is `AS48552-UNT-L1`, one of own constants `M1-UNT-L1`, IM7 and L1 are reused for the public coupon, and a given code that clashes is still refused by name; `lib/coupon-form-definition.json` regenerated with the new help text, held equal to the package by `test_studio_tool.py`.

## Amendment 2, 2026-11-10 (a stored coupon whose spec no longer loads keeps its codes and stops nothing else; found on the hosted site)

**Context.** Naming a coupon reads every stored coupon's spec, and so did the coupon list. On 2026-11-10 the hosted store held a dog-bone saved before ADR-0075 amendment 1 required its extensometer to lie in its narrow section; its spec no longer loaded, and the first refusal stopped every setup check, live solve and list on the site ("strain.gauge_length (44) must lie within the dog-bone's narrow section").

**Options.**
1. *List it apart and keep its codes* (chosen). `stored_coupons` returns the specs that load and, apart, those the current rules refuse with why; naming reserves a refused coupon's material and layup codes by its folder's name, so no new coupon takes them with another meaning, and the list shows it with its reason.
2. *Skip it.* Rejected: a new coupon could take its codes with another meaning, and with its name, write into its folder.
3. *Load it with the newer rules relaxed.* Rejected: every rule would need an old and a new form.

**Decision.** Option 1, in `fea/src/anisotropy_fea/intake.py` (`stored_coupons`, `designation_for`) and `fea/tools/studio_tool.py` (`coupons`, `values`: reopening it says why it cannot be). A code held only by such a coupon is refused with its name and the reason; the engineer gives another code, or the coupon is fixed or removed.

**Evidence.** `fea/tests/test_studio_tool.py`: `test_a_stored_coupon_the_rules_now_refuse_does_not_stop_the_others` and `test_a_refused_coupons_codes_stay_its_own`, on the public D638 spec with its extensometer stretched past the narrow section.
