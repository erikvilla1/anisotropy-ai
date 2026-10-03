"""Unit systems for entering and reporting values. The engine itself always works in SI.

Each entry maps a quantity to (factor, label): a value in that unit times the factor is
the SI value. Inch and pound-force are exact by definition. Temperature enters only as a
change, so no offset is needed: a change of 1 degF is 5/9 K, and 1/degF is 9/5 per K.
Compliances are the inverses of the matching stiffness or load units: "compliance" for
S and S-bar, and "a", "b", "d" for the blocks of the inverted ABD matrix.
"""

LBF = 4.4482216152605  # N
INCH = 0.0254  # m
PSI = LBF / INCH**2  # Pa
DEG_F = 5 / 9  # K per degF of temperature change

UNIT_SYSTEMS = {
    "SI": {
        "modulus": (1e9, "GPa"), "stress": (1e6, "MPa"), "length": (1e-3, "mm"),
        "N": (1.0, "N/m"), "M": (1.0, "N*m/m"), "kappa": (1.0, "1/m"),
        "A": (1e6, "MN/m"), "B": (1e3, "kN"), "D": (1.0, "N*m"),
        "alpha": (1.0, "1/degC"), "delta_T": (1.0, "degC"),
        "compliance": (1e-9, "1/GPa"), "a": (1.0, "m/N"), "b": (1.0, "1/N"), "d": (1.0, "1/(N*m)"),
    },
    "US": {
        "modulus": (1e6 * PSI, "Msi"), "stress": (1e3 * PSI, "ksi"), "length": (INCH, "in"),
        "N": (LBF / INCH, "lb/in"), "M": (LBF, "lb*in/in"), "kappa": (1 / INCH, "1/in"),
        "A": (1e6 * LBF / INCH, "10^6 lb/in"), "B": (1e3 * LBF, "10^3 lb"), "D": (LBF * INCH, "lb*in"),
        "alpha": (1 / DEG_F, "1/degF"), "delta_T": (DEG_F, "degF"),
        "compliance": (1 / (1e6 * PSI), "1/Msi"), "a": (INCH / LBF, "in/lb"), "b": (1 / LBF, "1/lb"),
        "d": (1 / (LBF * INCH), "1/(lb*in)"),
    },
    "psi": {
        "modulus": (PSI, "psi"), "stress": (PSI, "psi"), "length": (INCH, "in"),
        "N": (LBF / INCH, "lb/in"), "M": (LBF, "lb*in/in"), "kappa": (1 / INCH, "1/in"),
        "A": (LBF / INCH, "lb/in"), "B": (LBF, "lb"), "D": (LBF * INCH, "lb*in"),
        "alpha": (1 / DEG_F, "1/degF"), "delta_T": (DEG_F, "degF"),
        "compliance": (1 / PSI, "1/psi"), "a": (INCH / LBF, "in/lb"), "b": (1 / LBF, "1/lb"),
        "d": (1 / (LBF * INCH), "1/(lb*in)"),
    },
}
