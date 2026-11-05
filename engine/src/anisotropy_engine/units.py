"""Unit systems for entering and reporting values. The engine itself always works in SI.

Each entry maps a quantity to (factor, label): a value in that unit times the factor is
the SI value. Inch and pound-force are exact by definition. Temperature enters only as a
change, so no offset is needed: a change of 1 degF is 5/9 K, and 1/degF is 9/5 per K.
Compliances are the inverses of the matching stiffness or load units: "compliance" for
S and S-bar, and "a", "b", "d" for the blocks of the inverted ABD matrix. "areal_mass" is
mass per area; its pound is the pound-mass, exact by definition.

Four systems report results: "SI" (GPa, MPa, mm, N/m), "mm-MPa" (the millimetre-newton system
the coupon decks use: MPa, mm, N/mm, N*mm/mm), "US" (Msi, ksi, in, lb/in) and "psi". A value
may also enter in a unit of its own (ADR-0060): UNITS names every unit a value may carry, with
its dimension and its factor to SI, and `to_si` converts one value, refusing a unit it does not
know or one of the wrong dimension. The engine never guesses a unit (ADR-0003).
"""

LBF = 4.4482216152605  # N
INCH = 0.0254  # m
PSI = LBF / INCH**2  # Pa
DEG_F = 5 / 9  # K per degF of temperature change
POUND_MASS = 0.45359237  # kg, exact by definition
FOOT = 12 * INCH  # m

UNIT_SYSTEMS = {
    "SI": {
        "modulus": (1e9, "GPa"), "stress": (1e6, "MPa"), "length": (1e-3, "mm"),
        "N": (1.0, "N/m"), "M": (1.0, "N*m/m"), "kappa": (1.0, "1/m"),
        "A": (1e6, "MN/m"), "B": (1e3, "kN"), "D": (1.0, "N*m"),
        "alpha": (1.0, "1/degC"), "delta_T": (1.0, "degC"),
        "compliance": (1e-9, "1/GPa"), "a": (1.0, "m/N"), "b": (1.0, "1/N"), "d": (1.0, "1/(N*m)"),
        "areal_mass": (1.0, "kg/m^2"),
    },
    "mm-MPa": {
        "modulus": (1e6, "MPa"), "stress": (1e6, "MPa"), "length": (1e-3, "mm"),
        "N": (1e3, "N/mm"), "M": (1.0, "N*mm/mm"), "kappa": (1e3, "1/mm"),
        "A": (1e3, "N/mm"), "B": (1.0, "N"), "D": (1e-3, "N*mm"),
        "alpha": (1.0, "1/degC"), "delta_T": (1.0, "degC"),
        "compliance": (1e-6, "1/MPa"), "a": (1e-3, "mm/N"), "b": (1.0, "1/N"), "d": (1e3, "1/(N*mm)"),
        "areal_mass": (1.0, "kg/m^2"),  # nobody quotes a mass per square millimetre
    },
    "US": {
        "modulus": (1e6 * PSI, "Msi"), "stress": (1e3 * PSI, "ksi"), "length": (INCH, "in"),
        "N": (LBF / INCH, "lb/in"), "M": (LBF, "lb*in/in"), "kappa": (1 / INCH, "1/in"),
        "A": (1e6 * LBF / INCH, "10^6 lb/in"), "B": (1e3 * LBF, "10^3 lb"), "D": (LBF * INCH, "lb*in"),
        "alpha": (1 / DEG_F, "1/degF"), "delta_T": (DEG_F, "degF"),
        "compliance": (1 / (1e6 * PSI), "1/Msi"), "a": (INCH / LBF, "in/lb"), "b": (1 / LBF, "1/lb"),
        "d": (1 / (LBF * INCH), "1/(lb*in)"), "areal_mass": (POUND_MASS / INCH**2, "lb/in^2"),
    },
    "psi": {
        "modulus": (PSI, "psi"), "stress": (PSI, "psi"), "length": (INCH, "in"),
        "N": (LBF / INCH, "lb/in"), "M": (LBF, "lb*in/in"), "kappa": (1 / INCH, "1/in"),
        "A": (LBF / INCH, "lb/in"), "B": (LBF, "lb"), "D": (LBF * INCH, "lb*in"),
        "alpha": (1 / DEG_F, "1/degF"), "delta_T": (DEG_F, "degF"),
        "compliance": (1 / PSI, "1/psi"), "a": (INCH / LBF, "in/lb"), "b": (1 / LBF, "1/lb"),
        "d": (1 / (LBF * INCH), "1/(lb*in)"), "areal_mass": (POUND_MASS / INCH**2, "lb/in^2"),
    },
}

# Every unit a value may carry on its own: name -> (dimension, factor to SI). A modulus and a strength
# share the dimension "pressure"; a force resultant is a force per unit width; a moment resultant is a
# moment per unit width, so N*m/m and N*mm/mm are both the newton.
UNITS: dict[str, tuple[str, float]] = {
    "Pa": ("pressure", 1.0), "kPa": ("pressure", 1e3), "MPa": ("pressure", 1e6), "GPa": ("pressure", 1e9),
    "psi": ("pressure", PSI), "ksi": ("pressure", 1e3 * PSI), "Msi": ("pressure", 1e6 * PSI),
    "m": ("length", 1.0), "cm": ("length", 1e-2), "mm": ("length", 1e-3), "in": ("length", INCH),
    "N/m": ("force_per_length", 1.0), "N/mm": ("force_per_length", 1e3), "kN/m": ("force_per_length", 1e3),
    "kN/mm": ("force_per_length", 1e6), "lb/in": ("force_per_length", LBF / INCH), "kip/in": ("force_per_length", 1e3 * LBF / INCH),
    "N*m/m": ("moment_per_length", 1.0), "N*mm/mm": ("moment_per_length", 1.0), "kN*m/m": ("moment_per_length", 1e3),
    "lb*in/in": ("moment_per_length", LBF), "kip*in/in": ("moment_per_length", 1e3 * LBF),
}

# The dimension each quantity kind of UNIT_SYSTEMS takes when a value enters with its own unit.
QUANTITY_DIMENSIONS = {"modulus": "pressure", "stress": "pressure", "length": "length", "N": "force_per_length", "M": "moment_per_length"}


def units_of(kind: str) -> tuple[str, ...]:
    """The units a value of this kind may carry, in the table's order."""
    if kind not in QUANTITY_DIMENSIONS:
        raise ValueError(f"no units are listed for {kind!r}; one of {tuple(QUANTITY_DIMENSIONS)}")
    dimension = QUANTITY_DIMENSIONS[kind]
    return tuple(name for name, (d, _factor) in UNITS.items() if d == dimension)


def to_si(value: float, unit: str, kind: str) -> float:
    """A value in its own unit as the SI value the engine takes (Pa, m, N/m or N*m/m).

    An unknown unit, or one of another dimension (a length where a modulus is expected), is refused by name.
    """
    allowed = units_of(kind)
    if unit not in UNITS:
        raise ValueError(f"unknown unit {unit!r} for {kind}; one of {', '.join(allowed)}")
    dimension, factor = UNITS[unit]
    if dimension != QUANTITY_DIMENSIONS[kind]:
        raise ValueError(f"{unit} is not a {kind} unit; one of {', '.join(allowed)}")
    return value * factor


def from_si(value: float, unit: str, kind: str) -> float:
    """The SI value in the unit named, the inverse of `to_si`, with the same refusals."""
    return value / (to_si(1.0, unit, kind))


def in_system(value: float, unit: str, kind: str, system: str) -> float:
    """A value entered with its own unit, in the unit a reporting system uses for that kind: what a case file states."""
    if system not in UNIT_SYSTEMS:
        raise ValueError(f"units must be one of {tuple(UNIT_SYSTEMS)}")
    return to_si(value, unit, kind) / UNIT_SYSTEMS[system][kind][0]
