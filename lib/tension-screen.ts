/**
 * The tension coupon from its material and layup (ADR-0090): what the tension screen sends, when it has enough to send, and how it shows
 * what the software chose. The page computes nothing: the fea package (`anisotropy_fea.tension_input`) chooses every row the engineer was
 * not asked for and says why, in the checklist's `built` list.
 */
import { customerText } from "./studio-copy";
import {
  FORM_VERSION, fieldByKey, labelFor, libraryOptions, NO_STANDARD, PLY_KEYS, shortHelp, unitLabels, unitWords, type Checklist, type FieldDefinition, type StudioForm,
  type StudioValues,
} from "./studio-form";

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
/** The screen's own hints under its inputs (audit fea-run-6): the form's help is written for the Excel form and names the team's tools, so
 * the product view says what a value is in its own words. A row not listed here keeps the first sentence of its help. */
export const TENSION_HINTS: Record<string, string> = {
  own_name: "Letters, digits, - and _; no spaces, e.g. PREPREG-01.",
  own_E1: "Stiffness along the fibres.",
  own_E2: "Stiffness across the fibres, in the plane of the ply.",
  own_G12: "In-plane shear stiffness.",
  own_nu12: "How much the ply narrows across the fibres when stretched along them, e.g. 0.3; no unit.",
  own_F1t: "Give all five strengths, or none (then no failure check).",
  own_F1c: "Strength along the fibres in compression, as a positive number.",
  own_F2t: "Strength across the fibres in tension.",
  own_F2c: "Strength across the fibres in compression, as a positive number.",
  own_F6: "In-plane shear strength.",
  own_source: "Where these numbers come from: a datasheet and its date, or a test report.",
  ply_thickness: "The cured thickness of one ply, e.g. 0.127.",
  G13: "Out-of-plane shear modulus, fibre-thickness plane. Optional: G12 is used if blank.",
  G23: "Out-of-plane shear modulus across the fibres. Optional.",
  control: "Displacement or force at the top grip.",
  value: "A positive number, e.g. 1 mm or 10000 N.",
  length: "The whole coupon, end to end, tabs included, e.g. 250.",
  width: "Across the coupon, e.g. 25.",
  tab_length: "How much of each end the grip holds, e.g. 56.",
  element_size: "Smaller is finer and slower, e.g. 2.",
};
/** The screen's own labels where the form's label is a code (audit fea-run-6). */
export const TENSION_LABELS: Record<string, string> = { own_nu12: "Own material: ν₁₂" };
/** A row's label on the screen: its own, else the form's in the coupon's units. */
export const tensionLabel = (key: string, units = "mm-MPa"): string =>
  TENSION_LABELS[key] ?? (fieldByKey[key] ? labelFor(fieldByKey[key], units) : key);
/** A row's label and hint where the setup check offers it in the assistant (components/studio/check-fix.tsx): the screen's own words, as
 * on the rail, unless every test is offered (the development view); a hint unfit for a customer is left out (audit fea-run-6). */
export function fixRowWords(field: FieldDefinition, units: string, allTests: boolean): { label: string; hint: string } {
  return {
    label: (!allTests && TENSION_LABELS[field.key]) || labelFor(field, units),
    hint: customerText((allTests ? undefined : TENSION_HINTS[field.key]) ?? shortHelp(field)) ?? "",
  };
}

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
    else for (const key of OWN_REQUIRED) if (!filled(form, key)) missing.push(tensionLabel(key));
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

/** The rows "Model settings" shows: the engineering choices (audit fea-run-15). Who set the coupon up, the day, where its size is recorded
 * from and the grip region are the record's bookkeeping, kept in the checklist and the package, not shown here. */
export const SHOWN_BUILT = ["test", "units", "standard", "width", "length", "tab_length", "strain_device", "strain_length", "grips", "control", "value",
  "element_size", "G13", "G23", "criteria"];
/** The package's values in words, not codes (audit fea-run-12): "nodal" grips hold every node of each tab, which an engineer calls clamped. */
const VALUE_WORDS: Record<string, Record<string, string>> = {
  grips: { nodal: "Clamped", coupling: "Through a reference point" },
  criteria: { all: "All", none: "None" },
  control: { displacement: "Displacement", force: "Force" },
  strain_device: { extensometer: "Extensometer", "strain gauge": "Strain gauge" },
};

/** The checklist's list of what the software chose, as lines: the row's label in the coupon's units, the value in words, and why; only the
 * engineering rows, in the order the package chose them. The value row is labelled by its loading type ("Applied displacement (mm)"). */
export function builtLines(checklist: Checklist | null, units = "mm-MPa"): BuiltLine[] {
  const built: BuiltRow[] = (checklist?.built ?? []).filter((b) => SHOWN_BUILT.includes(b.row));
  const lab = unitLabels(units);
  const control = String(built.find((b) => b.row === "control")?.value ?? "");
  return built.map((b) => {
    const field = fieldByKey[b.row];
    const label = b.row === "value" && (control === "displacement" || control === "force")
      ? `Applied ${control} (${lab[control === "force" ? "force" : "length"]})` : tensionLabel(b.row, units);
    const value = typeof b.value === "number" ? `${b.value}${field?.unit && !/\(/.test(label) ? ` ${lab[field.unit] ?? ""}` : ""}`
      : b.row === "units" ? unitWords(String(b.value)) : b.row === "test" ? sentenceCase(String(b.value))
        : VALUE_WORDS[b.row]?.[String(b.value)] ?? String(b.value);
    return { key: b.row, label, value, reason: b.reason };
  });
}
const sentenceCase = (text: string): string => (text ? text.charAt(0).toUpperCase() + text.slice(1) : text);
