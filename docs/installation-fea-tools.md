# Installing the finite element tools | 2026-10-15

What each tool is for, where to get it, and how our code finds it. Everything here is UNVERIFIED until it has been run on the machine in question; the evaluation note of the chunk that first uses a tool pastes its version line.

| Tool | What it is for | Needed by |
| --- | --- | --- |
| Python packages in `fea/` (`uv sync`) | our reader, mesher, writers, kernel, plots, VTK export | every chunk |
| Gmsh (Python package `gmsh`, 4.15.2 installed 2026-10-19) | meshing geometries the structured mesher cannot: the open-hole coupon's O-grid (chunk A2) | optional extra `mesh`; tests skip with a reason without it |
| CalculiX (`ccx`) | the independent reference solver that runs our generated decks | chunk B onward, optional |
| PrePoMax | a free Windows GUI bundling CalculiX: opens our CalculiX decks and `.frd` results | optional, founder's machine |
| ParaView | opens the `.vtu` files our examples write | optional |

## Installed on the founder's machine (2026-10-15)

- **PrePoMax v2.6.0** (portable zip from https://prepomax.fs.um.si/Files/Downloads/PrePoMax%20v2.6.0.zip, 209 MB, 223 files) unpacked to `C:\Tools\PrePoMax v2.6.0\`; the archive is kept in `C:\Tools\downloads\prepomax\`. It bundles **CalculiX 2.22** as `Solver\ccx_dynamic.exe` (its `-v` prints "This is Version 2.22"), a Gmsh caller, NetGen, and `Tools\abqodb_to_ccxfrd.py`. .NET Framework 4.8 is present.
- **`ANISOTROPY_CCX`** is set for the user to `C:\Tools\PrePoMax v2.6.0\Solver\ccx_dynamic.exe` (new shells see it; this session's shells may not).
- **Smoke run**: a one-element isotropic S4 plate (10 mm square, 2 mm thick, bottom edge fixed, top edge held in x and pulled 0.1 mm) ran in 0.2 s with no error. The `.dat` reports the total force on the top set as 1.571092E+04 N and the element stresses `sxx = 259.23`, `syy = 785.55` MPa at all eight integration points: with both edges held in x the state is `sigma_y = E eps / (1 - nu^2) = 70000 x 0.01 / 0.8911 = 785.5 MPa` and `sigma_x = nu sigma_y = 259.2 MPa`, so the solver and the deck conventions agree with the closed form. Files under `.local/fea/checks/calculix/smoke/`. The `.dat` block headers seen: `forces (fx,fy,fz) for set TOP and time`, `total force (fx,fy,fz) for set TOP and time`, `displacements (vx,vy,vz) for set TOP and time`, `stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz) for set EALL and time`, each stress row ending with a `_shell_0000000001` tag; a shell gives eight integration points per element. This resolves the "wording of the forces and totals blocks" item; the composite-shell conventions (layer order, points per layer, orientation, shear strain) remain for the detection run.
- **Abaqus 2025** (checked 2026-10-24): `C:\SIMULIA\Commands` is on `PATH` (`abaqus.bat`, `abq2025.bat`); `abaqus python` is Python 3.10.5. Its licence is UC San Diego's FlexNet server (`34000@its-flex-srv.ucsd.edu`, `academic=TEACHING`): usable for the course and the team comparison, never for a customer deliverable, and only while the machine reaches that server. Every solve takes tokens from a shared pool. An ODB opens only in its own Abaqus version or newer, so the team's 2026 ODBs cannot be read here; the extraction script travels to whoever made the ODB (ADR-0045).

### Opening our models in PrePoMax

Start `C:\Tools\PrePoMax v2.6.0\PrePoMax.exe`. File, Import, choose an Abaqus input file, and pick a generated deck, for example `.localeabaqusNnotched-im7-8552ours
odalNnotched-im7-8552-nodal-abaqus.inp` (written by `fea/examples/build_model.py`; the committed copy is in `fea/checks/unnotched-im7-8552/decks/`). Whether PrePoMax takes the part-and-instance structure, the composite shell section with five-field layer lines and the LAMINA material of that deck is UNVERIFIED (the manual says its syntax is mostly common with Abaqus); the CalculiX-dialect deck that the next chunk writes is the one meant for it. Results from CalculiX (`.frd`) open through File, Open results. The smoke run's `.frd` under `.local/fea/checks/calculix/smoke/` is a first file to try.

## Founder's Windows 11 machine (the steps, for a second machine)

1. **Gmsh**: from `fea/`, `uv sync --extra mesh` (the extra declares `gmsh>=4.13`; PyPI's Windows wheel gave 4.15.2 on 2026-10-19). Check with `uv run python -c "import gmsh; print(gmsh.__version__)"`. Only `fea/examples/build_model.py`, `run_calculix.py` and `docs/models/build.py` on an `open_hole_tension` spec or record need it; the committed decks and the validation cases do not. On Ubuntu the wheel also needs the system library libGLU (`sudo apt-get install -y libglu1-mesa`); without it `import gmsh` raises `OSError` and `gmsh_available()` reports None.
2. **CalculiX through PrePoMax** (recommended): download the portable zip from https://prepomax.fs.um.si/downloads/, unzip to a folder such as `C:\Tools\PrePoMax\`, and find the bundled solver under its `Solver` folder (`ccx_*.exe`). Set the environment variable `ANISOTROPY_CCX` to that executable's full path, or add the folder to `PATH`. PrePoMax needs .NET Framework 4.8. The bundled CalculiX version is recorded when installed (planned v2.6.0 stable).
   - Alternatives: the Windows builds listed on http://www.dhondt.de (bConverged, calculixforwin on SourceForge, the GE GitHub build) for a newer `ccx`; or WSL Ubuntu-24.04 with `sudo apt install calculix-ccx` (2.21), which our runner can only use through a wrapper script (not provided yet).
3. **ParaView**: installer from https://www.paraview.org/download/. Open a `.vtu` from `.local/fea/checks/vtk/` or any `ours/` folder under `.local/fea/`, press Apply, colour by a field, Warp By Vector on Displacement.

## Continuous integration (GitHub Actions, ubuntu-latest)

The `fea` job runs `sudo apt-get update && sudo apt-get install -y calculix-ccx` (package in Ubuntu 24.04 universe, binary `/usr/bin/ccx`, version 2.21), prints `ccx -v` into the log (it exits with code 201 after printing, so the step tolerates that), then `uv sync --locked --extra mesh` so Gmsh is present (chunk A2; `libglu1-mesa` is installed beside CalculiX because the Gmsh wheel loads libGLU). The `manual` job installs the same library and runs the model documents with `--extra mesh`, since the open-hole record's document regenerates its mesh. Tests that need a tool skip with a stated reason when it is absent, so a missing tool never fails the suite silently.

## How the code finds the tools

- `anisotropy_fea.calculix.find_ccx()` (chunk B): an explicit path argument, then `ANISOTROPY_CCX`, then `ccx` on `PATH`.
- `anisotropy_fea.abaqus.find_abaqus()` (ADR-0045): an explicit path argument, then `ANISOTROPY_ABAQUS`, then `abaqus` on `PATH` (on Windows the `.bat` under `C:\SIMULIA\Commands`). `run_abaqus` solves a deck in the foreground (`abaqus job=<job> input=<job>.inp interactive ask_delete=OFF`) and reads the `.dat`, `.msg` and `.sta` for errors, since Abaqus exits with code 0 after an input error; `extract_fields` runs `fea/tools/abaqus_extract_fields.py` under `abaqus python`, which imports nothing of ours. Abaqus is optional: nothing in the pipeline needs it, and the tests that use it skip when it is absent.
- Gmsh: `anisotropy_fea.mesher.gmsh_available()` returns the version or None; `gmsh_open_hole_plate` raises `MeshError` with the install command when the package is missing.

## What stays out of the repository

Solver outputs (`.dat`, `.frd`, `.sta`, `.cvg`, `.12d`) and figures are written under `.local/` and are git-ignored; the committed artefacts are the specs, the generated decks and the comparison records holding numbers with provenance (ADR-0007, ADR-0030).
