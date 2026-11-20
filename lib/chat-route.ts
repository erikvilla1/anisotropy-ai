import { aboutAsked, type AboutTopic } from "./chat-about";
import { asksFailure, namesCriterion } from "./result-failure";
import { summaryAsked, type SummaryQuantity } from "./result-summary";
import { asksElement, readFollowUp, readResultQuestion, type ResultQuestion } from "./result-question";
import { asksWhy } from "./result-why";
import { asksWorking } from "./result-working";
import { isConditionOrLoad, setupAsked, termAsked, type FeaTerm, type TermQuestion } from "./fea-terms";
import { toolNamed } from "./chat-tools";
import { applyMessage, isSwitchRequest, unitsNamed, type ChatStep } from "./studio-chat";
import { unitsOf, type StudioForm } from "./studio-form";
import { namesPlateEdit } from "./studio-plate";

/** Who answers a message in the coupon chat (ADR-0121): the page's own readers in a fixed order, then a model where one reads, then the
 * setup's patterns. `components/studio/coupon-chat.tsx` sends every message through `routeMessage` and answers by the route it returns, so
 * the question banks in `tests/assistant-questions/` try the very choice the page makes. Nothing here answers: it only names who does. */

/** A message that opens as a question: with results on the page it asks about them, and the setup's patterns do not read it, so "why is
 * ply 4 in compression?" never changes the test to compression (ADR-0100). */
export const ASKING = /^\s*(?:why|what|where|which|compare)\b/i;

/** A message that asks rather than tells (ADR-0121 amendment 2): it opens with a word that asks ("what", "how", "is", "does", "should"),
 * or it ends in a question mark and asks for nothing to be done ("can you make it 30 wide?" is a request, and is read as one). "What
 * about" and "how about" offer a value, so they are no question. A question is never read into rows of the setup: "how did you get
 * 16740 N" changes no load. */
const ASKS_OPEN = /^\s*(?:why|what(?!\s+about\b)|where|which|who|whom|whose|when|how(?!\s+about\b)|compare|is|are|was|were|does|should|shall|am|(?:do|did|have|has)(?=\s+(?:you|u|i|we|they|it|this|my|the)\b))\b/i;
const REQUEST = /^\s*(?:please|(?:can|could|would|will)\s+(?:you|u|we|i)|may\s+i|let'?s|i(?:'d|\s+would)\s+like|i\s+want)\b/i;
export const isQuestion = (text: string): boolean => ASKS_OPEN.test(text) || (/\?\s*$/.test(text) && !REQUEST.test(text));

/** A question of whether the setup is ready ("is it ready to run?", "is my setup ok?", "can I run it?", "what's missing?"): the setup is
 * checked and the answer opens with Yes or No (ADR-0121 amendment 2). */
const READY = [
  /^\s*(?:is|are)\s+(?:it|this|that|the\s+(?:setup|coupon|model|form)|my\s+(?:setup|coupon|model|form)|everything|all|we|i)\s+(?:all\s+)?(?:ready|ok|okay|good|fine|set|complete|done|right|correct|valid)\b/i,
  /^\s*(?:can|could|may)\s+(?:i|we|you)\s+(?:run|solve)(?:\s+(?:it|this|now|the\s+(?:analysis|model|coupon)))*\s*[?.!]*\s*$/i,
  /^\s*(?:ready(?:\s+to\s+(?:run|go|solve))?|good\s+to\s+go|all\s+set)\s*\?\s*$/i,
  /^\s*(?:is\s+)?(?:anything|something)\s+missing\b/i,
  /^\s*what(?:'s|’s|s|\s+is|\s+are)\s+(?:still\s+)?(?:missing|left)\b/i,
  /^\s*what\s+else\s+(?:do|does)\s+(?:you|it|i)\s+need\b/i,
  /^\s*(?:does|do)\s+(?:it|this|my\s+setup|the\s+setup|everything)\s+look\s+(?:ok|okay|good|right|fine)\b/i,
];
export const asksReady = (text: string): boolean => READY.some((p) => p.test(text));
/** "run it" alone: run when the setup is checked and ready, else check it and say what is still to fix. */
const BARE_RUN = /^\s*(?:run|solve|go|run\s+it|solve\s+it|run\s+(?:the\s+)?analysis|run\s+the\s+model)\s*[.!]*\s*$/i;
/** "check", and the ways it is mistyped. */
const CHECK = /^\s*(?:check|chek|chekc|cehck|chcek|chck|chk|check\s+setup|check\s+the\s+setup|check\s+it|verify(?:\s+(?:it|the\s+setup))?)\b/i;

/** Every route a message can take, in the order `routeMessage` tries them. A new route is a new way of answering, and the question banks
 * must ask at least one question that takes it (`tests/assistant-questions.test.ts`). */
export const ROUTES = ["start-over", "term", "about", "working", "why", "why-none", "summary", "value", "failure", "element", "follow-up", "read-only",
  "ready", "setup-fixed", "run", "check", "full-form", "laminate", "name", "model", "unread", "patterns"] as const;
export type RouteName = (typeof ROUTES)[number];

export type ChatRoute =
  | { route: "start-over" } // "start over": a blank coupon
  | { route: "term"; term: TermQuestion } // what an Abaqus word means, or this model's boundary conditions and loads (ADR-0110)
  | { route: "about"; topic: AboutTopic } // who the assistant is, the units, what is offered: fixed words (ADR-0121 amendment 2)
  | { route: "working" } // the formula or the proof behind the answer (ADR-0103)
  | { route: "why" } // a question of why, answered in words from the results and the theory pages (ADR-0102)
  | { route: "why-none" } // a question of why with no result (or no API) to answer from
  | { route: "summary"; quantity: SummaryQuantity } // the reaction, the largest displacement, the modulus of the whole result (ADR-0099 amendment 4)
  | { route: "value"; question: ResultQuestion } // a value of the results, read by the page's patterns (ADR-0099)
  | { route: "failure" } // which ply fails first, whether it fails, at what load (ADR-0099 amendment 1)
  | { route: "element"; element: number | "picked" | "last" | null } // what an element is, or where (ADR-0099 amendment 3)
  | { route: "follow-up"; question: ResultQuestion } // "now in ply 5": the question before it, with one thing changed (ADR-0099 amendment 3)
  | { route: "read-only" } // an imported model or a past run is on the page: nothing is changed by talking (ADR-0105, ADR-0109)
  | { route: "ready" } // "is it ready to run?": the setup checked, the answer opening with Yes or No (ADR-0121 amendment 2)
  | { route: "setup-fixed"; term: FeaTerm } // "add a boundary condition" where the test fixes them (ADR-0110)
  | { route: "run" }
  | { route: "check" }
  | { route: "full-form" }
  | { route: "laminate" } // the laminate calculator, named (ADR-0060)
  | { route: "name" } // the answer to "Who is running it?"
  | { route: "model" } // a model reads it: a question of the results first, else rows of the setup (ADR-0088, ADR-0100, ADR-0101)
  | { route: "unread" } // a question nothing could read: what can be asked, never a row of the setup
  | { route: "patterns" }; // the setup's own patterns read it into rows, or point at the panel that asks for the next thing (ADR-0055)

/** What the chat knows when a message arrives. */
export type ChatState = {
  form: StudioForm;
  /** An imported model or a past run has the stage. */
  readOnly: boolean;
  /** Results are on the page. */
  results: boolean;
  /** The results carry a fact sheet (`explanation.facts`), which a question of why is answered from. */
  facts: boolean;
  /** The page reaches an API. */
  api: boolean;
  /** A model reads messages (`/v1/workspace/assistant` says it proposes). */
  modelReads: boolean;
  /** A plate is set up and a model reads its regions (ADR-0101). */
  onPlate: boolean;
  /** The setup is checked and ready to run. */
  ready: boolean;
  /** The step the chat's open question asks, if it asked one ("reopen" when it offers saved coupons). */
  step: ChatStep | "reopen" | null;
  /** The element last spoken of ("it"). */
  about: number | null;
  /** The last question about a value, which a fragment follows. */
  thread: ResultQuestion | null;
  /** The laminate calculator can be opened from here. */
  laminate: boolean;
};

/** Whether a message nothing read is a question, said so with what can be asked, rather than read by the setup's patterns: with results on
 * the page anything that opens as a question of them (ADR-0100), and anywhere a question (ADR-0121 amendment 2). */
export const asksUnread = (text: string, results: boolean): boolean => (results && ASKING.test(text)) || isQuestion(text);

/** Whether a model reads a message as a question of the results before it reads it as rows of the setup (ADR-0100): with results on the
 * page, unless the message does not open as a question and the setup's patterns read something in it. */
export const modelAsksResults = (text: string, form: StudioForm, results: boolean): boolean =>
  results && (ASKING.test(text) || applyMessage(form, text).understood.length === 0);

/** Who answers a message: the first reader, in a fixed order, that claims it. The order is the page's rule, not a ranking: a fixed word
 * (a term, the working, a why) is answered before a value, a value before a failure, a question before an edit, and an edit before a guess. */
/** The ways the words a question turns on are mistyped, read as meant (ADR-0099 amendment 4): "whcih ply fails first", "wher is the max
 * shear". Only the reading uses them; the message is kept as typed. */
const TYPOS: [RegExp, string][] = [
  [/\b(?:whcih|wich|whihc|whitch|wihch|hwich)\b/gi, "which"], [/\b(?:wher|whre|wehre)\b/gi, "where"], [/\b(?:waht|wht|whta|wat)\b/gi, "what"],
  [/\b(?:fials|failes|fale)\b/gi, "fails"], [/\b(?:fial|fai|faill)\b/gi, "fail"], [/\bteh\b/gi, "the"], [/\b(?:frist|fisrt|firts)\b/gi, "first"],
];
export const spelled = (text: string): string => TYPOS.reduce((out, [typo, word]) => out.replace(typo, word), text);

export function routeMessage(typed: string, s: ChatState): ChatRoute {
  const text = spelled(typed);
  const edits = () => applyMessage(s.form, text).understood.length > 0;
  if (!s.readOnly && /^(start over|reset|new coupon|restart)\b/i.test(text)) return { route: "start-over" };
  // what an Abaqus word means, or this model's own boundary conditions and loads: fixed words, no model, with or without a result (ADR-0110)
  const term = termAsked(text);
  if (term) return { route: "term", term };
  // who the assistant is, the units, whether a material of one's own or inches are offered, which layup: fixed words, nothing changes
  // ("can I use inches?" switched the units before; ADR-0121 amendment 2)
  const topic = aboutAsked(text, s.readOnly);
  if (topic) return { route: "about", topic };
  // a request for the formula or the proof is answered with the package's own working, never read as a row or sent to a model (ADR-0103);
  // a question about a number of the answer is no new load: "how did you get 16740 N" (ADR-0121 amendment 2)
  if (asksWorking(text) && (!edits() || isQuestion(text))) return { route: "working" };
  // a question of why is answered in words from the results on the page, before anything reads it as a value or a row (ADR-0102); with
  // no result there is nothing to answer from, and a question is never a row: "why is ply 4 in compression?" changes no test
  if (asksWhy(text)) return s.api && s.results && s.facts ? { route: "why" } : { route: "why-none" };
  // the reaction, the largest displacement or the modulus of the result, as the result card prints it (ADR-0099 amendment 4)
  const quantity = s.results ? summaryAsked(text) : null;
  if (quantity) return { route: "summary", quantity };
  // a criterion named with a word of failure asks its first ply, never a table of the largest stresses: "which ply fails first by max stress"
  if (asksFailure(text) && namesCriterion(text)) return { route: "failure" };
  if (namesCriterion(text) && /\b(?:first[- ]ply[- ]failure|fpf|fails?\s+first|first\s+to\s+fail)\b/i.test(text)) return { route: "failure" };
  const question = readResultQuestion(text);
  if (question) return { route: "value", question };
  // which ply fails first, or whether it fails, is the package's own answer, never a table of the largest stresses (ADR-0099 amendment 1)
  if (asksFailure(text)) return { route: "failure" };
  if (s.results) {
    // what an element is, or where it sits, is said from the fields, never asked back as a choice of quantity (ADR-0099 amendment 3);
    // "it" is an element only when one was just spoken of
    const ofElement = asksElement(text);
    if (ofElement && (ofElement.element !== "last" || s.about !== null)) return { route: "element", element: ofElement.element };
    // a follow-up of a few words takes its ply, its place and its quantity from the question before it (ADR-0099 amendment 3)
    const next = edits() ? null : readFollowUp(text, s.thread);
    if (next) return { route: "follow-up", question: next };
  }
  // an imported model's rows are the file's (ADR-0105) and a past run is shown as it was solved (ADR-0109): nothing below reads a message into either
  if (s.readOnly) return { route: "read-only" };
  // whether the setup is ready is the setup check's answer, said as Yes or No (ADR-0121 amendment 2)
  if (asksReady(text)) return { route: "ready" };
  // "add a boundary condition" where the setup fixes them, "partition the coupon", "create a step": said once, nothing changes (ADR-0110).
  // On a plate read by a model, a boundary condition or a load is read into its lists instead (ADR-0101)
  const adding = setupAsked(text);
  if (adding && !(s.onPlate && isConditionOrLoad(adding)) && !edits()) return { route: "setup-fixed", term: adding };
  if (/^(run|solve|go|run it|run analysis)\b/i.test(text) && s.ready) return { route: "run" };
  // "run it" before the setup is ready: checked, so the engineer sees what is still to fix rather than nothing (ADR-0121 amendment 2)
  if (CHECK.test(text) || BARE_RUN.test(text)) return { route: "check" };
  if (/full form|spreadsheet|all (the )?rows|advanced/i.test(text)) return { route: "full-form" };
  if (s.laminate && toolNamed(text) === "laminate") return { route: "laminate" };
  // an answer to "Who is running it?" is a name, unless the message is an edit: one the page's patterns read ("finer mesh", "make it
  // compression"; ADR-0088 amendment 2) or, on a plate read by a model, one that names a region or an action on it (ADR-0101 amendment 1);
  // nor is a question a name
  const edit = edits() || (s.onPlate && namesPlateEdit(text));
  const asks = /\?\s*$/.test(text) || ASKING.test(text);
  if (s.step === "name" && !/\d/.test(text) && !edit && !asks) return { route: "name" };
  // another unit system named: the chat's own switch handles it (ADR-0061), since a proposal is read in the coupon's system
  const named = unitsNamed(text);
  if (s.modelReads && s.api && !isSwitchRequest(text) && (named === null || named === unitsOf(s.form))) return { route: "model" };
  // a question nothing above read is said so, with what can be asked: never read into rows (ADR-0100, ADR-0121 amendment 2)
  if (asksUnread(text, s.results)) return { route: "unread" };
  return { route: "patterns" };
}
