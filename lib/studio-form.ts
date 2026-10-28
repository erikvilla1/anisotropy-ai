/**
 * The studio's form (ADR-0051): the coupon input form's rows, as `fea/tools/export_form_definition.py` exports them, kept as text
 * while the engineer types and turned into the values object the API checks. Nothing here judges a value: `intake.check_form`
 * does, through `POST /v1/coupon-jobs/check`, and its refusals come back by row.
 */
import definition from "./coupon-form-definition.json";

export type FieldKind = "text" | "number" | "whole" | "date" | "list" | "angle";
export type FieldDefinition = {
  key: string; label: string; kind: FieldKind; help: string; required: boolean;
  default: string | number | null; words: string[]; at_least: number | null; above: number | null;
};
export type SectionDefinition = { title: string; fields: FieldDefinition[] };
export type LibraryEntry = Record<string, string | number | null>;
export type FormDefinition = {
  form_version: string; fea_version: string; units: string; row_units: Record<string, string>;
  sections: SectionDefinition[]; how_to: string[];
  glossary: { group: string; terms: { term: string; meaning: string; example: string }[] }[];
  tests: Record<string, string>; criteria: string[]; library: LibraryEntry[];
};
/** Every row's text as typed, by field key; blank means the row is empty. */
export type StudioForm = Record<string, string>;
/** The values object the API takes: the rows with numbers parsed, blanks left out (ADR-0046 amendment 3). */
export type StudioValues = Record<string, string | number | boolean | number[]>;

export const formDefinition = definition as FormDefinition;
export const FORM_VERSION = formDefinition.form_version;
export const fields: FieldDefinition[] = formDefinition.sections.flatMap((section) => section.fields);
export const fieldByKey: Record<string, FieldDefinition> = Object.fromEntries(fields.map((field) => [field.key, field]));
export const fieldByLabel: Record<string, FieldDefinition> = Object.fromEntries(fields.map((field) => [field.label, field]));
export const PLY_KEYS = fields.map((field) => field.key).filter((key) => /^ply_\d+$/.test(key));
export const HOLE_KEYS = ["hole_diameter", "hole_circumferential", "hole_radial", "hole_ring", "hole_growth"];
export const OPEN_HOLE_TEST = "open-hole tension";
const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

/** The public IM7/8552 example (the stand-in of `fea/tests/public_coupon.py`): a complete, solvable coupon to start from. */
export const EXAMPLE: StudioForm = {
  filled_by: "", date: "", notes: "", test: "unnotched tension", material_code: "IM7", layup_code: "", standard: "none",
  size_from: "the public IM7/8552 check fea/checks/unnotched-im7-8552/", team_model: "not built yet", test_data: "none",
  length: "250", width: "25", tab_length: "56", ply_1: "45", ply_2: "0", ply_3: "-45", ply_4: "90", symmetric: "yes", ply_thickness: "",
  library: "im7-8552", G13: "4688.43", G23: "3000", criteria: "all", f12_star: "", control: "displacement", value: "1", element_size: "2",
  grips: "coupling", region: "tabs",
};

/** Every row blank but the defaults the form states. */
export function blankForm(): StudioForm {
  const form: StudioForm = {};
  for (const field of fields) form[field.key] = field.default === null || field.default === undefined ? "" : String(field.default);
  return form;
}

export function exampleForm(today: string): StudioForm {
  return { ...blankForm(), ...EXAMPLE, date: today };
}

/** The sections to show for a test: the open-hole rows only for open-hole tension (the tool ignores them otherwise). */
export function sectionsFor(form: StudioForm): SectionDefinition[] {
  const openHole = form.test === OPEN_HOLE_TEST;
  return formDefinition.sections.filter((section) => openHole || !section.fields.some((field) => HOLE_KEYS.includes(field.key)));
}

/** The values object: numbers parsed where the row is a number, blanks left out, a text that is not a number left as text so the
 * API's check refuses it by row. No physics, no defaults beyond the form's own. */
export function buildValues(form: StudioForm): StudioValues {
  const values: StudioValues = { form_version: FORM_VERSION };
  for (const field of fields) {
    const text = (form[field.key] ?? "").trim();
    if (!text) continue;
    if ((field.kind === "number" || field.kind === "whole" || field.kind === "angle") && NUMBER.test(text)) values[field.key] = Number(text);
    else values[field.key] = text;
  }
  return values;
}

/** The form's text from a values object (a coupon read back through `GET /v1/coupons/{name}/values`). */
export function formFromValues(values: Record<string, unknown>): StudioForm {
  const form = blankForm();
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

export type CheckItem = { id: string; label: string; state: "pass" | "warn" | "fail" | "missing" | "pending"; message: string; rows: string[] };
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

/** The first sentence of a row's help, for the hint under its input. */
export function shortHelp(field: FieldDefinition): string {
  const text = field.help.split(/(?<=[.;])\s/)[0] ?? "";
  return text.length > 140 ? text.slice(0, 137).trimEnd() + "..." : text;
}

export const libraryOptions: { id: string; name: string; thickness: number | null }[] = formDefinition.library.map((entry) => ({
  id: String(entry.Id), name: String(entry.Name), thickness: typeof entry["Ply thickness (mm)"] === "number" ? entry["Ply thickness (mm)"] : null,
}));
