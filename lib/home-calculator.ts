import { loadNames, type CalculatorForm, type LoadName } from "./laminate-api";
import { findLibraryOption } from "./material-library-options";

/** What the home page's laminate view holds (audit of 2026-10-31, item 4). The material is one of the library's cited
 * datasets; typed values belong to the full calculator page. `loads` is null until the user opens the loads and types one:
 * first-ply failure is shown only when loading conditions are provided. */
export type HeroState = {
  library: string;
  layup: string;
  thickness_mm: string;
  loads: Record<LoadName, string> | null;
};

export const DEFAULT_LIBRARY = "im7-8552::ncamp-im7-8552-2019-rtd-measured-v1";
export const DEFAULT_LAYUP = "[45/-45/0/90]s";

export function zeroLoads(): Record<LoadName, string> {
  return Object.fromEntries(loadNames.map((name) => [name, "0"])) as Record<LoadName, string>;
}

export function defaultHeroState(): HeroState {
  const option = findLibraryOption(DEFAULT_LIBRARY);
  return { library: DEFAULT_LIBRARY, layup: DEFAULT_LAYUP, thickness_mm: option?.thickness_mm ?? "", loads: null };
}

/** True when the user typed at least one load that is not zero; blanks count as nothing typed. */
export function loadsEntered(loads: Record<LoadName, string> | null): boolean {
  return loads !== null && loadNames.some((name) => loads[name].trim() !== "" && Number(loads[name]) !== 0);
}

/** The calculator form the home view sends: the chosen dataset, one thickness for every ply of the expanded layup, and the
 * loads typed or zeros. Null when the dataset is unknown. The request itself is built by `buildAnalysisRequest`. */
export function heroForm(state: HeroState, angles: number[]): CalculatorForm | null {
  const option = findLibraryOption(state.library);
  if (!option) return null;
  return {
    material: {
      library: option.value, E1_GPa: option.E1_GPa, E2_GPa: option.E2_GPa, G12_GPa: option.G12_GPa, nu12: option.nu12,
      source_reference: option.citation,
    },
    plies: angles.map((angle) => ({ angle_deg: String(angle), thickness_mm: state.thickness_mm })),
    loads: state.loads ?? zeroLoads(),
  };
}

/** The key under which "Want to check the math?" leaves the form for /calculator, in sessionStorage. */
export const calculatorHandoffKey = "laminate-calculator-handoff";

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
const isText = (value: unknown): value is string => typeof value === "string";

/** The stored form, or null when the stored value is not one; nothing is filled in. */
export function readCalculatorHandoff(raw: unknown): CalculatorForm | null {
  let payload: unknown = raw;
  if (isText(raw)) {
    try { payload = JSON.parse(raw); } catch { return null; }
  }
  if (!isObject(payload) || !isObject(payload.form)) return null;
  const form = payload.form;
  const material = form.material;
  if (!isObject(material) || !["library", "E1_GPa", "E2_GPa", "G12_GPa", "nu12", "source_reference"].every((key) => isText(material[key]))) return null;
  if (!Array.isArray(form.plies) || !form.plies.length
    || !form.plies.every((ply) => isObject(ply) && isText(ply.angle_deg) && isText(ply.thickness_mm))) return null;
  const loads = form.loads;
  if (!isObject(loads) || !loadNames.every((name) => isText(loads[name]))) return null;
  return {
    material: {
      library: material.library as string, E1_GPa: material.E1_GPa as string, E2_GPa: material.E2_GPa as string,
      G12_GPa: material.G12_GPa as string, nu12: material.nu12 as string, source_reference: material.source_reference as string,
    },
    plies: form.plies.map((ply) => ({ angle_deg: (ply as Record<string, string>).angle_deg, thickness_mm: (ply as Record<string, string>).thickness_mm })),
    loads: Object.fromEntries(loadNames.map((name) => [name, loads[name] as string])) as Record<LoadName, string>,
  };
}
