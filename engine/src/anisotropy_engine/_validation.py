"""Shared checks for numerical inputs that do not pass through a Pydantic model."""

import numpy as np


def finite_vector(value, name: str, size: int = 3) -> np.ndarray:
    """Require a one-dimensional vector of the stated size, with no NaN or infinity."""
    vector = np.asarray(value, dtype=float)
    if vector.shape != (size,):
        raise ValueError(f"{name} must have exactly {size} components in a one-dimensional vector")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite numbers")
    return vector
