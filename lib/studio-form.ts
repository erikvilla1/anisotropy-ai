/**
 * The studio's form (ADR-0051): the coupon input form's rows, as `fea/tools/export_form_definition.py` exports them, kept as text
 * while the engineer types and turned into the values object the API checks. Nothing here judges a value: `intake.check_form`
 * does, through `POST /v1/coupon-jobs/check`, and its refusals come back by row.
 */
import definition from "./coupon-form-definition.json";

export type FieldKind = "text" | "number" | "whole" | "date" | "list" | "angle";
/** The kind of unit a row's number carries: a length, a stress, a force, or an amount that is a length or a force by the loading type. */
export type UnitKind = "length" | "stress" | "force" | "amount";
export type FieldDefinition = {
  key: string; label: string; kind: FieldKind; help: string; required: boolean;
  default: string | number | null; words: string[]; at_least: number | null; above: number | null;
  unit: UnitKind | null;
  /** For a row with a unit: its label in each unit system a coupon may be stated in, and our default in each (ADR-0061). */
  labels?: Record<string, string>; defaults?: Record<string, number>;
};
export type SectionDefinition = { title: string; fields: FieldDefinition[] };
export type LibraryEntry = Record<string, string | number | null>;
export type UnitSystem = { words: string; labels: Record<string, string> };
export type LibraryConstants = { E1: number; E2: number; G12: number; ply_thickness: number | null };
export type FormDefinition = {
  form_version: string; fea_version: string; units: string; row_units: Record<string, string>;
  /** Every system a coupon may be stated in, as the engine labels it; `deck_units` is the system the decks are written in. */
  unit_systems: Record<string, UnitSystem>; deck_units: string;
  sections: SectionDefinition[]; how_to: string[];
  glossary: { group: string; terms: { term: string; meaning: string; example: string }[] }[];
  tests: Record<string, string>; criteria: string[]; library: LibraryEntry[];
  /** Each library material's E1, E2, G12 and ply thickness in every system, written by the engine: the page converts nothing. */
  library_constants: Record<string, Record<string, LibraryConstants>>;
  plate?: { test: string; edges: string[]; areas: string[]; with_tabs: string[]; with_hole: string[]; dofs: Record<string, string> };
  /** The test standards the Standard row offers (ADR-0072): each with its tests, the rows it needs, its specimens or classes with their sizes in
   * every system, and its requirements by clause. The page judges nothing: the checklist's Test standard item carries the judgement. */
  standards: { none: string; profiles: StandardProfile[] };
};
/** A size a standard names: a specimen (C1869 A, B) or a class of laminate (D3039 Table 2), by row, in every unit system. */
export type StandardPreset = {
  key: string; label: string; clause: string; minimum: string[]; note: string; values: Record<string, Record<string, number>>;
  thickness: Record<string, number | null>;
};
export type StandardRequirement = { id: string; clause: string; level: string; text: string; rows: string[] };
export type StandardProfile = {
  id: string; designation: string; title: string; organisation: string; catalog_url: string; edition_note: string; systems: string; rights: string;
  tests: string[]; aliases: string[]; needs: string[]; variant_words: string[]; variants: StandardPreset[]; classes: StandardPreset[];
  requirements: StandardRequirement[];
};
/** Every row's text as typed, by field key; blank means the row is empty. */
export type StudioForm = Record<string, string>;
/** The values object the API takes: the rows with numbers parsed, blanks left out (ADR-0046 amendment 3); a plate adds its lists (ADR-0054). */
export type StudioValues = Record<string, string | number | boolean | number[] | unknown[]>;

export const formDefinition = definition as FormDefinition;
export const FORM_VERSION = formDefinition.form_version;
export const fields: FieldDefinition[] = formDefinition.sections.flatMap((section) => section.fields);
export const fieldByKey: Record<string, FieldDefinition> = Object.fromEntries(fields.map((field) => [field.key, field]));
/** A row by its label in any unit system: what a checklist names ("Length (in)" for a coupon stated in inches). */
export const fieldByLabel: Record<string, FieldDefinition> = Object.fromEntries(
  fields.flatMap((field) => [[field.label, field], ...Object.values(field.labels ?? {}).map((label) => [label, field])]),
);
/** The unit systems in the order the engine offers them; the first is the form's own, mm-MPa. */
export const UNIT_SYSTEMS: string[] = Object.keys(formDefinition.unit_systems);
export const DEFAULT_UNITS = formDefinition.units;
export const DECK_UNITS = formDefinition.deck_units;
/** The system a form is stated in: its Units row, or the form's own when the row is blank or unknown (the check refuses the unknown word). */
export const unitsOf = (form: StudioForm): string => (UNIT_SYSTEMS.includes(form.units ?? "") ? form.units : DEFAULT_UNITS);
export const unitLabels = (units: string): Record<string, string> => formDefinition.unit_systems[units]?.labels ?? formDefinition.unit_systems[DEFAULT_UNITS].labels;
export const unitWords = (units: string): string => formDefinition.unit_systems[units]?.words ?? units;
/** A row's label in a system: "Length (mm)" is "Length (in)" for a coupon stated in in-psi; a row without a unit keeps its label. */
export const labelFor = (field: FieldDefinition, units: string): string => field.labels?.[units] ?? field.label;
/** A library material's constants in a system, as the engine wrote them; null when the material is not in the library. */
export const libraryConstantsIn = (id: string, units: string): LibraryConstants | null => formDefinition.library_constants[id]?.[units] ?? null;
export const PLY_KEYS = fields.map((field) => field.key).filter((key) => /^ply_\d+$/.test(key));
export const HOLE_KEYS = ["hole_diameter", "hole_circumferential", "hole_radial", "hole_ring", "hole_growth"];
export const BENDING_KEYS = ["span", "overhang", "load_span"];
export const GRIP_KEYS = ["grips", "region", "tab_length"];
export const LOADING_KEYS = ["control", "value"];
export const OPEN_HOLE_TEST = "open-hole tension";
export const BENDING_TESTS = ["three-point bending", "four-point bending"];
export const FOUR_POINT_TEST = "four-point bending";
export const PLATE_TEST = formDefinition.plate?.test ?? "plate";
export const NO_STANDARD = formDefinition.standards.none;
export const STANDARDS: StandardProfile[] = formDefinition.standards.profiles;
/** Bonded tabs and the strain measurement: rows of the pulled and pushed tests only, which the check refuses for bending and a plate. */
export const TAB_KEYS = ["tab_thickness", "tab_bevel", "tab_material"];
export const STRAIN_KEYS = ["strain_device", "strain_length"];
/** The dog-bone's rows (ADR-0075): a narrow section joined to the full width by fillets, for unnotched tension only. */
export const DOGBONE_KEYS = ["narrow_width", "narrow_length", "radius", "outer_radius"];
export const DOGBONE_TEST = "unnotched tension";
/** One isotropic material, a plastic (ADR-0075): its thickness, E and nu, with its name and source on the Own material rows. It is built for
 * the pulled and pushed tests, and it has no plies, no ply material and, until its yield and failure are modelled, no criterion. */
export const ISOTROPIC_KEYS = ["thickness", "own_E", "own_nu"];
export const ISOTROPIC_TESTS = ["unnotched tension", "unnotched compression", "open-hole tension"];
export const PLY_MATERIAL_KEYS = ["library", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6", "G13", "G23", "f12_star"];
/** Whether the form states one isotropic material: its Material kind row says so, on a test that takes one. */
export const isIsotropic = (form: StudioForm): boolean => form.material_kind === "isotropic" && ISOTROPIC_TESTS.includes(form.test);
/** The standard the form's Standard row names; null for none, a blank row or a word the list does not hold (the check refuses it). */
export const standardOf = (form: StudioForm): StandardProfile | null => STANDARDS.find((p) => p.designation === form.standard) ?? null;
/** The standards that cover a test, as the Standard row offers them. */
export const standardsFor = (test: string): StandardProfile[] => STANDARDS.filter((p) => p.tests.includes(test));

/** What each test is, in the words of the Test row's own help as the engine writes it ("unnotched tension (a plain strip pulled)"), for the
 * first step's choices (ADR-0062 amendment 1); a test the help does not describe gets an empty string, which `tests/workspace-panels.test.ts`
 * refuses. */
export function testDescription(test: string): string {
  const help = fieldByKey.test?.help ?? "";
  const escaped = test.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return help.match(new RegExp(`(?:^|[:,] |or )${escaped} \\(([^)]*)\\)`))?.[1] ?? "";
}

/** The words a list row offers on this form (ADR-0072): the Standard row "none" and the standards of the test picked (every one before a
 * test is picked), the Specimen row the specimens of the standard picked; every other row its own words. The check still refuses a word
 * that does not belong. */
export function wordsFor(field: FieldDefinition, form: StudioForm): string[] {
  if (field.key === "standard") return [NO_STANDARD, ...(form.test ? standardsFor(form.test) : STANDARDS).map((p) => p.designation)];
  if (field.key === "specimen") return standardOf(form)?.variant_words ?? field.words;
  return field.words;
}

/** The form with another test, and what was cleared: a standard that does not cover the new test goes back to none, with its specimen,
 * and the note says so, so no row keeps a word the check would refuse. */
export function withTest(form: StudioForm, test: string): { form: StudioForm; note: string } {
  const standard = standardOf(form);
  if (!standard || standard.tests.includes(test)) return { form: { ...form, test }, note: "" };
  return {
    form: { ...form, test, standard: NO_STANDARD, specimen: "" },
    note: `${standard.designation} covers ${standard.tests.join(" and ")}, not ${test || "a blank test"}: the Standard row is back to none.`,
  };
}

/** The form with another standard: a specimen the new standard does not name is cleared. */
export function withStandard(form: StudioForm, designation: string): StudioForm {
  const next = { ...form, standard: designation };
  const words = standardOf(next)?.variant_words ?? [];
  return words.includes(form.specimen ?? "") ? next : { ...next, specimen: "" };
}

/** Rows merged into the form as the chat states them: a test that the standard picked does not cover clears the standard, and a standard
 * clears a specimen it does not name, as the panels do (ADR-0072). */
export function mergeRows(form: StudioForm, rows: StudioForm): StudioForm {
  let next: StudioForm = { ...form, ...rows };
  if (rows.test !== undefined && rows.standard === undefined) next = withTest({ ...next, test: form.test }, rows.test).form;
  if (rows.standard !== undefined) next = withStandard(next, rows.standard);
  return next;
}

/** A standard's sizes the form can take: its specimens (C1869 A, B) or its classes of laminate (D3039 Table 2). */
export const presetsOf = (profile: StandardProfile): StandardPreset[] => [...profile.variants, ...profile.classes];

/** The rows a standard's size sets, in the coupon's units as the engine wrote them (the page converts nothing), with the specimen it names
 * and the words of Where the size comes from. A size without bonded tabs (D3039's balanced class, gripped through emery cloth) clears the tab
 * rows another size of the same standard set; the tab length it does not give stays as typed. A D638 type without Type IV's outer radius
 * clears it, and a size that gives the gage length names the extensometer the standard measures it with when no device is typed (ADR-0075). */
export function presetRows(form: StudioForm, profile: StandardProfile, preset: StandardPreset): StudioForm {
  const rows: StudioForm = {};
  for (const [key, value] of Object.entries(preset.values[unitsOf(form)] ?? {})) rows[key] = String(value);
  const somewhere = (key: string) => presetsOf(profile).some((p) => Object.values(p.values).some((v) => key in v));
  if (somewhere("tab_thickness") && !("tab_thickness" in rows)) for (const key of TAB_KEYS) rows[key] = "";
  if (somewhere("outer_radius") && !("outer_radius" in rows)) rows.outer_radius = "";
  if ("strain_length" in rows && !(form.strain_device ?? "").trim()) rows.strain_device = "extensometer";
  if (profile.variant_words.includes(preset.key)) rows.specimen = preset.key;
  rows.size_from = `${profile.designation}, ${preset.clause}: ${preset.label}` + (preset.note ? `; ${preset.note}` : "");
  return rows;
}
const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

/** The public IM7/8552 example (the stand-in of `fea/tests/public_coupon.py`): a complete, solvable coupon to start from. */
export const EXAMPLE: StudioForm = {
  filled_by: "", date: "", notes: "", units: "mm-MPa", test: "unnotched tension", material_code: "", layup_code: "", standard: "none",
  size_from: "the public IM7/8552 check fea/checks/unnotched-im7-8552/", team_model: "not built yet", test_data: "none",
  length: "250", width: "25", tab_length: "56", ply_1: "45", ply_2: "0", ply_3: "-45", ply_4: "90", symmetric: "yes", ply_thickness: "",
  library: "im7-8552", G13: "4688.43", G23: "3000", criteria: "all", f12_star: "", control: "displacement", value: "1", element_size: "2",
  grips: "coupling", region: "tabs",
};

/** Every row blank but the defaults the form states, in the given unit system (a default length, the element size, is the engine's
 * figure for that system). */
export function blankForm(units: string = DEFAULT_UNITS): StudioForm {
  const form: StudioForm = {};
  for (const field of fields) {
    const value = field.defaults?.[units] ?? field.default;
    form[field.key] = value === null || value === undefined ? "" : String(value);
  }
  form.units = UNIT_SYSTEMS.includes(units) ? units : DEFAULT_UNITS;
  return form;
}

export function exampleForm(today: string): StudioForm {
  return { ...blankForm(), ...EXAMPLE, date: today };
}

/** The sections to show for a test: the open-hole rows only for open-hole tension and for a plate, the bending rows only for the bending
 * tests, which have supports instead of grips and tabs, the loading span only for four-point bending, and for a plate (ADR-0054) neither the
 * grips nor the loading rows, since it lists its supports and loads over regions (the tool ignores the rest otherwise). The dog-bone's rows
 * show for unnotched tension; an isotropic material (ADR-0075) shows its thickness, E and nu in place of the plies, the ply material and the
 * criterion. */
export function sectionsFor(form: StudioForm): SectionDefinition[] {
  const openHole = form.test === OPEN_HOLE_TEST;
  const bending = BENDING_TESTS.includes(form.test);
  const plate = form.test === PLATE_TEST;
  const isotropic = isIsotropic(form);
  const visible = (field: FieldDefinition): boolean => {
    if (HOLE_KEYS.includes(field.key)) return openHole || plate;
    if (BENDING_KEYS.includes(field.key)) return bending && (field.key !== "load_span" || form.test === FOUR_POINT_TEST);
    if (field.key === "tab_length") return !bending;
    if (GRIP_KEYS.includes(field.key)) return !bending && !plate;
    if (LOADING_KEYS.includes(field.key)) return !plate;
    if (TAB_KEYS.includes(field.key) || STRAIN_KEYS.includes(field.key)) return !bending && !plate;
    if (field.key === "specimen") return (standardOf(form)?.variant_words.length ?? 0) > 0; // only a standard that names its specimens asks
    if (DOGBONE_KEYS.includes(field.key)) return form.test === DOGBONE_TEST;
    if (field.key === "material_kind") return ISOTROPIC_TESTS.includes(form.test);
    if (ISOTROPIC_KEYS.includes(field.key)) return isotropic;
    if (PLY_KEYS.includes(field.key) || PLY_MATERIAL_KEYS.includes(field.key) || ["symmetric", "ply_thickness", "criteria"].includes(field.key)) return !isotropic;
    return true;
  };
  return formDefinition.sections
    .map((section) => ({ title: section.title, fields: section.fields.filter(visible) }))
    .filter((section) => section.fields.length > 0);
}

/** The values object: numbers parsed where the row is a number, blanks left out, a text that is not a number left as text so the
 * API's check refuses it by row. No physics, no defaults beyond the form's own. */
export function buildValues(form: StudioForm, lists?: Record<string, unknown[]>): StudioValues {
  const values: StudioValues = { form_version: FORM_VERSION };
  const visible = new Set(sectionsFor(form).flatMap((section) => section.fields.map((field) => field.key)));
  for (const field of fields) {
    if (!visible.has(field.key)) continue; // a row the test does not use (the tabs of a bending coupon) is not sent
    const text = (form[field.key] ?? "").trim();
    if (!text) continue;
    if ((field.kind === "number" || field.kind === "whole" || field.kind === "angle") && NUMBER.test(text)) values[field.key] = Number(text);
    else values[field.key] = text;
  }
  if (form.test === PLATE_TEST && lists) for (const [key, list] of Object.entries(lists)) values[key] = list as unknown as number[];
  return values;
}

/** The form's text from a values object (a coupon read back through `GET /v1/coupons/{name}/values`). */
export function formFromValues(values: Record<string, unknown>): StudioForm {
  const form = blankForm(typeof values.units === "string" ? values.units : DEFAULT_UNITS);
  const angles = values.angles;
  if (Array.isArray(angles)) angles.forEach((angle, i) => { form[`ply_${i + 1}`] = angle === null || angle === undefined ? "" : String(angle); });
  for (const field of fields) {
    const value = values[field.key];
    if (value === null || value === undefined) continue;
    if (Array.isArray(value)) form[field.key] = value.join(", ");
    else if (typeof value === "boolean") form[field.key] = value ? "yes" : "no";
    else form[field.key] = String(value);
  }
  return form;
}

/** One requirement of the coupon's standard as the check judged it (ADR-0072): met, a deviation, an advisory, a note, the laboratory's, or na. */
export type JudgedRequirement = StandardRequirement & { state: "met" | "deviation" | "advisory" | "note" | "lab" | "na"; value: string; limit: string };
export type CheckItem = {
  id: string; label: string; state: "pass" | "warn" | "fail" | "missing" | "pending"; message: string; rows: string[]; requirements?: JudgedRequirement[];
};
export type Checklist = { items: CheckItem[]; designation: string | null; coupon_exists: boolean; attempts: number; state: "ready" | "blocked"; problems: string[] };

/** The rows a checklist names, by field key, with the item's message: what the form highlights. */
export function rowErrorsFrom(checklist: Checklist): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const item of checklist.items) {
    if (item.state !== "fail" && item.state !== "missing") continue;
    for (const label of item.rows) {
      const field = fieldByLabel[label];
      if (field && !errors[field.key]) errors[field.key] = item.message;
    }
  }
  return errors;
}

/** The first sentence of a row's help, for the hint under its input; "e.g." and "i.e." do not end a sentence. */
export function shortHelp(field: FieldDefinition): string {
  const text = field.help.split(/(?<!\be\.g\.|\bi\.e\.)(?<=[.;])\s/)[0] ?? "";
  return text.length > 140 ? text.slice(0, 137).trimEnd() + "..." : text;
}

export const libraryOptions: { id: string; name: string; thickness: number | null }[] = formDefinition.library.map((entry) => ({
  id: String(entry.Id), name: String(entry.Name), thickness: typeof entry["Ply thickness (mm)"] === "number" ? entry["Ply thickness (mm)"] : null,
}));
