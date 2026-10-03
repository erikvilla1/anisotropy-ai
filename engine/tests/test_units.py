import pytest

from anisotropy_engine.units import PSI, UNIT_SYSTEMS


def test_psi_follows_the_exact_inch_and_pound_force_definitions():
    assert PSI == pytest.approx(6894.757293168361, rel=1e-15)


def test_every_unit_system_covers_the_same_quantities():
    quantities = {name: set(system) for name, system in UNIT_SYSTEMS.items()}
    assert quantities["US"] == quantities["SI"] == quantities["psi"]


@pytest.mark.parametrize("system, kind, value, si_value", [
    ("US", "modulus", 1.0, 6.894757293e9),   # 1 Msi
    ("US", "stress", 1.0, 6.894757293e6),    # 1 ksi
    ("psi", "modulus", 2.13e7, 146.8583e9),  # 21.3 Msi
    ("SI", "A", 60.24, 60.24e6),             # MN/m
    ("US", "N", 1.0, 175.1268),              # lb/in in N/m
])
def test_conversions_to_si(system, kind, value, si_value):
    assert value * UNIT_SYSTEMS[system][kind][0] == pytest.approx(si_value, rel=1e-6)
