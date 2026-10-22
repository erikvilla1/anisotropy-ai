# Evaluation: every coupon model has an identity card and a name (ADR-0038) | 2026-10-21

- **Scope.**
  - A `[coupon]` table in the spec, with its validation, and `coupon_card` for the full card.
  - The six model specs get cards and titles that start with the coupon's name.
  - The name and card are carried into the deck heading, the team comparison and its zip, `our-models.zip` and the record documents.
  - The three CalculiX twins are re-run because their deck headings changed.
- **Branch:** `feat/coupon-identity`, from main at 06f1884.

## What the files say about the coupon

The team's files, in `.local/fea/tension-coupon/team/2026-10-16/`:

```text
Tension-test.inp:  ** Job name: Tension-test Model name: Model-1    *Part, name=CFRP-Coupon
                   *Material, name=X840-Z60 / *Elastic, type=LAMINA / 80000.,80000., 0.06, 6480., 5100., 4070.
slides (pptx):     slide1 "Tensile Coupon | Static General | Last Revised: October 16, 2026"; slides 2-10 Part ... Visualization
abaqus.rpy.1:      openMdb('SE253-HW1-Tutorial3-2023-HF2.cae') ... s.rectangle(point1=(0.0, 0.0), point2=(10.0, 80.0))
                   ... Part(name='CFRP-Coupon' ...) ... CompositePly(... material='X840-Z60' ... thickness=0.1 ...) x 5, symmetric=True
```

What this shows:

- **No name or standard.** None of the files names a specimen or a standard.
- **The material.** The elastic values are the "Fabric" row of Chen 2015, Table 3.1, our `x840-z60-pw`.
- **The layup.** [0/45/-45/45/0]s holds four +45 plies and two −45 plies, so it is not balanced.

Chen 2015 (`pdftotext` of the local copy):

- The list of figures shows coupon tests of three kinds: ENF (Figures 3.3 to 3.10), curved beam (3.13 to 3.22) and shear-tie compression (3.23 to 3.28). No flat tension, compression or open-hole coupon appears.
- Section 3.2.1 reads: "Basic material characterization tests were not conducted in this thesis work because the majority of the linear-elastic, strength, and fracture energy properties were provided by the material manufacturer." The page is printed 79.

## Commands and captured output

The specs load, and each title starts with its coupon name:

```text
compression-coupon-nodal.toml | X840PW-UNC-L1, unnotched compression
compression-coupon.toml | X840PW-UNC-L1, unnotched compression
open-hole-coupon-nodal.toml | X840PW-OHT-L1, open-hole tension
open-hole-coupon.toml | X840PW-OHT-L1, open-hole tension
tension-coupon-nodal.toml | X840PW-UNT-L1, unnotched tension
tension-coupon.toml | X840PW-UNT-L1, unnotched tension
```

`uv run python tools/regenerate_decks.py`:

- **Changed:** the nine decks under `fea/models/`, in their headings only.
- **Unchanged:** the seven decks under `fea/checks/`.

The three CalculiX twins were re-run with `examples/run_calculix.py` into `.local/fea/<test>/runs/calculix/`, and the records were rewritten with `tools/record_from_dat.py` using the flags in each README. The `notes` of each record were restored, because the tool writes them empty unless `--notes` is given; the READMEs now show that flag. The records were compared with the copies saved before the change, number by number:

```text
compression-coupon-calculix.toml: 71 numbers, largest relative change 0.00e+00 (None), largest change of a near-zero value 1.7e-17
open-hole-coupon-calculix.toml: 71 numbers, largest relative change 1.37e-05 (expected.ply_stress_local.CFRP-Coupon-1.1011.10[2]), largest change of a near-zero value 1.2e-11
tension-coupon-calculix.toml: 71 numbers, largest relative change 3.78e-08 (expected.ply_strain_local.CFRP-Coupon-1.395.1[2]), largest change of a near-zero value 6.3e-13
   text keys changed (each): ['deck_kernel_sha256', 'deck_reference_sha256', 'title']
```

The open-hole change is S12 of the far element's top ply: 0.0056820 MPa, against 391 MPa for S22 in the same ply, changed by 8e-8 MPa.

`uv run --project fea python docs/models/team.py .local/fea/tension-coupon/comparison/team-comparison.toml`, after removing the manifest's `title`:

```text
equivalence: 23 of 23 items the same; largest node offset 1.87e-06 mm; 800 elements matched
inner: S11 600/600 agree, largest difference 0.425 %; S22 600/600 agree, largest difference 0.160 %; Mises 600/600 agree, largest difference 0.200 %
```

The first pages of the comparison PDF and of `docs/models/build.py fea/models/tension-coupon/records/tension-coupon-calculix.toml` were rendered and checked by eye: X840PW-UNT-L1 as the title, "Unnotched tension coupon" under it, then the card.

`docs/models/share.py tension-coupon compression-coupon --no-pdf` zips the folders `X840PW-UNC-L1/` and `X840PW-UNT-L1/`. The README has a key to the codes (X840PW, UNC, UNT, L1) and each coupon's card. The full run, `uv run --project fea python docs/models/share.py`, gives `3 models zipped`: 17 files, a CalculiX comparison document in each of `X840PW-OHT-L1/`, `X840PW-UNC-L1/` and `X840PW-UNT-L1/` (69 of 69 values each), and no `.frd`. It was built before the commit, so it is stamped `06f1884 + local changes`; it should be rebuilt after the merge.

From `fea/`: `uv run pytest -q tests/test_coupon.py tests/test_team_document.py` gives `14 passed`, and `uv run pytest -q -ra tests ../engine/tests` gives `729 passed in 96.14s`, with none skipped.

## Not run, UNVERIFIED

- Opening a deck with the new heading in Abaqus/CAE. The heading lines are comments, and the existing ones were already longer than the new ones.
