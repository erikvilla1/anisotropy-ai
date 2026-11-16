/** A question that asks for a reason or a meaning, answered in words from the results and our theory pages (ADR-0102). A question that
 * asks for a value ("stress in ply 5 at element 120", "where is the shear highest?") is the lookup's (ADR-0099, ADR-0100). */
import { shownSentence } from "./studio-copy";
import type { ResultAnswer } from "./studio-api";

const OPENS = /^\s*(?:why\b|how come\b|explain\b|what (?:causes|makes|explains)\b|what does\b.+\bmean\b|what is meant by\b)/i;
const ENDS = /\bwhy\b[^.?!]*\?\s*$/i; // "ply 4 is in compression, why?"

/** Whether a message asks why, or what something means. */
export const asksWhy = (text: string): boolean => OPENS.test(text) || ENDS.test(text);

/** The fact sheet a question is answered from: the shown result's, when it holds any fact. An older result carries none. */
export function factsOf(explanation: { facts: Record<string, unknown> } | null | undefined): Record<string, unknown> | null {
  const facts = explanation?.facts;
  return facts && Object.keys(facts).length ? facts : null;
}

export type WhyLines = {
  /** The answer's sentences as the page shows them; none when no answer was written or none is fit to show. */
  prose: string[];
  /** The theory sections named under it: those the answer rests on, or, with no prose, those the question found. */
  sources: string[];
  /** What the small line under the answer says. */
  note: string;
};

/** What the page shows of an answer: its sentences in the product's own words (a sentence that names a program is left out, ADR-0091),
 * the sections by document and title, and one line saying what the answer rests on or why there is none. */
export function whyLines(answer: ResultAnswer, preview: boolean): WhyLines {
  const prose = answer.prose.map(shownSentence).filter((sentence): sentence is string => sentence !== null);
  const sources = answer.sources.map((s) => `${s.document}, ${s.title}`);
  const named = sources.length ? ` ${sources.length > 1 ? "Sections" : "Section"} of the theory behind it: ${sources.join("; ")}.` : "";
  if (!prose.length) {
    const none = answer.withheld ? "An answer was written, but it held a number the results do not, so it is not shown."
      : "A question like this is not answered in words here yet.";
    return { prose, sources, note: none + named };
  }
  const basis = answer.covered && sources.length ? `From the results and the theory: ${sources.join("; ")}.` : "From the results; the theory pages do not explain this yet.";
  return { prose, sources, note: `${basis} Every number is the results’ own.${preview ? " From the preview: run the analysis to verify it." : ""}` };
}
