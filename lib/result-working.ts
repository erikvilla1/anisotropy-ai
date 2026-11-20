/** The working behind an answer, shown when the engineer asks for it (ADR-0103): "show me the formula", "prove it", "how was that
 * calculated?". The package wrote every step with its values (`fields.summary.working`); the page finds the chain asked for and shows
 * it. No model reads the request or writes a number. */
import { formatNumber } from "./number-format";
import { CRITERION_NAMES } from "./studio-answer";
import type { Fields, Working, WorkingChain } from "./studio-api";

const THING = "(?:formulas?|formulae|equations?|proof|derivation|working|workings|calculations?|maths?|steps)";
const ASKS = [
  new RegExp(`\\b(?:show|send|give|see|display|print|what(?:'s| is| are)|where(?:'s| is| are)|which|can i (?:see|have|get)|walk me through|i (?:want|need))\\b.*\\b${THING}\\b`, "i"),
  new RegExp(`^\\s*(?:the |your |its )?${THING}(?: (?:please|for .+|of .+|behind .+))?[.?!]*\\s*$`, "i"),
  /\b(?:prove|derive)\b/i,
  /\bstep[- ]by[- ]step\b/i,
  /\b(?:stress(?:es)?|strains?|failure index|failure load|load at failure)\s+(?:formulas?|formulae|equations?)\b/i, // "stress equation"
  /\bhow (?:is|was|were|are|did|do|does) (?:you|that|this|it|the|those|these)\b.*\b(?:calculated?|computed?|get|got|worked out|come from|came from|solved?|arrived? at|derived?)\b/i,
];

/** Whether a message asks for the working: a formula, a proof, the steps, or how a value was calculated. */
export const asksWorking = (text: string): boolean => ASKS.some((pattern) => pattern.test(text));

/** The criterion a message names, when it names one. */
export function criterionNamed(text: string): string | null {
  if (/\btsai[- ]?hill\b/i.test(text)) return "tsai_hill";
  if (/\btsai[- ]?wu\b/i.test(text)) return "tsai_wu";
  if (/\bmax(?:imum)?[- ]?strain\b/i.test(text)) return "max_strain";
  if (/\bmax(?:imum)?[- ]?stress\b/i.test(text)) return "max_stress";
  return null;
}

/** The one step of the working a message asks for by its quantity (ADR-0103 amendment 1): "equation for stress" is the ply's stress from
 * its strain, not the whole check. A criterion named ("the working for max stress"), or a message that names none or more than one of
 * them ("show me the formula", "derive the failure factor"), asks for the whole working: null. */
export function stepAsked(text: string): "strain" | "stress" | "criterion" | "loading" | null {
  if (criterionNamed(text)) return null;
  const named = ([
    ["criterion", /\bfailure index\b|\bindex of failure\b/i],
    ["loading", /\b(?:failure|first[- ]ply[- ]failure) (?:load|force|displacement)\b|\b(?:load|force|displacement) at (?:first[- ]ply )?failure\b/i],
    ["stress", /\bstress(?:es)?\b|σ|\bsigma\b|τ|\btau\b/i],
    ["strain", /\bstrains?\b|ε|\bepsilon\b|γ|\bgamma\b/i],
  ] as const).filter(([, pattern]) => pattern.test(text)).map(([step]) => step);
  return named.length === 1 ? named[0] : null;
}

const isText = (v: unknown): v is string => typeof v === "string";
const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

function isChain(v: unknown): v is WorkingChain {
  return isObject(v) && isNumber(v.ply) && isNumber(v.angle) && isText(v.element) && isText(v.where) && isNumber(v.factor) && Array.isArray(v.steps) && v.steps.length > 0
    && v.steps.every((s) => isObject(s) && isText(s.id) && isText(s.title) && isText(s.source) && isText(s.text)
      && Array.isArray(s.given) && s.given.every((g) => isObject(g) && isText(g.symbol) && isNumber(g.value) && isText(g.unit) && isText(g.what))
      && Array.isArray(s.equations) && s.equations.every((e) => isObject(e) && (e.formula === null || isText(e.formula)) && isText(e.substituted)
        && (e.result === null || (isObject(e.result) && isText(e.result.symbol) && isNumber(e.result.value) && isText(e.result.unit)))));
}

/** The working a result carries, read only in its own shape; null on a result solved before it or where none is written. */
export function workingOf(fields: Pick<Fields, "summary"> | null | undefined): Working | null {
  const working = fields?.summary.working;
  if (!isObject(working) || !isObject(working.criteria) || (working.basis !== "gauge" && working.basis !== "whole")) return null;
  const criteria = Object.fromEntries(Object.entries(working.criteria).filter(([, chain]) => isChain(chain)));
  return Object.keys(criteria).length ? { ...(working as Working), criteria: criteria as Record<string, WorkingChain> } : null;
}

export type FoundWorking =
  /** `step`: the one step the message asks for by its quantity, when it asks for one and the chain has it (`stepAsked`). */
  | { kind: "chain"; criterion: string; name: string; chain: WorkingChain; basis: string; others: string[]; step: WorkingChain["steps"][number] | null }
  /** The criterion named has no working written, though the result has others'. */
  | { kind: "not-worked"; name: string; others: string[] };

/** The chain a message asks for: the criterion it names, else the earliest of the answer, else the first written. Null with no working. */
export function workingFor(fields: Pick<Fields, "summary"> | null | undefined, text: string): FoundWorking | null {
  const working = workingOf(fields);
  if (!working || !fields) return null;
  const written = Object.keys(working.criteria);
  const nameOf = (criterion: string) => CRITERION_NAMES[criterion] ?? criterion;
  const named = criterionNamed(text);
  if (named && !written.includes(named)) return { kind: "not-worked", name: nameOf(named), others: written.map(nameOf) };
  const earliest = fields.summary.verdict?.earliest ?? (working.basis === "gauge" ? fields.summary.earliest_gauge : fields.summary.earliest);
  const criterion = named ?? (earliest && written.includes(earliest) ? earliest : written[0]);
  const chain = working.criteria[criterion];
  const asked = stepAsked(text);
  return { kind: "chain", criterion, name: nameOf(criterion), chain, basis: working.basis === "gauge" ? "the gauge section" : "the whole model",
    others: written.filter((c) => c !== criterion).map(nameOf), step: asked ? chain.steps.find((s) => s.id === asked) ?? null : null };
}

/** A value put into a formula, as the page prints it: the figures the package wrote, the page's own minus and power of ten. */
export const givenText = (value: number, figures = 6): string => formatNumber(value, { figures, zeros: false });
