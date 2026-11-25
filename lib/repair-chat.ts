/**
 * The repair's chat (ADR-0136): what the page reads in a message by its own patterns, and how it answers. A change is read into the
 * engine's form (`RepairChange`, `engine/src/anisotropy_engine/repair/changes.py`) and a sweep into `RepairSweep`
 * (`repair/sweeps.py`), every number taken from the engineer's words with the unit as written, which the engine converts; the API
 * previews the change, or runs the sweep, before anything on the page changes. A question about the result is answered from the
 * report, the solved slice, the followed bond (ADR-0140) and the repair carried with its plies damaging (ADR-0141) the page already
 * holds, every number as the engine or the solver gave it; a question of why, how or what a thing is from the reference pages the API's search finds. A question that asks for a verdict is told the page gives none,
 * with what it does give. Nothing here computes a result. Pure: no React, no browser, so `tests/repair-chat.test.ts` runs it.
 */
import {
  ADHESIVE_FIELDS, bondWords, CARRIES_IS_NOT_THE_STRENGTH, COVER_FIELDS, DAMAGE_FIELDS, EXTERNAL_PATCH_FIELDS, FIRST_WORDS, inSentence, kindOf, LET_GO_IS_NOT_THE_STRENGTH,
  NOT_THE_STRENGTH, PANEL_FIELDS, peakPlace, pliesNeedsWords, pliesWords, plyBefore, REPAIR_UNIT_LABELS, shown, sliceWords, unitsOf, unitText, valueAt,
  type BondReport, type PliesReport, type RepairDescription, type RepairField, type RepairKind, type RepairReport, type SliceReport, type SolveNeed,
} from "./repair";

/** Every way the repair's chat answers a message. */
export const REPAIR_ROUTES = ["repair-change", "repair-sweep", "repair-result", "repair-reference", "repair-command", "repair-unread"] as const;
export type RepairRoute = (typeof REPAIR_ROUTES)[number];

/** What a change may set, by the engine's names. */
export type RepairQuantity = "step_length" | "bondline" | "load" | "damage" | "cover_overlap" | "patch_overlap";
/** What a sweep may vary: `steps` is the same plies grouped in every number of steps that divides them. */
export type SweepQuantity = "step_length" | "bondline" | "cover_overlap" | "patch_overlap" | "steps";
/** A change as the engine's `RepairChange` takes it. `unit` is the engine's spelling of the unit the message writes, or the message's
 * own word when the engine has none, which it then refuses in words; left out, the value is in the file's unit. */
export type RepairChange =
  | { action: "set"; quantity: RepairQuantity; value: number; unit?: string }
  | { action: "add_steps" | "remove_steps" | "set_steps"; count: number; angles?: number[] }
  | { action: "regroup" | "regroup_steps"; count: number };
/** A sweep as the engine's `RepairSweep` takes it: the range and the load are the message's, each in its unit as written. */
export type RepairSweep = { quantity: SweepQuantity; start?: number; end?: number; unit?: string; load?: number; load_unit?: string };
/** What a question of the result asks for. */
export type RepairTopic = "shear" | "limit" | "elastic" | "peel" | "ply" | "first" | "forces" | "size" | "steps" | "layup" | "stated" | "verdict" | "bond" | "carries";

export type RepairAsk =
  /** A change: read whole (`change`), or not (`problem`, in the page's words, and whether it asks back rather than declines). */
  | { route: "repair-change"; change: RepairChange | null; problem: string | null; asks: boolean; panel?: string }
  /** A sweep: read whole, or not; `assumed` says what the page took when the message named no quantity. */
  | { route: "repair-sweep"; sweep: RepairSweep | null; problem: string | null; asks: boolean; assumed?: boolean }
  /** `onset` says a question of the bond's failure asks where or when it starts, not when the bond lets go; `failed` that a question of
   * the load the repair carries asks what had failed by then. */
  | { route: "repair-result"; topic: RepairTopic; field?: RepairField; panel?: string; load?: { value: number; unit?: string }; onset?: boolean; plies?: "yes-no" | "which";
      failed?: boolean }
  /** A question of why, how or what a thing is: the reference pages answer it, beside the repair's own number on what it names. */
  | { route: "repair-reference"; topic: RepairTopic | null }
  | { route: "repair-command"; command: "solve" | "bond" | "plies" | "report" | "shape" | "undo" }
  | { route: "repair-unread" };

export const QUANTITY_WORDS: Record<RepairQuantity | "steps", string> = {
  step_length: "the step length", bondline: "the bondline's thickness", load: "the load", damage: "the damage's diameter",
  cover_overlap: "the cover plies' overlap", patch_overlap: "the patch's overlap", steps: "the number of steps",
};
const QUANTITY_PANEL: Record<RepairQuantity, string> = {
  step_length: "repair-damage", bondline: "repair-adhesive", load: "repair-loads", damage: "repair-damage", cover_overlap: "repair-cover", patch_overlap: "repair-patch",
};
const EXAMPLE_VALUE: Record<RepairQuantity, [string, string]> = { // a value to show in an example, in millimetres and in inches
  step_length: ["10 mm", "0.5 in"], bondline: ["0.15 mm", "0.006 in"], load: ["150 N/mm", "800 lb/in"], damage: ["30 mm", "1 in"],
  cover_overlap: ["15 mm", "0.5 in"], patch_overlap: ["20 mm", "0.75 in"],
};

/** A message as the patterns read it: lower case, one space, typographic signs made plain. */
function plain(text: string): string {
  return text.toLowerCase().replace(/[’‘]/g, "'").replace(/[“”]/g, '"').replace(/[−–—]/g, "-").replace(/º/g, "°").replace(/\s+/g, " ").trim();
}

// ---------------------------------------------------------------------------------------------------- numbers and their units

/** A unit as the engine spells it (engine units.py); a unit the engine has no name for goes to it as written and is refused there. */
const ENGINE_UNIT: Record<string, string> = {
  mm: "mm", millimeter: "mm", millimeters: "mm", millimetre: "mm", millimetres: "mm", cm: "cm", m: "m", in: "in", inch: "in", inches: "in", '"': "in",
  "n/mm": "N/mm", "n/m": "N/m", "kn/m": "kN/m", "kn/mm": "kN/mm", "lb/in": "lb/in", "lbf/in": "lb/in", "lbs/in": "lb/in", "lb/inch": "lb/in", "lbf/inch": "lb/in",
  "lbs/inch": "lb/in", pli: "lb/in", "kip/in": "kip/in", "kips/in": "kip/in", psi: "psi", ksi: "ksi", msi: "Msi", mpa: "MPa", gpa: "GPa",
};
const LENGTH_UNITS = new Set(["mm", "cm", "m", "in"]);
const LOAD_UNITS = new Set(["N/mm", "N/m", "kN/m", "kN/mm", "lb/in", "kip/in"]);
const NUMBER = String.raw`(\d+\s*\/\s*\d+(?![\d/])|\d*\.\d+|\d+)`;
const UNIT = String.raw`(kn\/mm|kn\/m|n\/mm|n\/m|lbf?s?\/in(?:ch)?\b|kips?\/in\b|pli\b|millimet(?:er|re)s?\b|mm\b|cm\b|inch(?:es)?\b|in\b|"|ft\b|feet\b|foot\b|mils?\b|thou\b|microns?\b|µm|um\b|psi\b|ksi\b|msi\b|mpa\b|gpa\b|m\b|%|percent\b)`;
const VALUE = new RegExp(String.raw`(?<![\w./-])${NUMBER}\s*${UNIT}?`, "g");

type Written = { value: number; unit?: string; kind: "length" | "load" | "relative" | "other" | null; at: number; end: number };

/** A number as written: a decimal, or a simple fraction ("1/2"). */
function numberOf(text: string): number {
  const parts = text.split("/").map((part) => Number(part.trim()));
  return parts.length === 2 ? parts[0] / parts[1] : parts[0];
}

/** Every number a message writes, each with the unit that follows it and where it stands. */
function written(text: string): Written[] {
  const found: Written[] = [];
  for (const m of text.matchAll(VALUE)) {
    const value = numberOf(m[1]);
    if (!Number.isFinite(value)) continue;
    const word = m[2];
    const unit = word === undefined ? undefined : ENGINE_UNIT[word] ?? word;
    const kind = unit === undefined ? null : unit === "%" || unit === "percent" ? "relative" : LENGTH_UNITS.has(unit) ? "length" : LOAD_UNITS.has(unit) ? "load" : "other";
    found.push({ value, ...(unit === undefined ? {} : { unit }), kind, at: m.index ?? 0, end: (m.index ?? 0) + m[0].length });
  }
  return found;
}

const COUNT_WORDS: Record<string, number> = {
  a: 1, an: 1, one: 1, another: 1, single: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
};
const COUNT = String.raw`(\d+|another|single|one|two|three|four|five|six|seven|eight|nine|ten|an|a)`;
const countOf = (word: string): number => COUNT_WORDS[word] ?? Number(word);

// ---------------------------------------------------------------------------------------------------- what a message names

const BONDLINE = /\bbond\s*-?\s*lines?\b|\bglue\s*-?\s*lines?\b|\badhesive(?:'s)? (?:layer )?thickness\b|\bthickness of the (?:adhesive|bond|glue)\b|\badhesive layer\b|\b(?:thicker|thinner) adhesive\b/;
const STEP_LENGTH = /\bstep(?:'s)? lengths?\b|\blength of (?:each |the |a |every )?steps?\b|\b(?:each|every) step\b|\bledges?\b|\bstep (?:width|size)s?\b|\bsteps? (?:longer|shorter)\b|\b(?:longer|shorter) steps?\b/;
const OVERLAP = /\boverlaps?\b/;
const DAMAGE = /\b(?:damage|hole|deepest cut)(?:'s)?(?: diameter| size)?\b|\bdiameter\b/;
const LOAD = /\bload\b|\bloading\b|\bpull\b|\btension\b/;

/** The quantity a message names, or null. "The overlap" is the cover plies' on a flush repair and the patch's on one bonded on top. */
function quantityOf(text: string, kind: RepairKind, values: Written[] = []): RepairQuantity | null {
  if (BONDLINE.test(text)) return "bondline";
  if (STEP_LENGTH.test(text)) return "step_length";
  if (/\bcover\b/.test(text) && OVERLAP.test(text)) return "cover_overlap";
  if (/\bpatch\b/.test(text) && OVERLAP.test(text)) return "patch_overlap";
  if (OVERLAP.test(text)) return kind === "external" ? "patch_overlap" : "cover_overlap";
  if (DAMAGE.test(text)) return "damage";
  if (/\bsteps?\b/.test(text) && values.some((v) => v.kind === "length")) return "step_length"; // "make the steps 10 mm"
  if (LOAD.test(text) || values.some((v) => v.kind === "load")) return "load";
  return null;
}

const ASKING = /^(?:what|what's|whats|which|how|why|does|do|is|are|can (?:i|it|we|this|the)|should|where|when|will|would)\b/;
const WHAT_IF = /^(?:what if|what happens if|what would happen if|how about|what about|and if|suppose|say)\b/;
const SET = /\b(?:set|make|change|use|put|increase|decrease|reduce|raise|lower|bump|try|give|shorten|lengthen|thicken|widen|grow|shrink|go (?:back )?to|go with|switch|move|want|should be)\b/;
const ADD = /\b(?:add|ad|adding|another|one more|more|extra|additional)\b/; // "ad a step" is read as it was meant
const REMOVE = /\b(?:remove|removing|take (?:off|out|away)|delete|drop|fewer|less)\b/;
const RELATIVE = /\b(?:double|halve|half|twice|triple|increase|decrease|reduce|raise|lower|bump|shorten|lengthen|thicken|thin|widen|grow|shrink|longer|shorter|thicker|thinner|bigger|smaller|higher|more|less)\b/;

/** The ply angles a message gives a new step: "of 45/-45", "with a 0° ply", "[0, 90]". Every angle is one the message writes. */
function anglesOf(after: string): number[] | undefined {
  if (!/°|\bdeg|\bpl(?:y|ies)\b|\bangles?\b|\[|-?\d\s*\/\s*-?\d/.test(after)) return undefined;
  const angles = [...after.replace(/\b\d+\s*pl(?:y|ies)\b/g, " ").matchAll(/(?<![\w.])[+-]?\d+(?:\.\d+)?/g)].map((m) => Number(m[0]));
  return angles.length ? angles : undefined;
}

const change = (problem: string, asks = true, panel?: string): RepairAsk => ({ route: "repair-change", change: null, problem, asks, ...(panel ? { panel } : {}) });

/** A message read as a change of the steps, or null: steps added, removed, set to a number, or the same plies regrouped. */
function stepsChange(text: string, values: Written[]): RepairAsk | null {
  if (!/\bsteps?\b/.test(text)) return null;
  const read = (found: RepairChange): RepairAsk => ({ route: "repair-change", change: found, problem: null, asks: false });
  const per = text.match(new RegExp(String.raw`\b${COUNT}\s+pl(?:y|ies)\s+(?:per|a|each|in (?:each|every|a)|to (?:each|a|every))\s+step\b`))
    ?? (ADD.test(text) || REMOVE.test(text) ? null : text.match(new RegExp(String.raw`\bsteps of ${COUNT}\s+pl(?:y|ies)\b`)));
  if (per) return read({ action: "regroup", count: countOf(per[1]) });
  const same = /\bsame plies\b/.test(text) || /\b(?:regroup|group|split|divide)\b/.test(text) || /\bcut (?:it|them|the plies|the (?:same )?four plies)\b/.test(text);
  const stepped = text.match(new RegExp(String.raw`\b${COUNT}\s+(?:equal\s+)?steps?\b`));
  if (same && stepped) return read({ action: "regroup_steps", count: countOf(stepped[1]) });
  if (values.some((v) => v.kind === "length") || STEP_LENGTH.test(text)) return null; // a step's length, not the number of steps
  const after = text.slice(text.search(/\bsteps?\b/));
  if (REMOVE.test(text) && !/\badd\b/.test(text)) {
    const few = text.match(new RegExp(String.raw`\b${COUNT}\s+(?:fewer\s+|less\s+)?steps?\b`));
    return read({ action: "remove_steps", count: few ? countOf(few[1]) : 1 });
  }
  if (ADD.test(text)) {
    const more = text.match(new RegExp(String.raw`\b${COUNT}\s+(?:more\s+|extra\s+|additional\s+|new\s+)?steps?\b`));
    const angles = anglesOf(after);
    return read({ action: "add_steps", count: more ? countOf(more[1]) : 1, ...(angles ? { angles } : {}) });
  }
  const to = text.match(/\bsteps?\s*(?:to|=|:|at)\s*(\d+)\b/) ?? text.match(/\bnumber of steps\s*(?:to|=|:|at|of)?\s*(\d+)\b/);
  if (to) return read({ action: "set_steps", count: Number(to[1]) });
  if (stepped && /^\d+$|^(?:two|three|four|five|six|seven|eight|nine|ten|one)$/.test(stepped[1]) && (SET.test(text) || WHAT_IF.test(text) || /^\S+ steps?$/.test(text))) {
    const angles = anglesOf(after);
    return read({ action: "set_steps", count: countOf(stepped[1]), ...(angles ? { angles } : {}) });
  }
  return null;
}

const NOT_CHANGED_HERE = "The chat changes the step length, the number of steps, the bondline's thickness, the load, the damage's diameter and the overlaps. Plies, materials and the rest are changed in the model tree on the left.";
/** A fracture energy of the adhesive, by its names. */
const ENERGY = /\benerg(?:y|ies)\b|\btoughness\b|\bg\s?(?:1|2|i|ii)c\b/;

/** A message read as a change: whole, or with what is missing in the page's words. Null when the message is not a change. */
function changeOf(text: string, kind: RepairKind): RepairAsk | null {
  if (ASKING.test(text) && !WHAT_IF.test(text)) return null;
  const values = written(text);
  const steps = stepsChange(text, values);
  if (steps) return steps;
  const verb = SET.test(text) || ADD.test(text) || REMOVE.test(text) || WHAT_IF.test(text);
  if ((verb || /\b(?:use|swap|replace|switch)\b/.test(text))
    && /\b(?:cover pl(?:y|ies)|patch|pl(?:y|ies)|lay-?ups?|angles?|materials?|adhesive|laminate|shear modulus|shear strength|peel strength|poisson|kind of repair|panel)\b/.test(text)
    && !quantityOf(text.replace(/\bcover pl(?:y|ies)\b/, "cover"), kind, values)) {
    return change(NOT_CHANGED_HERE, false);
  }
  // a fracture energy is written in the load's unit: never read one as the load
  if (verb && ENERGY.test(text)) return change(NOT_CHANGED_HERE, false, "repair-adhesive");
  const quantity = quantityOf(text, kind, values);
  if (!quantity) return null;
  const example = `“set ${QUANTITY_WORDS[quantity]} to ${EXAMPLE_VALUE[quantity][0]}”`;
  const relative = values.some((v) => v.kind === "relative") || /\bby\s+\d|\btimes\b|\b(?:double|halve|half|twice|triple)\b/.test(text);
  if (relative || (!values.length && (RELATIVE.test(text) || verb))) {
    return change(`To what value? The chat sets ${QUANTITY_WORDS[quantity]} to the value you give and does not work one out: for example ${example}.`, true, QUANTITY_PANEL[quantity]);
  }
  if (!values.length) return null;
  const bare = /(?:\bto\b|=|:|\bof\b|\bat\b|\bis\b)?\s*$/.test(text.slice(0, values[0].at)) && values.length === 1;
  if (!verb && !bare) return null;
  const wanted = quantity === "load" ? "load" : "length";
  const fitting = values.filter((v) => v.kind === wanted || v.kind === null || v.kind === "other");
  const picked = fitting.find((v) => v.kind === wanted) ?? fitting[0] ?? values[0];
  if (fitting.filter((v) => v.kind === picked.kind).length > 1) {
    return change(`One value at a time: send each change as its own message, for example ${example}.`);
  }
  return { route: "repair-change", change: { action: "set", quantity, value: picked.value, ...(picked.unit ? { unit: picked.unit } : {}) }, problem: null, asks: false };
}

const SWEEPING = /\bsweep\b|\bvary(?:ing)?\b|\brange\b|\bcompare\b|\btry\b.*\b(?:from|between|values|several|different)\b/;
const PICKING = /\bsmallest\b|\bfewest\b|\bminimum\b|\bminimal\b|\bleast\b|\bshortest\b|\bthinnest\b|\bnarrowest\b|\boptimi[sz]e\b|\bbest\b|\bhow (?:many|few) steps (?:do i need|are needed|would it take|does it take|would i need)\b|\bwhat (?:step length|bondline(?: thickness)?|overlap) (?:do i need|is needed|would i need|keeps)\b/;
const RANGE = new RegExp(String.raw`(?:\bfrom|\bbetween)\s+${NUMBER}\s*${UNIT}?\s*(?:to|and|up to|through|until|-)\s*${NUMBER}\s*${UNIT}?`);
const RANGE_BARE = new RegExp(String.raw`(?<![\w./-])${NUMBER}\s*${UNIT}?\s*(?:to|-)\s*${NUMBER}\s*${UNIT}`);

/** A message read as a sweep: whole, or with what is missing. Null when the message asks for none. */
function sweepOf(text: string, kind: RepairKind): RepairAsk | null {
  const range = text.match(RANGE) ?? (SWEEPING.test(text) || PICKING.test(text) ? text.match(RANGE_BARE) : null);
  const sweeping = SWEEPING.test(text) || (range !== null && !ASKING.test(text)), picking = PICKING.test(text);
  if (!sweeping && !picking) return null;
  const sweep = (problem: string, asks = true): RepairAsk => ({ route: "repair-sweep", sweep: null, problem, asks });
  let quantity: SweepQuantity | null = null;
  if (STEP_LENGTH.test(text)) quantity = "step_length";
  else if (BONDLINE.test(text)) quantity = "bondline";
  else if (OVERLAP.test(text)) quantity = /\bpatch\b/.test(text) || (kind === "external" && !/\bcover\b/.test(text)) ? "patch_overlap" : "cover_overlap";
  else if (/\bsteps\b|\bnumber of steps?\b/.test(text)) quantity = "steps";
  else if (sweeping && LOAD.test(text) && !picking) {
    return sweep("A sweep of the load would show nothing new: every stress grows in step with the load, and the load at the adhesive's elastic limit does not change with it. Sweep the step length, the number of steps, the bondline's thickness or an overlap.", false);
  } else if (sweeping && DAMAGE.test(text)) {
    return sweep("A sweep changes the step length, the number of steps, the bondline's thickness or an overlap. The damage's diameter is set by the damage: change it with “set the damage's diameter to 30 mm”.", false);
  }
  const assumed = quantity === null;
  const found: RepairSweep = { quantity: quantity ?? "step_length" };
  const values = written(text);
  let inRange: [number, number] = [-1, -1];
  if (range && found.quantity !== "steps") {
    const at = range.index ?? 0;
    inRange = [at, at + range[0].length];
    const [start, end] = [numberOf(range[1]), numberOf(range[3])];
    const units = [range[2], range[4]].filter((u) => u !== undefined).map((u) => ENGINE_UNIT[u] ?? u);
    if (units.length === 2 && units[0] !== units[1]) return sweep("One unit for the range: for example “sweep the step length from 3 to 25 mm”.");
    if (!(start < end)) return sweep("A range runs from its smaller value up to its larger one: for example “from 3 to 25 mm”.");
    found.start = start; found.end = end;
    if (units.length) found.unit = units[units.length - 1];
  }
  const outside = values.filter((v) => v.at < inRange[0] || v.at >= inRange[1]);
  const stress = outside.find((v) => v.kind === "other" && /^(?:psi|ksi|Msi|MPa|GPa)$/.test(v.unit ?? ""));
  const withUnit = outside.find((v) => v.kind === "load");
  const named = withUnit ?? outside.find((v) => v.kind === null
    && /\b(?:at|for|under|to|of|carry|carries|carrying|take|takes|hold|holds|reach|reaches|restore|restores|back|elastic at|up to)\s*$/.test(text.slice(0, v.at))
    && !(found.quantity === "steps" && new RegExp(String.raw`^\s*(?:,|and\b|or\b|equal\b|steps?\b)`).test(text.slice(v.end))));
  if (named) { found.load = named.value; if (named.unit) found.load_unit = named.unit; }
  if (picking && found.load === undefined) {
    if (stress) return sweep("Name the load per unit width the adhesive is to stay elastic at, not a stress: for example “the smallest step length that stays elastic at 230 N/mm”.");
    if (/\bstrength\b|%|\bpercent\b/.test(text)) {
      return sweep("The page has no strength to bring back. Name a load per unit width, and the sweep finds the smallest repair whose adhesive is still elastic at it: for example “the smallest repair that stays elastic at 230 N/mm”.");
    }
    return sweep("Smallest for what load? Name the load per unit width the adhesive is to stay elastic at: for example “the smallest step length that stays elastic at 230 N/mm”.");
  }
  return { route: "repair-sweep", sweep: found, problem: null, asks: false, ...(assumed ? { assumed: true } : {}) };
}

// ---------------------------------------------------------------------------------------------------- questions

/** A value the description states, which a question may ask for: the field it sits in and the step that shows it. */
const STATED: [RegExp, (kind: RepairKind) => RepairField, string][] = [
  [/\b(?:adhesive(?:'s)? )?shear strength\b|\bstrength of the adhesive\b/, () => ADHESIVE_FIELDS[2], "repair-adhesive"],
  [/\bpeel strength\b/, () => ADHESIVE_FIELDS[4], "repair-adhesive"],
  [/\b(?:peel|mode (?:i|1|one)|opening)\b.*\b(?:fracture )?(?:energy|toughness)\b|\b(?:energy|toughness)\b.*\b(?:in peel|mode (?:i|1|one))\b|\bg\s?(?:1|i)c\b/, () => ADHESIVE_FIELDS[5], "repair-adhesive"],
  [/\b(?:shear|mode (?:ii|2|two)|sliding)\b.*\b(?:fracture )?(?:energy|toughness)\b|\b(?:energy|toughness)\b.*\b(?:in shear|mode (?:ii|2|two))\b|\bg\s?(?:2|ii)c\b/, () => ADHESIVE_FIELDS[6], "repair-adhesive"],
  [/\bshear modulus\b/, () => ADHESIVE_FIELDS[0], "repair-adhesive"],
  [BONDLINE, () => ADHESIVE_FIELDS[1], "repair-adhesive"],
  [/\bstep(?:'s)? lengths?\b|\bhow long (?:is|are) (?:each|the|a) steps?\b|\blength of (?:each |the |a )?steps?\b/, (kind) => DAMAGE_FIELDS[kind][2], "repair-damage"],
  [/\bcover\b.*\boverlap\b|\boverlap of the cover\b/, () => COVER_FIELDS[1], "repair-cover"],
  [OVERLAP, (kind) => (kind === "external" ? EXTERNAL_PATCH_FIELDS[1] : COVER_FIELDS[1]), "repair-patch"],
  [/\b(?:damage|hole)(?:'s)? (?:diameter|size)\b|\bdiameter of the (?:damage|hole)\b|\bhow (?:big|wide|large) is the (?:damage|hole)\b/, (kind) => DAMAGE_FIELDS[kind][0], "repair-damage"],
  [/\b(?:applied|stated) load\b|\bwhat(?:'s| is) the load$|\bwhat (?:is the )?load (?:is )?(?:applied|stated|on it)\b|\bwhat load (?:is|are) (?:it|we) (?:under|at)\b|\bload per unit width\b/, () => PANEL_FIELDS[2], "repair-loads"],
];

function statedOf(text: string, kind: RepairKind): { field: RepairField; panel: string } | null {
  for (const [pattern, field, panel] of STATED) {
    if (pattern.test(text)) return { field: field(kind), panel };
  }
  return null;
}

const VERDICT = /\bstrong enough\b|\bstrength\b|\bsafe\b|\bwill it (?:fail|hold|break|survive|work)\b|\bdoes it (?:pass|fail|hold|work)\b|\bis (?:it|this|the repair) (?:ok|okay|good|fine|acceptable|adequate|enough|sound)\b|\bmargins?\b|\bpass(?:es)?\b|\bfactor of safety\b|\bsafety factor\b|\bfailure load\b|\bultimate\b|\bcan (?:it|the repair|this) (?:carry|take|hold|survive)\b|\b(?:it|repair|this) carr(?:y|ies)\b|\bcarry (?:the|that|this|my) load\b|\brestor|\bgood enough\b|\bverdict\b|\bairworthy\b|\b(?:ok|okay|fine|acceptable|enough)$/;

/** The bond past its elastic limit (ADR-0140): softening, parting, letting go, the patch coming off. */
const BOND_FAILS = /\blets? go\b|\bletting go\b|\blet go\b|\bde-?bond|\bdis-?bond|\bunzip|\b(?:comes?|coming|came|pops?|peels?|peeling) off\b|\bdetach|\bseparat|\bprogressive (?:failure|damage)\b|\bdamage (?:initiation|onset)\b|\bcohesive\b|\bfracture\b|\b(?:bond|adhesive|bond\s*-?\s*line|glue)(?:'s)?\b.*\b(?:fails?|failed|failure|failing|breaks?|broken|parts?|parted|softens?|softened|softening|damaged?|cracks?|cracked|gives? (?:way|out)|capacity)\b|\b(?:fails?|failed|failure|breaks?|softens?|softening|damage|cracks?|parts|parted)\b.*\b(?:bond|adhesive|bond\s*-?\s*line|glue)\b|\bbond(?:'s)? strength\b|\bstrength of the bond\b/;
/** A question of the bond's failure that sets it against the plies': "does the bond fail before the plies?". */
const BOND_OR_PLIES = /\b(?:before|after|or|than|sooner|earlier|later)\b.*\b(?:pl(?:y|ies)|laminate|patch plies|fib(?:er|re)s?)\b|\b(?:pl(?:y|ies)|laminate|fib(?:er|re)s?)\b.*\b(?:before|after|first|or)\b/;
/** A question of the bond's failure that asks for its start: where or when it first softens. */
const BOND_STARTS = /\bsoftens?\b|\bsoftening\b|\bstarts?\b|\bbegins?\b|\binitiat|\bonset\b|\bfirst\b/;

/** The load the repair carries with its plies damaging (ADR-0141): asked for as a load, or as what breaks or cracks in the plies. */
const LARGEST_LOAD = /\b(?:largest|maximum|max|highest|biggest|most|ultimate|failure|collapse) load\b|\bload capacity\b/;
const PLIES_FAIL = /\b(?:pl(?:y|ies)|fib(?:er|re)s?|matrix)\b.*\b(?:damag\w*|breaks?|broken|breaking|cracks?|cracked|cracking|gives? (?:way|out))\b|\b(?:damag\w*|breaks?|broken|cracks?|cracked|cracking)\b.*\b(?:pl(?:y|ies)|fib(?:er|re)s?|matrix)\b|\bwhat (?:had|has) failed\b|\bwhat gives\b/;
const CARRIES = new RegExp(`${LARGEST_LOAD.source}|${PLIES_FAIL.source}|\\b(?:how much|what|which) load\\b.*\\b(?:carr(?:y|ies)|holds?|takes?|withstands?|fails?|breaks?)\\b`
  + "|\\bhow much (?:load )?(?:can|does|will|would) (?:it|the repair|this|the slice) (?:carry|hold|take)\\b|\\bwhen does (?:the repair|it|the slice) (?:fail|break|come apart)\\b");
/** A part of the repair named as what carries: the force in the patch or the laminate under the stated load, not the largest load. */
const PART_CARRIES = /\b(?:patch|laminate|cover)\b.*\b(?:carr(?:y|ies)|takes?|picks? up|share)\b/;

function topicOf(text: string): RepairTopic | null {
  // a strength or a fracture energy the adhesive states is a value of the file, not the bond's failure
  if (BOND_FAILS.test(text) && !/\b(?:peel|shear) (?:stress|strength)\b/.test(text) && !ENERGY.test(text)) return "bond";
  if (/\bpeel/.test(text)) return "peel";
  if (/\bfirst ply\b|\bwhich ply\b|\bply (?:fails?|failure|stress(?:es)?)\b|\bplies fail\b/.test(text)) return "ply";
  if (/\b(?:what|which)\b.*\b(?:first|governs?)\b|\bfails? first\b|\bcomes? first\b|\blimit first\b|\bweakest\b|\bcritical\b|\bgovern/.test(text)) return "first";
  if (CARRIES.test(text) && !PART_CARRIES.test(text) && !/\belastic\b/.test(text)) return "carries";
  if (/\b(?:still|stays?|remains?|stay) elastic\b|\belastic at\b|\bpast (?:its|the) elastic limit\b/.test(text)) return "elastic";
  if (/\belastic limit\b|\blimit load\b|\byield/.test(text)) return "limit";
  if (/\bshe[ae]r\b|\bbond\s*-?\s*line stress\b|\badhesive stress\b|\bstress in the (?:adhesive|bond\s*-?\s*line|glue)\b|\bpeak\b|\b(?:max(?:imum)?|largest|highest|biggest) stress\b|\bworks hardest\b/.test(text)) return "shear";
  if (/\b(?:patch|laminate|cover)\b.*\b(?:carr(?:y|ies)|takes?|picks? up|force|share)\b|\bhow much (?:load|force)\b|\bload transfer\b|\bforce in the (?:patch|laminate)\b|\bload path\b/.test(text)) return "forces";
  if (/\bhow many steps\b|\bnumber of steps\b|\bhow many plies (?:per|in each|in a|a) step\b|\bplies per step\b/.test(text)) return "steps";
  if (/\blay-?ups?\b|\bstacking\b|\bply angles\b|\bwhat plies\b|\bwhich plies\b|\bplies (?:are )?in the (?:patch|laminate|cover)\b|\bpatch plies\b|\bhow many plies\b/.test(text)) return "layup";
  if (/\bhow (?:wide|big|large|deep|thick)\b|\b(?:width|diameter|size|depth|thickness)\b|\bacross\b|\bhow much (?:material|laminate) is (?:cut|removed)\b|\bplies (?:are )?(?:cut|removed|left)\b/.test(text)) return "size";
  return null;
}

/** "what is peel stress?", "what does the pick mean?", "explain shear lag": a definition, from the pages. "What is the peel stress?",
 * with its article, asks for this repair's value. */
const DEFINING = /^(?:what's|whats|what is|what are)\s+(?:a |an )?(?!the\b)[a-z]|\bwhat does (?:a |an |the )?[\w\s'-]+ mean\b|\bwhat(?:'s| is) the difference\b|\bdifference between\b|\bwhat (?:is|are) (?:the )?(?:[\w\s'-]+ )?for\b|^(?:explain|define|describe|tell me about)\b/;

/** How a message is answered on the repair's page: a change previewed, a sweep run, a question of the result answered from the report
 * and the solved slice, a question of why, how or what answered from the reference pages, a command, or "not read". */
/** A fragment that leans on the message before it, "and at 250?", "what about 300 N/mm", "now 0.2 mm": the question, the sweep or the
 * change before, with the value it names in place of the one before. Null when the message is not such a fragment, or nothing before
 * it took a value. */
function following(text: string, before: RepairAsk | undefined): RepairAsk | null {
  if (!before) return null;
  const rest = text.replace(/^(?:(?:and|now|then|ok|okay|so)\s+)+/, "").replace(/^(?:(?:what|how) about|what if|try)\s+/, "").replace(/^(?:at|for|with|to|under)\s+/, "").replace(/\s+(?:instead|then)$/, "");
  if (before.route === "repair-result" && before.topic === "bond" && /^where(?: is that| does (?:it|that) (?:start|begin|soften))?$|^when does (?:it|that) (?:start|begin|soften)$/.test(rest)) {
    return { route: "repair-result", topic: "bond", onset: true };
  }
  const values = written(rest);
  if (values.length !== 1 || values[0].at !== 0 || values[0].end !== rest.length) return null; // the value and nothing else
  const { value, unit, kind } = values[0];
  if (before.route === "repair-result" && (before.topic === "elastic" || before.topic === "verdict") && kind !== "length") {
    return { ...before, load: { value, ...(unit ? { unit } : {}) } };
  }
  if (before.route === "repair-sweep" && before.sweep && before.sweep.load !== undefined && kind !== "length") {
    const { load_unit: _, ...sweep } = before.sweep;
    return { ...before, sweep: { ...sweep, load: value, ...(unit ? { load_unit: unit } : {}) } };
  }
  if (before.route === "repair-change" && before.change?.action === "set" && (kind === null || (before.change.quantity === "load" ? kind === "load" : kind === "length"))) {
    const { unit: _, ...change } = before.change;
    return { ...before, change: { ...change, value, ...(unit ? { unit } : {}) } };
  }
  return null;
}

/** What a message asks of the repair's chat. `before` is what the message before it was read as, which a fragment leans on. */
export function readRepairAsk(message: string, kind: RepairKind = "flush", before?: RepairAsk): RepairAsk {
  const text = plain(message).replace(/[?!.]+$/, "").trim();
  const follows = following(text, before);
  if (follows) return follows;
  if (/^(?:undo|revert|go back|put it back|change it back)(?: that| it| the last change| the change| please)*$/.test(text)) return { route: "repair-command", command: "undo" };
  // "what is the maximum load it carries" asks for a load of this repair; "maximum" alone would read as a sweep's pick
  if (LARGEST_LOAD.test(text) && !BOND_FAILS.test(text) && !/\bsweep\b|\bstays? elastic\b/.test(text) && !SET.test(text)) return { route: "repair-result", topic: "carries" };
  const sweep = sweepOf(text, kind);
  if (sweep) return sweep;
  const changed = changeOf(text, kind);
  if (changed) return changed;
  if (/\b(?:follow|run|start|do|trace|take|load)\b.*\b(?:bond|de-?bond(?:ing)?|dis-?bond(?:ing)?|progressive (?:failure|damage)|to failure|until it (?:lets go|fails|comes off))\b|^progressive (?:failure|damage)(?: analysis)?$/.test(text)
    && !ASKING.test(text) && !BONDLINE.test(text)) return { route: "repair-command", command: "bond" };
  if (/^(?:please\s+)?carry (?:it|the repair|this|the slice)\b|\b(?:run|start|do|follow|carry)\b.*\b(?:ply damage|pl(?:y|ies)'? damag\w*|damage in the plies|plies (?:crack|break|fail)\w*)\b|\buntil it (?:cannot|can't|can not|no longer) (?:hold|carry|carries|holds)\b/.test(text)
    && !ASKING.test(text)) return { route: "repair-command", command: "plies" };
  if (/^(?:please\s+)?(?:re-?)?solve\b|\b(?:run|start|do)\s+(?:the\s+)?(?:slice|solve|finite element|fe|fea)\b|\bsolve (?:the |this |a )?(?:slice|repair|section|model)\b/.test(text)
    && !/^(?:what|why|how|does|is)\b/.test(text)) return { route: "repair-command", command: "solve" };
  if (/\b(?:step file|\.step|\.stp|cad|solids?)\b/.test(text) && /\b(?:export|download|save|get|give|make|send|build|open)\b/.test(text)) return { route: "repair-command", command: "shape" };
  if ((/\b(?:report|pdf)\b/.test(text) && /\b(?:open|show|print|make|get|give|save|export|download|generate|create|write)\b/.test(text)) || /^(?:the )?report$/.test(text)) return { route: "repair-command", command: "report" };
  const topic = topicOf(text);
  if (DEFINING.test(text)) return { route: "repair-reference", topic };
  if (/\bwhy\b|\bhow come\b|\bhow (?:does|do|is|are|can|should|would)\b|\bshould i\b|\bexplain\b|\bdoes (?:a|an|adding|making|using)\b|\brules?(?: of thumb)?\b|\bguidelines?\b/.test(text)) {
    return { route: "repair-reference", topic: topic ?? (VERDICT.test(text) ? "verdict" : null) };
  }
  const stated = statedOf(text, kind);
  // a fracture energy is a value the adhesive states, whatever else the words "peel" and "shear" name
  if (stated && (!topic || stated.field.unit === "energy")) return { route: "repair-result", topic: "stated", ...stated };
  // "What is the peel strength" asks for the value the adhesive states, not for the peel stress of the solved slice.
  if (stated && /\b(?:shear|peel) strength\b/.test(text) && !/\b(?:reach|reaches|reached|exceed|exceeds|pass|passes|above|below|over|under|when|where|at what|enough|safe|ok|okay|adequate|restor\w*)\b/.test(text)) {
    return { route: "repair-result", topic: "stated", ...stated };
  }
  const named = written(text).find((v) => v.kind === "load" || (v.kind === null && /\b(?:at|carry|take|hold|under|for)\s*$/.test(text.slice(0, v.at))));
  const load = named ? { load: { value: named.value, ...(named.unit ? { unit: named.unit } : {}) } } : {};
  if (topic === "elastic") return { route: "repair-result", topic, ...load };
  if (topic === "bond") {
    if (BOND_OR_PLIES.test(text)) return { route: "repair-result", topic, plies: /^(?:does|do|is|are|will|would|can)\b/.test(text) ? "yes-no" : "which" };
    return { route: "repair-result", topic, ...(BOND_STARTS.test(text) ? { onset: true } : {}) };
  }
  if ((topic === "forces" && /\b(?:patch|laminate|cover)\b/.test(text)) || topic === "ply" || topic === "first" || topic === "peel") return { route: "repair-result", topic };
  if (topic === "carries") return { route: "repair-result", topic, ...(PLIES_FAIL.test(text) ? { failed: true } : {}) };
  if (VERDICT.test(text) && !(stated && /\b(?:shear|peel) strength\b/.test(text))) return { route: "repair-result", topic: "verdict", ...load };
  if (stated && (topic === null || topic === "size" || topic === "shear")) return { route: "repair-result", topic: "stated", ...stated };
  if (topic) return { route: "repair-result", topic };
  if (/\?$/.test(plain(message)) || ASKING.test(text)) return { route: "repair-reference", topic: null };
  return { route: "repair-unread" };
}

// ---------------------------------------------------------------------------------------------------- the page's answers

/** What the chat says: its kind, the answer as the heading, the lines under it (the basis first), what it read, the step it points to
 * and what the engineer may start from it. */
export type RepairOffer = "solve" | "report" | "bond" | "plies";
export type RepairSaid = { kind: string; heading: string; lines: string[]; data: Record<string, unknown>; panel?: string; offer?: RepairOffer };

const said = (kind: string, heading: string, lines: string[] = [], data: Record<string, unknown> = {}, panel?: string, offer?: RepairOffer): RepairSaid =>
  ({ kind, heading, lines, data, ...(panel ? { panel } : {}), ...(offer ? { offer } : {}) });

const capital = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);
const numbered = (n: number, one: string, many: string): string => `${n} ${n === 1 ? one : many}`;

/** What the page holds when a message is answered: the description, the hand calculation's report, the solved slice when it belongs to
 * the repair as it stands, whether an older solve is kept, and what a solve still needs; and the same of the bond followed until it
 * lets go (ADR-0140), `bondNeeds` null where the analysis service follows no bonds; and the same of the repair carried with its plies
 * damaging (ADR-0141), with its second run on a finer mesh when there is one, and `pliesRunning` what a run under way is doing. */
export type RepairHeld = { repair: RepairDescription; report: RepairReport | null; slice: SliceReport | null; sliceStale: boolean; needs: readonly SolveNeed[];
  bond?: BondReport | null; bondStale?: boolean; bondNeeds?: readonly SolveNeed[] | null;
  plies?: PliesReport | null; pliesFiner?: PliesReport | null; pliesStale?: boolean; pliesNeeds?: readonly SolveNeed[] | null; pliesRunning?: string | null };

/** A change as the page read it, before the engine words it: what the engineer checks the reading by. */
export function changeLine(found: RepairChange): string {
  if (found.action === "set") return `${capital(QUANTITY_WORDS[found.quantity])} set to ${shown(found.value)}${found.unit ? ` ${found.unit}` : " in the repair's own unit"}.`;
  const angles = "angles" in found && found.angles ? `, of plies at ${found.angles.map((a) => `${shown(a)}°`).join(", ")}` : "";
  if (found.action === "add_steps") return `${capital(numbered(found.count, "step", "steps"))} added${angles}.`;
  if (found.action === "remove_steps") return `${capital(numbered(found.count, "step", "steps"))} removed.`;
  if (found.action === "set_steps") return `The number of steps set to ${found.count}${angles}.`;
  return found.action === "regroup" ? `The same plies in steps of ${numbered(found.count, "ply", "plies")}.` : `The same plies cut in ${numbered(found.count, "step", "steps")}.`;
}

/** A sweep as the page read it. */
export function sweepLine(found: RepairSweep, assumed = false): string {
  const what = found.quantity === "steps" ? "The same plies in every number of steps that divides them"
    : `${capital(QUANTITY_WORDS[found.quantity])}${found.start !== undefined && found.end !== undefined ? ` from ${shown(found.start)} to ${shown(found.end)}${found.unit ? ` ${found.unit}` : ""}` : ", from a fifth of its value to twice it"}`;
  const load = found.load === undefined ? "" : `, for the smallest repair whose adhesive is still elastic at ${shown(found.load)}${found.load_unit ? ` ${found.load_unit}` : " in the repair's own unit"}`;
  return `${what}${load}.${assumed ? " No quantity was named, so the step length is swept: name the number of steps, the bondline or the overlap to sweep another." : ""}`;
}

/** What comes first in a solved slice, as a heading. */
const FIRST_SHORT: Record<"adhesive" | "peel" | "ply", string> = { adhesive: "The adhesive's elastic limit in shear", peel: "The bondline's peel strength", ply: "A ply's strength" };
const SOLVE_FIRST = "Solve the slice to get it: a few seconds.";
const staleLine = (held: RepairHeld): string => (held.sliceStale ? "The slice was solved for the repair as it was: solve it again for the repair as it stands." : SOLVE_FIRST);

/** The step that states what following the bond still needs: the adhesive's own numbers, or the rest of what a solve needs. */
const bondPanel = (needs: readonly SolveNeed[]): string => (needs.some((n) => n.path.startsWith("adhesive.")) ? "repair-adhesive" : "repair-solve");
const FOLLOW_FIRST = "Follow the bond to get it: about ten seconds.";

/** A question of the bond past its elastic limit (ADR-0140): the load at which the followed bond lets go in this model, or where and
 * when it first softens, as the solver gave them; without a run, what a run needs or the offer to start one. Never a strength. */
function bondAnswer(ask: Extract<RepairAsk, { route: "repair-result" }>, held: RepairHeld): RepairSaid {
  const bond = held.bond ?? null, needs = held.bondNeeds ?? null;
  if (ask.plies && held.plies) { // the run with the plies damaging answers it whether or not the bond alone was followed
    const carried = carriedBondOrPlies(ask.plies, held.plies, held.pliesFiner ?? null);
    if (carried) return carried;
  }
  if (!bond) {
    const heading = "The bond is not followed yet";
    if (needs === null) return said("none", heading, ["This page works the bondline by hand and as a solved slice, both elastic: neither says when the bond lets go."], {}, "repair-solve");
    if (needs.length) return said("none", heading, [`To follow it until it lets go, the repair still needs ${needs.map((n) => n.words).join("; ")}.`], {}, bondPanel(needs));
    return said("none", heading, [held.bondStale ? "The bond was followed for the repair as it was: follow it again for the repair as it stands." : FOLLOW_FIRST], {}, "repair-solve", "bond");
  }
  const words = bondWords(bond), u = bond.units, force = unitText(u.force), length = unitText(u.length);
  const data = { onset: bond.onset.load, let_go: bond.let_go?.load ?? null };
  if (ask.onset) {
    return said("result", `The bond first softens at ${shown(bond.onset.load)} ${force}, ${shown(bond.onset.r)} ${length} from the middle`, [
      `In ${inSentence(bond.onset.part)}: ${words.onsetStress}`,
      bond.let_go ? `${words.headline}. ${LET_GO_IS_NOT_THE_STRENGTH}` : words.short,
    ], data, "repair-solve");
  }
  if (ask.plies) return (held.plies ? carriedBondOrPlies(ask.plies, held.plies, held.pliesFiner ?? null) : null) ?? bondOrPlies(ask.plies, bond, held, data);
  const before = plyBefore(bond, held.slice);
  return said("result", words.headline, [words.softens, ...(words.extent ? [words.extent] : [words.short]), ...(before ? [before] : []), ...(bond.let_go ? [LET_GO_IS_NOT_THE_STRENGTH] : [])],
    data, "repair-solve");
}

/** The step that states what carrying the repair still needs: a ply material's strengths and energies, or what following the bond needs. */
const pliesPanel = (needs: readonly SolveNeed[]): string => (needs.some((n) => n.path.startsWith("patch.")) ? "repair-patch"
  : needs.some((n) => n.path.startsWith("parent.")) ? "repair-laminate" : bondPanel(needs));
const CARRY_FIRST = "Carry the repair until it cannot hold the load to get it: a few minutes.";

/** What had failed at the largest load a carried repair held, as a heading: the run's own counts. */
function failedHeading(plies: PliesReport): string {
  const at = plies.at_held, force = unitText(plies.units.force), length = unitText(plies.units.length);
  const parts = [
    ...(Math.abs(at.bond.softening) > 1e-9 * at.bond.length ? [`${shown(at.bond.softening)} ${length} of the bond past its strength`] : []),
    ...(Math.abs(at.bond.parted) > 1e-9 * at.bond.length ? [`${shown(at.bond.parted)} ${length} of it parted`] : []),
    ...at.plies.map((row) => `${row.elements.toLocaleString("en-US")} elements of ply ${row.crack === "matrix" ? "cracked along the fibres" : row.crack === "fibre_tension" ? "broken across the fibres" : "crushed along the fibres"}`),
  ];
  return parts.length ? `At ${shown(plies.load.held)} ${force}, the largest load held: ${parts.join(", ")}` : `Nothing had failed at ${shown(plies.load.held)} ${force}, the largest load held`;
}

/** A question of the load the repair carries with its plies damaging (ADR-0141), or of what had failed by then: from the run the page
 * holds, as the solver gave it; without one, what a run needs, that one is under way, or the offer to start one. Never a strength.
 * Null where the analysis service makes no such run, so the page's plain answer on verdicts stands. */
function carriesAnswer(ask: Extract<RepairAsk, { route: "repair-result" }>, held: RepairHeld): RepairSaid | null {
  const plies = held.plies ?? null, needs = held.pliesNeeds ?? null;
  if (!plies) {
    if (needs === null) return null;
    const heading = "The repair is not carried to that load yet";
    if (held.pliesRunning) return said("none", "The repair is being carried now", [held.pliesRunning, "Ask again when it is done: the Solve step shows it."], {}, "repair-solve");
    if (needs.length) return said("none", heading, [pliesNeedsWords(needs)], {}, pliesPanel(needs));
    return said("none", heading, [held.pliesStale ? "It was carried as it was: carry it again for the repair as it stands." : CARRY_FIRST], {}, "repair-solve", "plies");
  }
  const words = pliesWords(plies, held.pliesFiner ?? null);
  const data = { held: plies.load.held, not_held: plies.load.not_held, onset: plies.onset.load };
  if (ask.failed) return said("result", failedHeading(plies), [...words.failed, ...(words.gives ? [words.gives] : []), `${words.headline}. ${CARRIES_IS_NOT_THE_STRENGTH}`], data, "repair-solve");
  return said("result", words.headline, [words.bracket, words.softens, ...(words.gives ? [words.gives] : []), ...(held.pliesFiner ? [words.mesh] : []), CARRIES_IS_NOT_THE_STRENGTH],
    data, "repair-solve");
}

/** "Does the bond fail before the plies?" where the repair was carried with its plies damaging: what had failed at the largest load
 * held says which gives. Null when neither had begun to fail there, and the elastic runs answer as before. */
function carriedBondOrPlies(asked: "yes-no" | "which", plies: PliesReport, finer: PliesReport | null): RepairSaid | null {
  const words = pliesWords(plies, finer), at = plies.at_held, yes = asked === "yes-no";
  const parted = Math.abs(at.bond.parted) > 1e-9 * at.bond.length;
  if (!at.plies.length && !parted) return null;
  const heading = at.plies.length && !parted ? `${yes ? "No: the" : "The"} plies give first in this model; no part of the bond has parted`
    : !at.plies.length ? `${yes ? "Yes: the" : "The"} bond gives first in this model; no ply has begun to fail` : "The bond and the plies have both begun to fail at the largest load held";
  return said("result", heading, [`${words.headline}. ${words.bracket}`, words.softens, ...words.failed, CARRIES_IS_NOT_THE_STRENGTH],
    { held: plies.load.held, not_held: plies.load.not_held, onset: plies.onset.load }, "repair-solve");
}

/** "Does the bond fail before the plies?": the load at which the followed bond lets go beside the load at which the solved slice's
 * first ply reaches a strength, the earlier named first. The two are separate elastic-ply models, which the answer says. */
function bondOrPlies(asked: "yes-no" | "which", bond: BondReport, held: RepairHeld, data: Record<string, unknown>): RepairSaid {
  const words = bondWords(bond), force = unitText(bond.units.force), fell = bond.let_go;
  const slice = held.slice, ply = slice && slice.units.force === bond.units.force ? slice.first_ply : null;
  if (!fell) return said("result", words.headline, [words.short], data, "repair-solve");
  if (!ply) {
    return said("none", `${words.headline}; the plies' loads are not worked here`,
      [slice ? "The solved slice checks no ply: the materials state no strengths." : staleLine(held), LET_GO_IS_NOT_THE_STRENGTH], data, "repair-solve", slice ? undefined : "solve");
  }
  const pliesFirst = ply.load < fell.load, yes = asked === "yes-no";
  const plyLoad = `${shown(ply.load)} ${force}`, bondLoad = `${shown(fell.load)} ${force}`;
  const softens = `The bond first softens at ${shown(bond.onset.load)} ${force} and goes on carrying load while it softens.`;
  if (pliesFirst) {
    return said("result", `${yes ? "No: a" : "A"} ply reaches a strength first, at ${plyLoad}`, [
      `${capital(inSentence(ply.name))}, in the solved slice. The bond lets go later in this model, at ${bondLoad}, with every ply kept elastic.`,
      softens,
      "From the ply's load on, the plies' damage, which neither run follows, would change both answers.",
    ], { ...data, first_ply: ply.load }, "repair-solve");
  }
  return said("result", `${yes ? "Yes: the" : "The"} bond lets go first in this model, at ${bondLoad}`, [
    `In the solved slice the first ply, ${inSentence(ply.name)}, reaches a strength at ${plyLoad}.`, softens, LET_GO_IS_NOT_THE_STRENGTH,
  ], { ...data, first_ply: ply.load }, "repair-solve");
}

function resultAnswer(ask: Extract<RepairAsk, { route: "repair-result" }>, held: RepairHeld, report: RepairReport): RepairSaid {
  const u = report.units, stress = unitText(u.stress), force = unitText(u.force), length = unitText(u.length);
  const lap = report.lap, answer = lap.answer, slice = held.slice, sizes = report.sizes;
  const kind = report.kind;
  const noLoad = () => said("none", "No load stated yet", ["State a load per unit width, under Panel and load, to work the bondline."], {}, "repair-loads");
  const noSlice = (heading: string) => (held.needs.length
    ? said("none", heading, [`The solve of the slice still needs ${held.needs.map((n) => n.words).join("; ")}.`], {}, "repair-solve")
    : said("none", heading, [staleLine(held)], {}, "repair-solve", "solve"));
  switch (ask.topic) {
    case "bond": return bondAnswer(ask, held);
    case "carries": {
      const carried = carriesAnswer(ask, held);
      if (carried) return carried;
      return resultAnswer({ route: "repair-result", topic: "verdict" }, held, report);
    }
    case "stated": {
      const field = ask.field!;
      const value = valueAt(held.repair, field.path);
      const unit = field.unit && field.unit !== "deg" ? REPAIR_UNIT_LABELS[unitsOf(held.repair)][field.unit] : "";
      const panel = ask.panel;
      if (value === undefined) return said("none", `${field.label}: not stated`, [field.hint ?? "The repair states no value for it."], { path: field.path }, panel);
      return said("result", `${field.label}: ${typeof value === "number" ? shown(value) : String(value)}${unit ? ` ${unit}` : ""}`, ["As the repair states it."], { path: field.path, value }, panel);
    }
    case "size": {
      const cut = kind === "external"
        ? `A ${report.patch_layup.length}-ply patch bonded on top, ${shown(sizes.patch_thickness)} ${length} thick, over a hole through the laminate.`
        : `${capital(numbered(sizes.plies_removed, "ply", "plies"))} cut ${shown(sizes.depth)} ${length} deep${sizes.through ? ", through every ply" : `; ${numbered(sizes.plies_left, "ply is", "plies are")} left under the patch`}.`;
      return said("result", `${shown(sizes.repair_diameter)} ${length} across`, [cut, `The laminate is ${shown(sizes.thickness)} ${length} thick.`],
        { repair_diameter: sizes.repair_diameter }, "repair-damage");
    }
    case "steps": {
      const steps = Number(valueAt(held.repair, "steps.count")), per = Number(valueAt(held.repair, "steps.plies") ?? 1);
      return said("result", `${capital(numbered(steps, "step", "steps"))} of ${numbered(per, "ply", "plies")} each`,
        [`Each step is ${shown(Number(valueAt(held.repair, "steps.length")))} ${length} long; the repair is ${shown(sizes.repair_diameter)} ${length} across.`], { steps, plies_per_step: per }, "repair-damage");
    }
    case "layup": {
      const list = (angles: unknown): string => `[${(Array.isArray(angles) ? angles : []).map((a) => String(a).replace("-", "−")).join("/")}]`;
      const cover = valueAt(held.repair, "cover.layup");
      return said("result", `Patch ${list(report.patch_layup)}, ${kind === "external" ? "from the laminate upward" : "deepest ply first"}`, [
        `Laminate ${list(valueAt(held.repair, "parent.layup"))}, bottom ply first.`,
        ...(kind === "external" ? [] : [valueAt(held.repair, "patch.layup") === undefined ? "The patch repeats the angles of the plies removed." : "The patch's plies are listed on the Patch step."]),
        ...(cover !== undefined ? [`Cover plies ${list(cover)}.`] : []),
      ], { patch: report.patch_layup }, "repair-patch");
    }
    case "shear": {
      if (!answer || lap.load === undefined) return noLoad();
      const peak = Math.abs(answer.peak_shear.value);
      return said("result", `${shown(peak)} ${stress} by hand, ${peakPlace(report)}`, [
        `The largest shear stress in the adhesive under ${shown(lap.load)} ${force}.`,
        slice ? `Solved as a slice: ${shown(Math.abs(slice.bond.peak_shear.value))} ${stress}, ${shown(slice.bond.peak_shear.r)} ${length} from the middle (${inSentence(slice.bond.peak_shear.part)}).`
          : held.sliceStale ? "The slice was solved for the repair as it was: solve it again to compare." : "The solved slice gives it too, with the peel stress.",
      ], { peak_shear: peak, slice: slice ? Math.abs(slice.bond.peak_shear.value) : null }, "repair-solve");
    }
    case "limit": {
      if (!answer || lap.load === undefined) return noLoad();
      if (answer.elastic_limit_load === undefined) {
        return said("none", "No elastic limit load: the adhesive states no shear strength", ["State it on the Adhesive step: the stress at the adhesive's elastic limit."], {}, "repair-adhesive");
      }
      return said("result", `${shown(answer.elastic_limit_load)} ${force} by hand`, [
        `The load at which the adhesive reaches its elastic limit in shear, ${peakPlace(report)}.`,
        ...(slice && slice.elastic_limit_load !== null ? [`Solved as a slice: ${shown(slice.elastic_limit_load)} ${force}.`] : []),
        NOT_THE_STRENGTH,
      ], { elastic_limit_load: answer.elastic_limit_load, slice: slice?.elastic_limit_load ?? null }, "repair-solve");
    }
    case "elastic": {
      if (!answer || lap.load === undefined) return noLoad();
      const limit = answer.elastic_limit_load;
      if (limit === undefined) return said("none", "No elastic limit load: the adhesive states no shear strength", ["State it on the Adhesive step: the stress at the adhesive's elastic limit."], {}, "repair-adhesive");
      const reaches = `The adhesive reaches its elastic limit in shear at ${shown(limit)} ${force}, ${peakPlace(report)}.`;
      if (ask.load?.unit && ask.load.unit !== u.force) {
        return said("result", `The adhesive reaches its elastic limit at ${shown(limit)} ${force} by hand`, [`Give the load in ${force} to compare it: the page converts no number.`, NOT_THE_STRENGTH], { elastic_limit_load: limit }, "repair-solve");
      }
      const at = ask.load?.value ?? lap.load, elastic = at <= limit;
      return said("result", `${elastic ? "Yes" : "No"}, by hand: ${elastic ? "still elastic" : "past its elastic limit"} at ${shown(at)} ${force}`, [
        reaches,
        ...(slice?.first ? [`In the solved slice, ${FIRST_WORDS[slice.first.what]} first, at ${shown(slice.first.load)} ${force}.`] : []),
        NOT_THE_STRENGTH,
      ], { elastic, at, elastic_limit_load: limit }, "repair-solve");
    }
    case "peel": {
      if (!slice) return noSlice("The hand calculation has no peel stress");
      const peel = slice.bond.peak_peel;
      return said("result", `${shown(peel.value)} ${stress} in the solved slice`, [
        `The largest peel stress, ${shown(peel.r)} ${length} from the middle (${inSentence(peel.part)}).`,
        slice.peel_limit_load !== null ? `It reaches the peel strength at ${shown(slice.peel_limit_load)} ${force}.` : "Not judged: the adhesive states no peel strength.",
        "The hand calculation has no peel stress.",
      ], { peak_peel: peel.value }, "repair-solve");
    }
    case "ply": {
      if (!slice) return noSlice("The plies are checked in the solved slice");
      return said("result", slice.first_ply ? `${capital(inSentence(slice.first_ply.name))} at ${shown(slice.first_ply.load)} ${force}` : "No ply is checked", [sliceWords(slice).ply, ...(slice.first ? [sliceWords(slice).first] : [])],
        { first_ply: slice.first_ply?.name ?? null }, "repair-solve");
    }
    case "first": {
      if (!slice) {
        if (!answer || answer.elastic_limit_load === undefined) return noSlice("What comes first is found in the solved slice");
        return said("none", "By hand, only the adhesive's shear is worked", [
          `It reaches its elastic limit at ${shown(answer.elastic_limit_load)} ${force}. ${NOT_THE_STRENGTH}`, "The solved slice adds the peel stress and each ply, and says which comes first.",
        ], {}, "repair-solve", held.needs.length ? undefined : "solve");
      }
      if (!slice.first) return said("none", "Nothing is judged in the slice", ["The repair states no strength of the adhesive or of the plies to hold the stresses to."], {}, "repair-adhesive");
      const words = sliceWords(slice);
      return said("result", `${FIRST_SHORT[slice.first.what]}, at ${shown(slice.first.load)} ${force}`,
        [`In the solved slice, as the load grows, ${FIRST_WORDS[slice.first.what]} first.`, slice.first.what === "ply" ? words.ply : NOT_THE_STRENGTH],
        { first: slice.first }, "repair-solve");
    }
    case "forces": {
      if (!answer || lap.load === undefined) return noLoad();
      const forces = answer.boundary_forces, last = forces[forces.length - 1];
      // "carries" is the force in the patch under the load stated, by hand: where the laminate ends, all of it
      return said("result", `The patch carries ${shown(last)} of the ${shown(lap.load)} ${force} at ${lap.ends_at_the_middle ? "the middle" : "the hole"}`, [
        lap.ends_at_the_middle ? "At the repair's middle the plies left under the patch carry the rest." : "At the edge of the hole the laminate ends, so the patch carries all of it.",
        `By hand, at the inner end of each step: ${lap.steps.map((step, i) => `${inSentence(step.name).replace(/^the /, "")} ${shown(forces[i + 1])}`).join(", ")} ${force}.`,
      ], { boundary_forces: forces }, "repair-solve");
    }
    default: { // a verdict: the page gives none, and says what it does give
      if (!answer || lap.load === undefined) return said("verdict", "This page gives no strength or verdict", ["It gives the adhesive's largest shear stress and the load at its elastic limit, once a load is stated."], {}, "repair-loads");
      const limit = answer.elastic_limit_load;
      const lines: string[] = [];
      if (limit === undefined) lines.push(`By hand, the largest bondline shear is ${shown(Math.abs(answer.peak_shear.value))} ${stress} under ${shown(lap.load)} ${force}. The adhesive states no shear strength, so no elastic limit load is given.`);
      else {
        const sameUnit = ask.load && (!ask.load.unit || ask.load.unit === u.force);
        lines.push(sameUnit
          ? `By hand, the adhesive is ${ask.load!.value <= limit ? "still elastic" : "past its elastic limit"} at ${shown(ask.load!.value)} ${force}: it reaches that limit at ${shown(limit)} ${force}.`
          : `By hand, the adhesive reaches its elastic limit in shear at ${shown(limit)} ${force}; the load stated is ${shown(lap.load)} ${force}.`);
      }
      lines.push(slice?.first ? `In the solved slice, ${FIRST_WORDS[slice.first.what]} first, at ${shown(slice.first.load)} ${force}.` : "The solved slice adds the peel stress and each ply, and says which comes first.");
      const fell = held.bond?.let_go ?? null, carried = held.plies ?? null;
      if (fell && held.bond) lines.push(`With the bond followed, it lets go at ${shown(fell.load)} ${unitText(held.bond.units.force)} in this model.`);
      if (carried) {
        lines.push(`With the plies damaging as well, ${pliesWords(carried).card.replace(/ Not the repair's strength\.$/, "")}`);
        lines.push("None of these is the repair's strength: plies parting from each other are not followed, and what the analysis leaves out is listed under the results.");
      } else if (fell) lines.push("None of these is the repair's strength: the plies are not checked for damage, and what the analysis leaves out is listed under the results.");
      else lines.push("Neither is a failure load: the adhesive yields before it fails, and what the analysis leaves out is listed under the results.");
      return said("verdict", "This page gives no strength or verdict", lines, { elastic_limit_load: limit ?? null, let_go: fell?.load ?? null, carries: carried?.load.held ?? null }, "repair-solve",
        slice || held.needs.length ? undefined : "solve");
    }
  }
}

/** The repair's own number on what a question of why or how names, to stand beside the pages' words. */
function whyFacts(topic: RepairTopic, held: RepairHeld): string[] {
  if (topic === "bond") {
    const bond = held.bond ?? null, force = bond ? unitText(bond.units.force) : "";
    return bond?.let_go ? [`Here: the bond first softens at ${shown(bond.onset.load)} ${force} and lets go at ${shown(bond.let_go.load)} ${force} in this model.`] : [];
  }
  if (topic === "carries") {
    const plies = held.plies ?? null;
    return plies ? [`Here, with the plies damaging: ${pliesWords(plies).card.replace(/ Not the repair's strength\.$/, "")}`] : [];
  }
  const report = held.report;
  const answer = report?.lap.answer;
  if (!report || !answer) return [];
  const stress = unitText(report.units.stress), force = unitText(report.units.force);
  if (topic === "shear") return [`Here: ${shown(Math.abs(answer.peak_shear.value))} ${stress} by hand, ${peakPlace(report)}.`];
  if (topic === "limit" || topic === "verdict" || topic === "elastic") return answer.elastic_limit_load === undefined ? [] : [`Here: the adhesive reaches its elastic limit at ${shown(answer.elastic_limit_load)} ${force} by hand.`];
  if (topic === "peel") return held.slice ? [`Here: ${shown(held.slice.bond.peak_peel.value)} ${stress} in the solved slice (${inSentence(held.slice.bond.peak_peel.part)}).`] : [];
  if (topic === "first") return held.slice?.first ? [`Here: ${FIRST_WORDS[held.slice.first.what]} first, at ${shown(held.slice.first.load)} ${force}, in the solved slice.`] : [];
  return [];
}

export const REPAIR_EXAMPLES = "Ask “what is the largest shear?”, “add a step”, “make each step 0.5 in”, “when does the bond let go?” or “sweep the step length for the smallest repair that stays elastic at 230 N/mm”.";

/** What the chat says to a message as read, from what the page holds. A change and a sweep are then worked by the API. */
export function repairAnswer(ask: RepairAsk, held: RepairHeld): RepairSaid {
  switch (ask.route) {
    case "repair-change":
      if (!ask.change) return said(ask.asks ? "ask" : "refused", ask.asks ? "One question" : "Not a change the chat makes", [ask.problem ?? ""], {}, ask.panel);
      return said("preview", "Preview of a change", [changeLine(ask.change)], { change: ask.change });
    case "repair-sweep":
      if (!ask.sweep) return said(ask.asks ? "ask" : "refused", ask.asks ? "One question" : "Not a sweep the chat runs", [ask.problem ?? ""]);
      return said("sweep", `Sweep of ${QUANTITY_WORDS[ask.sweep.quantity]}`, [sweepLine(ask.sweep, ask.assumed)], { sweep: ask.sweep });
    case "repair-command":
      if (ask.command === "solve") {
        return held.needs.length
          ? said("none", "The slice cannot be solved yet", [`It still needs ${held.needs.map((n) => n.words).join("; ")}.`], { command: "solve" }, "repair-solve")
          : said("solve", "Solving the slice", ["It takes a few seconds. The drawings and the Solve step show it too."], { command: "solve" }, "repair-solve");
      }
      if (ask.command === "bond") {
        const needs = held.bondNeeds ?? null;
        if (needs === null) return said("none", "The bond cannot be followed here", ["This page works the bondline by hand and as a solved slice."], { command: "bond" }, "repair-solve");
        return needs.length
          ? said("none", "The bond cannot be followed yet", [`It still needs ${needs.map((n) => n.words).join("; ")}.`], { command: "bond" }, bondPanel(needs))
          : said("bond", "Following the bond until it lets go", ["About ten seconds. Details and the Solve step show it too."], { command: "bond" }, "repair-solve");
      }
      if (ask.command === "plies") {
        const needs = held.pliesNeeds ?? null;
        if (needs === null) return said("none", "The repair cannot be carried to that load here", ["This page works the bondline by hand and as a solved slice."], { command: "plies" }, "repair-solve");
        if (held.pliesRunning) return said("none", "The repair is being carried already", [held.pliesRunning, "The Solve step shows it when it is done."], { command: "plies" }, "repair-solve");
        return needs.length
          ? said("none", "The repair cannot be carried yet", [pliesNeedsWords(needs)], { command: "plies" }, pliesPanel(needs))
          : said("plies", "Carrying the repair until it cannot hold the load", ["A few minutes, nine at most; it goes on if you leave the page. Details and the Solve step show it when it is done."],
            { command: "plies" }, "repair-solve");
      }
      if (ask.command === "undo") return said("undo", "Undo", [], { command: "undo" });
      return ask.command === "report"
        ? said("said", "The report opens from Report and shape", ["It lays this repair out for paper: print it, or save it as a PDF from there."], { command: "report" }, "repair-report", "report")
        : said("said", "The STEP file is built in Report and shape", ["Every ply and the adhesive as a named solid, in millimetres."], { command: "shape" }, "repair-report");
    case "repair-reference":
      return said("reference", "Answered from our reference pages", ask.topic ? whyFacts(ask.topic, held) : [], { topic: ask.topic });
    case "repair-unread":
      return said("redirect", "Not a message I can read yet", [REPAIR_EXAMPLES]);
    default:
      if (!held.report) return said("none", "The repair is being worked", ["Ask again once its answer is shown."]);
      return resultAnswer(ask, held, held.report);
  }
}

// ---------------------------------------------------------------------------------------------------- what the API answers

/** What a change is judged by (`summary` of the engine's `repair/changes.py`), in the report's units. */
export type RepairSummary = {
  kind: RepairKind; steps: number; plies_per_step: number; plies_removed: number; plies_left: number; patch_plies: number; patch_diameter: number;
  repair_diameter: number; load: number | null; peak_shear: { value: number; name: string; end: "start" | "end" } | null; elastic_limit_load: number | null;
};
/** A change previewed (`POST /v1/repairs/changes`): the engine's sentence, the repair file it gives and both summaries. */
export type RepairChangePreview = {
  run_id: string | null; engine_version: string; change: Record<string, unknown>; words: string; repair: RepairDescription;
  before: RepairSummary; after: RepairSummary; units: RepairReport["units"];
};
export type SweepRow = {
  value: number; current: boolean; refused: string | null; repair_diameter?: number; steps?: number; plies_per_step?: number;
  peak_shear?: { value: number; name: string; end: "start" | "end" } | null; elastic_limit_load?: number | null; elastic: boolean | null;
};
/** What a solved slice says of a sweep's pick (`pick_check` of the engine's `repair/sweeps.py`), or why it was not solved. */
export type SweepCheck = { state: "solved" | "needs" | "refused" | "failed"; holds: boolean | null; close?: boolean; words: string[] };
/** A sweep's answer (`POST /v1/repairs/sweeps`): the engine's rows, pick and sentences, and the pick's check. */
export type RepairSweepAnswer = {
  run_id: string | null; engine_version: string; sweep: Record<string, unknown>; quantity: { name: SweepQuantity; words: string; unit: string };
  units: RepairReport["units"]; load: number; target: number | null; rows: SweepRow[]; pick: number | null; picked: RepairDescription | null;
  flat_from: { value: number; elastic_limit_load: number; every_row: boolean } | null; most: { value: number; elastic_limit_load: number } | null;
  words: string[]; answer: string[]; cautions: string[]; check: SweepCheck | null;
};

/** A row of the preview's table: a quantity as it is and as changed; `better` says which way it moved (null: unchanged or no way). */
export type PreviewRow = { label: string; before: string; after: string; better: boolean | null };

const placeOf = (peak: RepairSummary["peak_shear"]): string => (peak ? `${peak.end === "start" ? "outer" : "inner"} end of ${inSentence(peak.name)}` : "–");

function moved(before: number | null | undefined, after: number | null | undefined, good: 1 | -1): boolean | null {
  // a value that prints the same before and after has not moved, as far as the page says: no mark on two equal numbers
  if (before === null || before === undefined || after === null || after === undefined || shown(before) === shown(after)) return null;
  return (after - before) * good > 0;
}

/** The preview's table: the steps, the repair's width, the largest bondline shear and where, and the load at the adhesive's elastic
 * limit, as it is and as changed, each as the engine gave it. A lower shear and a higher limit load are marked as the better way; the
 * width is not judged. */
export function previewRows(p: RepairChangePreview): PreviewRow[] {
  const u = p.units, a = p.before, b = p.after;
  const steps = (s: RepairSummary) => `${s.steps} of ${numbered(s.plies_per_step, "ply", "plies")}`;
  const rows: PreviewRow[] = [
    { label: "Steps", before: steps(a), after: steps(b), better: null },
    { label: `Repair width (${unitText(u.length)})`, before: shown(a.repair_diameter), after: shown(b.repair_diameter), better: null },
  ];
  if (a.load !== null || b.load !== null) rows.push({ label: `Load (${unitText(u.force)})`, before: shown(a.load), after: shown(b.load), better: null });
  if (a.peak_shear || b.peak_shear) {
    rows.push({ label: `Largest shear (${unitText(u.stress)})`, before: shown(a.peak_shear?.value), after: shown(b.peak_shear?.value), better: moved(a.peak_shear?.value, b.peak_shear?.value, -1) });
  }
  if (a.elastic_limit_load !== null || b.elastic_limit_load !== null) {
    rows.push({ label: `Elastic limit load (${unitText(u.force)})`, before: shown(a.elastic_limit_load), after: shown(b.elastic_limit_load), better: moved(a.elastic_limit_load, b.elastic_limit_load, 1) });
  }
  return rows;
}

/** Where the largest shear is, as it is and as changed, in a sentence under the preview's table: a place is words, not a number, and
 * two of them side by side are wider than the chat. */
export function previewPlace(p: RepairChangePreview): string | null {
  const a = p.before.peak_shear, b = p.after.peak_shear;
  if (!b) return null;
  if (!a) return `The largest shear is at the ${placeOf(b)}.`;
  return placeOf(a) === placeOf(b) ? `The largest shear stays at the ${placeOf(b)}.` : `The largest shear moves from the ${placeOf(a)} to the ${placeOf(b)}.`;
}

/** A swept quantity as a column's head and an answer's first words. */
const SWEPT: Record<SweepQuantity, string> = { step_length: "Step length", bondline: "Bondline thickness", cover_overlap: "Cover overlap", patch_overlap: "Patch overlap", steps: "Steps" };

/** A sweep's table as the page lists it: a row for every value, with the pick and the repair as it stands marked. */
export type SweepTable = { head: string[]; rows: { cells: string[]; refused: string | null; pick: boolean; current: boolean; elastic: boolean | null }[] };

export function sweepTable(a: RepairSweepAnswer): SweepTable {
  const u = a.units, steps = a.quantity.name === "steps";
  const head = [steps ? "Steps" : `${SWEPT[a.quantity.name]} (${unitText(a.quantity.unit)})`, `Width (${unitText(u.length)})`,
    `Largest shear (${unitText(u.stress)})`, `Elastic limit load (${unitText(u.force)})`];
  if (a.target !== null) head.push(`Elastic at ${shown(a.target)} ${unitText(u.force)}`);
  const rows = a.rows.map((row, i) => {
    const value = steps && row.steps !== undefined ? `${row.steps} of ${numbered(row.plies_per_step ?? 1, "ply", "plies")}` : shown(row.value);
    const cells = row.refused !== null ? [value] : [value, shown(row.repair_diameter), shown(row.peak_shear?.value), shown(row.elastic_limit_load),
      ...(a.target !== null ? [row.elastic === null ? "–" : row.elastic ? "Yes" : "No"] : [])];
    return { cells, refused: row.refused, pick: a.pick === i, current: row.current, elastic: row.elastic };
  });
  return { head, rows };
}

/** A sweep's answer as a heading: the pick, that there is none, or what was swept. */
export function sweepHeading(a: RepairSweepAnswer): string {
  const force = unitText(a.units.force);
  if (a.target === null) return `${a.rows.filter((row) => row.refused === null).length} values of ${a.quantity.words} worked by hand`;
  if (a.pick === null) return `None of these stays elastic at ${shown(a.target)} ${force}`;
  const row = a.rows[a.pick];
  const value = a.quantity.name === "steps" ? `${numbered(row.steps ?? row.value, "step", "steps")} of ${numbered(row.plies_per_step ?? 1, "ply", "plies")}`
    : `${SWEPT[a.quantity.name]} ${shown(row.value)} ${unitText(a.quantity.unit)}`;
  // The pick is the hand calculation's. Where its solved slice does not hold it, or is too close to say, the heading says so.
  if (a.check?.holds === false) return `${value} by hand; the slice says no`;
  if (a.check?.close) return `${value} by hand; too close in the slice`;
  return `${value}: still elastic at ${shown(a.target)} ${force}`;
}
