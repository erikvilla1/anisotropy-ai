import type { Fields } from "./studio-api";
import { PROBE_COLUMNS, probeTable } from "./studio-fields";

/** A typed question about a result, read by fixed patterns (ADR-0099): the place it names and the quantities it asks for. It holds no
 * number of a result; `answerResultQuestion` reads those from the fields the page shows, as the probe table does (ADR-0066 amendment 2). */
export type ResultQuestion = {
  /** The element's number as the model labels it, "picked" for the element clicked on the model ("here"), null when none is named. */
  element: number | "picked" | null;
  /** The ply, counted from the bottom face, or null for every ply of the element. */
  ply: number | null;
  /** The quantities asked for, by the probe table's column names (`PROBE_COLUMNS`). */
  columns: string[];
};

/** What the page says of each column: the symbol, the quantity in words, whether it carries the stress unit, and the viewer's field of
 * the same quantity (`fieldOptions`), which the model is coloured by when the answer is shown on it. */
export const RESULT_COLUMNS: Record<string, { symbol: string; words: string; stress: boolean; field: string }> = {
  S11: { symbol: "σ₁", words: "stress along the fibres", stress: true, field: "S11" },
  S22: { symbol: "σ₂", words: "stress across the fibres", stress: true, field: "S22" },
  S12: { symbol: "τ₁₂", words: "in-plane shear stress", stress: true, field: "S12" },
  Mises: { symbol: "Mises", words: "Mises stress", stress: true, field: "mises" },
  Tresca: { symbol: "Tresca", words: "Tresca stress", stress: true, field: "tresca" },
  "Max. Principal": { symbol: "max. principal", words: "largest principal stress", stress: true, field: "max_principal" },
  "Mid. Principal": { symbol: "mid. principal", words: "middle principal stress", stress: true, field: "mid_principal" },
  "Min. Principal": { symbol: "min. principal", words: "smallest principal stress", stress: true, field: "min_principal" },
  Pressure: { symbol: "pressure", words: "pressure", stress: true, field: "pressure" },
  E11: { symbol: "ε₁", words: "strain along the fibres", stress: false, field: "E11" },
  E22: { symbol: "ε₂", words: "strain across the fibres", stress: false, field: "E22" },
  E12: { symbol: "γ₁₂", words: "engineering shear strain", stress: false, field: "E12" },
};

const SUBSCRIPTS: Record<string, string> = { "₁": "1", "₂": "2" };
const ELEMENT = /\b(?:element|elem|el)\b\.?\s*(?:#|no\.?|number)?\s*(\d{1,9})\b/;
const PICKED = /\b(?:here|this (?:element|spot|place|point|one)|that element|(?:the )?(?:picked|selected|clicked|highlighted) (?:element|one))\b/;
const PLY = /\b(?:ply|layer|lamina)\b\.?\s*(?:#|no\.?|number)?\s*(\d{1,4})\b/;
const STRESS_WORD = /\bstress(?:es)?\b/;
// "strain gauge", "strain device" and "strain length" are rows of the setup, not questions about a result
const STRAIN_WORD = /\bstrains?\b(?!\s+(?:gau?ge|device|length))/;
/** A component named by its code or symbol: it stands for itself, whatever else the message says. */
const CODES: [string, RegExp][] = [
  ["S11", /\bs11\b|\bsigma[\s_-]?11?(?!\s?2)\b|σ\s?11?(?!\s?2)/],
  ["S22", /\bs22\b|\bsigma[\s_-]?22?\b|σ\s?22?/],
  ["S12", /\bs12\b|\bsigma[\s_-]?12\b|σ\s?12|\btau(?:[\s_-]?12)?\b|τ/],
  ["Mises", /\b(?:von\s+)?mises\b/],
  ["Tresca", /\btresca\b/],
  ["E11", /\be11\b|\bepsilon[\s_-]?11?(?!\s?2)\b|ε\s?11?(?!\s?2)/],
  ["E22", /\be22\b|\bepsilon[\s_-]?22?\b|ε\s?22?/],
  ["E12", /\be12\b|\bepsilon[\s_-]?12\b|ε\s?12|\bgamma(?:[\s_-]?12)?\b|γ/],
];
/** A direction in words, which belongs to the quantity named beside it: "transverse strain", "shear stress". */
const ALONG = /\balong the fib(?:re|er)s?\b|\bin the fib(?:re|er)s?\b|\bfib(?:re|er)[\s-]?(?:direction|stress|strain)\b|\blongitudinal\b/;
const ACROSS = /\bacross the fib(?:re|er)s?\b|\bperpendicular to the fib(?:re|er)s?\b|\btransverse\b/;
const SHEAR = /\bshear\b/;
// a message that opens by setting something ("make ply 5 ...", "apply a stress of ...") states the setup, whatever it goes on to name
const SETTING = /^\s*(?:make|set|change|use|apply|add|put|pull|push|load|hold|fix)\b/;

/** The message as a question about a result, or null when it is not one: it must name a quantity (a stress or a strain) and a place (an
 * element, a ply, or "here"). Anything else is the setup's to read. */
export function readResultQuestion(message: string): ResultQuestion | null {
  const text = message.toLowerCase().replace(/[₁₂]/g, (c) => SUBSCRIPTS[c]);
  if (SETTING.test(text)) return null;
  const named = ELEMENT.exec(text);
  const element = named ? Number(named[1]) : PICKED.test(text) ? "picked" : null;
  const plyNamed = PLY.exec(text);
  const ply = plyNamed ? Number(plyNamed[1]) : null;
  if (element === null && ply === null) return null;

  const columns = new Set(CODES.filter(([, pattern]) => pattern.test(text)).map(([name]) => name));
  if (/\bprincipal\b/.test(text)) for (const name of ["Max. Principal", "Mid. Principal", "Min. Principal"]) columns.add(name);
  const directions = [ALONG.test(text), ACROSS.test(text), SHEAR.test(text)];
  const inWords = (codes: [string, string, string]) => {
    if (directions.some(Boolean)) codes.forEach((code, i) => { if (directions[i]) columns.add(code); });
    else if (!codes.some((code) => columns.has(code))) codes.forEach((code) => columns.add(code)); // "the stress": the three in the fibre axes
  };
  // "Mises stress" names Mises alone; a plain "stress" is the ply's own three components
  if (STRESS_WORD.test(text.replace(/\b(?:mises|tresca|principal)\s+stress(?:es)?\b/g, " "))) inWords(["S11", "S22", "S12"]);
  if (STRAIN_WORD.test(text)) inWords(["E11", "E22", "E12"]);
  const ordered = PROBE_COLUMNS.filter((c) => columns.has(c));
  return ordered.length ? { element, ply, columns: ordered } : null;
}

export type ResultRow = { ply: number; angle: number; face: string | null; values: (number | null)[] };
/** The answer read from the fields: the element by its number and its place, the rows asked for, and how the values are taken. */
export type ResultValues = {
  kind: "values";
  /** The element's index in the mesh the page shows, for the viewer; `label` is its number as the model writes it. */
  element: number;
  label: string;
  instance: string;
  centroid: [number, number];
  /** The named element sets it belongs to, as the model writes them. */
  sets: string[];
  columns: string[];
  rows: ResultRow[];
  /** How the values are taken (the probe table's own note): the centroid, no averaging, the fibre axes. */
  note: string;
};
export type ResultAnswer = ResultValues | { kind: "ask"; text: string } | { kind: "refused"; text: string };

const numberOf = (label: string) => label.slice(label.lastIndexOf(".") + 1);

/** The values a question asks for, read from the fields as the package wrote them: nothing is computed, converted or rounded here. A
 * place that is not in the model is refused with what the model holds; a question that names no element asks for one. */
export function answerResultQuestion(fields: Fields, question: ResultQuestion, picked: number | null): ResultAnswer {
  const labels = fields.mesh.element_labels;
  let element: number;
  if (typeof question.element === "number") {
    const found = labels.flatMap((label, i) => (numberOf(label) === String(question.element) ? [i] : []));
    if (!found.length) {
      const numbers = labels.map((l) => Number(numberOf(l))).filter(Number.isFinite);
      const range = numbers.length ? ` Its elements are numbered ${Math.min(...numbers)} to ${Math.max(...numbers)}.` : "";
      return { kind: "refused", text: `This model has no element ${question.element}.${range}` };
    }
    if (found.length > 1) return { kind: "refused", text: `More than one part has an element ${question.element}: ${found.map((i) => labels[i]).join(", ")}. Click the one you mean on the model and ask again.` };
    element = found[0];
  } else if (picked !== null && picked >= 0 && picked < labels.length) element = picked;
  else return { kind: "ask", text: "Which element? Click one on the model, or name its number, e.g. “element 120”." };

  const plies = fields.mesh.plies;
  if (question.ply !== null && (question.ply < 1 || question.ply > plies)) {
    return { kind: "refused", text: `This laminate has ${plies} ${plies === 1 ? "ply" : "plies"}, counted from the bottom face; there is no ply ${question.ply}.` };
  }
  const table = probeTable(fields, element);
  const at = question.columns.map((c) => PROBE_COLUMNS.indexOf(c));
  const rows = table.rows.filter((r) => question.ply === null || r.ply === question.ply)
    .map((r) => ({ ply: r.ply, angle: r.angle, face: r.face, values: at.map((i) => r.values[i] ?? null) }));
  const sets = Object.entries(fields.mesh.element_sets).filter(([, members]) => members.includes(element)).map(([name]) => name);
  return { kind: "values", element, label: table.label, instance: table.instance, centroid: table.centroid, sets, columns: question.columns, rows, note: table.note };
}

/** The unit a column is printed with: the fields' stress label, and none for a strain. */
export function resultUnit(fields: Fields, column: string): string {
  return RESULT_COLUMNS[column]?.stress ? fields.labels.stress ?? "" : "";
}

/** One value as a sentence, when the question asked for one: "σ₁ in ply 5 (-45°) at element 1212 is 123.4 MPa." Null when the answer
 * holds more than one value, which the page shows as a table. */
export function resultSentence(answer: ResultValues, unit: string, print: (value: number | null) => string): string | null {
  if (answer.rows.length !== 1 || answer.columns.length !== 1) return null;
  const row = answer.rows[0];
  const face = row.face ? `, ${row.face} face` : "";
  const value = row.values[0];
  if (value === null) return `No ${RESULT_COLUMNS[answer.columns[0]].words} is written for ply ${row.ply} at element ${answer.label}.`;
  return `${RESULT_COLUMNS[answer.columns[0]].symbol} in ply ${row.ply} (${row.angle}°${face}) at element ${answer.label} is ${print(value)}${unit ? ` ${unit}` : ""}.`;
}
