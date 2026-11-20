# ADR-0125: A spar cap is a strip of each skin over each web with its own layup, any layup may change in zones along the span, and the hand calculation works a section per stretch

- Status: Proposed; the finite element check and the STEP file take caps and zones since amendment 1
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 ("Plan order: project, rules, caps, chat", the order of the wing chat's plan, whose third step is this; and "Strip of skin over each web", the choice on how a spar cap is defined) | Drafted by: Claude Code
- Related: [ADR-0115](ADR-0115-a-wing-is-one-description-worked-first-as-a-beam-by-the-engine-over-every-flight-case-at-once-and-the-finite-element-model-of-the-same-description-is-its-check.md), [ADR-0116](ADR-0116-a-wings-shape-is-built-by-gmsh-opencascade-from-the-same-description-as-surfaces-at-mid-thickness-and-its-step-file-names-every-part.md), [ADR-0117](ADR-0117-a-wing-is-checked-in-calculix-with-composite-shells-under-superposed-load-patterns-its-panels-buckle-as-the-engines-ritz-plates-on-the-models-loads-and-flutter-is-a-typical-section-estimate.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0123](ADR-0123-a-layups-design-rules-are-judged-by-the-engine-on-the-stack-alone-as-warnings-with-their-limits-in-the-wing-file-and-change-no-number-of-the-analysis.md), `engine/src/anisotropy_engine/wing/description.py`, `engine/src/anisotropy_engine/wing/section.py`, `engine/src/anisotropy_engine/wing/analysis.py`, `engine/src/anisotropy_engine/layup_rules.py`, `components/workspace/wing-rail.tsx`
- Area: engine, fea, website

## Context

The founder asked on 2026-11-19 that the wing's chat take "Add 2 0 plies to the spar caps from the root to 40% span", and that its answers draw on ply drop ratios among other rules. A wing had one layup for each part, the same from root to tip, and no spar caps: the skin ran whole between the spars, and nothing in the engine could say where a ply ends. The wing chat's plan puts caps and changes along the span in the engine before the chat (its step 3), so the chat of step 5 only fills in a description the engine already reads. The plan offered three ways to define a cap; the founder chose "Strip of skin over each web": the upper and lower skin over each spar get a layup and width of their own, which can change along the span, and the rest of the skin keeps its own layup.

## Options considered

1. **What a spar cap is.**
   - (a) A strip of each skin centred on each web, as wide as given along the chord, with a solid layup of its own. Chosen by the founder: it is how a composite box is laid up, and its plies are a skin's plies, checked the same way.
   - (b) A flange of the web, an L or a C bonded to the skin. Not chosen: a part of its own, with a bond line to model.
   - (c) A concentrated area at each corner (a boom). Rejected: no plies to check, and the chat could not add a 0° ply to it.
2. **How a layup changes along the span.**
   - (a) Zones on any layup, the skin's, the spar web's or the caps': each a stretch of the half span with a half stack of its own, from a start to an end as fractions of it, the part's own stack outside its zones. Chosen: "root to 40 %" is a zone, and the same table serves every part. A rib stands at one station and has none.
   - (b) A stack per station. Rejected: hard to type and to read, and a wing changes at a few places.
3. **The section with caps.**
   - (a) Each stretch of a skin, a cap, the panel between the caps and the other cap, at its own mid-surface under the airfoil's surface, joined by a straight step where they differ; the step passes the shear flow on and carries no spanwise load; the half of each cap outside the box an open flange whose flow is nothing at its free edge and joins the cell's at its corner. Chosen: the shell model of ADR-0116 will place the parts the same way in the second slice, and it keeps the cell's equilibrium exact.
   - (b) The cap and the skin at one mid-surface. Rejected: a solid cap beside a cored skin would sit inside the core, and the web's height would be wrong by half the difference.
   - (c) The cap inside the box only. Rejected: half of its plies, the half outside, would carry nothing and be checked nowhere.
4. **Along the span.**
   - (a) One section per stretch of constant layup; the stations the equally spaced ones and every change twice, once with each side's section; the first bending frequency of a beam of about 200 cubic elements with an edge at every change; divergence and reversal with each stretch's section taken as the whole wing's, the lowest kept. Chosen: every check stays the hand calculation of ADR-0115, and a wing without changes gives what it gave.
   - (b) A section blended across a change. Rejected: a ply drop is a step, and a blend would put stiffness where there are no plies.
5. **Ply drops.**
   - (a) Three rules at each change, warnings as in ADR-0123: at most 2 plies ending at one place, both halves counted; a run-out of 20 times the thickness that ends, which must fit in the thicker side's stretch; and the outside ply running on over the ends. The plies that end are found by matching the thinner stack to the thicker from the outside; a change that cannot be matched so changes angle or order and fails the third. Their limits `drop_ratio` and `max_dropped` are in `[design_rules]`. Chosen: each needs only the two stacks and the stretch's length, and a designer may set them aside with a reason.
   - (b) The drop's taper in the stiffness. Left out: a few millimetres of run-out on a stretch of hundreds.
6. **The finite element check and the STEP file.**
   - (a) Both refuse caps and zones, by name, until the second slice builds them. Chosen: the hand calculation, the page and the rules come first; a check of another wing than the one on the page would mislead.
   - (b) Build them now. Deferred to the second slice: the shell model needs each part's offset from its mid-surface and the shape needs its faces cut at every cap edge and zone edge.

## Decision

Options 1(a), 2(a), 3(a), 4(a), 5(a) and 6(a). A wing file takes an optional `[spar_caps]` table (`front_width`, `rear_width` in the length unit, `half_stack`, solid) and an optional `zones` list on `[skin]`, `[spar]` and `[spar_caps]`, each zone an inline table `{ start = 0, end = 0.4, half_stack = [...] }`. The engine refuses zones that overlap or leave 0 to 1, a rib with zones, caps that meet between the spars or reach the leading or trailing edge, a cap with a core, and a cap thicker than the airfoil where it lies. `span_segments` cuts the wing wherever any part's stack changes; `box_section` takes a segment; `analyze_wing` works one section per stretch. The report adds the masses of the caps, the cap's modulus and thickness, one row per stretch (`stretches`: start, end, EI, GJ, shear center, mass per length), the drop limits in `rule_limits`, and for each rule its `span` (a stretch's start and end, fractions of the half span) or `at` (a change). The drawings add the caps' mid-surfaces and the stations of the changes. The wing page adds a Spar caps box (add, widths, half stack, zones, rules, remove) and a "Change the plies along the span" list under the skin, the spar web and the caps, with each part's rules grouped by stretch and by drop.

## As built (2026-11-20)

- `Zone`, `Layup.zones`, `Layup.stretches`, `Layup.with_stack`, `SparCaps`, `Wing.spar_caps`, `Wing.cap_edges_m`, `Wing.has_zones`, `SpanSegment` and `span_segments` in `engine/src/anisotropy_engine/wing/description.py`.
- `engine/src/anisotropy_engine/wing/section.py`: `mid_surface_heights` with a thickness, `PointSet`, the runs of `box_section` with the steps and flanges, per-metre masses (`mass_skins_kg_m`, `mass_caps_kg_m`, `mass_spars_kg_m`, `mass_core_kg_m`), `skin_panel_widths_m`.
- `engine/src/anisotropy_engine/wing/analysis.py`: `Stretch`, `WingResult.stretches`, `WingResult.first_bending_frequency_Hz`, `WingResult.mass_kg(part)`, `stations_of`, `bending_frequency` (with `_beam_nodes`, which keeps no element shorter than a quarter of the others), `lowest_aeroelastic`, and the ply checks per stretch of wall.
- `engine/src/anisotropy_engine/layup_rules.py`: `ply_drop_rules`, the limits `drop_ratio` (1 to 200, default 20) and `max_dropped` (a whole number of at least 1, default 2), and their sources; `engine/docs/theory.md` section 15.
- `engine/src/anisotropy_engine/wing/wing_file.py`: `[spar_caps]`, `zones`, the drop limits, `wing_rules` with `span` and `at`, the report's and the drawings' new entries.
- `fea/src/anisotropy_fea/wing_model.py` and `fea/src/anisotropy_fea/wing_shape.py` refuse caps and zones by name.
- `lib/wing.ts` (`SPAR_CAP_FIELDS`, `newSparCaps`, `zonesOf`, `withZones`, `newZone`, `spanWords`, inline tables in the wing file), `lib/wing-versions.ts` (labels of the caps and zones), `components/workspace/wing-rail.tsx` (`SparCapFields`, `ZonesFields`, `ZoneRow`, rules grouped by stretch and drop), `components/workspace/wing-stage.tsx` (caps in the section, their edges and the changes on the planform, EI and GJ per stretch, the caps' mass), `app/workspace/workspace.css`.
- `scripts/wing-choices.py` writes a second answer, `tests/fixtures/wing/caps-answer.json`: the example with the caps the page adds and a cap zone from the root to 40 % with one more 0° ply each side of the middle, checked against the API like the first.
- Numbered ADR-0125: the workspace's sections (pull request #249) took ADR-0124 first.
- A wing without caps or zones gives every number it gave to the last digit or two of a double (the sums run in another order); `tests/fixtures/wing/example-answer.json` differs only there and by the new keys.

## Why (evidence)

- `cd engine && uv run pytest -q tests/test_wing_caps.py`: 28 passed, 2026-11-20. A flat-sided box with caps summed by hand strip by strip: its $`EI`$, its $`GJ`$ by Bredt-Batho with the steps in the loop, its enclosed area and its masses agree within $`10^{-12}`$. On NACA 2412 and 0012 boxes with caps of 50 mm and 40 mm, the shear flow with the steps put back carries a unit shear (within the 0.1 % of the trapezoid rule) at the shear center and is nothing at each flange's free edge; the bending load sums to the moment within $`10^{-12}`$ and to no force. The beam of a uniform wing cut at 40 %, 37 % and 12.35 % of the span gives the closed-form frequency within $`2\times10^{-6}`$.
- `cd engine && uv run pytest -q`: 690 passed, 2026-11-20 (the whole engine suite, the wing's earlier tests unchanged but for the masses now per metre).
- The example with the caps of the page and the cap zone (`tests/fixtures/wing/caps-answer.json`): every case passes, the lowest margin +0.940 (web buckling, case 6); EI 39,613 N·m² from the root to 40 % and 34,762 N·m² beyond; the caps 1.13 kg of 2.93 kg; the first bending frequency 23.1 Hz against 19.6 Hz without caps; each drop rule met (2 plies end, 7.32 mm of run-out in 800 mm, the outside ply runs on); the caps miss the 10 % rule as the skins do.
- The drop rules' sources are common practice as the plan states them, not yet read in a primary source: UNVERIFIED. The reference pages of step 4 must read them and correct the defaults or the words if they differ.
- Divergence and reversal of a changing wing are an estimate, not a bound (theory section 15); no stretch-by-stretch solution was compared.

## Consequences

- The chat of step 5 can turn "Add 2 0 plies to the spar caps from the root to 40% span" into one cap zone, and the engine's answer says what it changes and which rules it meets.
- The finite element check and the STEP download refuse a wing with caps or zones until the second slice, so for now the hand calculation is the only answer for such a wing.
- The skin outside the box, but for the caps' outer halves, is still in neither the stiffness nor the mass. So a wing with caps reads heavier than it is by the skin those outer halves replace: on the example's 45 mm caps about 0.47 kg of its 2.85 kg, worked by hand (four strips 22.5 mm wide and 2 m long of the cored skin's 2.6 kg/m²), not by the engine.
- A cap is the same width from root to tip; a cap that narrows toward the tip needs another table.

## How we will know it was wrong

- The finite element model of the second slice, with the caps at their offsets, puts EI, GJ or the shear center of a capped box further from the hand calculation than ADR-0117 found for the plain box (2 %, 4 % and 0.3 mm).
- The founder's wings need caps of another shape (a flange of the web, a cap that narrows), or zones that are not a stretch of the half span.
- A primary source gives other drop limits, or a designer reads a drop warning as a failed wing.

## Amendment 1, 2026-11-20 (the second slice: the finite element check and the STEP file take caps and zones)

**Context.** Option 6(a) refused caps and zones in the finite element check and the STEP download until the second slice, so a wing with caps had only its hand calculation. Option 6(b) named what the second slice needs: each part's offset from its mid-surface in the shell model, and the shape's faces cut at every cap edge and zone edge.

**Options.** (a) One reference surface for every skin and cap face, the caps' mid-surface at the root (the skin's at the root when the wing has no caps), each face's shells offset to its own mid-surface with CalculiX's `OFFSET`, in thicknesses along the normal as in Abaqus. Chosen: the webs then run between the caps' mid-surfaces as in the hand calculation (option 3(a)), the faces stay joined so the mesh is one piece, and where two faces of different offset or thickness meet CalculiX's knot keeps the step between their mid-surfaces. (b) Each face drawn at its own mid-surface, with step faces between them. Rejected: the step faces would be parts of their own, with plies and a section, that the hand calculation does not have. (c) The faces at the airfoil's surface, every one offset inward by half its thickness. Rejected: the webs would end at the airfoil's surface, longer than the hand calculation's by the caps' thickness, and every face would need an offset, the plain wing's too.

**Decision.** Option (a). The shape cuts each skin at the caps' four edges with planes across the chord, then each face where its own stack changes with planes across the span; the webs only where the spar's stack changes; a rib stays whole. Each face is a part of its own in the STEP file, named by its place and stretch ("Upper front spar cap, root to 40 %", "Upper skin, between the caps, 70 % to tip"), and the part table gives its offset, how far inside the drawn face its mid-surface lies: in a CAD program, move the face inward by it, then thicken both sides by half. The finite element model gives every face a shell section of its own stack and offset; a cap's plies count with the skin's in the checks; the box of `skins="box"` keeps each cap whole, its outer half too, and no skin outside the webs; the airload of the box goes from the front cap's fore edge to the rear cap's aft edge; a skin panel runs between the caps' inner edges, and a rib bay a zone's edge crosses is a panel per stretch with the bay's length, each of its own layup. A wing without caps or zones is drawn, meshed and solved as before.

**Evidence.**
- `cd fea && uv run --extra mesh pytest -q tests/test_wing_shape.py tests/test_wing_model.py tests/test_wing_check.py`: 49 passed, 2026-11-20 (the plain wing's earlier tests unchanged).
- The capped box of the example (45 mm caps of [0/0/45/-45/0]s, no zones) against `box_section`, at 40 mm elements: EI +0.3 %, GJ +4.3 %, shear center 0.34 mm aft (chord 450 mm). The plain box the same day at 40 mm: +2.0 %, +4.2 % and 0.22 mm. With every offset set to nothing the capped box was +13 %, +28 % and 2.6 mm off: the offsets are what bring it in. GJ is as close as the plain box's, whose 4 % is the clamped root holding the box's warping (ADR-0117); the shear center is 0.12 mm further than the plain box's and 0.04 mm past the 0.3 mm this record set as the mark of a wrong model; no cause was found, the step joint (rigid in the model, a wall of the skin's shear stiffness in the hand calculation) the likeliest. Recorded rather than hidden; a finer study is open.
- The example with caps, the cap zone from the root to 40 % and a thinner skin from 70 % to the tip, through `wing_check` at 40 mm: tip deflection 34.31 mm against the hand calculation's 34.20 mm in case 1; the lowest margin outboard of the root zone +1.080 against +1.073, both the upper front cap's 0° ply in case 6.
- The STEP file of that wing read back: 27 faces, each name with its area to 1e-9 and the extent its cuts give it.

