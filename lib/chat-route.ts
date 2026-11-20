import { asksFailure } from "./result-failure";
import { asksElement, readFollowUp, readResultQuestion, type ResultQuestion } from "./result-question";
import { asksWhy } from "./result-why";
import { asksWorking } from "./result-working";
import { isConditionOrLoad, setupAsked, termAsked, type FeaTerm, type TermQuestion } from "./fea-terms";
import { readIntent } from "./work-intent";
import { applyMessage, isSwitchRequest, unitsNamed, type ChatStep } from "./studio-chat";
import { unitsOf, type StudioForm } from "./studio-form";
import { namesPlateEdit } from "./studio-plate";

/** Who answers a message in the coupon chat (ADR-0121): the page's own readers in a fixed order, then a model where one reads, then the
 * setup's patterns. `components/studio/coupon-chat.tsx` sends every message through `routeMessage` and answers by the route it returns, so
 * the question banks in `tests/assistant-questions/` try the very choice the page makes. Nothing here answers: it only names who does. */

/** A message that opens as a question: with results on the page it asks about them, and the setup's patterns do not read it, so "why is
 * ply 4 in compression?" never changes the test to compression (ADR-0100). */
export const ASKING = /^\s*(?:why|what|where|which|compare)\b/i;

/** Every route a message can take, in the order `routeMessage` tries them. A new route is a new way of answering, and the question banks
 * must ask at least one question that takes it (`tests/assistant-questions.test.ts`). */
export const ROUTES = ["start-over", "term", "working", "why", "why-none", "value", "failure", "element", "follow-up", "read-only", "setup-fixed",
  "run", "check", "full-form", "section", "name", "model", "unread", "patterns"] as const;
export type RouteName = (typeof ROUTES)[number];
/** What the coupon chat opens when asked for by name (ADR-0124): another section, or the wing's page under FEA (ADR-0118 amendment 1). */
export type SectionAsked = "laminate" | "cad" | "wing";

export type ChatRoute =
  | { route: "start-over" } // "start over": a blank coupon
  | { route: "term"; term: TermQuestion } // what an Abaqus word means, or this model's boundary conditions and loads (ADR-0110)
  | { route: "working" } // the formula or the proof behind the answer (ADR-0103)
  | { route: "why" } // a question of why, answered in words from the results and the theory pages (ADR-0102)
  | { route: "why-none" } // a question of why with no result (or no API) to answer from
  | { route: "value"; question: ResultQuestion } // a value of the results, read by the page's patterns (ADR-0099)
  | { route: "failure" } // which ply fails first, whether it fails, at what load (ADR-0099 amendment 1)
  | { route: "element"; element: number | "picked" | "last" | null } // what an element is, or where (ADR-0099 amendment 3)
  | { route: "follow-up"; question: ResultQuestion } // "now in ply 5": the question before it, with one thing changed (ADR-0099 amendment 3)
  | { route: "read-only" } // an imported model or a past run is on the page: nothing is changed by talking (ADR-0105, ADR-0109)
  | { route: "setup-fixed"; term: FeaTerm } // "add a boundary condition" where the test fixes them (ADR-0110)
  | { route: "run" }
  | { route: "check" }
  | { route: "full-form" }
  | { route: "section"; target: SectionAsked } // another section (Laminate, CAD) or another kind of FEA work (a wing) asked for (ADR-0124)
  | { route: "name" } // the answer to "Who is running it?"
  | { route: "model" } // a model reads it: a question of the results first, else rows of the setup (ADR-0088, ADR-0100, ADR-0101)
  | { route: "unread" } // a question of the results nothing could read: what can be asked
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
  /** Another section (Laminate, CAD) can be opened from here (ADR-0124). */
  sections: boolean;
};

/** Whether a model reads a message as a question of the results before it reads it as rows of the setup (ADR-0100): with results on the
 * page, unless the message does not open as a question and the setup's patterns read something in it. */
export const modelAsksResults = (text: string, form: StudioForm, results: boolean): boolean =>
  results && (ASKING.test(text) || applyMessage(form, text).understood.length === 0);

/** Who answers a message: the first reader, in a fixed order, that claims it. The order is the page's rule, not a ranking: a fixed word
 * (a term, the working, a why) is answered before a value, a value before a failure, a question before an edit, and an edit before a guess. */
export function routeMessage(text: string, s: ChatState): ChatRoute {
  const edits = () => applyMessage(s.form, text).understood.length > 0;
  if (!s.readOnly && /^(start over|reset|new coupon|restart)\b/i.test(text)) return { route: "start-over" };
  // what an Abaqus word means, or this model's own boundary conditions and loads: fixed words, no model, with or without a result (ADR-0110)
  const term = termAsked(text);
  if (term) return { route: "term", term };
  // a request for the formula or the proof is answered with the package's own working, never read as a row or sent to a model (ADR-0103)
  if (asksWorking(text) && !edits()) return { route: "working" };
  // a question of why is answered in words from the results on the page, before anything reads it as a value or a row (ADR-0102); with
  // no result there is nothing to answer from, and a question is never a row: "why is ply 4 in compression?" changes no test
  if (asksWhy(text)) return s.api && s.results && s.facts ? { route: "why" } : { route: "why-none" };
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
  // "add a boundary condition" where the setup fixes them, "partition the coupon", "create a step": said once, nothing changes (ADR-0110).
  // On a plate read by a model, a boundary condition or a load is read into its lists instead (ADR-0101)
  const adding = setupAsked(text);
  if (adding && !(s.onPlate && isConditionOrLoad(adding)) && !edits()) return { route: "setup-fixed", term: adding };
  if (/^(run|solve|go|run it|run analysis)\b/i.test(text) && s.ready) return { route: "run" };
  if (/^(check|check setup)\b/i.test(text)) return { route: "check" };
  if (/full form|spreadsheet|all (the )?rows|advanced/i.test(text)) return { route: "full-form" };
  // another section, or a wing, asked for by the words every chat reads (ADR-0124): "open the laminate calculator", "CAD please",
  // "I want to start a wing analysis", where one can be opened; a wing opens its own page under FEA (ADR-0118 amendment 1)
  const wanted = readIntent(text);
  if (wanted?.start && s.sections && (wanted.target === "wing" || wanted.target === "laminate" || wanted.target === "cad")) {
    return { route: "section", target: wanted.target };
  }
  // an answer to "Who is running it?" is a name, unless the message is an edit: one the page's patterns read ("finer mesh", "make it
  // compression"; ADR-0088 amendment 2) or, on a plate read by a model, one that names a region or an action on it (ADR-0101 amendment 1);
  // nor is a question a name
  const edit = edits() || (s.onPlate && namesPlateEdit(text));
  const asks = /\?\s*$/.test(text) || ASKING.test(text);
  if (s.step === "name" && !/\d/.test(text) && !edit && !asks) return { route: "name" };
  // another unit system named: the chat's own switch handles it (ADR-0061), since a proposal is read in the coupon's system
  const named = unitsNamed(text);
  if (s.modelReads && s.api && !isSwitchRequest(text) && (named === null || named === unitsOf(s.form))) return { route: "model" };
  if (s.results && ASKING.test(text)) return { route: "unread" };
  return { route: "patterns" };
}
