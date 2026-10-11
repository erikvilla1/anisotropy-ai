"""The cited material library as engine inputs (ADR-0020).

The website records every material value with its source, page and printed unit in
`lib/curated-materials.ts`. `scripts/export-material-library.ts` writes those records to
`data/material-library.json` inside this package, and this module turns one dataset into a
`Lamina` in SI units with the citation of every value it used. The conversion happens here
and nowhere else (ADR-0002). Nothing is defaulted: a dataset that lacks an elastic input set,
a Poisson ratio or a value the caller needs raises an error that names what is missing
(ADR-0003).

Which recorded key supplies which engine quantity:

- E1, E2, G12, nu12: the dataset's own `elasticInputs` map (tensile moduli and the tensile
  Poisson ratio for test reports; the single moduli of textbook tables).
- Strengths, all five or none: F1t; F1c, or the cross-ply back-out F1c-derived when no direct
  value exists; F2t; F2c; F6 from F12 (a V-notched beam or textbook shear strength) or from
  F12-5pct (ASTM D3518 at 5% strain). The 0.2% offset shear strength is never used as F6.
- Thermal expansion, both or none: alpha1 and alpha2.
- Ply thickness: tply, or tply-WT for the woven glass record.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

from .lamina import Lamina, Strengths, ThermalExpansion
from .units import DEG_F, INCH, PSI

LIBRARY_FILE = "data/material-library.json"

# Printed unit -> (factor to SI, SI unit). A value times the factor is the SI value.
_TO_SI = {
    "Pa": (1.0, "Pa"), "MPa": (1e6, "Pa"), "GPa": (1e9, "Pa"),
    "psi": (PSI, "Pa"), "ksi": (1e3 * PSI, "Pa"), "Msi": (1e6 * PSI, "Pa"),
    "—": (1.0, "—"),
    "m": (1.0, "m"), "mm": (1e-3, "m"), "in": (INCH, "m"),
    "10⁻⁶/K": (1e-6, "1/K"), "10⁻⁶/°C": (1e-6, "1/K"), "10⁻⁶/°F": (1e-6 / DEG_F, "1/K"),
}
_MODULUS_UNITS = {"Pa", "MPa", "GPa", "psi", "ksi", "Msi"}
_STRENGTH_KEYS = {"F1t": ("F1t",), "F1c": ("F1c", "F1c-derived"), "F2t": ("F2t",), "F2c": ("F2c",),
                  "F6": ("F12", "F12-5pct")}
_ALPHA_KEYS = {"alpha1": ("alpha1",), "alpha2": ("alpha2",)}
_THICKNESS_KEYS = ("tply", "tply-WT")


@dataclass(frozen=True)
class CitedValue:
    """One library value the engine used, in SI and as printed, with its page."""

    role: str  # the engine quantity: E1, E2, G12, nu12, F1t, F1c, F2t, F2c, F6, alpha1, alpha2, tply
    key: str  # the library property key it came from
    value: float  # SI
    unit: str  # SI unit
    source_value: float
    source_unit: str
    basis: str
    page: int
    printed_page: int | None
    reference_url: str


@dataclass(frozen=True)
class LibraryMaterial:
    """A library dataset resolved to engine inputs, with the citation of every value used."""

    material_id: str
    name: str
    dataset_id: str
    dataset: str
    record_revision: str | None
    rights: str
    citation: str
    lamina: Lamina
    ply_thickness_m: float | None
    values: tuple[CitedValue, ...]
    not_provided: tuple[str, ...]  # what this dataset cannot supply, and why

    def value(self, role: str) -> CitedValue:
        for item in self.values:
            if item.role == role:
                return item
        raise KeyError(role)


@lru_cache(maxsize=1)
def load_library() -> dict:
    """The exported library, read once from the package data file."""
    data = json.loads((files("anisotropy_engine") / LIBRARY_FILE).read_text(encoding="utf-8"))
    if data.get("schemaVersion") != 1 or not isinstance(data.get("datasets"), list):
        raise ValueError("material-library.json is not a schema version 1 library export")
    return data


def list_datasets() -> list[dict]:
    """Every dataset: material id and name, dataset id and label, whether it has elastic inputs."""
    return [{"material_id": d["materialId"], "name": d["name"], "dataset_id": d["datasetId"],
             "dataset": d["dataset"], "primary": d["primary"], "rights": d["source"]["rights"],
             "elastic_inputs": d["elasticInputs"] is not None}
            for d in load_library()["datasets"]]


def find_dataset(material_id: str, dataset_id: str | None = None) -> dict:
    """The dataset record for a material: its primary dataset, or the named one."""
    datasets = [d for d in load_library()["datasets"] if d["materialId"] == material_id]
    if not datasets:
        known = sorted({d["materialId"] for d in load_library()["datasets"]})
        raise ValueError(f"unknown library material {material_id!r}; known materials: {known}")
    if dataset_id is None:
        return next(d for d in datasets if d["primary"])
    for d in datasets:
        if d["datasetId"] == dataset_id:
            return d
    raise ValueError(f"material {material_id!r} has no dataset {dataset_id!r}; "
                     f"its datasets are {[d['datasetId'] for d in datasets]}")


def _si(prop: dict, allowed_units: set[str] | None = None) -> tuple[float, str]:
    if "valueEnd" in prop or "valueQualifier" in prop:
        raise ValueError(f"{prop['key']} is a range or a bound, not a single value")
    unit = prop["unit"]
    if unit not in _TO_SI or (allowed_units is not None and unit not in allowed_units):
        raise ValueError(f"{prop['key']} has unit {unit!r}, which the loader cannot convert here")
    factor, si_unit = _TO_SI[unit]
    return float(prop["value"]) * factor, si_unit


def _cite(role: str, prop: dict, dataset: dict, allowed_units: set[str] | None = None) -> CitedValue:
    value, unit = _si(prop, allowed_units)
    reference = dataset["source"]["url"]
    return CitedValue(role=role, key=prop["key"], value=value, unit=unit,
                      source_value=float(prop.get("sourceValue", prop["value"])),
                      source_unit=prop.get("sourceUnit", prop["unit"]), basis=prop["basis"],
                      page=int(prop["sourcePage"]), printed_page=prop.get("printedPage"),
                      reference_url=f"{reference}#page={prop['sourcePage']}")


def _first(props: dict[str, dict], keys: tuple[str, ...]) -> dict | None:
    return next((props[key] for key in keys if key in props), None)


def library_material(material_id: str, dataset_id: str | None = None) -> LibraryMaterial:
    """Resolve a library dataset to a `Lamina` in SI with the citation of every value used.

    Raises ValueError for an unknown material or dataset, or a dataset without an elastic
    input set. Strengths and thermal expansion are attached only when the dataset supplies a
    complete set; otherwise `not_provided` says what is missing.
    """
    d = find_dataset(material_id, dataset_id)
    props = {p["key"]: p for p in d["properties"]}
    inputs = d["elasticInputs"]
    if not inputs:
        raise ValueError(f"dataset {d['datasetId']!r} of {material_id!r} has no elastic input set: {d['application']}")
    cited = [_cite(role, props[inputs[role]], d, _MODULUS_UNITS if role != "nu12" else {"—"})
             for role in ("E1", "E2", "G12", "nu12")]
    not_provided: list[str] = []

    strengths = None
    found = {role: _first(props, keys) for role, keys in _STRENGTH_KEYS.items()}
    missing = [f"{role} (none of {', '.join(keys)})" for role, keys in _STRENGTH_KEYS.items() if found[role] is None]
    if missing:
        not_provided.append("strengths: missing " + "; ".join(missing))
    else:
        strength_values = [_cite(role, prop, d, _MODULUS_UNITS) for role, prop in found.items()]
        cited.extend(strength_values)
        strengths = Strengths(**{v.role: v.value for v in strength_values})

    expansion = None
    alphas = {role: _first(props, keys) for role, keys in _ALPHA_KEYS.items()}
    if all(alphas.values()):
        alpha_values = [_cite(role, prop, d, {"10⁻⁶/K", "10⁻⁶/°C", "10⁻⁶/°F"}) for role, prop in alphas.items()]
        cited.extend(alpha_values)
        expansion = ThermalExpansion(**{v.role: v.value for v in alpha_values})
    else:
        not_provided.append("thermal expansion: no alpha1 and alpha2")

    thickness = _first(props, _THICKNESS_KEYS)
    ply_thickness_m = None
    if thickness is None:
        not_provided.append("ply thickness: no tply")
    else:
        t = _cite("tply", thickness, d, {"m", "mm", "in"})
        cited.append(t)
        ply_thickness_m = t.value

    lamina = Lamina(E1=cited[0].value, E2=cited[1].value, G12=cited[2].value, nu12=cited[3].value,
                    strengths=strengths, thermal_expansion=expansion)
    source = d["source"]
    citation = f"{source['title']} · {source['revision']} · {source['publisher']}" + (f" · {source['date']}" if source["date"] else "")
    return LibraryMaterial(material_id=d["materialId"], name=d["name"], dataset_id=d["datasetId"], dataset=d["dataset"],
                           record_revision=d["recordRevision"], rights=source["rights"], citation=citation,
                           lamina=lamina, ply_thickness_m=ply_thickness_m, values=tuple(cited),
                           not_provided=tuple(not_provided))
