import library from "../engine/src/anisotropy_engine/data/material-library.json";
import { PSI_MPA } from "./material-analysis";

/** Library datasets the calculator can pick: those with an elastic input set. Display values only;
 * the API resolves the dataset itself and returns the SI values it used. */
export type LibraryOption = {
  value: string; materialId: string; datasetId: string; label: string;
  E1_GPa: string; E2_GPa: string; G12_GPa: string; nu12: string; thickness_mm: string | null; citation: string;
  /** Recorded values the home page shows beside the moduli, as the record states them; null when it states none.
   * The engine cites the same keys in the same order (ADR-0059); the API's provenance is the value to trust. */
  alpha1_per_K: string | null; alpha2_per_K: string | null; density_kg_per_m3: string | null; Vf_percent: string | null;
};

const toGPa: Record<string, number> = { GPa: 1, MPa: 1e-3, Msi: PSI_MPA * 1e3, ksi: PSI_MPA, psi: PSI_MPA * 1e-3, Pa: 1e-9 };
const toMm: Record<string, number> = { mm: 1, m: 1e3, in: 25.4 };
const toKgPerM3: Record<string, number> = { "kg/m³": 1, "g/cm³": 1e3, "lb/ft³": 0.45359237 / 0.3048 ** 3 };
const toMicroPerK: Record<string, number> = { "10⁻⁶/K": 1, "10⁻⁶/°C": 1, "10⁻⁶/°F": 1.8 };
const DENSITY_KEYS = ["density", "density-LT", "density-WT", "density-nominal"];
const VF_KEYS = ["Vf", "Vf-LT", "Vf-WT", "Vf-nominal"];
const show = (value: number) => String(Number(value.toPrecision(6)));

function option(d: (typeof library.datasets)[number]): LibraryOption | null {
  if (!d.elasticInputs) return null;
  const prop = (key: string) => d.properties.find(p => p.key === key);
  const first = (keys: string[]) => keys.map(prop).find((p) => p !== undefined);
  const inputs = d.elasticInputs as Record<"E1" | "E2" | "G12" | "nu12", string>;
  const modulus = (key: string) => { const p = prop(key)!; return show(p.value * toGPa[p.unit]); };
  const tply = prop("tply") ?? prop("tply-WT");
  const converted = (p: { value: number; unit: string } | undefined, factors: Record<string, number>) =>
    p && p.unit in factors ? show(p.value * factors[p.unit]) : null;
  const vf = first(VF_KEYS);
  return {
    value: `${d.materialId}::${d.datasetId}`, materialId: d.materialId, datasetId: d.datasetId,
    label: `${d.name} · ${d.dataset}`,
    E1_GPa: modulus(inputs.E1), E2_GPa: modulus(inputs.E2), G12_GPa: modulus(inputs.G12), nu12: String(prop(inputs.nu12)!.value),
    thickness_mm: tply && tply.unit in toMm ? show(tply.value * toMm[tply.unit]) : null,
    citation: `${d.source.title} · ${d.source.revision} · dataset ${d.datasetId} (record ${d.recordRevision ?? "n/a"}); E1 from page ${prop(inputs.E1)!.sourcePage}`,
    alpha1_per_K: converted(prop("alpha1"), toMicroPerK), alpha2_per_K: converted(prop("alpha2"), toMicroPerK),
    density_kg_per_m3: converted(first(DENSITY_KEYS), toKgPerM3),
    Vf_percent: vf && vf.unit === "%" ? show(vf.value) : null,
  };
}

export const libraryOptions: LibraryOption[] = library.datasets.map(option).filter((o): o is LibraryOption => o !== null);
export const findLibraryOption = (value: string) => libraryOptions.find(o => o.value === value);
