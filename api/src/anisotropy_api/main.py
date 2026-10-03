"""A synchronous local API. It adapts HTTP to the engine; it contains no laminate math."""

from importlib.metadata import version

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.response import midplane_response

from .schemas import AnalysisRequest, AnalysisResponse


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
    allow_methods=["POST"],
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


@app.post("/v1/laminates/response", response_model=AnalysisResponse)
def analyze_laminate(problem: AnalysisRequest) -> AnalysisResponse:
    """Validate a problem, call existing stiffness/response functions, and serialize their output."""
    material = problem.material.to_engine()
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

    return AnalysisResponse(
        engine_version=version("anisotropy-engine"),
        inputs=problem,
        A_N_per_m=A.tolist(), B_N=B.tolist(), D_N_m=D.tolist(),
        midplane_strain=eps0.tolist(), curvature_per_m=kappa.tolist(),
    )
