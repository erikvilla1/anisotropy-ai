/**
 * The tension coupon from its material and layup (ADR-0090): what the tension screen sends, when it has enough to send, and how it shows
 * what the software chose. The page computes nothing: the fea package (`anisotropy_fea.tension_input`) chooses every row the engineer was
 * not asked for and says why, in the checklist's `built` list.
 */
import { FORM_VERSION, fieldByKey, labelFor, libraryOptions, NO_STANDARD, PLY_KEYS, unitLabels, type Checklist, type StudioForm, type StudioValues } from "./studio-form";

export const TENSION_INPUT = "tension";
export const D3039 = "ASTM D3039/D3039M-17";

/** The engineer's own material: the constants, the source, and the ply thickness the library would otherwise give; G13 and G23 optional. */
export const OWN_MATERIAL_KEYS = ["own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6", "own_source",
  "ply_thickness", "G13", "G23"];
export const OWN_REQUIRED = ["own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_source", "ply_thickness"];
/** What "Change a choice" offers besides the own material (Erik, 2026-11-11): the pull or force, the size and tabs, the element size. */
export const LOAD_KEYS = ["control", "value"];
export const SIZE_KEYS = ["length", "width", "tab_length"];
export const MESH_KEYS = ["element_size"];
/** Every row the screen may send: nothing else of an older project's rows goes with it. */
export const TENSION_KEYS = ["library", ...PLY_KEYS, "symmetric", "standard", "filled_by", ...OWN_MATERIAL_KEYS, ...LOAD_KEYS, ...SIZE_KEYS, ...MESH_KEYS];

const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;
const filled = (form: StudioForm, key: string): boolean => Boolean((form[key] ?? "").trim());

/** Whether the coupon is the engineer's own material: no library material picked. */
export const isOwnMaterial = (form: StudioForm): boolean => !filled(form, "library");
/** Whether the picked library material's record gives no ply thickness, so the engineer gives it: the screen then shows the box (the
 * library holds nine such records, AS4/8552 among them). An id the library does not hold is left to the setup check. */
export function needsPlyThickness(form: StudioForm): boolean {
  if (isOwnMaterial(form)) return false;
  const picked = libraryOptions.find((m) => m.id === (form.library ?? "").trim());
  return picked !== undefined && picked.thickness === null;
}
/** Whether the standard is D3039 or none. A form that names no test yet is a new one: D3039, whatever the blank form's Standard row says;
 * the screen's two choices write the test with the standard, so a choice of none is kept. */
export const underD3039 = (form: StudioForm): boolean => !(form.test ?? "").trim() || (form.standard ?? "").trim() !== NO_STANDARD;
/** Rows whose blank-form default is left to the software when unchanged, so the choice and its reason appear under How we built it. */
const LEFT_AT_DEFAULT = ["element_size"];

/** What is still missing before the screen can build: the material, the layup, and with no standard the size. Empty when ready. */
export function tensionMissing(form: StudioForm): string[] {
  const missing: string[] = [];
  if (isOwnMaterial(form)) {
    if (!OWN_REQUIRED.some((key) => filled(form, key))) missing.push("the material");
    else for (const key of OWN_REQUIRED) if (!filled(form, key)) missing.push(fieldByKey[key]?.label ?? key);
  } else if (needsPlyThickness(form) && !filled(form, "ply_thickness")) missing.push(fieldByKey.ply_thickness?.label ?? "ply_thickness");
  if (!filled(form, "ply_1") || !filled(form, "symmetric")) missing.push("the layup");
  if (!underD3039(form)) for (const key of SIZE_KEYS) if (!filled(form, key)) missing.push(fieldByKey[key]?.label ?? key);
  return missing;
}
export const tensionReady = (form: StudioForm): boolean => tensionMissing(form).length === 0;

/** The values file the screen sends: its own rows only, numbers parsed, blanks left out, and `"input": "tension"` so the fea package
 * chooses the rest. A library material sends no own constants; an own material sends no library id. */
export function tensionValues(form: StudioForm): StudioValues {
  const values: StudioValues = { form_version: FORM_VERSION, input: TENSION_INPUT };
  const own = isOwnMaterial(form);
  for (const key of TENSION_KEYS) {
    if (own ? key === "library" : OWN_MATERIAL_KEYS.includes(key) && key !== "ply_thickness") continue;
    if (key === "standard" && !(form.test ?? "").trim()) continue; // a new form: the package chooses D3039
    const text = (form[key] ?? "").trim();
    if (!text) continue;
    if (LEFT_AT_DEFAULT.includes(key) && text === String(fieldByKey[key]?.default ?? "")) continue;
    const kind = fieldByKey[key]?.kind;
    values[key] = (kind === "number" || kind === "whole" || kind === "angle") && NUMBER.test(text) ? Number(text) : text;
  }
  return values;
}

export type BuiltRow = { row: string; value: unknown; reason: string };
export type BuiltLine = { key: string; label: string; value: string; reason: string };

/** The checklist's list of what the software chose, as lines: the row's label in the coupon's units, the value, and why. */
export function builtLines(checklist: Checklist | null, units = "mm-MPa"): BuiltLine[] {
  const built: BuiltRow[] = checklist?.built ?? [];
  const lab = unitLabels(units);
  return built.map((b) => {
    const field = fieldByKey[b.row];
    const label = field ? labelFor(field, units) : b.row;
    const value = typeof b.value === "number" ? `${b.value}${field?.unit && !/\(/.test(label) ? ` ${lab[field.unit] ?? ""}` : ""}` : String(b.value);
    return { key: b.row, label, value, reason: b.reason };
  });
}
