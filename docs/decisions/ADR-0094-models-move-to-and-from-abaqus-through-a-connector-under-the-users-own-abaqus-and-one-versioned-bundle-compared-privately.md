# ADR-0094: Models move to and from Abaqus through a connector under the user's own Abaqus and one versioned bundle, compared privately

- Status: Proposed. Step 1 of the build order is built (the bundle format and the comparison command); the rest is a plan. Parts 6, 7 and 8 of the Decision were confirmed by the founder on 2026-11-12
- Date: 2026-11-12
- Decided by: Founder, 2026-11-12 ("plan this before implementing anything"; then "i think we should make this more automated"; "if user wants to easily interchange between abaqus and our software we need to create that ease"; "make the interface very friendly for the user"; and, on a card, "Start with the decision record"; his words with the spelling corrected); 2026-11-12 ("yes on all", on parts 6, 7 and 8 as put to him) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0029](ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md), [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md), [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md) (amendment 3 stays), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md) (one exception, part 7), `fea/src/anisotropy_fea/abaqus_reader.py`, `fea/src/anisotropy_fea/equivalence.py`, `fea/tools/abaqus_every_output.py`, `fea/tools/compare_every_output.py`

## Context

One of the team is building a tension coupon in Abaqus/CAE to the standard the studio offers (D3039). The founder asked which of the files we need to learn from it, and whether a script in our backend can read them.

- **The way out today** is the job's solver input (`.inp`), which Abaqus/CAE imports as a mesh without geometry, and the package document's step-by-step guide, followed by hand.
- **The way in today** is the command line on the founder's machine: `abaqus_reader` reads a deck, `equivalence` compares two models item by item, and the package's `5-verify/` scripts read an ODB and judge every output by zone (ADR-0089 amendment 3). The hosted site takes no model.
- **`.odb` and `.cae` are binary.** Every open-source reader of them found on 2026-11-12 runs inside Abaqus's own Python (see Why). The hosted tier has no Abaqus and cannot have one: the only licence is a teaching licence on the founder's machine (`fea/tools/run_abaqus.py`).
- **Runs are not private.** `records.list_jobs` and `GET /v1/coupon-jobs` list every job to every signed-in user; only projects check an owner (`records.owns_project`).
- **The workspace never names Abaqus** (ADR-0091, `BANNED_TERMS` in `lib/studio-copy.ts`).
- The team's models never enter this repository (ADR-0042), and only the unnotched tension coupon is offered (ADR-0089).

## Options considered

1. **Files by hand**: the user exports reports from CAE and uploads them with the deck. Rejected by the founder: "we need to be able to read his files without him downloading csv per csv".
2. **Read `.odb` and `.cae` on our server with an open-source library.** Rejected: none was found that works without Abaqus.
3. **Run Abaqus on our server.** Rejected: no licence that allows it (ADR-0056).
4. **The results file** (`.fil`, which a deck may ask for and which is documented and readable without Abaqus). Kept as a later, optional route. It does not carry the model as built in CAE, the user must edit the deck, and whether it carries every ply's values is UNVERIFIED.
5. **A connector that runs under the user's own Abaqus and writes one bundle; a build script for the way out.** Chosen.
6. **For the assistant, adopt an agent framework** such as FEA_Assisted_Agent (three tools in a loop on one fixed cantilever, no tests). Rejected: the pattern of three tools is kept, its code is not, and no model writes a number (ADR-0001).

## Decision

1. **One bundle, one format, both directions.** A zip with a manifest (`bundle_version`, the unit system as stated, the Abaqus version, the connector's version, the time, a SHA-256 per file), the `.inp` as solved, the model as built (parts, sections, layup, orientations, materials, boundary conditions, step and mesh controls, read from the `.cae` into JSON), the results per element and ply in the columns of `abaqus_every_output.py` with the reactions, and the `.jnl` as text. A bundle that breaks a rule is refused with every reason (ADR-0003). Nothing in a bundle is ever executed by us: a `.jnl`, `.rpy` or script is stored and read as text.
2. **The way in is a connector**: one script, the standard library only, run by the user with their own Abaqus. Version 1 is one command that writes the bundle from a job's `.odb` and its `.cae`. A menu in CAE ("Send to Anisotropy", "Open from Anisotropy") and a watched folder come after it.
3. **The way out is a build script.** Beside the `.inp`, the studio writes a script from the same spec that CAE runs (File > Run Script) to build a native, editable model: geometry, the composite layup, the step, the grips and the mesh.
4. **The comparison is ours, by tested code.** `fea/tools/abaqus_upload.py check|compare` joins the reader, `equivalence` and the every-output comparison, with ADR-0089's acceptance (the reaction and the gauge within 1 %, the free length within 3 %). A model on a different mesh is compared by position in the gauge and at the reaction, and the result says so.
5. **ADR-0089 amendment 3 stays.** The engineer's own run of `5-verify/` remains the audit's evidence. The upload adds the same comparison on our side, so that it shows beside the run.
6. **An upload is private.** It belongs to the user who sent it, is stored under its own prefix (`uploads/<id>/`) with an owner in a table of its own, and never enters this repository. The connector sends with a token the user creates. Confirmed by the founder: the founders also see an upload; nothing from an upload goes to the assistant's model provider in version 1; a stored bundle may train a later model only when it is the team's own, and an outside user's only by a box they tick.
7. **It shows as a card on the run's page, the answer first** ("Agrees with ours" or what differs, then the model, the pull force, the gauge section, between gauge and tabs), and as a chapter of its own in the document. The validation table keeps its three columns (the founder, 2026-11-08: "open source calculix is enough"). Confirmed by the founder, and a change to ADR-0091: this card, the menu and their downloads name Abaqus, because here it is the user's own program and not a tool of ours; the banned-term test allows the word in these components only.
8. **The assistant gets three fixed tools on the user's machine**: build from our script, run the job, send the bundle. It chooses among them; it writes no Abaqus script that is run and no number (ADR-0048, ADR-0052). Confirmed by the founder.
9. **Scope**: what `abaqus_reader` reads (flat S4 or S4R shells, one linear static step) for the tension coupon of ADR-0089. Anything else is refused with the reason.

Build order, one small pull request each: the bundle format and the comparison command; the connector; the build script; the assistant's tools; storage, tokens and the owner check; the card; the document's chapter; the menu and the watched folder; a bundle opened as a studio project; the results-file route.

## As built (2026-11-12, step 1: the bundle format and the comparison command)

- `fea/src/anisotropy_fea/bundle.py`: bundle version 1, `open_bundle` and `write_bundle`. The roles are `deck` and `every_output` (required), `reactions`, `model` and `journal`. The standard library only, Python 3.10 or later, so the connector can run it under Abaqus's own Python. A bundle may unpack to 256 MiB at most, a limit chosen without a measured job.
- `fea/tools/abaqus_upload.py`: `pack` (a bundle from a deck and the files `abaqus_every_output.py` wrote), `check` (what a bundle holds, and whether it is in scope) and `compare` (a bundle beside a run of ours, from that run's every-output file and deck). Exit 0 agrees, 1 differs or incomplete, 2 refused or out of scope; `--json` writes the result.
- `equivalence.equivalence_without_mesh` and `equivalence.outline`, for two models of one coupon on different meshes; `deck_equivalence` is unchanged.
- Differences from the plan: the results come as the every-output files, not as the field reports of `abaqus_report`, so that module is not joined. On another mesh the pairing is our element nearest each of their centroids, the gauge and the reaction are judged, and the free length is reported only. `compare` needs our deck beside our results. The model as built from the `.cae` has a role in the format and no reader yet: the connector writes it in step 2.

## Why (evidence)

- **The comparison already works on our own deck**: run in Abaqus/Standard 2025, the reaction within 0.007 %, every gauge value within 0.0074 %, every free-length value within 0.65 %, and a part moved and renumbered is paired by position with the same verdict (`fea/checks/d3039-im7-8552/README.md`, ADR-0089 amendments 2 and 3).
- **Open-source readers, read on 2026-11-12.** Paraqus, ODB2VTK, [pylife's odbserver](https://github.com/boschresearch/pylife), abaqustools and [SAPT](https://github.com/gcastellazzi/SAPT) read an ODB through Abaqus's own Python. pybaqus and suanpan read the `.fil` only. [abqpy](https://github.com/haiiliin/abqpy) is type hints for writing scripts and reads no file. [FEA_Assisted_Agent](https://github.com/Farhad-Davaripour/FEA_Assisted_Agent) is described in option 6. A project not listed here is UNVERIFIED.
- **The privacy gap**: `api/src/anisotropy_api/records.py` (`list_jobs` has no owner filter) and `api/src/anisotropy_api/main.py` (`list_coupon_jobs`).
- **Step 1, on our own kernel's runs of the public D3039 check** written in the exporter's columns (`fea/tests/test_abaqus_upload.py`, `fea/tests/test_bundle.py`, 30 tests): the same run agrees item by item and value by value; a coupon drawn about its centre and a bundle in m-Pa agree; a mesh half as fine agrees in the gauge within 0.062 % and at the reaction within 0.045 %, its free length reported and not judged; a gauge value 2 % off, another layup and another size are found. No run of Abaqus is among them: a bundle from a real run is UNVERIFIED.
- **No evidence yet** for: reading the model as built from a `.cae`; a build script whose model reproduces our deck's answer; a token that passes the site's sign-in; a team model on a mesh of its own; the bundle's size for a real job.

## Consequences

- A user with Abaqus moves a model either way with one action and no export by hand; a user without Abaqus loses nothing.
- We depend on the Python inside the user's Abaqus. Abaqus 2025 runs Python 3.10 (`docs/installation-fea-tools.md`); which older versions the connector supports is open.
- The connector is our code on a user's machine, and the repository has no licence file. It cannot go to an outside user before the founder chooses one.
- Showing runs to their owner only is a separate change, needed before outside users.
- The teaching licence allows the team's comparison only, never a customer deliverable.
- A new table, a new storage prefix and a token are added to the hosted tier.

## How we will know it was wrong

- The model that the build script makes in CAE does not reproduce our deck's answer within ADR-0089's acceptance on the D3039 check.
- A user's Abaqus cannot run the connector (its version, or a rule of their company): the results-file route or files by hand becomes the first route.
- An open-source library reads `.odb` without Abaqus: reading on our server is considered again.
- The bundle format needs a second breaking change within three months of version 1.
