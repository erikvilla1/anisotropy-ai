import type { Fields } from "./studio-api";

/** A question of the whole result rather than a ply's value (ADR-0099 amendment 4): the reaction at the grip, the largest displacement,
 * the laminate's modulus. Each is read from the fields the page shows, as the result card and the test quantities print it; nothing is
 * computed here. The first real-model run of the question banks (2026-11-20) found "what is the reaction force" told it was not on offer. */

export type SummaryQuantity = "reaction" | "displacement" | "modulus";

const ASKS = /^\s*(?:(?:and|so|ok|okay|now)[,.]?\s+)?(?:what(?:'s|’s|s)?|whats|how\s+(?:much|big|large|stiff)|show(?:\s+me)?|give(?:\s+me)?|tell\s+me|which|where)\b|\?\s*$|^\s*(?:the\s+)?(?:max(?:imum)?\s+)?[a-z\s'’-]{0,30}\s*[.?!]*\s*$/i;
const REACTION = /\b(?:reaction(?:\s+force)?s?|rf[123]?|grip\s+force|force\s+(?:at|on)\s+the\s+(?:top\s+|bottom\s+)?grip|force\s+(?:it\s+)?(?:carries|takes)|load\s+(?:it\s+)?(?:carries|takes)|(?:force|load)\s+does\s+it\s+(?:carry|take)|how\s+much\s+(?:force|load))\b/i;
const DISPLACEMENT = /\b(?:displacement|deflection|deformation)s?\b/i;
const MODULUS = /\b(?:modulus|young'?s|stiffness|e[\s_-]?x)\b/i;
/** A modulus of the material or of a ply is the library's, not this result's. */
const OF_MATERIAL = /\b(?:material|resin|fib(?:re|er)s?|matrix|ply|plies|lamina|e1|e2|g12|g13|g23|im7|as4|t650|x840|8552)\b/i;
/** A message that sets a value states the setup. */
const SETTING = /^\s*(?:make|set|change|use|apply|add|put|pull|push|load|hold|fix)\b/i;

/** The whole-result quantity a message asks for, or null. */
export function summaryAsked(text: string): SummaryQuantity | null {
  // the load at failure is the failure answer's, never the reaction as applied
  if (SETTING.test(text) || !ASKS.test(text) || /\b(?:fail\w*|break\w*|broke|first[- ]ply|fpf)\b/i.test(text)) return null;
  if (/\b(?:ply|plies|layer|lamina|element|elem|node)\b/i.test(text)) return null; // a ply's or an element's value is a lookup (ADR-0099)
  if (REACTION.test(text)) return "reaction";
  if (DISPLACEMENT.test(text)) return "displacement";
  if (MODULUS.test(text) && !OF_MATERIAL.test(text)) return "modulus";
  return null;
}

/** The answer as the chat says it: the value as the heading and what it is of, or why this result holds none. */
export function summaryAnswer(fields: Fields, asked: SummaryQuantity, print: (value: number) => string): { title: string; lines: string[]; found: boolean } {
  const s = fields.summary, lab = fields.labels;
  if (asked === "reaction") {
    const r = s.reaction;
    const applied = s.applied ? `Under the applied ${print(Math.abs(s.applied.value))} ${s.applied.unit}${s.applied.direction ? ` ${s.applied.direction}` : ""}.` : null;
    return { title: `Reaction: ${print(Math.abs(r.value))} ${lab.force ?? ""}`.trim(), found: true,
      lines: [[r.set, r.sense].filter(Boolean).join(", "), ...(applied ? [applied] : [])] };
  }
  if (asked === "displacement") {
    const d = s.max_displacement;
    const node = d.label.split(".").pop();
    // a followed plate (ADR-0142): what a linear solve of the same plate gives beside it, and where every load level is
    const linear = s.followed ? `With nonlinear geometry; a linear solve of the same plate gives ${print(Math.abs(s.followed.linear.largest))} ${lab.length ?? ""}. Every load level is in the table under Details.` : null;
    return { title: `Largest displacement: ${print(Math.abs(d.value))} ${lab.length ?? ""}`.trim(), found: true,
      lines: [`node ${node}${d.axis ? `, along ${d.axis}` : ""}`, ...(linear ? [linear] : [])] };
  }
  const tm = s.test_method;
  const chord = tm?.strain?.chord;
  if (tm && chord) {
    const words = tm.reduction?.modulus ?? "chord modulus";
    const theory = tm.laminate_theory.isotropic ? "the material's own" : "laminate theory";
    return { title: `${words.charAt(0).toUpperCase()}${words.slice(1)}: ${print(chord.modulus)} ${tm.units.modulus}`, found: true,
      lines: [`${print(chord.from * 1e6)} to ${print(chord.to * 1e6)} microstrain, over the ${tm.reduction?.area ?? "gross area"}; ${theory} ${print(tm.laminate_theory.modulus)} ${tm.units.modulus}`] };
  }
  return { title: "No modulus in this result", found: false,
    lines: ["The modulus is measured as a test standard sets it out. Choose ASTM D3039 under Test and run again: the result then gives the chord modulus beside laminate theory's."] };
}
