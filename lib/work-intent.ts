/** What a message asks to work on (ADR-0124): a section of the workspace (FEA, CAD, Laminate) or a kind of FEA work (a coupon test, a
 * wing), and whether it asks to start it or only asks about it. Fixed words, no model, so the same message is read the same way on the
 * start screen and in every section's chat. "What is a coupon test?" names a coupon but starts nothing; "I want to test some coupons",
 * "coupon testing", "ABD of [0/90]s" or "Laminate" start one: a statement that names the work asks for it. Pure, so `tests/work-intent.test.ts` runs it in Node. */

export type WorkTarget = "coupon" | "wing" | "fea" | "laminate" | "cad";
export type Intent = { target: WorkTarget; start: boolean };

/** The words of each target, the most specific first: a coupon's or a wing's words win over FEA's, and the laminate's are the words of
 * a laminate problem, not "laminate" alone, which every coupon's layup is. */
const WORDS: readonly [WorkTarget, RegExp][] = [
  ["coupon", /\b(coupons?|dog-?bones?|open[- ]hole|unnotched|(tension|compression|shear|bending) (tests?|testing|specimens?)|(three|four|3|4)[- ]point bend(ing)?|d3039|d5766|d6641|d3518|d7264|d638)\b/i],
  ["wing", /\b(wings?|spar caps?|wing box|airfoils?|aerofoils?)\b/i],
  ["laminate", /\b(laminate (response|problem|theory|section|workspace|calculator|tool)|abd( matri(x|ces))?|classical lamination|clt|hand calc(ulation)?s?|homework)\b/i],
  ["cad", /\b(cad|solidworks|step file|draw (a|the) (part|shape|geometry))\b/i], // not "sketch": the coupon has one on the page
  ["fea", /\b(fea|finite elements?|calculix|abaqus|ansys)\b/i],
];

/** A section's or a kind's own name, said alone or nearly so ("Laminate", "CAD please", "coupon testing"): a pick. */
const NAMES: readonly [WorkTarget, RegExp][] = [
  ["laminate", /\blaminates?\b/i],
  ["coupon", /\bcoupons?\b/i],
  ["wing", /\bwings?\b/i],
  ["cad", /\bcad\b/i],
  ["fea", /\bfea\b/i],
];

/** A message that opens as a question, or ends as one. */
const QUESTION = /^\s*(what|why|how|when|where|which|who|whose|is|are|was|were|does|do|did|should|would|could|will|explain|define|describe|tell me about|difference)\b|\?\s*$/i;
/** Words that ask for the work itself, inside a question: "can you set up a coupon?" starts one, "what is a coupon?" does not. */
const ASKS_FOR = /\b(can you|could you|can we|can i|please|help me|set (it )?up|setup|start|begin|switch|go to|move to|open|take me)\b/i;

const words = (text: string): number => text.trim().split(/\s+/).filter(Boolean).length;

/** What a message asks to work on, or null when it names no section and no kind of work. */
export function readIntent(text: string): Intent | null {
  const said = text.trim();
  if (!said) return null;
  if (words(said) <= 3) { // a name said alone is a pick, whatever it opens with
    const named = NAMES.find(([, re]) => re.test(said));
    if (named && !/\?\s*$/.test(said)) return { target: named[0], start: true };
  }
  const found = WORDS.find(([, re]) => re.test(said));
  if (!found) return null;
  // a statement naming the work asks for it; a question starts nothing unless it asks for the work itself
  return { target: found[0], start: !QUESTION.test(said) || ASKS_FOR.test(said) };
}

/** The section a target is worked in. */
export function sectionOf(target: WorkTarget): "fea" | "cad" | "laminate" {
  return target === "coupon" || target === "wing" || target === "fea" ? "fea" : target;
}

/** Whether a message says more than the kind of work it asks for, so it is worth carrying to the section's assistant: a number, a layup
 * in brackets, or rows the receiving chat reads (`reads`, the coupon chat's own patterns). "I want to test some coupons" is not carried;
 * "test an IM7/8552 open-hole coupon" is. */
export function saysMore(text: string, reads: (text: string) => boolean = () => false): boolean {
  return /\d|\[/.test(text) || reads(text);
}

/** Each target's name as the page says it: on a button, a question and a card. */
export const TARGET_TITLES: Record<WorkTarget, string> = { coupon: "Coupon test", wing: "Wing analysis", fea: "FEA", laminate: "Laminate", cad: "CAD" };
