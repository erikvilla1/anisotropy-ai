# Evaluation: the local FEA folders in one folder per test, and zip-only handoffs (ADR-0036, chunk 2) | 2026-10-21

- Scope: `.local/fea/` is moved from tool-first (`abaqus/<test>/`, `calculix-prepomax/<test>/`) to test-first: `.local/fea/<test>/{team/<date>/, runs/{kernel,calculix,team-in-calculix}/, comparison/}`, `.local/fea/checks/` and `.local/fea/share/` with zips only.
- Deletions approved by the founder on 2026-10-21: the `prepomax-tension-*` runs and record, the runs and kernel builds under the old spec names, the IM7/8552 local runs, `scratch/`, and the unzipped share folders and old zips.
- Code: `docs/models/team.py` writes one zip and drops `calculix_results`. `docs/models/share.py` finds the models by convention; `docs/models/our-models.toml` is deleted. Both scripts share `write_zip` and `zip_is_ours`.
- Tests and docs: `test_local_tension_deck.py` and `test_convert_deck.py` read `.local/fea/tension-coupon/team/2026-10-16/`. `test_team_document.py` is rewritten for zips. The skill, the readmes and the docstrings are updated.
- Branch: `feat/fea-local-one-folder`, stacked on `feat/fea-one-folder-per-test` (PR #65).

## Commands and captured output

Inventory before and after (`find .local/fea -type f`), accounted for by a scratch script:

```text
before: 270 files, 849 MB          after: 93 files, 218 MB
{'old readme replaced': 8, 'deleted (approved)': 193, 'moved unchanged': 60, 'moved, then rebuilt or path-edited': 8}
new files (rebuilt runs, zips, readmes): 22
problems: 1
   SIZE CHANGED abaqus/tension-coupon/team/README.md -> tension-coupon/team/2026-10-16/README.md: 1550 -> 1687
```

The one size change is the team folder's README, whose links to our folders were edited on purpose. Every file the team sent (deck, `.odb`, `.dat`, `.prt`, `.ipm`, `.log`, replays, CSV reports, slides, template) moved unchanged.

The kernel runs, from `fea/`: `examples/build_model.py models/<test>/<test>.toml --out ../.local/fea/<test>/runs/kernel`

```text
kernel solve: reaction at RF-Top = [-1.92143e-09, 105993] N; equilibrium residual 1.44e-07 N
kernel solve: reaction at RF-Top = [-4.28554e-12, -5060.13] N; equilibrium residual 1.24e-08 N
kernel solve: reaction at RF-Top = [3.45171e-10, 9420.94] N; equilibrium residual 1e-07 N
```

From the root: `docs/models/team.py .local/fea/tension-coupon/comparison/team-comparison.toml` and `docs/models/share.py`

```text
equivalence: 23 of 23 items the same; largest node offset 1.87e-06 mm; 800 elements matched
inner: S11 600/600 agree, largest difference 0.425 %; S22 600/600 agree, largest difference 0.160 %; Mises 600/600 agree, largest difference 0.200 %
Zip written to ...\.local\fea\share\tension-coupon-comparison.zip
3 models zipped to ...\.local\fea\share\our-models.zip
```

The zips are 414,759 bytes (12 files, PDF included) and 2,159,565 bytes (17 files, three PDFs included), and neither holds a `.frd`. Before this chunk they were 3.7 MB and 31 MB.

From `fea/`: `uv run pytest -q -rs tests/test_local_tension_deck.py tests/test_convert_deck.py tests/test_team_document.py` gives `13 passed`, with none skipped, so the local team files were found. `uv run pytest -q` gives `281 passed`. The CI command `uv run pytest -q -ra tests ../engine/tests` gives `718 passed in 90.97s`.

## Not run, UNVERIFIED

- The team opening the new zips.
- Re-running the team's deck in CalculiX from its new folder (`runs/team-in-calculix/` holds the run of 2026-10-16, moved unchanged).
