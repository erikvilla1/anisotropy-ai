import type { Fields, ResultOffer, ResultRequest } from "./studio-api";
import { DEFAULT_CHOICE, PROBE_COLUMNS, probeTable, valuesFor } from "./studio-fields";

/** Which end of a quantity an extreme question asks for (ADR-0100): the largest value with its sign (the most tensile), the smallest (the
 * most compressive), or the largest magnitude. */
export type Sense = "largest" | "smallest" | "magnitude";

/** Where an extreme is looked for (ADR-0100): the gauge section as the package means it (the elements it read, ADR-0108), the whole model, a named element set, or "default": the gauge section where the model has one, else the whole model. */
export type Region = "default" | "gauge" | "whole" | { set: string };

/** A typed question about a result, read by fixed patterns (ADR-0099) or by a model into the same fixed form (ADR-0100): the place it
 * names and the quantities it asks for. It holds no number of a result; `answerResultQuestion` reads those from the fields the page
 * shows, as the probe table does (ADR-0066 amendment 2). */
export type ResultQuestion =
  | {
    kind: "values";
    /** The element's number as the model labels it, "picked" for the element clicked on the model ("here"), null when none is named. */
    element: number | "picked" | null;
    /** The plies, counted from the bottom face, or null for every ply of the element. */
    plies: number[] | null;
    /** The quantities asked for, by the probe table's column names (`PROBE_COLUMNS`). */
    columns: string[];
  }
  | {
    /** Where a quantity is largest: one stored value picked out of those of the plies and the region named, never a derived number. */
    kind: "extreme";
    sense: Sense;
    plies: number[] | null;
    region: Region;
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
const EXTREME_WORDS: [Sense, RegExp][] = [
  ["smallest", /\b(?:min(?:imum)?|lowest|smallest|least|most compressive|most negative)\b/],
  ["largest", /\b(?:max(?:imum)?|highest|most tensile|most positive)\b/],
  ["magnitude", /\b(?:largest|biggest|greatest|peak|worst|most)\b/],
];
// "maximum stress" and "maximum strain" also name failure criteria, which are rows of the setup
const CRITERION = /\b(?:max(?:imum)?[\s-]+(?:stress|strain))\s+(?:criterion|criteria|theory|failure)\b|\bcriteri(?:on|a)\b/;
const GAUGE = /\bgau?ge\b/;
const WHOLE = /\b(?:whole|entire|anywhere|everywhere|overall|including the (?:grips?|tabs?)|at the (?:grips?|tabs?))\b/;
/** A quantity with no sign to speak of: its extreme is its largest magnitude, whatever word asks for it. */
const UNSIGNED = new Set(["S12", "E12", "Mises", "Tresca"]);
// a message that opens by setting something ("make ply 5 ...", "apply a stress of ...") states the setup, whatever it goes on to name
const SETTING = /^\s*(?:make|set|change|use|apply|add|put|pull|push|load|hold|fix)\b/;

/** The message as a question about a result, or null when it is not one. It must name a quantity (a stress or a strain) and either a
 * place (an element, a ply, or "here") or an extreme ("highest", "largest", "minimum"). Anything else is the setup's to read. */
export function readResultQuestion(message: string): ResultQuestion | null {
  const text = message.toLowerCase().replace(/[₁₂]/g, (c) => SUBSCRIPTS[c]);
  if (SETTING.test(text) || CRITERION.test(text)) return null;
  const named = ELEMENT.exec(text);
  const element = named ? Number(named[1]) : PICKED.test(text) ? "picked" : null;
  const plyNamed = PLY.exec(text);
  const plies = plyNamed ? [Number(plyNamed[1])] : null;
  const sense = EXTREME_WORDS.find(([, pattern]) => pattern.test(text))?.[0] ?? null;
  if (element === null && plies === null && sense === null) return null;

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
  if (!ordered.length) return null;
  // an element named, or "here", is a place to read every value at; with none, an extreme word asks where the quantity is largest
  if (element !== null || sense === null) return { kind: "values", element, plies, columns: ordered };
  const region: Region = GAUGE.test(text.replace(/\bstrain\s+gau?ge\b/g, " ")) ? "gauge" : WHOLE.test(text) ? "whole" : "default";
  return { kind: "extreme", sense, plies, region, columns: ordered };
}

/** What a message may name of these results, for a model to read a loose question against (ADR-0100): the quantities, the plies and
 * their angles, whether there is a gauge section, whether an element is clicked. No value of the results is in it. */
export function resultOffer(fields: Fields, message: string, picked: number | null): ResultOffer {
  return { message, quantities: [...PROBE_COLUMNS], plies: fields.mesh.angles.map((angle, i) => ({ ply: i + 1, angle })), gauge: gaugeSection(fields) !== null,
    picked: picked !== null && picked >= 0 && picked < fields.mesh.element_labels.length };
}

/** A model's reading, as the API's guard kept it, as the typed question the page runs; null when it names nothing the probe table holds.
 * The page judges the place again when it answers: an element or a ply the model does not hold is refused there. */
export function questionFrom(request: ResultRequest): ResultQuestion | null {
  if (request.kind === "failure") return null; // the package's own answer, not a value of the probe table (lib/result-failure.ts)
  const columns = PROBE_COLUMNS.filter((c) => request.quantities.includes(c));
  if (!columns.length) return null;
  const plies = request.plies.length ? request.plies : null;
  if (request.kind === "extreme") return request.sense ? { kind: "extreme", sense: request.sense, plies, region: request.region, columns } : null;
  return { kind: "values", element: request.element ?? (request.here ? "picked" : null), plies, columns };
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
/** One ply's extreme of a quantity: a stored value, the element it is at, and the plies it is tied with at that very value. */
export type ExtremeRow = { ply: number; angle: number; face: string | null; value: number; element: number; label: string; sets: string[] };
/** Where a quantity is largest (ADR-0100): per quantity asked for, each ply's extreme over the region, and which ply holds the overall. */
export type ResultExtremes = {
  kind: "extremes";
  /** The end asked for, per column: an unsigned quantity is always read by magnitude. */
  blocks: { column: string; sense: Sense; rows: ExtremeRow[]; best: number; tied: number[] }[];
  /** The region read, in words ("the gauge section"), and how many elements it holds. */
  region: string;
  elements: number;
  /** Whether the overall extreme of some quantity sits at a grip's clamped edge, where stress grows as the mesh is refined (ADR-0066). */
  atGrip: boolean;
  note: string;
};
export type ResultAnswer = ResultValues | ResultExtremes | { kind: "ask"; text: string } | { kind: "refused"; text: string };

const numberOf = (label: string) => label.slice(label.lastIndexOf(".") + 1);

/** The values a question asks for, read from the fields as the package wrote them: nothing is computed, converted or rounded here. A
 * place that is not in the model is refused with what the model holds; a question that names no element asks for one. */
export function answerResultQuestion(fields: Fields, question: ResultQuestion, picked: number | null): ResultAnswer {
  const labels = fields.mesh.element_labels;
  const count = fields.mesh.plies;
  const unknown = (question.plies ?? []).find((ply) => !Number.isInteger(ply) || ply < 1 || ply > count);
  if (unknown !== undefined) {
    return { kind: "refused", text: `This laminate has ${count} ${count === 1 ? "ply" : "plies"}, counted from the bottom face; there is no ply ${unknown}.` };
  }
  const asked = question.plies ? [...new Set(question.plies)].sort((a, b) => a - b) : null;
  if (question.kind === "extreme") return extremesOf(fields, question, asked);
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

  const table = probeTable(fields, element);
  const at = question.columns.map((c) => PROBE_COLUMNS.indexOf(c));
  const rows = table.rows.filter((r) => asked === null || asked.includes(r.ply))
    .map((r) => ({ ply: r.ply, angle: r.angle, face: r.face, values: at.map((i) => r.values[i] ?? null) }));
  return { kind: "values", element, label: table.label, instance: table.instance, centroid: table.centroid, sets: setsOf(fields, element), columns: question.columns, rows, note: table.note };
}

const setsOf = (fields: Fields, element: number) => Object.entries(fields.mesh.element_sets).filter(([, members]) => members.includes(element)).map(([name]) => name);

/** The elements with a gripped node: the row along each tab line, the clamped edge (ADR-0066), by the grips' node sets as the fields
 * name them. Empty for a model without grips. */
function atGrips(fields: Fields): Set<number> {
  const gripped = new Set(Object.entries(fields.mesh.node_sets).filter(([name]) => /^Grip-/.test(name)).flatMap(([, nodes]) => nodes));
  const out = new Set<number>();
  if (gripped.size) fields.mesh.quads.forEach((quad, e) => { if (quad.slice(0, 4).some((n) => gripped.has(n))) out.add(e); });
  return out;
}

/** The gauge section as the package reads it: the elements it wrote with the fields (`mesh.gauge_elements`, ADR-0108: the `Gauge` set at
 * least the stand-off from each tab line), so the page derives none. A result solved before that record holds no list and is read by its
 * own rule (ADR-0085): the `Gauge` set less the elements at a gripped node. Null for a model without a gauge section. A test holds the
 * page's reading to the package's own extremes. */
export function gaugeSection(fields: Fields): number[] | null {
  const read = fields.mesh.gauge_elements;
  if (read !== undefined) return read?.length ? read : null;
  const gauge = fields.mesh.element_sets.Gauge;
  const grips = atGrips(fields);
  return gauge?.length && grips.size ? gauge.filter((e) => !grips.has(e)) : null;
}

/** Each ply's extreme of each quantity over a region (ADR-0100): the values are the fields' own, per element and ply (and face), and one of
 * them is picked; nothing is summed, averaged or derived. The first element in the mesh's order holds a tie between elements. */
function extremesOf(fields: Fields, question: Extract<ResultQuestion, { kind: "extreme" }>, asked: number[] | null): ResultAnswer {
  const sets = fields.mesh.element_sets;
  const gauge = gaugeSection(fields);
  let members: number[], region: string;
  if (typeof question.region === "object") {
    const name = question.region.set;
    if (!sets[name]) return { kind: "refused", text: `This model has no region “${name}”.${Object.keys(sets).length ? ` Its regions are ${Object.keys(sets).join(", ")}.` : ""}` };
    [members, region] = [sets[name], `the region ${name}`];
  } else if (question.region === "gauge" && !gauge) return { kind: "refused", text: "This model has no gauge section between grips. Ask for the whole model, or name an element." };
  else if (question.region !== "whole" && gauge) [members, region] = [gauge, "the gauge section"];
  else [members, region] = [fields.mesh.element_labels.map((_, i) => i), "the whole model"];
  const faces = fields.mesh.faces?.length ? fields.mesh.faces : [null];
  const plies = asked ?? fields.mesh.angles.map((_, i) => i + 1);
  const blocks = question.columns.map((column) => {
    const sense: Sense = UNSIGNED.has(column) ? "magnitude" : question.sense;
    const score = (v: number) => (sense === "largest" ? v : sense === "smallest" ? -v : Math.abs(v));
    const rows: ExtremeRow[] = [];
    for (const ply of plies) {
      let found: { value: number; element: number; face: string | null } | null = null;
      faces.forEach((face, f) => {
        const values = valuesFor(fields, { ...DEFAULT_CHOICE(fields), id: RESULT_COLUMNS[column].field, ply, face: f, averaged: false }).values;
        for (const e of members) {
          const v = values[e];
          if (typeof v === "number" && Number.isFinite(v) && (found === null || score(v) > score(found.value))) found = { value: v, element: e, face };
        }
      });
      const hit = found as { value: number; element: number; face: string | null } | null;
      if (hit) rows.push({ ply, angle: fields.mesh.angles[ply - 1], face: hit.face, value: hit.value, element: hit.element, label: numberOf(fields.mesh.element_labels[hit.element]), sets: setsOf(fields, hit.element) });
    }
    let best = 0;
    rows.forEach((row, i) => { if (score(row.value) > score(rows[best].value)) best = i; });
    const tied = rows.filter((row, i) => i !== best && score(row.value) === score(rows[best].value)).map((row) => row.ply);
    return { column, sense, rows, best, tied };
  }).filter((block) => block.rows.length);
  if (!blocks.length) return { kind: "refused", text: "These results hold no value of that quantity." };
  const grips = atGrips(fields);
  return { kind: "extremes", blocks, region, elements: members.length, atGrip: blocks.some((b) => grips.has(b.rows[b.best].element)),
    note: "Element centroids, no averaging, fibre axes." };
}

/** The unit a column is printed with: the fields' stress label, and none for a strain. */
export function resultUnit(fields: Fields, column: string): string {
  return RESULT_COLUMNS[column]?.stress ? fields.labels.stress ?? "" : "";
}

/** One value as a sentence, when the question asked for one: "σ₁ in ply 5 (-45°) at element 1212 is 123.4 MPa." Null when the answer
 * holds more than one value, which the page shows as a table. */
/** An extreme's end in words, before the symbol: "largest σ₁" (with its sign, the most tensile), "smallest σ₁", "largest |τ₁₂|". */
export function extremeWords(column: string, sense: Sense): string {
  const symbol = RESULT_COLUMNS[column].symbol;
  return sense === "magnitude" ? `largest |${symbol}|` : `${sense} ${symbol}`;
}

/** A chat answer as the page says it (ADR-0099 amendment 2): the answer itself as the heading, and short labels for what it is of. */
export type AnswerLines = { headline: string; facts: string[] };

const plyLabel = (row: { ply: number; angle: number; face: string | null }) => `ply ${row.ply} (${row.angle}°)${row.face ? `, ${row.face} face` : ""}`;

/** An extreme in short: "Largest |τ₁₂|: −45.86 MPa", then "ply 1 (45°)", "element 73", "gauge section", "tied with plies 3, 6, 8". */
export function extremeLines(block: ResultExtremes["blocks"][number], region: string, unit: string, print: (value: number | null) => string): AnswerLines {
  const row = block.rows[block.best];
  const words = extremeWords(block.column, block.sense);
  const tied = block.tied.length ? [`tied with ${block.tied.length > 1 ? "plies" : "ply"} ${block.tied.join(", ")}`] : [];
  return { headline: `${words.charAt(0).toUpperCase()}${words.slice(1)}: ${print(row.value)}${unit ? ` ${unit}` : ""}`,
    facts: [plyLabel(row), `element ${row.label}`, region.replace(/^the /, ""), ...tied] };
}

/** One value in short: "σ₁ = 1182 MPa", then "ply 2 (0°)", "element 125". Null when the answer holds more than one value, which is a table's. */
export function valueLines(answer: ResultValues, unit: string, print: (value: number | null) => string): AnswerLines | null {
  if (answer.rows.length !== 1 || answer.columns.length !== 1) return null;
  const row = answer.rows[0];
  const symbol = RESULT_COLUMNS[answer.columns[0]].symbol;
  const value = row.values[0];
  return { headline: value === null ? `No ${symbol} written here` : `${symbol} = ${print(value)}${unit ? ` ${unit}` : ""}`, facts: [plyLabel(row), `element ${answer.label}`] };
}
