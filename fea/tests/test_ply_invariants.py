"""Tresca, the principal stresses and the pressure of each ply (ADR-0066 amendment 2): what Abaqus prints beside Mises for a shell
section point, checked against closed forms of plane stress."""

from __future__ import annotations

import math

import numpy as np
import pytest

from anisotropy_fea.recovery import INVARIANTS, PlyField, ply_invariants, ply_mises


def field_of(*states: tuple[float, float, float]) -> PlyField:
    """One element whose plies carry these (s11, s22, s12) states."""
    stress = np.array(states, dtype=float)
    zeros = np.zeros_like(stress)
    return PlyField(angles_deg=[np.zeros(len(states))], strain_xy=[zeros], stress_xy=[stress], strain_12=[zeros], stress_12=[stress])


def one(field: PlyField) -> dict[str, np.ndarray]:
    return {name: values[0] for name, values in ply_invariants(field).items()}


def test_uniaxial_tension_and_compression():
    got = one(field_of((300.0, 0.0, 0.0), (-200.0, 0.0, 0.0)))
    assert got["tresca"].tolist() == [300.0, 200.0]  # Tresca equals Mises for a uniaxial state
    assert ply_mises(field_of((300.0, 0.0, 0.0)))[0][:, 0].tolist() == [300.0]
    assert got["max_principal"].tolist() == [300.0, 0.0]  # the zero through the thickness is the largest in compression
    assert got["min_principal"].tolist() == [0.0, -200.0]
    assert got["pressure"].tolist() == [-100.0, pytest.approx(200.0 / 3.0)]


def test_pure_shear():
    tau = 50.0
    got = one(field_of((0.0, 0.0, tau)))
    assert got["max_principal"][0] == pytest.approx(tau) and got["min_principal"][0] == pytest.approx(-tau) and got["mid_principal"][0] == 0.0
    assert got["tresca"][0] == pytest.approx(2 * tau)
    assert ply_mises(field_of((0.0, 0.0, tau)))[0][0, 0] == pytest.approx(math.sqrt(3.0) * tau)
    assert got["pressure"][0] == 0.0


def test_equal_biaxial_tension_puts_the_zero_last_and_tresca_reaches_it():
    got = one(field_of((100.0, 100.0, 0.0)))
    assert (got["max_principal"][0], got["mid_principal"][0], got["min_principal"][0]) == (100.0, 100.0, 0.0)
    assert got["tresca"][0] == 100.0  # in-plane the two principals are equal; the through-thickness zero sets Tresca
    assert ply_mises(field_of((100.0, 100.0, 0.0)))[0][0, 0] == pytest.approx(100.0)


def test_a_general_state_matches_mohrs_circle_and_the_order_holds_everywhere():
    rng = np.random.default_rng(7)
    states = rng.uniform(-500.0, 500.0, size=(40, 3))
    got = one(field_of(*map(tuple, states)))
    centre = (states[:, 0] + states[:, 1]) / 2.0
    radius = np.hypot((states[:, 0] - states[:, 1]) / 2.0, states[:, 2])
    in_plane = np.stack([centre + radius, centre - radius], axis=1)
    assert np.allclose(np.sort(np.column_stack([in_plane, np.zeros(40)]), axis=1),
                       np.column_stack([got["min_principal"], got["mid_principal"], got["max_principal"]]))
    assert np.all(got["max_principal"] >= got["mid_principal"]) and np.all(got["mid_principal"] >= got["min_principal"])
    assert np.allclose(got["tresca"], np.maximum.reduce([in_plane[:, 0], in_plane[:, 1], np.zeros(40)]) - np.minimum.reduce([in_plane[:, 0], in_plane[:, 1], np.zeros(40)]))
    assert np.allclose(got["pressure"], -(states[:, 0] + states[:, 1]) / 3.0)


def test_a_shell_state_keeps_its_two_faces():
    stress = np.array([[[100.0, 0.0, 0.0], [-100.0, 0.0, 0.0]]])  # one ply, bottom and top face
    zeros = np.zeros_like(stress)
    field = PlyField(angles_deg=[np.zeros(1)], strain_xy=[zeros], stress_xy=[stress], strain_12=[zeros], stress_12=[stress], faces=("bottom", "top"))
    got = one(field)
    assert set(got) == set(INVARIANTS) and got["tresca"].shape == (1, 2)
    assert got["tresca"].tolist() == [[100.0, 100.0]] and got["max_principal"].tolist() == [[100.0, 0.0]]
