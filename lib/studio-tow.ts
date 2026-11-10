/**
 * The fibre tow test of ASTM D4018 in the studio (ADR-0074): a test on the coupon form's Test list that is no coupon. Its rows, the rows of a
 * specimen and the words of the Fig. 1 failure code come from `fea/tools/export_form_definition.py` (`tow`); this module only keeps them as
 * text while the engineer types and builds the values object `POST /v1/tow-tests` reads. Nothing here judges or computes: the fea package
 * judges the record, the engine computes every number.
 */
import { FORM_VERSION, formDefinition, NO_STANDARD, standardsFor, type Checklist, type FieldDefinition, type SectionDefinition, type StudioForm } from "./studio-form";
import type { PanelState } from "./workspace-panels";

export type TowDefinition = {
  test: string; kind: string; shared: string[]; sections: SectionDefinition[]; specimen_fields: FieldDefinition[]; item_of_row: Record<string, string>;
  failure_code: { type: Record<string, string>; area: Record<string, string>; location: Record<string, string> };
  units: Record<string, string>;
};
/** One specimen as typed: its rows by key, text. */
export type TowSpecimenRow = Record<string, string>;

export const towDefinition = (formDefinition as unknown as { tow: TowDefinition }).tow;
export const TOW_TEST = towDefinition.test;
export const towSections: SectionDefinition[] = towDefinition.sections;
export const towFields: FieldDefinition[] = towSections.flatMap((section) => section.fields);
export const towFieldByKey: Record<string, FieldDefinition> = Object.fromEntries(towFields.map((field) => [field.key, field]));
export const specimenFields: FieldDefinition[] = towDefinition.specimen_fields;
export const TOW_KEYS = towFields.map((field) => field.key);
/** The coupon form's rows the tow reads too, and the labels its checklist names them by. */
export const TOW_SHARED = towDefinition.shared;
const SHARED_LABELS: Record<string, string> = { test: "Test", standard: "Standard", filled_by: "Filled in by", date: "Date", notes: "Notes to us" };
const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

export const isTow = (form: StudioForm): boolean => form.test === TOW_TEST;

/** The standard a tow record may name: none, or the tow's standard (D4018). */
export const towStandards = (): string[] => [NO_STANDARD, ...standardsFor(TOW_TEST).map((p) => p.designation)];

/** The tow's rows the form does not hold yet, at the definition's defaults (bundles: 1): what picking the tow test adds, never overwriting a
 * row already typed. */
export function towDefaults(form: StudioForm): StudioForm {
  const rows: StudioForm = {};
  for (const field of towFields) if (form[field.key] === undefined) rows[field.key] = field.default === null || field.default === undefined ? "" : String(field.default);
  return rows;
}

export function blankSpecimen(n: number): TowSpecimenRow {
  const row: TowSpecimenRow = {};
  for (const field of specimenFields) row[field.key] = field.default === null || field.default === undefined ? "" : String(field.default);
  row.id = String(n);
  return row;
}

/** The next specimen's name: one past the largest number used, so a deleted row's name is not reused by accident. */
export function nextSpecimen(rows: TowSpecimenRow[]): TowSpecimenRow {
  const numbers = rows.map((r) => Number(r.id)).filter((n) => Number.isInteger(n) && n > 0);
  return blankSpecimen((numbers.length ? Math.max(...numbers) : 0) + 1);
}

function typed(field: FieldDefinition, text: string): string | number {
  return (field.kind === "number" || field.kind === "whole") && NUMBER.test(text) ? Number(text) : text;
}

/** A pasted block of specimens: one per line, its cells split by tabs (a spreadsheet's copy) or commas, in the specimen rows' order; a
 * blank status is valid. Text only: every cell is read and judged by the fea package when the record is calculated. */
export function pastedSpecimens(text: string): TowSpecimenRow[] {
  const columns = specimenFields.map((f) => f.key);
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const cells = line.includes("\t") ? line.split("\t") : line.split(",");
    const row: TowSpecimenRow = {};
    columns.forEach((key, i) => { row[key] = (cells[i] ?? "").trim(); });
    if (!row.status) row.status = "valid";
    return row;
  });
}

/** The values object of a tow record: the shared rows and the tow's, numbers parsed where the row is a number, blanks left out, and the
 * specimens, each with its typed cells; a text that is not a number is left as text so the API refuses it by row. No physics, no defaults. */
export function towValues(form: StudioForm, specimens: TowSpecimenRow[]): Record<string, unknown> {
  const values: Record<string, unknown> = { form_version: FORM_VERSION, test: TOW_TEST };
  for (const key of TOW_SHARED) {
    if (key === "test") continue;
    const text = (form[key] ?? "").trim();
    if (text) values[key] = text;
  }
  for (const field of towFields) {
    const text = (form[field.key] ?? "").trim();
    if (text) values[field.key] = typed(field, text);
  }
  values.specimens = specimens.map((row) => {
    const out: Record<string, string | number> = {};
    for (const field of specimenFields) {
      const text = (row[field.key] ?? "").trim();
      if (text) out[field.key] = typed(field, text);
    }
    return out;
  });
  return values;
}

/** The rows a tow checklist names, by key (a shared row by its coupon key, the specimen list as `specimens`), with the item's message. */
export function towRowErrors(checklist: Checklist): Record<string, string> {
  const byLabel: Record<string, string> = Object.fromEntries([
    ...towFields.map((field) => [field.label, field.key]), ...Object.entries(SHARED_LABELS).map(([key, label]) => [label, key]), ["Specimens", "specimens"],
  ]);
  const errors: Record<string, string> = {};
  for (const item of checklist.items) {
    if (item.state !== "fail" && item.state !== "missing") continue;
    for (const label of item.rows) {
      const key = byLabel[label];
      if (key && !errors[key]) errors[key] = item.message;
    }
  }
  return errors;
}

/** A Fig. 1 failure code in words, as the definition lists the letters; null when it is not three letters of the figure. */
export function failureCodeWords(code: string): string | null {
  const c = code.trim().toUpperCase();
  const { type, area, location } = towDefinition.failure_code;
  if (c.length !== 3 || !type[c[0]] || !area[c[1]] || !location[c[2]]) return null;
  return `${type[c[0]]}, ${area[c[1]]}, ${location[c[2]]}`;
}

/** The tow's panels, each with its rows and the checklist items that judge them. */
export type TowPanelId = "tow-project" | "tow-fibre" | "tow-mass" | "tow-strand" | "tow-test" | "tow-specimens" | "tow-calculate";
export const TOW_PANELS: { id: TowPanelId; title: string; keys: string[]; items: string[] }[] = [
  { id: "tow-project", title: "Project", keys: ["test", "standard", "filled_by", "date", "notes"], items: ["standard"] },
  { id: "tow-fibre", title: "The fibre tow", keys: towSections[0].fields.map((f) => f.key), items: ["identity"] },
  { id: "tow-mass", title: "Mass per unit length and density", keys: towSections[1].fields.map((f) => f.key), items: ["fibre"] },
  { id: "tow-strand", title: "The impregnated strand", keys: towSections[2].fields.map((f) => f.key), items: ["fibre"] },
  { id: "tow-test", title: "The tensile test", keys: [...towSections[3].fields, ...towSections[4].fields].map((f) => f.key), items: ["test"] },
  { id: "tow-specimens", title: "Specimens tested", keys: [], items: ["specimens"] },
  { id: "tow-calculate", title: "Calculate", keys: [], items: ["results"] },
];

const SEVERITY: Record<Exclude<PanelState, "none">, number> = { pass: 0, pending: 1, warn: 2, fail: 3, missing: 3 };

/** The worst state among a tow panel's checklist items, as the coupon's panels show theirs; `none` before a calculation. */
export function towPanelState(id: TowPanelId, checklist: Checklist | null): PanelState {
  const wanted = TOW_PANELS.find((p) => p.id === id)?.items ?? [];
  const states = (checklist?.items ?? []).filter((item) => wanted.includes(item.id)).map((item) => item.state);
  return states.reduce<PanelState>((worst, s) => (worst === "none" || SEVERITY[s] > SEVERITY[worst as Exclude<PanelState, "none">] ? s : worst), "none");
}
