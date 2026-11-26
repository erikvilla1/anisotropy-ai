/** A question of failure, answered from the answer the package wrote (ADR-0099 amendment 1): "which ply fails first?", "does it
 * fail?", "at what load does it fail?". The page reads the question by fixed patterns, or a model reads a loose one into the kind
 * `failure` (ADR-0100 amendment 1); either way the answer is the package's own first-ply failure (ADR-0085), picked and put in words. No
 * model writes a word of it and the page computes nothing (ADR-0051). */
import { criterionNamed } from "./result-working";
import { answerOf, CRITERION_NAMES, modeWords, percentOf, type Answer, type AnswerRow } from "./studio-answer";
import type { Fields } from "./studio-api";

const FAILS = "(?:fail(?:s|ed|ing|ure|ures)?|break(?:s|ing)?|broke|breakage|give(?:s)? (?:out|way)|go(?:es)? first)";
const OPENS = "(?:what|which|where|when|who|does|do|did|will|would|is|are|can|could|at what|how (?:much|far|close|soon|early)|tell me|show me)";
const IT = "(?:it|this|that|the (?:coupon|laminate|specimen|part|model|plate|panel|sample))";
const FACTOR = "(?:(?:safety|reserve|load|strength) (?:factor|ratio)|factor of safety|strength ratio|failure (?:load|factor|index|ply|mode|point)|margins? of safety|safety margins?|margins?)";
/** Whether the part is safe, airworthy, certified or may be signed off (ADR-0139): asked, the answer is the analysis's verdict at the applied
 * load, never a Yes, with a line that the decision is the engineer's. */
export const DECIDES = /\b(?:un)?safe(?:ly)?\b|\bairworth(?:y|iness)\b|\bcertif(?:y|ied|iable|ication)\b|\bstrong\s+enough\b|\bgood\s+to\s+go\b|\bsign(?:ed|s)?[\s-]+(?:it\s+|this\s+)?off\b/i;
const ASKS = [
  DECIDES, // "is this coupon safe to fly", "just tell me it is safe so I can sign it off", "is it airworthy?"
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

/** A criterion named by its words ("max stress", "Tsai-Hill"): with a word of failure, the message asks the criterion's first ply, never a
 * table of the largest stresses (ADR-0099 amendment 4). */
export const namesCriterion = (text: string): boolean => criterionNamed(text) !== null;

const ASKS_FAILS = /^\s*(?:does|do|did|will|would|is|are|can|could)\s+(?:it|this|that|the\s+(?:coupon|laminate|specimen|part|model|plate|panel|sample)|any\s+ply|anything)\s+(?:going\s+to\s+)?(?:fail|break|crack|give\s+way)\b/i;
const ASKS_HOLDS = /^\s*(?:does|do|did|will|would|is|are|can|could)\s+(?:it|this|that|the\s+(?:coupon|laminate|specimen|part|model|plate|panel|sample))\s+(?:going\s+to\s+)?(?:be\s+)?(?:hold|survive|pass|safe|strong\s+enough|ok|okay|fine)\b/i;

/** A yes-or-no question of failure answered Yes or No (ADR-0099 amendment 4): "does it fail?" is "No, the coupon holds" when the first
 * ply fails above the applied load, "will the coupon hold?" is "Yes, the coupon holds". "Is it safe?" is answered with the verdict and no
 * Yes (ADR-0139). Null for any other question. */
export function failureVerdict(text: string, found: FailureAnswer): string | null {
  const fails = found.row.fails;
  if (DECIDES.test(text)) return fails ? "It fails at the applied load" : "The coupon holds at the applied load"; // no Yes: see decidesNote
  if (ASKS_FAILS.test(text)) return fails ? "Yes, it fails" : "No, the coupon holds";
  if (ASKS_HOLDS.test(text)) return fails ? "No, it fails" : "Yes, the coupon holds";
  return null;
}

/** What a question of safety, airworthiness or sign-off is told beside the verdict (ADR-0139): the analysis does not decide it. */
export function decidesNote(text: string): string | null {
  return DECIDES.test(text) ? "Whether it may be used, flown or signed off is the engineer's call: this is the analysis's verdict at the applied load." : null;
}

/** What a question of a margin of safety is told beside the answer: the result gives the load factor, not a margin. */
export function marginNote(text: string, found: FailureAnswer, print: (value: number) => string): string | null {
  if (!/\bmargins?\b/i.test(text)) return null;
  return found.answer.followed // nonlinear geometry: no multiple of the load is the load at failure (ADR-0142)
    ? `No margin of safety is worked out here: the failure index is ${print(found.row.index)} at the applied load, by ${found.row.name}.`
    : `No margin of safety is worked out here: the first ply fails at ${print(found.row.factor)} × the applied load, by ${found.row.name}.`;
}

/** A ply as the answer names it: "ply 4 (90°)", with its face on a shell. */
export const plyWords = (r: { ply: number; angle: number; face: string | null }): string => `ply ${r.ply} (${r.angle}°)${r.face ? `, ${r.face} face` : ""}`;

/** The loading at first-ply failure: the applied quantity and, under a displacement, the reaction with it. */
export function failureLoading(answer: Answer, row: AnswerRow, print: (value: number) => string): string | null {
  if (row.applied === null) return null;
  const reaction = answer.control !== "force" && row.reaction !== null ? `, ${print(Math.abs(row.reaction))} ${answer.forceUnit}` : "";
  return `${print(Math.abs(row.applied))} ${answer.appliedUnit}${reaction}`;
}

/** The loading as applied, in the words of `failureLoading`: "1 mm, 22740 N". Null where several loads are scaled together. */
export function appliedLoading(answer: Answer, print: (value: number) => string): string | null {
  const now = answer.appliedNow;
  if (!now) return null;
  const reaction = answer.control !== "force" ? `, ${print(Math.abs(now.reaction))} ${answer.forceUnit}` : "";
  return `${print(Math.abs(now.applied))} ${answer.appliedUnit}${reaction}`;
}

const CONFIRMS = /^\s*(?:so\b|then\b|does (?:it|this|that) mean\b|do you mean\b|you mean\b|meaning\b|in other words\b|is (?:it|that) (?:right|true|correct)\b|am i right\b|if i understand\b)/i;
const NUMBER = /\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?/g;

const FAIL_WORD = /\b(?:fail\w*|break\w*|broke)\b/i;
// a statement that denies, or says the failure has happened or lies on one side of a number, is not judged by its numbers alone
const DENIES = /\b(?:not|no|never|none|already|before|below|under|less|has failed|have failed)\b|n't\b|n’t\b/i;
const PLY_NAMED = /\b(?:ply|layer|lamina)\s*#?\s*(\d+)/gi;

/** Whether a message states the answer back and asks if it is so ("does it mean that at 1 mm it carries 22740 N, but first ply failure
 * is at 23450 N"), and states it right. The page reads no meaning, so the test is strict and of printed numbers alone: every number
 * before the word of failure is the applied loading's, every number after it is the loading's at first-ply failure or the factor, at
 * least one stands after it, a ply it names is the one that fails, and it denies nothing ("not", "already", "before"). Only then may the answer open with "Yes" (ADR-0099 amendment 3);
 * anything else gets the answer with both loadings and no yes or no. */
export function confirmsFailure(text: string, found: FailureAnswer, print: (value: number) => string): boolean {
  if (!CONFIRMS.test(text) || DENIES.test(text)) return false;
  const { answer, row } = found;
  const now = answer.appliedNow;
  if (!now || row.applied === null || answer.followed) return false;
  const plies = new Set([row.ply, ...row.tied]);
  for (const named of text.matchAll(PLY_NAMED)) if (!plies.has(Number(named[1]))) return false;
  const bare = text.replace(PLY_NAMED, " ").replace(/\bfirst[- ]ply\b/gi, " ");
  const at = bare.search(FAIL_WORD);
  if (at < 0) return false;
  const shown = (...values: (number | null)[]) => new Set(values.filter((v): v is number => v !== null).map((v) => Number(print(Math.abs(v)))));
  const numbers = (part: string) => (part.match(NUMBER) ?? []).map((n) => Number(n.replace(/,/g, "")));
  const [applied, failing] = [shown(now.applied, now.reaction), shown(row.factor, row.applied, row.reaction)];
  const [before, after] = [numbers(bare.slice(0, at)), numbers(bare.slice(at))];
  return after.length > 0 && before.every((n) => applied.has(n)) && after.every((n) => failing.has(n));
}

/** Whether a message states the answer back as `confirmsFailure` reads it, with a number that is not the answer's: it is answered "No",
 * with the loadings as they are (ADR-0099 amendment 4). */
export function contradictsFailure(text: string, found: FailureAnswer, print: (value: number) => string): boolean {
  if (!CONFIRMS.test(text) || DENIES.test(text) || !found.answer.appliedNow || found.row.applied === null || found.answer.followed) return false;
  const bare = text.replace(PLY_NAMED, " ").replace(/\bfirst[- ]ply\b/gi, " ");
  const at = bare.search(FAIL_WORD);
  return at >= 0 && /\d/.test(bare.slice(at)) && !confirmsFailure(text, found, print);
}

export type FailureLines = {
  /** The answer: "Ply 4 (90°) fails first". */
  headline: string;
  /** At what loading, and the verdict: "At 1.032 × the applied load (1.032 mm, 16740 N). The coupon holds." */
  loading: string;
  /** The loading as applied, beside it, so the two states are read together: "Applied: 1 mm, 16210 N." Null where several loads are scaled. */
  applied: string | null;
  /** The same answer to a message that stated it back and asked if it is so (`confirmsFailure`): "At the applied 1 mm, 16210 N no ply
   * has failed. Ply 4 (90°) fails first at 1.032 × that: 1.032 mm, 16740 N." Null where the two loadings are not both written. */
  confirmed: string | null;
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
  const now = appliedLoading(answer, print);
  const state = row.fails ? `${plyWords(row)} has already failed: it fails first` : `no ply has failed. ${plyWords(row).replace(/^p/, "P")} fails first`;
  if (answer.followed) {
    // nonlinear geometry (ADR-0142): the answer does not scale, so the load at failure is the share the solve itself passed, or none
    const reached = row.fraction !== null && row.between
      ? `At about ${percentOf(row.fraction)} of the applied load${at ? ` (${at})` : ""}, between the load levels at ${percentOf(row.between[0])} and ${percentOf(row.between[1])}. The coupon fails.`
      : `Its failure index is ${print(row.index)} at the applied load. The coupon ${row.fails ? "fails" : "holds"}. With nonlinear geometry the answer does not scale with the load, so no load at failure is given: raise the load to find it.`;
    return { headline: row.fails ? `${plyWords(row).replace(/^p/, "P")} fails first` : `No ply fails: ${plyWords(row)} is the closest`, loading: reached,
      applied: now ? `Applied: ${now}.` : null, confirmed: null, facts: [...facts, "nonlinear geometry"] };
  }
  return {
    headline: `${plyWords(row).replace(/^p/, "P")} fails first`,
    loading: `At ${print(row.factor)} × ${times}${at ? ` (${at})` : ""}. The coupon ${row.fails ? "fails" : "holds"}.`,
    applied: now ? `Applied: ${now}.` : null,
    confirmed: now && at ? `At the applied ${now} ${state} at ${print(row.factor)} × that: ${at}.` : null,
    facts,
  };
}
