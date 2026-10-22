# ADR-0038: Every coupon model carries an identity card and a name of the form material-test-layup

- Status: Proposed; the folders carry the name too, by [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md) (option 4 taken after all)
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (the coupon's name, such as X840PW-UNT-L1, is the title, with the type of test; the team's tension coupon has the same name as ours) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/spec.py` (`Coupon`, `coupon_card`), `fea/tests/test_coupon.py`, [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [ADR-0036](ADR-0036-one-folder-per-fea-test.md), [evaluation](../evaluations/fea/2026-10-21-coupon-identity.md)

## Context

The founder could not tell which coupon was being compared. Folders, specs and documents named only the kind of test: `tension-coupon`, "Tension coupon", "Tensile Coupon". What the files say:

- **The team's files.** The deck says `Job name: Tension-test Model name: Model-1` and the part is `CFRP-Coupon`. The slides say "Tensile Coupon, Static General". The Abaqus/CAE replay (`abaqus.rpy.1`) opens a class tutorial model, `SE253-HW1-Tutorial3-2023-HF2.cae`, and then draws a new 10 mm by 80 mm rectangle. No standard or specimen name appears anywhere.
- **The material.** The team typed the "Fabric" row of Chen 2015, Table 3.1 (X840-Z60 plain weave, E1 = E2 = 80 GPa). That row is our library record `x840-z60-pw`.
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
- **One coupon, one name.** The team's build and its CalculiX twin share one card. The team's own model of the same coupon has the same name: X840PW-UNT-L1 is the team's Tension-test.
- **Where the name shows:**
  - every generated deck heading (the name, the test and the four entered keys);
  - the team comparison: its title, its card and its zip README;
  - `our-models.zip`: one folder per coupon name, and in the README each card and a key to the codes, built from the coupons zipped;
  - the title page of each record document.
- **No title in the manifest.** The team-comparison manifest loses its `title` key, so the name comes from the spec only.
- **The codes today:**
  - X840PW: X840-Z60 plain-weave fabric, `x840-z60-pw`;
  - UNT, UNC and OHT;
  - L1: [0/45/-45/45/0]s.

  This gives X840PW-UNT-L1, X840PW-UNC-L1 and X840PW-OHT-L1.

## Why (evidence)

- The findings above come from the team's deck, replay and slides and from the text of Chen 2015 (local copies). The commands are in the evaluation note.
- The three CalculiX twins were re-run after their deck headings changed. Every recorded number is unchanged to 1.4e-5 relative; the largest change is 8e-8 MPa on a 0.0057 MPa shear stress.
- The team comparison still finds 23 of 23 items the same and 0.43 % agreement from y = 25 to 55 mm.
- `uv run pytest -q -ra tests ../engine/tests` passed 729 tests with none skipped.

## Consequences

- **What the name tells.** Every document and zip names the coupon, and the card states plainly that no coupon has a standard or test data yet. The comparison with the team stays solver against solver.
- **New codes.** A new material or layup needs a new code, listed in `fea/models/README.md`.
- **The decks changed** (their headings only), so the records were re-run.

## How we will know it was wrong

Revisit if two coupons with the same material, test and layup but different sizes are needed: the uniqueness test will refuse the second, and the name will need a size code. Revisit also if the team or the cofounder name the same coupons differently.
