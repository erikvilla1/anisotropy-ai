# Installing the finite element tools | 2026-10-15

What each tool is for, where to get it, and how our code finds it. Everything here is UNVERIFIED until it has been run on the machine in question; the evaluation note of the chunk that first uses a tool pastes its version line.

| Tool | What it is for | Needed by |
| --- | --- | --- |
| Python packages in `fea/` (`uv sync`) | our reader, mesher, writers, kernel, plots, VTK export | every chunk |
| Gmsh (Python package `gmsh`) | meshing geometries the structured mesher cannot: the open-hole coupon | chunk A2 onward, optional |
| CalculiX (`ccx`) | the independent reference solver that runs our generated decks | chunk B onward, optional |
| PrePoMax | a free Windows GUI bundling CalculiX: opens our CalculiX decks and `.frd` results | optional, founder's machine |
| ParaView | opens the `.vtu` files our examples write | optional |

## Founder's Windows 11 machine

1. **Gmsh**: from `fea/`, `uv sync --extra mesh` (planned in chunk A2; the extra declares `gmsh>=4.13`, PyPI ships a Windows wheel). Check with `uv run python -c "import gmsh; print(gmsh.__version__)"`.
2. **CalculiX through PrePoMax** (recommended): download the portable zip from https://prepomax.fs.um.si/downloads/, unzip to a folder such as `C:\Tools\PrePoMax\`, and find the bundled solver under its `Solver` folder (`ccx_*.exe`). Set the environment variable `ANISOTROPY_CCX` to that executable's full path, or add the folder to `PATH`. PrePoMax needs .NET Framework 4.8. The bundled CalculiX version is recorded when installed (planned v2.6.0 stable).
   - Alternatives: the Windows builds listed on http://www.dhondt.de (bConverged, calculixforwin on SourceForge, the GE GitHub build) for a newer `ccx`; or WSL Ubuntu-24.04 with `sudo apt install calculix-ccx` (2.21), which our runner can only use through a wrapper script (not provided yet).
3. **ParaView**: installer from https://www.paraview.org/download/. Open a `.vtu` from `.local/fea-vtk/` or `.local/fea-models/`, press Apply, colour by a field, Warp By Vector on Displacement.

## Continuous integration (GitHub Actions, ubuntu-latest)

Planned for chunk B in the `fea` job: `sudo apt-get update && sudo apt-get install -y calculix-ccx` (package in Ubuntu 24.04 universe, binary `/usr/bin/ccx`), `uv sync --locked --extra mesh`, and `ccx -v` printed into the log. Tests that need a tool skip with a stated reason when it is absent, so a missing tool never fails the suite silently.

## How the code finds the tools

- `anisotropy_fea.calculix.find_ccx()` (chunk B): an explicit path argument, then `ANISOTROPY_CCX`, then `ccx` on `PATH`.
- Gmsh: `import gmsh` inside a try; `gmsh_available()` returns the version or None.

## What stays out of the repository

Solver outputs (`.dat`, `.frd`, `.sta`, `.cvg`, `.12d`) and figures are written under `.local/` and are git-ignored; the committed artefacts are the specs, the generated decks and the comparison records holding numbers with provenance (ADR-0007, ADR-0030).
