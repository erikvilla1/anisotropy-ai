# Anisotropy engine

Python laminate analysis. It has no web or database code, so it can be tested on its own and called from the API, scripts or notebooks.

## Run the tests

Requires [uv](https://docs.astral.sh/uv/).

```sh
cd engine
uv sync
uv run pytest
```

## Conventions

- SI base units everywhere: Pa, m, N, N/m. Conversion to MPa, GPa, ksi or Msi happens only for display.
- Axis 1 is the fiber direction and axis 2 is transverse in-plane.
- Shear strain is engineering shear: gamma12 = 2 * epsilon12.
- Ply angle theta is in degrees, positive counterclockwise from laminate axis x to fiber axis 1.
- Plies are listed from the bottom face up. z is measured from the mid-plane, positive upward, so the first ply starts at z = -h/2.
- Compressive strengths are entered as positive magnitudes.
- Strength ratio R is the factor on all applied loads at which a criterion predicts failure (Daniel & Ishai's safety factor S_f). Margin of safety is MS = R / FS - 1 for a required factor of safety FS.
- First-ply failure is the onset of damage in one ply, not the ultimate strength of the laminate. Thermal residual stresses are not included yet.
- Invalid input raises an error. The engine never substitutes a default value; the Tsai-Wu interaction term `f12_star` must be given explicitly.

## Modules

| Module | Contents |
| --- | --- |
| `lamina.py` | Ply elastic constants and optional `Strengths` (`Lamina`), and the plane-stress reduced stiffness `Q` |
| `rotation.py` | Stress and strain transformations and the rotated ply stiffness `Q_bar` |
| `laminate.py` | Ply stack (`Ply`), ply interface heights and the laminate `A`, `B`, `D` matrices |
| `response.py` | Applied `Loads`, the 6x6 ABD solve for mid-plane strain and curvature, and strain and stress on each ply face |
| `failure.py` | Maximum-stress and Tsai-Wu strength ratios, margin of safety, and first-ply failure of a laminate |
