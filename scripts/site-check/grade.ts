/** The fixed checks of the site check (ADR-0138): what can be told of an answer on the live site without a model. Each check that does
 * not hold says why, with the criterion of the `chat-answer-quality` skill it fails. The model judge grades the rest afterwards, and
 * only answers that pass every check here. */
import { bannedIn } from "../../lib/studio-copy";
import { FEA_KINDS, workspace } from "../../lib/workspaces";
import type { Question } from "../../tests/assistant-questions/harness";
import { NumberPool, untraced } from "./numbers";

/** What the robot saw of one answer in the browser. */
export type Seen = {
  /** The answer's heading, the text shown, and the text folded under Details. */
  heading: string;
  shown: string;
  folded: string;
  /** The test ids and kinds of the answer's parts, which say what kind of answer the page gave ("chat-values", "chat-why", ...). */
  parts: string[];
  /** Whether the answer offers to change the model: a card of rows to tick, or an Apply button. */
  applies: boolean;
  /** From Enter to the answer standing still, in seconds. */
  seconds: number;
  /** Whether the answer had not stood still when the robot stopped waiting. */
  timedOut: boolean;
  /** What the page said it was still doing then, under an answer it had shown ("Checking the setup…"). */
  busy?: string;
  /** The calls to the model the question made on the site. */
  modelCalls: number;
  /** Script errors on the page while it was answered. */
  errors: string[];
  /** The heading of the answer before, when the question leans on earlier messages. */
  before?: string;
  /** The answer first shown, when the page then worked and replaced it: a sweep, a solve. The bank's page answer is that first one. */
  interim?: { heading: string; shown: string; folded: string };
  /** Numbers the question quotes that this page's result does not hold: the bank wrote them of its example's result, so its words for
   * the answer ("Yes") need not hold here, and only the judge grades the answer's words. */
  foreign?: string[];
};

export type Level = "fails" | "weak";
export type Check = { name: string; level: Level; note: string; criterion?: number };

/** How long an answer may take, in seconds: the page's own answer, and one a model read or wrote. Beyond the first it is weak, beyond the
 * second it fails. */
export const SECONDS = { page: [5, 20], model: [20, 60] } as const;

/** The page's words when an answer could not be had: an outage, not an answer (criterion 11). */
const OUTAGE = /could not be answered right now|is unavailable right now|try again in a (moment|minute)/i;
/** The parts of an answer the model wrote in words: its numbers must all be the engine's (ADR-0052, ADR-0102). */
const PROSE = /^(chat-why|chat-general|fea-start-answer)/;
/** Words a repair's answer never uses of the repair unless it says the repair is not so (ADR-0136): the hand calculation and the slice
 * give an elastic limit load, never a strength, a margin or a safe design. */
const REPAIR_WORDS = /\b(strong enough|margin|safe|carries the load|restores)\b/i;
const NEGATION = /\b(not|no|never|neither|nor|cannot|isn['’]t|aren['’]t|doesn['’]t|without)\b/i;

/** The repair words a text uses without a negation before them in the same sentence. */
export function repairClaims(text: string): string[] {
  const out: string[] = [];
  for (const sentence of text.split(/(?<=[.!?:])\s+|\n+/)) {
    const found = REPAIR_WORDS.exec(sentence);
    if (found && !NEGATION.test(sentence.slice(0, found.index))) out.push(found[0]);
  }
  return out;
}

const hasDigit = (text: string) => /\d/.test(text);

/** The pages whose state on the live site differs from the bank's example of them by design, and how. The bank's words for an answer
 * there are of its example: a mismatch is weak, and the judge, told the difference, grades the answer. */
export const LIVE_DIFFERS: Readonly<Record<string, string>> = {
  setup: "the customer's setup screen takes the geometry from the standard and previews first-ply failure before any run; the bank's example of a setup has no preview",
  "wing-caps": "the spar caps are added by their button, the same along the span, so the wing has no ply drop; the bank's example has a zone that ends",
};

/** Where a page the bank's answer "Opens <title>" opens: a section of the workspace or a kind of FEA work with a page of its own. */
export const OPENS: Readonly<Record<string, string>> = {
  ...Object.fromEntries((["laminate", "cad", "fea"] as const).map((id) => [workspace(id).title, workspace(id).href])),
  ...Object.fromEntries(FEA_KINDS.filter((k) => k.href).map((k) => [k.title, k.href!])),
};

/** Every fixed check an answer does not hold. `modelRead`: whether the site read the question with a model, so the page's own expected
 * answer (`answer` in the bank) does not apply and the judge holds it to `live` instead. `pool`: the numbers the engine sent and the
 * page printed outside the chat, and the question's own (a pool of their own, so a number one question quotes never traces another's). */
export function fixedChecks(question: Question, seen: Seen, pool: NumberPool | readonly NumberPool[], modelRead: boolean): Check[] {
  const out: Check[] = [];
  const text = [seen.heading, seen.shown, seen.folded].join("\n");
  if (!text.trim()) {
    out.push({ name: "answered", level: "fails", note: "no answer appeared", criterion: 11 });
    return out;
  }
  if (seen.timedOut) { // an answer, but the page had not finished with it: slow work after it, or an answer that keeps changing
    out.push({ name: "answered", level: "weak", criterion: 11,
      note: seen.busy ? `the page was still at work under its answer when the robot stopped waiting (“${seen.busy}”)` : "the answer was still changing when the robot stopped waiting" });
  }
  if (OUTAGE.test(seen.shown)) out.push({ name: "answered", level: "fails", note: "the page said it could not answer right now", criterion: 11 });
  const [slow, late] = modelRead || seen.modelCalls > 0 ? SECONDS.model : SECONDS.page;
  if (seen.seconds > late) out.push({ name: "time", level: "fails", note: `answered after ${seen.seconds.toFixed(1)} s (${late} s at most)` });
  else if (seen.seconds > slow) out.push({ name: "time", level: "weak", note: `answered after ${seen.seconds.toFixed(1)} s (${slow} s is the aim)` });
  const banned = bannedIn(text);
  if (banned.length) out.push({ name: "names", level: "fails", note: `names ${banned.join(", ")}`, criterion: 8 });
  if (seen.heading.length > 60) out.push({ name: "heading", level: "fails", note: `heading of ${seen.heading.length} characters (60 at most)`, criterion: 8 });
  if (seen.applies && question.kind !== "change" && question.kind !== "command") {
    out.push({ name: "changes", level: "fails", note: "a question offered to change the model", criterion: 1 });
  }
  const loose = untraced([seen.heading, seen.shown, seen.folded].join("\n"), pool);
  if (loose.length) {
    const prose = seen.parts.some((part) => PROSE.test(part));
    out.push({ name: "numbers", level: prose ? "fails" : "weak", criterion: 4,
      note: `${loose.length === 1 ? "a number" : "numbers"} not found in what the engine sent or the page shows: ${[...new Set(loose)].slice(0, 6).join(", ")}` });
  }
  const expected = question.answer ?? {};
  const opens = expected.opens;
  if (opens && !seen.foreign?.length && ![seen.heading, seen.interim?.heading ?? ""].some((h) => h.startsWith(opens))) {
    out.push({ name: "expected", level: LIVE_DIFFERS[question.page] ? "weak" : "fails", note: `does not open with “${opens}”`, criterion: 1 });
  }
  for (const words of expected.never ?? []) {
    if (text.toLowerCase().includes(words.toLowerCase())) out.push({ name: "expected", level: "fails", note: `says “${words}”` });
  }
  const opened = seen.parts.includes("opened-page") ? /^The page opened (\S+)\.$/.exec(seen.shown)?.[1] ?? "" : null;
  if (opened !== null) { // the answer is another page: it must be the one the bank names
    const title = expected.heading?.startsWith("Opens ") ? expected.heading.slice(6) : null;
    const wanted = title ? OPENS[title] : undefined;
    if (!title) out.push({ name: "expected", level: "fails", note: `opened ${opened}, which the bank does not expect`, criterion: 1 });
    else if (wanted && opened.replace(/\/$/, "") !== wanted) out.push({ name: "expected", level: "fails", note: `opened ${opened}, expected ${wanted}`, criterion: 1 });
  } else if (!modelRead && !seen.foreign?.length) {
    // the page's own answer, whose words the bank states, as first shown; a number in them is the example's, so only words are held
    const level: Level = LIVE_DIFFERS[question.page] ? "weak" : "fails";
    const headings = [seen.heading, seen.interim?.heading];
    const said = [text, seen.interim ? [seen.interim.heading, seen.interim.shown, seen.interim.folded].join("\n") : ""].join("\n");
    if (expected.heading && !hasDigit(expected.heading) && !headings.includes(expected.heading)) {
      out.push({ name: "expected", level, note: `heading “${seen.heading}”, expected “${expected.heading}”` });
    }
    for (const words of expected.says ?? []) {
      if (!hasDigit(words) && !said.includes(words)) out.push({ name: "expected", level, note: `does not say “${words}”` });
    }
  }
  if (question.page.startsWith("repair")) {
    const claims = repairClaims(text);
    if (claims.length) out.push({ name: "repair", level: "fails", note: `calls the repair “${claims.join("”, “")}”: a repair's answer gives an elastic limit load` });
  }
  if (seen.before && seen.before === seen.heading && /\?$|^One question$|^Which /.test(seen.heading)) {
    out.push({ name: "asked-twice", level: "fails", note: `the same question back twice: “${seen.heading}”`, criterion: 11 });
  }
  if (seen.errors.length) out.push({ name: "page", level: "fails", note: `the page's script failed: ${seen.errors[0].slice(0, 200)}`, criterion: 9 });
  return out;
}

/** The verdict of the fixed checks alone: fails if any fails, weak if any is weak, else none (the judge decides). */
export function fixedVerdict(checks: readonly Check[]): Level | null {
  return checks.some((c) => c.level === "fails") ? "fails" : checks.length ? "weak" : null;
}
