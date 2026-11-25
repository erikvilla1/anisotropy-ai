/**
 * The tension coupon from its material and layup (ADR-0090): what the tension screen sends, when it has enough to send, and how it shows
 * what the software chose. The page computes nothing: the fea package (`anisotropy_fea.tension_input`) chooses every row the engineer was
 * not asked for and says why, in the checklist's `built` list.
 */
import { formatNumber } from "./number-format";
import { customerText } from "./studio-copy";
import {
  FORM_VERSION, fieldByKey, labelFor, libraryConstantsIn, libraryOptions, libraryValuesIn, NO_STANDARD, PLY_KEYS, shortHelp, unitLabels, unitsOf, unitWords, type Checklist,
  type FieldDefinition, type StudioForm, type StudioValues,
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
/** The engineer's own G13 and G23, typed for a library material too when they have measured them (ADR-0111 amendment 5). */
export const TRANSVERSE_KEYS = ["G13", "G23"];
/** The rows of the own material a library material sends too, when given: the ply thickness the library may lack, and G13 and G23. */
const LIBRARY_TOO = ["ply_thickness", ...TRANSVERSE_KEYS];
/** The hints under the G13 and G23 fields of a library material: a blank field keeps the estimate shown. */
export const TRANSVERSE_HINTS: Record<string, string> = {
  G13: "Shear in the plane of the fibres and the thickness. Leave blank for the estimate.",
  G23: "Shear across the fibres, through the thickness. Leave blank for the estimate.",
};

export function tensionValues(form: StudioForm): StudioValues {
  const values: StudioValues = { form_version: FORM_VERSION, input: TENSION_INPUT };
  const own = isOwnMaterial(form);
  for (const key of TENSION_KEYS) {
    if (own ? key === "library" : OWN_MATERIAL_KEYS.includes(key) && !LIBRARY_TOO.includes(key)) continue;
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

/** The number the software chose for each row left blank, from the latest check's `built` list, by row: what a blank field under Change
 * settings stands for, shown as its placeholder so the size, the load and the mesh read as values in use, not as nothing (ADR-0090
 * amendment 1). The page chooses none of them; with no check yet there are none. */
export function valuesInUse(checklist: Checklist | null): Record<string, string> {
  return Object.fromEntries((checklist?.built ?? []).filter((b) => typeof b.value === "number")
    .map((b) => [b.row, formatNumber(b.value as number, { zeros: false })]));
}

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
/** A name for the material copied out of a library record: the record's id in capitals, as a name the decks accept (a letter first, then
 * letters, digits, - and _). An id that starts with a digit, as "7781-5245c" does, takes an M in front. */
export function ownNameFromLibrary(id: string): string {
  const cleaned = id.toUpperCase().replace(/[^A-Za-z0-9_-]/g, "-").slice(0, 79);
  return /^[A-Za-z]/.test(cleaned) ? cleaned : `M${cleaned}`;
}

/** The chosen library material's values copied into the engineer's own rows (ADR-0111 amendment 6), so a material picked from the library
 * can be edited rather than only read. Every constant goes across exactly as the engine wrote it, never as the four figures the page
 * prints, so copying and changing nothing changes no number; G13 and G23 carry the estimates the coupon was already built with, and the
 * source names the record the numbers came from. The coupon then holds the engineer's own constants, as one typed from the start does: the
 * library's record is no longer cited, because the numbers are no longer only its own. Null when no library material is chosen. */
export function ownFromLibrary(form: StudioForm): StudioForm | null {
  const id = (form.library ?? "").trim();
  const units = unitsOf(form);
  const picked = libraryOptions.find((m) => m.id === id);
  const v = libraryValuesIn(id, units);
  // the moduli as the rows hold them (MPa, not the GPa the step prints): `library_constants`, written by the engine in every system
  const c = libraryConstantsIn(id, units);
  if (!picked || !v || !c) return null;
  const text = (x: number | null): string => (x === null ? "" : String(x));
  return {
    library: "",
    own_name: ownNameFromLibrary(id),
    own_E1: text(c.E1), own_E2: text(c.E2), own_G12: text(c.G12), own_nu12: text(v.nu12),
    ...(v.strengths
      ? { own_F1t: text(v.strengths.F1t), own_F1c: text(v.strengths.F1c), own_F2t: text(v.strengths.F2t), own_F2c: text(v.strengths.F2c), own_F6: text(v.strengths.F6) }
      : { own_F1t: "", own_F1c: "", own_F2t: "", own_F2c: "", own_F6: "" }),
    // the ply thickness the library gives, if any; a record without one leaves the row for the engineer, as picking it does
    ply_thickness: (form.ply_thickness ?? "").trim() || text(c.ply_thickness),
    // the values the coupon was already built with: the engineer's own if they gave them, else the estimates, now theirs to change
    G13: (form.G13 ?? "").trim() || text(v.estimates.G13), G23: (form.G23 ?? "").trim() || text(v.estimates.G23),
    own_source: `${picked.name} from our library, edited here${picked.source ? ` · ${picked.source}` : ""}`,
  };
}

/** One constant of the chosen material as the Material step shows it: its symbol, its value with the unit, and whether it is an estimate. */
export type ValueLine = { key: string; label: string; value: string; estimate?: boolean };

/** The chosen library material's constants, shown under the choice in the Material step (ADR-0111 amendment 4), as the engine wrote them
 * in the coupon's system (`library_values`): the stiffness column (E1, E2, G12, nu12, and the ply thickness when the library gives one)
 * and the strength column, null for a material the library gives no strengths for. Null for the engineer's own material, whose values
 * are the fields they typed, and before a material is chosen. The page converts nothing; it only prints by the one number rule. */
export function libraryValueLines(form: StudioForm, { ownTransverse = false }: { ownTransverse?: boolean } = {}): {
  stiffness: ValueLine[]; strengths: ValueLine[] | null; transverse: { estimates: Record<string, string>; rule: string };
} | null {
  if (isOwnMaterial(form)) return null;
  const units = unitsOf(form);
  const v = libraryValuesIn(form.library, units);
  if (!v) return null;
  const lab = unitLabels(units);
  const n = (x: number) => formatNumber(x, { zeros: false });
  const line = (key: string, label: string, value: string, estimate = false): ValueLine => ({ key, label, value, ...(estimate ? { estimate } : {}) });
  // G13 and G23 the library does not give: the estimates, marked, unless the engineer gives their own in the fields (ADR-0111 amendment 5)
  const transverse = ownTransverse ? [] : [line("G13", "G13", `${n(v.G13)} ${lab.modulus}`, true), line("G23", "G23", `${n(v.G23)} ${lab.modulus}`, true)];
  const stiffness = [
    line("E1", "E1", `${n(v.E1)} ${lab.modulus}`), line("E2", "E2", `${n(v.E2)} ${lab.modulus}`), line("G12", "G12", `${n(v.G12)} ${lab.modulus}`),
    ...transverse, line("nu12", "ν12", n(v.nu12)),
    ...(v.ply_thickness === null ? [] : [line("ply_thickness", "Ply", `${n(v.ply_thickness)} ${lab.length}`)]),
  ];
  const strengths = v.strengths
    ? (["F1t", "F1c", "F2t", "F2c", "F6"] as const).map((role) => line(role, role, `${n(v.strengths![role])} ${lab.stress}`)) : null;
  return { stiffness, strengths, transverse: { estimates: { G13: n(v.estimates.G13), G23: n(v.estimates.G23) }, rule: v.transverse_rule } };
}

const sentenceCase = (text: string): string => (text ? text.charAt(0).toUpperCase() + text.slice(1) : text);
