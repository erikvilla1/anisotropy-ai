"""What a membrane solve returns, in SI, with lookups by deck names (ADR-0029)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mesh import Mesh
from .model import ElementKey, NodeKey


@dataclass(frozen=True)
class MembraneSolution:
    mesh: Mesh
    displacement: np.ndarray  # (n, 2), m: u and v per mesh node; coupled nodes carry their reference node's values
    reaction: np.ndarray  # (n, 2), N: at prescribed dofs of representative nodes; zero elsewhere
    strain: np.ndarray  # (ne, 3): eps_x, eps_y, gamma_xy at the element centroid
    gauss_strain: np.ndarray  # (ne, 4, 3): the same at the four Gauss points
    section_force: np.ndarray  # (ne, 3), N/m: Nx, Ny, Nxy at the centroid
    free_residual: float  # largest |K u - f| at a free dof, N: roundoff, reported so a test can bound it

    def displacement_of(self, key: NodeKey) -> np.ndarray:
        return self.displacement[self.mesh.node(key)]

    def reaction_of(self, keys: tuple[NodeKey, ...] | list[NodeKey]) -> np.ndarray:
        """Summed reaction over the nodes named; for a coupled region name the reference node."""
        return self.reaction[[self.mesh.node(key) for key in keys]].sum(axis=0)

    def strain_of(self, key: ElementKey) -> np.ndarray:
        return self.strain[self.mesh.element(key)]

    def section_force_of(self, key: ElementKey) -> np.ndarray:
        return self.section_force[self.mesh.element(key)]

    @property
    def total_reaction(self) -> np.ndarray:
        """Sum of all reactions; equals minus the applied concentrated loads in equilibrium."""
        return self.reaction.sum(axis=0)
