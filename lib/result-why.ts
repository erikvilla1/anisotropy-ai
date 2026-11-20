/** A question that asks for a reason or a meaning, answered in words from the results and our theory pages (ADR-0102). A question that
 * asks for a value ("stress in ply 5 at element 120", "where is the shear highest?") is the lookup's (ADR-0099, ADR-0100). */
import { shownSentence } from "./studio-copy";
import type { ResultAnswer } from "./studio-api";

const OPENS = /^\s*(?:why\b|how come\b|explain\b|what (?:causes|makes|explains)\b|what does\b.+\bmean\b|what is meant by\b)/i;
const ENDS = /\bwhy\b[^.?!]*\?\s*$/i; // "ply 4 is in compression, why?"

/** Whether a message asks why, or what something means. */
export const asksWhy = (text: string): boolean => OPENS.test(text) || ENDS.test(text);

/** The fact sheet a question is answered from: the shown result's, when it holds any fact. An older result carries none. */
/** Where a result's fact sheet says its answer is read ("the gauge section", "the whole model"), or null. */
export const readAt = (facts: Record<string, unknown> | null): string | null => (typeof facts?.basis === "string" && facts.basis.trim() ? facts.basis.trim() : null);

export function factsOf(explanation: { facts: Record<string, unknown> } | null | undefined): Record<string, unknown> | null {
  const facts = explanation?.facts;
  return facts && Object.keys(facts).length ? facts : null;
}

/** The most a heading holds, in characters (ADR-0121 amendment 7): the banks hold every heading to it. */
export const HEADING_ROOM = 60;

/** An answer's first sentence as its heading when it fits, the rest under it; a first sentence too long for a heading goes under `long`,
 * unchanged, since the page never cuts a model's words (ADR-0121 amendment 7). */
export function headed(prose: string[], long: string): { heading: string; more: string[] } {
  return prose[0].length <= HEADING_ROOM ? { heading: prose[0], more: prose.slice(1) } : { heading: long, more: prose };
}

export type WhyLines = {
  /** The answer's sentences as the page shows them; none when no answer was written or none is fit to show. */
  prose: string[];
  /** The heading: the answer's first sentence, or a fixed one when it is too long for a heading, or that there is none (ADR-0102
   * amendment 1, ADR-0121 amendment 7). */
  heading: string;
  /** The sentences under the heading. */
  more: string[];
  /** The theory sections the answer rests on, folded under Details, or, with no prose, those the question found. */
  sources: string[];
  /** What the small line under the answer says: where the result is read, what the answer rests on, and whether it is a preview. */
  note: string;
};

/** What the page shows of an answer: its sentences in the product's own words (a sentence that names a program is left out, ADR-0091), the
 * first as the heading; one short line saying where the result is read (the fact sheet's `basis`, ADR-0102 amendment 2) and what the answer
 * rests on, the sections by document and title folded under it; or why there is none. */
export function whyLines(answer: ResultAnswer, preview: boolean, place: string | null = null): WhyLines {
  const prose = answer.prose.map(shownSentence).filter((sentence): sentence is string => sentence !== null);
  const sources = answer.sources.map((s) => `${s.document}, ${s.title}`);
  if (!prose.length) {
    const see = sources.length ? ` See: ${sources.join("; ")}.` : "";
    const none = answer.withheld ? "The answer held a number the results do not, so it is not shown." : "Not answered in words yet.";
    return { prose, heading: "No answer in words", more: [], sources, note: none + see };
  }
  const covered = answer.covered && sources.length > 0;
  const basis = covered ? "From the results and our theory pages." : "From the results only.";
  const read = place ? `Read in ${place}. ` : "";
  return { prose, ...headed(prose, "Answered in words from the results"), sources: covered ? sources : [],
    note: `${read}${basis}${preview ? " Preview: run the analysis to verify." : ""}` };
}

/** What the FEA assistant of a blank project shows of an answer to a question (ADR-0124): its sentences in the product's own words, as
 * `whyLines` shows them (a sentence that names a program, or "engine", is left out, ADR-0091), and the sections it rests on. */
export function generalLines(answer: ResultAnswer): { prose: string[]; sources: string[] } {
  return { prose: answer.prose.map(shownSentence).filter((sentence): sentence is string => sentence !== null),
    sources: answer.sources.map((s) => `${s.document}, ${s.title}`) };
}
