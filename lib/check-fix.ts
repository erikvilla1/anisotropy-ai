/**
 * The rows a failing check item offers to fill in the chat (ADR-0062 amendment 2): each item's named rows, typed where it is read, then
 * applied together and checked again. The page judges nothing: the fea package's check names the rows and refuses a value, as it does when
 * the same rows are typed on the panels.
 */
import { fieldByKey, fieldByLabel, labelFor, PLY_KEYS, type CheckItem, type FieldDefinition, type StudioForm } from "./studio-form";

/** Rows this many or fewer are offered in the chat; an item naming more is fixed on its panel. */
export const MOST_ROWS = 6;

/** The rows each failing item offers, by item id, in the order the check names them: a row named by two items is offered under the first;
 * a ply is left to the layup step, which reads the whole stack as a notation; a label the form does not hold offers nothing. */
export function fixRows(items: CheckItem[]): Map<string, FieldDefinition[]> {
  const offered = new Set<string>();
  const out = new Map<string, FieldDefinition[]>();
  for (const item of items) {
    if (item.state !== "fail" && item.state !== "missing") continue;
    const rows: FieldDefinition[] = [];
    for (const label of item.rows) {
      const field = fieldByLabel[label];
      if (!field || PLY_KEYS.includes(field.key) || offered.has(field.key)) continue;
      offered.add(field.key);
      rows.push(field);
    }
    if (rows.length && rows.length <= MOST_ROWS) out.set(item.id, rows);
  }
  return out;
}

/** The rows typed in the chat that differ from the form's, trimmed; a row emptied is sent empty, which clears it. */
export function changedRows(form: StudioForm, typed: StudioForm): StudioForm {
  const rows: StudioForm = {};
  for (const [key, value] of Object.entries(typed)) {
    if (value.trim() !== (form[key] ?? "").trim()) rows[key] = value.trim();
  }
  return rows;
}

/** What the engineer's message says in the conversation: each row by its label in the coupon's units, with what was typed. */
export function fixEcho(rows: StudioForm, units: string): string {
  return Object.entries(rows).map(([key, value]) => {
    const field = fieldByKey[key];
    const label = field ? labelFor(field, units) : key;
    return value ? `${label}: ${value}` : `${label}: cleared`;
  }).join("; ");
}
