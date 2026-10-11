"""A synchronous local API. It adapts HTTP to the engine; it contains no laminate math."""

from importlib.metadata import version

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.library import library_material, list_datasets
from anisotropy_engine.response import midplane_response, prescribed_curvature_response

from .schemas import (
    AnalysisRequest, AnalysisResponse, LibraryMaterialInput, MaterialProvenance, PrescribedCurvatureRequest,
    PrescribedCurvatureResponse, VerificationResponse,
)


app = FastAPI(
    title="Anisotropy engine API",
    version=version("anisotropy-api"),
    description="Local development: one-material laminate stiffness and deformation in SI base units.",
)

# Only the local website origins used by this development project may read API responses.
# This browser policy is not authentication; deployment remains a separate future task.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return field locations and reasons without echoing malformed/non-finite input."""
    return JSONResponse(status_code=422, content={
        "detail": [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ],
    })


def resolve_material(choice) -> tuple[object, MaterialProvenance | None]:
    """Explicit constants are used as given; a library choice is resolved and cited (ADR-0020)."""
    if isinstance(choice, LibraryMaterialInput):
        resolved = choice.resolve()
        return resolved.lamina, MaterialProvenance.of(resolved)
    return choice.to_engine(), None


@app.get("/v1/materials")
def list_materials() -> list[dict]:
    """Every library dataset, and whether it has the elastic inputs an analysis needs."""
    return list_datasets()


@app.get("/v1/materials/{material_id}", response_model=MaterialProvenance)
def material_detail(material_id: str, dataset: str | None = None) -> MaterialProvenance:
    """The SI values the engine would use for a dataset, each with its page."""
    try:
        return MaterialProvenance.of(library_material(material_id, dataset))
    except ValueError as error:
        message = str(error)
        raise HTTPException(status_code=404 if message.startswith("unknown library material") or "has no dataset" in message else 422,
                            detail=message) from None


@app.post("/v1/laminates/response", response_model=AnalysisResponse)
def analyze_laminate(problem: AnalysisRequest) -> AnalysisResponse:
    """Validate a problem, call existing stiffness/response functions, and serialize their output."""
    material, provenance = resolve_material(problem.material)
    plies = [Ply(material=material, **ply.model_dump()) for ply in problem.plies]
    try:
        # Floating-point overflow/invalid operations must become errors, never JSON null/NaN.
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            A, B, D = abd_matrices(plies)
            eps0, kappa = midplane_response(plies, problem.loads.to_engine())
        if not all(np.isfinite(value).all() for value in (A, B, D, eps0, kappa)):
            raise FloatingPointError("Non-finite solver output")
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="These inputs do not produce a finite, solvable laminate response. Check values and units.",
        ) from exc

    return AnalysisResponse(material_provenance=provenance, 
        engine_version=version("anisotropy-engine"),
        inputs=problem,
        A_N_per_m=A.tolist(), B_N=B.tolist(), D_N_m=D.tolist(),
        midplane_strain=eps0.tolist(), curvature_per_m=kappa.tolist(),
    )


@app.post("/v1/laminates/prescribed-curvature", response_model=PrescribedCurvatureResponse)
def analyze_prescribed_curvature(problem: PrescribedCurvatureRequest) -> PrescribedCurvatureResponse:
    """Find required moments from explicit force resultants and a curvature constraint.

    Set all curvatures to zero for a flat laminate. This is a local constitutive
    calculation, not a displacement boundary-value problem or fixture design.
    Unknown moments must be omitted, not sent as zero or null. All calculation
    and numerical verification happen in the engine.
    """
    material = resolve_material(problem.material)[0]
    plies = [Ply(material=material, **ply.model_dump()) for ply in problem.plies]
    try:
        result = prescribed_curvature_response(
            plies, [problem.forces.Nx, problem.forces.Ny, problem.forces.Nxy],
            problem.prescribed_curvature_per_m,
        )
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="These inputs do not produce a finite, numerically verified prescribed-curvature response. Check values, units and conditioning.",
        ) from exc
    check = result.verification
    return PrescribedCurvatureResponse(material_provenance=resolve_material(problem.material)[1], 
        analysis_type="prescribed_curvature", engine_version=version("anisotropy-engine"), inputs=problem,
        A_N_per_m=result.A.tolist(), B_N=result.B.tolist(), D_N_m=result.D.tolist(),
        midplane_strain=result.midplane_strain.tolist(), moments_N_m_per_m=result.moments.tolist(),
        verification=VerificationResponse(
            passed=check.passed, recovered_midplane_strain=check.recovered_strain.tolist(),
            recovered_curvature_per_m=check.recovered_curvature.tolist(),
            strain_residual=check.strain_residual.tolist(), curvature_residual_per_m=check.curvature_residual.tolist(),
            strain_allowed_error=check.strain_allowed_error.tolist(),
            curvature_allowed_error_per_m=check.curvature_allowed_error.tolist(),
        ),
    )
