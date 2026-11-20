"""Air density with altitude: the International Standard Atmosphere up to 11 km.

ISO 2533:1975, equal to the U.S. Standard Atmosphere 1976 in this range: sea-level temperature
288.15 K and pressure 101 325 Pa, a temperature that falls 6.5 K per km of geopotential altitude,
air as a perfect gas with R = 287.052 87 J/(kg K), and g = 9.806 65 m/s^2.
"""

SEA_LEVEL_TEMPERATURE_K = 288.15
SEA_LEVEL_PRESSURE_PA = 101325.0
LAPSE_RATE_K_PER_M = 0.0065
GAS_CONSTANT = 287.05287  # J/(kg K)
STANDARD_GRAVITY = 9.80665  # m/s^2
TROPOPAUSE_M = 11000.0
SEA_LEVEL_DENSITY = SEA_LEVEL_PRESSURE_PA / (GAS_CONSTANT * SEA_LEVEL_TEMPERATURE_K)  # 1.2250 kg/m^3


def density_ratio(altitude_m: float) -> float:
    """sigma = rho / rho_0 at a geopotential altitude between sea level and 11 km."""
    if not 0 <= altitude_m <= TROPOPAUSE_M:
        raise ValueError(f"Altitude must be between 0 and {TROPOPAUSE_M:.0f} m, got {altitude_m}")
    exponent = STANDARD_GRAVITY / (GAS_CONSTANT * LAPSE_RATE_K_PER_M) - 1
    return (1 - LAPSE_RATE_K_PER_M * altitude_m / SEA_LEVEL_TEMPERATURE_K) ** exponent


def air_density(altitude_m: float) -> float:
    """rho in kg/m^3."""
    return SEA_LEVEL_DENSITY * density_ratio(altitude_m)
