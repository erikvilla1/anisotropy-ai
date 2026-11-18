/** A question of failure, answered from the answer the package wrote (ADR-0099 amendment 1): "which ply fails first?", "does it
 * fail?", "at what load does it fail?". The page reads the question by fixed patterns, or a model reads a loose one into the kind
 * `failure` (ADR-0100 amendment 1); either way the answer is the package's own first-ply failure (ADR-0085), picked and put in words. No
 * model writes a word of it and the page computes nothing (ADR-0051). */
import { criterionNamed } from "./result-working";
import { answerOf, CRITERION_NAMES, modeWords, type Answer, type AnswerRow } from "./studio-answer";
import type { Fields } from "./studio-api";

const FAILS = "(?:fail(?:s|ed|ing|ure|ures)?|break(?:s|ing)?|broke|breakage|give(?:s)? (?:out|way)|go(?:es)? first)";
const OPENS = "(?:what|which|where|when|who|does|do|did|will|would|is|are|can|could|at what|how (?:much|far|close|soon|early)|tell me|show me)";
const IT = "(?:it|this|that|the (?:coupon|laminate|specimen|part|model|plate|panel|sample))";
const FACTOR = "(?:(?:safety|reserve|load|strength) (?:factor|ratio)|factor of safety|strength ratio|failure (?:load|factor|index|ply|mode|point))";
const ASKS = [
  new RegExp(`^\\s*${OPENS}\\b.*\\b${FAILS}\\b`, "i"), // "what is the ply that fails", "does it fail?", "where does it break"
  new RegExp(`\\b${FAILS}\\b[^.!]*\\?\\s*$`, "i"), // "the first ply to fail?"
  new RegExp(`^\\s*(?:and )?(?:the )?(?:first[- ]ply[- ]failure|fpf|first (?:ply |layer |one )?to fail|first failure)\\s*[.?!]*\\s*$`, "i"),
  new RegExp(`^\\s*(?:does|will|would|can|could|is|did) ${IT} (?:going to )?(?:hold|survive|pass|safe|strong enough)\\b`, "i"), // "will it hold?"
  new RegExp(`^\\s*${OPENS}\\b.*\\b${FACTOR}\\b`, "i"), // "what is the strength ratio?"
  new RegExp(`^\\s*(?:the )?${FACTOR}\\s*[.?!]*\\s*$`, "i"),
];
// a message that opens by setting something states the setup, whatever it goes on to name ("use the Tsai-Wu failure criterion")
const SETTING = /^\s*(?:make|set|change|use|apply|add|put|pull|push|load|hold|fix|remove|drop|switch|pick|choose|select)\b/i;
// which criteria there are, or which to use, is a question of the setup's rows, not of this result
const OF_CRITERIA = /\b(?:which|what)\b[^?]*\bcriteri(?:on|a)\b[^?]*\b(?:can|could|should|may|do you|are (?:there|available|offered|supported)|to use)\b/i;

// a run, a check or a file that failed is not the coupon failing
const OF_THE_SOFTWARE = /\b(?:run|job|solver|solve|analysis|check|mesh|meshing|upload|import|download|document|pdf|report|sign[- ]?in|log[- ]?in|page|site|server)\b[^.?!]{0,40}\bfail/i;

/** Whether a message asks which ply fails first, whether the coupon fails, or at what loading. A question of why is `asksWhy`'s and a
 * request for the formula is `asksWorking`'s; the chat asks those first. */
export const asksFailure = (text: string): boolean => !SETTING.test(text) && !OF_CRITERIA.test(text) && !OF_THE_SOFTWARE.test(text) && ASKS.some((pattern) => pattern.test(text));

export type FailureAnswer = {
  answer: Answer;
  /** The criterion the sentences speak of: the one the message names, else the one that governs. */
  row: AnswerRow;
  /** A criterion the message names that this result does not hold, by its name; the governing one is spoken of in its place. */
  missing: string | null;
};

/** The package's answer for a question of failure; null for a result solved before the package wrote one. */
export function failureAnswer(fields: Fields, text: string): FailureAnswer | null {
  const answer = answerOf(fields);
  if (!answer) return null;
  const named = criterionNamed(text);
  const row = named ? answer.rows.find((r) => r.criterion === named) : undefined;
  return { answer, row: row ?? answer.earliest, missing: named && !row ? CRITERION_NAMES[named] ?? named : null };
}

/** A ply as the answer names it: "ply 4 (90°)", with its face on a shell. */
export const plyWords = (r: { ply: number; angle: number; face: string | null }): string => `ply ${r.ply} (${r.angle}°)${r.face ? `, ${r.face} face` : ""}`;

/** The loading at first-ply failure: the applied quantity and, under a displacement, the reaction with it. */
export function failureLoading(answer: Answer, row: AnswerRow, print: (value: number) => string): string | null {
  if (row.applied === null) return null;
  const reaction = answer.control !== "force" && row.reaction !== null ? `, ${print(Math.abs(row.reaction))} ${answer.forceUnit}` : "";
  return `${print(Math.abs(row.applied))} ${answer.appliedUnit}${reaction}`;
}

export type FailureLines = {
  /** The answer: "Ply 4 (90°) fails first". */
  headline: string;
  /** At what loading, and the verdict: "At 1.032 × the applied load (1.032 mm, 16740 N). The coupon holds." */
  loading: string;
  /** What it rests on, as short labels: the criterion, the mode, the element, where it is read, the plies tied. */
  facts: string[];
};

/** The answer in three short lines. Every number is the package's, printed by `print`; nothing is computed here. */
export function failureLines(found: FailureAnswer, print: (value: number) => string): FailureLines {
  const { answer, row } = found;
  const times = answer.everyLoad ? "every applied load" : "the applied load";
  const at = failureLoading(answer, row, print);
  const facts = [row.name, modeWords(row.mode).replace(/^the /, ""), `element ${row.label.split(".").pop()}`, answer.basisWords.replace(/^the /, "")];
  if (row.tied.length) facts.push(`tied with ${row.tied.length > 1 ? "plies" : "ply"} ${row.tied.join(", ")}`);
  return {
    headline: `${plyWords(row).replace(/^p/, "P")} fails first`,
    loading: `At ${print(row.factor)} × ${times}${at ? ` (${at})` : ""}. The coupon ${row.fails ? "fails" : "holds"}.`,
    facts,
  };
}
