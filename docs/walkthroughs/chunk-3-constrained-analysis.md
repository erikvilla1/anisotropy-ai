# Chunk 3: solve for moments that enforce a curvature

## What changed

The engine and API can now take known force resultants and a prescribed curvature, then calculate the moments required to achieve it. Enter all three curvatures as zero to keep the laminate flat in classical laminate theory. The existing forward calculator still takes known moments; this new operation is available through the API explorer and Python case calculator. It is the next callable tool for the planned chat harness, not a model connection yet.

## Try the new operation

Start or restart the local API from the repository root:

```powershell
uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs>, expand **POST /v1/laminates/prescribed-curvature**, select **Try it out**, paste `api/examples/flat-cross-ply.json`, and select **Execute**. Or, from another terminal:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/laminates/prescribed-curvature' -ContentType 'application/json' -InFile 'api/examples/flat-cross-ply.json' | ConvertTo-Json -Depth 10
```

The committed example is a constructed analytical check, not measured material data. Its independently expected moments are [-0.36, -0.18, 0] N*m/m. Small nonzero components near zero can be floating-point roundoff; inspect the reported residuals and tolerances. Personal coursework inputs and outputs stay in `.local/`.

For the existing terminal calculator:

```powershell
uv run --project engine python engine/examples/laminate_calculator.py engine/validation/cases/constructed-flat-cross-ply.toml
```

## What is known, constrained and unknown

| Role | JSON fields | Meaning |
| --- | --- | --- |
| Units/convention | `unit_system`, `stacking_order` | Required `SI_BASE` and `bottom_to_top`; no inferred ordering |
| Known material/stack | `material`, `plies` | Pa, metres, degrees, one material and a caller-supplied citation |
| Known forces | `forces.Nx`, `.Ny`, `.Nxy` | N/m; every component required, including explicit zeros |
| Prescribed deformation | `prescribed_curvature_per_m` | Three entries [kappa_x, kappa_y, kappa_xy], 1/m |
| Unknowns returned | `moments_N_m_per_m`, `midplane_strain` | Required [Mx, My, Mxy] and [eps_x, eps_y, gamma_xy] |
| Check returned | `verification` | Recovered deformation, signed residuals, allowed errors and passed=true |

Moments have no input field here. Supplying them as zero or null is rejected, because they are the quantities being solved. This differs from a forward request in which an explicitly known moment really is zero. The response echoes every accepted input and the installed engine version.

## Follow the functions

1. **`PrescribedCurvatureRequest`** in `api/src/anisotropy_api/schemas.py` checks the contract with Pydantic. Unknown fields, missing values, string/bool numeric coercion and NaN/infinity are rejected. `MaterialInput.validate_compliance()` retains the existing physical material check.
2. **`analyze_prescribed_curvature()`** in `api/src/anisotropy_api/main.py` converts accepted material/ply fields to engine objects and calls the engine. It serializes arrays to JSON lists; it implements no laminate equations.
3. **`prescribed_curvature_response()`** in `engine/src/anisotropy_engine/response.py` validates both three-component vectors, obtains A/B/D, solves `A eps0 = N - B kappa`, and evaluates `M = B eps0 + D kappa`. The same function handles zero and nonzero prescribed curvature.
4. **`midplane_response()`**, the existing full ABD solve, receives the known forces and calculated moments. It independently solves for the deformation using the same stiffness implementation. Both strain and curvature must agree with their reference values.
5. **`ResponseVerification`** stores the check; **`PrescribedCurvatureResult`** groups it with the moments, strain and stiffness matrices. These Python dataclasses organize data; they do not call a model or save a file.
6. **`VerificationResponse` / `PrescribedCurvatureResponse`** validate the outgoing JSON. A failed numerical check returns HTTP 422 with an error instead of a successful result. HTTP 200 only describes successful execution, not experimental validity.

## Libraries and boundaries

- **NumPy** supplies arrays and `linalg.solve`, which solves a simultaneous linear system without explicitly calculating its inverse. Array products perform the stiffness equations.
- **Pydantic** enforces the API's typed input/output contract. Python dataclasses group already-computed engine results.
- **FastAPI** routes HTTP requests and generates the interactive `/docs` page. **Uvicorn** runs that service.
- **pytest** runs analytical, equilibrium, rejection and integration checks; FastAPI's **TestClient** makes HTTP-like calls to the real application in process.

These libraries already existed in the project. No new runtime dependency was added. A future chat harness will construct this request and explain its checked response; it will not implement another solver.

## What the check means

For each component, allowed error is `absolute tolerance + 1e-9 * abs(reference)`. Absolute tolerances are 1e-12 for dimensionless strain and 1e-9 for curvature in 1/m. Residual means recovered minus reference. The engine returns all these values so the check can be inspected. See [the theory](../../engine/docs/theory.md) and [ADR-0013](../decisions/ADR-0013-prescribed-curvature-analysis.md).

Zero curvature removes bending/twist in this constitutive model; it does not fix rigid-body movement. Moments are per unit width and applied to the laminate, not the opposite reactions on a fixture. Reversing the physical stack reverses flattening moments. Thermal/moisture effects, support design and experimental validation remain outside this operation.

The forward check shares ABD code, so analytical scalar cases and separate through-thickness stress integration also test the implementation. Evidence: [evaluation](../evaluations/2026-10-03-prescribed-curvature.md). The next chunk is real chat tool calling and clarification handling.
