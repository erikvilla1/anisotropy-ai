/** The question banks of the assistant (ADR-0121): how a bank is read, what is on the page when a question is asked, and what the page
 * answers, in the words and numbers the chat shows. The banks are the JSON files beside this one; `tests/assistant-questions.test.ts`
 * holds the page to them, `api/tests/test_assistant_questions.py` the theory search, and `mcp-server/tests/test_questions.py` the MCP
 * server's tools. Nothing here computes a result: every number is read from the stored results the browser tests use. */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Fields, GeneralAnswer, ProposalAnswer, ResultAnswer, ResultReading } from "../../lib/studio-api";
import { ASKING, asksUnread, modelAsksResults, routeMessage, ROUTES, type ChatRoute, type ChatState, type RouteName } from "../../lib/chat-route";
import { aboutAnswer, checkTitle, unreadWords } from "../../lib/chat-about";
import { modelFileAnswer } from "../../lib/model-file";
import { MODEL_FILE_LABELS } from "../../lib/studio-api";
import { answerResultQuestion, comparisonNote, describeElement, extremeLines, RESULT_COLUMNS, questionFrom, resultOffer, resultUnit, thresholdVerdict, valueLines, type ResultQuestion } from "../../lib/result-question";
import { confirmsFailure, contradictsFailure, decidesNote, failureAnswer, failureLines, failureVerdict, marginNote } from "../../lib/result-failure";
import { summaryAnswer } from "../../lib/result-summary";
import { isConditionOrLoad, termLines } from "../../lib/fea-terms";
import { workingFor } from "../../lib/result-working";
import { applyMessage, unitsNamed } from "../../lib/studio-chat";
import { blankForm, exampleForm, PLATE_TEST, type StudioForm } from "../../lib/studio-form";
import { printed } from "../../lib/studio-colors";
import { couponOffer, plateLines, plateOffer, unreadLines } from "../../lib/proposals";
import { factsOf, generalLines, headed, readAt, whyLines } from "../../lib/result-why";
import { emptyPlate, plateValues } from "../../lib/studio-plate";
import { ownWords, plateFromCoupon, readPlateEdit } from "../../lib/plate-edits";
import { bannedIn, customerText } from "../../lib/studio-copy";
import { routeStart, START_ROUTES, TARGET_TITLES, type StartRoute } from "../../lib/work-intent";
import { privateAnswerOnStart } from "../../lib/chat-private";
import { ASKED_KINDS } from "../../lib/workspaces";
import { hasWork, newProject } from "../../lib/project-store";
import { readWingAsk, wingAnswer, WING_ROUTES, type WingAsk } from "../../lib/wing-chat";
import { readRepairAsk, repairAnswer, REPAIR_ROUTES, type RepairAsk, type RepairHeld } from "../../lib/repair-chat";
import type { WingDescription, WingReport } from "../../lib/wing";

export const FOLDER = "tests/assistant-questions";

/** The kind of question, which sets the shape of a good answer (the `chat-answer-quality` skill, criterion 1). */
export const KINDS = ["value", "which", "yes-no", "what-is", "why", "change", "command", "off-topic"] as const;
/** How it is typed: as written in a manual, with typos, a fragment that leans on the message before, loose words a model must read, another
 * program's words, units, or a bare word or two. */
export const STYLES = ["plain", "typo", "fragment", "loose", "jargon", "units", "terse"] as const;
/** What is on the page when it is asked. */
export const PAGES = ["blank", "setup", "ready", "results", "imported", "past", "plate", "start", "wing", "wing-caps", "repair", "repair-solved", "repair-external", "repair-bond"] as const;
/** Every way a message is answered: the coupon chat's routes (`lib/chat-route.ts`), then those of the FEA assistant of a blank project
 * (page "start", `routeStart` in `lib/work-intent.ts`, ADR-0124), then the wing's chat (pages "wing" and "wing-caps", `readWingAsk` in
 * `lib/wing-chat.ts`, ADR-0128), then the repair's chat (pages "repair", "repair-solved" with its slice solved, "repair-external" and
 * "repair-bond" with its bond followed until it lets go, ADR-0140; `readRepairAsk` in `lib/repair-chat.ts`, ADR-0136). */
export const ALL_ROUTES = [...ROUTES, ...START_ROUTES, ...WING_ROUTES, ...REPAIR_ROUTES] as const;
export type AnyRoute = (typeof ALL_ROUTES)[number];

export type Kind = (typeof KINDS)[number];
export type Style = (typeof STYLES)[number];
export type Page = (typeof PAGES)[number];

/** What a good answer holds, checked on the page's own answer (with no model reading). */
export type Expected = {
  /** The answer's kind: values, extremes, ask, refused, failure, element, term, working, rows, redirect, said. */
  kind?: string;
  /** The heading, exactly. */
  heading?: string;
  /** How the heading opens: "Yes" or "No" for a yes-or-no question (criterion 1). */
  opens?: string;
  /** Words the answer says somewhere (heading or lines), each as written. */
  says?: string[];
  /** Words it never says. */
  never?: string[];
  /** Rows of the setup the message changes, by key, as the form holds them. */
  rows?: Record<string, string>;
  /** The term of the glossary it answers with (ADR-0110). */
  term?: string;
  /** The criterion of a failure answer or of the working. */
  criterion?: string;
  /** The step of the working shown, by its id ("stress", "strain", "criterion", "loading"), or "all" for the whole working. */
  step?: string;
  /** The plies and the quantities a value answer reads. */
  plies?: number[];
  columns?: string[];
  /** The element a value or element answer names, by its number. */
  element?: string;
  /** A failure answer that confirms the engineer's own statement of it ("Yes"). */
  confirmed?: boolean;
  /** The change of plies a wing's message is read into (ADR-0128), or the change a repair's message is (ADR-0136), as the engine's
   * form takes it. */
  change?: Record<string, unknown>;
  /** The sweep a repair's message is read into (ADR-0136), as the engine's form takes it. */
  sweep?: Record<string, unknown>;
  /** A plate's supports and loads after the message, as the API takes them (ADR-0101 amendment 4): each list given is the whole list. */
  plate?: { supports?: unknown[]; loads?: unknown[] };
};

/** What a real model should read the question as (the real-model run, `scripts/assistant-live.py`). */
export type Live = {
  /** A question of the results, read into the typed request (ADR-0100). */
  request?: { kind: "values" | "extreme" | "failure" | "none"; quantities?: string[]; plies?: number[]; element?: number | null; sense?: string | null };
  /** Rows of the setup the model proposes, by key, value as written (ADR-0088). */
  proposals?: Record<string, string>;
  /** A plate's supports or loads it proposes, by region (ADR-0101). */
  plate?: { supports?: string[]; loads?: string[] };
  /** Whether the theory pages hold the reason (ADR-0102). */
  covered?: boolean;
  /** The kind of FEA work a model's answer on the start page offers to set up, or "none" (ADR-0124). */
  start?: "coupon" | "none";
  /** Anything else the judge should hold the answer to, in words. */
  judge?: string;
};

export type Question = {
  ask: string;
  kind: Kind;
  style: Style;
  page: Page;
  /** Earlier messages of the same talk, sent first. */
  after?: string[];
  /** The element clicked on the model, by its number. */
  picked?: number;
  /** The step the chat's open question asks ("name" for "Who is running it?"). */
  asking?: string;
  /** The Ansys file is offered to whoever asks, as to a founder's sign-in (ADR-0129); a customer's view without it. */
  ansys?: boolean;
  /** Who answers with a model reading messages, as on the hosted site. */
  route: AnyRoute;
  /** Who answers with no model, when that is pinned; otherwise the same route, or for a model's route the setup's patterns or "unread". */
  offline?: AnyRoute;
  answer?: Expected;
  /** The theory sections a question of why finds, best first (ADR-0102). */
  sections?: string[];
  /** The MCP server's tool a client should call for it, the arguments, and words its answer holds (ADR-0107). */
  mcp?: { tool: string; args: Record<string, unknown>; says?: string[]; refused?: boolean;
    /** For a refused question, the words a client's own answer holds when it told the refusal from what it already held, in the
     * real-model run; `says` (the tool's words) when absent. */
    said?: string[];
    /** What the client's conversation holds before the question, in the real-model run: the coupon stated ("setup"), or stated and solved
     * ("solved", the default for a tool that reads a result), the wing named ("wing": Anisotropy's example wing, ADR-0128) or the
     * repair named ("repair": Anisotropy's example of a flush stepped repair, ADR-0136). */
    context?: "setup" | "solved" | "wing" | "repair" };
  live?: Live;
  /** A known gap: the answer does not yet hold what is expected, by the skill's criterion. The bank fails when the gap closes, so the
   * mark comes off with the fix. A gap that opens "search:" is the theory search's (the API's test), "mcp:" the MCP server's; any other
   * is the page's. */
  gap?: string;
  /** Where the question comes from, when a person asked it. */
  source?: string;
};

export type Bank = {
  feature: string;
  title: string;
  records: string[];
  /** Files whose change means this bank must change too (`scripts/assistant-questions-check.mjs`). */
  watches: string[];
  /** A bank written before its feature: none of it runs until this is removed. */
  waiting?: string;
  questions: Question[];
};

/** Whether a question's gap is the page's, rather than the theory search's or the MCP server's. */
export const pageGap = (question: Question): boolean => !!question.gap && !/^(?:search|mcp):/.test(question.gap);

export function banks(folder = FOLDER): Bank[] {
  return readdirSync(folder).filter((name) => name.endsWith(".json")).sort()
    .map((name) => ({ ...(JSON.parse(readFileSync(join(folder, name), "utf8")) as Bank), file: name }));
}

const studio = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}`, "utf8"));
const imported = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio-import/${name}`, "utf8"));
/** The wing's page: the engine's answer to the example wing, and to the example with spar caps and a cap zone (ADR-0125). */
const WING_ANSWERS: Record<string, { report: WingReport; wing: WingDescription }> = {
  wing: JSON.parse(readFileSync("tests/fixtures/wing/example-answer.json", "utf8")),
  "wing-caps": JSON.parse(readFileSync("tests/fixtures/wing/caps-answer.json", "utf8")),
};
/** The repair's page (ADR-0136): the engine's answer to the flush example, the same with its slice solved, the example of a patch
 * bonded on top, and the flush example with its bond followed until it lets go (ADR-0140), as the page holds them when a message
 * is answered. */
const repairFile = (name: string) => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf8"));
const repairHeld = (answer: string, solve?: string, bond?: string): RepairHeld => {
  const found = repairFile(answer);
  return { repair: found.repair, report: found.report, slice: solve ? repairFile(solve).report : null, sliceStale: false, needs: found.needs,
    bond: bond ? repairFile(bond).report : null, bondStale: false, bondNeeds: found.bond_needs ?? null };
};
const REPAIR_HELD: Record<string, RepairHeld> = {
  repair: repairHeld("example-answer"), "repair-solved": repairHeld("example-answer", "example-solve"), "repair-external": repairHeld("external-answer"),
  "repair-bond": repairHeld("example-answer", "example-solve", "example-bond"),
};
const RESULTS = { fields: studio("fields.json") as Fields, facts: !!studio("explanation.json").facts, explanation: studio("explanation.json") };
const IMPORTED = { fields: imported("fields.json") as Fields, facts: !!imported("explanation.json").facts, explanation: imported("explanation.json") };

/** The page a question is asked on: the setup, the results shown and the chat's state, with or without a model reading. */
export type Scene = { form: StudioForm; fields: Fields | null; facts: Record<string, unknown> | null; state: ChatState; past: boolean; imported: boolean;
  picked: number | null; ansys: boolean };

export function scene(question: Question, modelReads: boolean): Scene {
  const example = exampleForm("2026-11-19");
  const results = question.page === "results" || question.page === "past" ? RESULTS : question.page === "imported" ? IMPORTED : null;
  const form = question.page === "blank" ? blankForm() : question.page === "plate" ? { ...example, test: PLATE_TEST, hole_diameter: "6" } : example; // a plate with a hole, so the hole can be held
  const fields = results?.fields ?? null;
  const picked = question.picked !== undefined && fields ? fields.mesh.element_labels.findIndex((l) => l.split(".").pop() === String(question.picked)) : -1;
  return {
    form, fields, facts: factsOf(results?.explanation) ?? null, past: question.page === "past", imported: question.page === "imported", picked: picked >= 0 ? picked : null,
    ansys: question.ansys === true,
    state: {
      form, readOnly: question.page === "imported" || question.page === "past", results: !!fields, facts: !!results?.facts, api: true, modelReads,
      onPlate: question.page === "plate" && modelReads, ready: question.page !== "blank" && question.page !== "setup", step: (question.asking as ChatState["step"]) ?? null,
      about: null, thread: null, sections: true, plates: true, plate: emptyPlate(), here: [],
    },
  };
}

/** What the chat says: the heading and the lines under it, as the page prints them, and what it read. */
export type Said = { kind: string; heading: string; lines: string[]; data: Record<string, unknown> };

const said = (kind: string, heading: string, lines: string[] = [], data: Record<string, unknown> = {}): Said => ({ kind, heading, lines, data });

function valueAnswer(s: Scene, question: ResultQuestion, text: string): Said {
  const answer = valueOnly(s, question);
  if (!s.fields || (answer.kind !== "values" && answer.kind !== "extremes")) return answer;
  // "is ply 2 above 1000 MPa?" opens with Yes or No (ADR-0099 amendment 4), as coupon-chat.tsx's answerQuestion says it
  const found = answerResultQuestion(s.fields, question, s.picked);
  const column = found.kind === "extremes" ? found.blocks[0]?.column : found.kind === "values" ? found.columns[0] : undefined;
  const verdict = column ? thresholdVerdict(text, found, resultUnit(s.fields, column), printed) : null;
  return verdict ? { ...answer, heading: verdict, lines: [answer.heading, ...answer.lines] } : answer;
}

function valueOnly(s: Scene, question: ResultQuestion): Said {
  if (!s.fields) return said("none", "No results to read yet", ["Stresses and strains come from a solved model."]);
  const answer = answerResultQuestion(s.fields, question, s.picked);
  if (answer.kind === "ask") return said("ask", "Which element?", [answer.text]);
  if (answer.kind === "refused") return said("refused", "Not in this model", [answer.text]);
  if (answer.kind === "values") {
    const lines = valueLines(answer, resultUnit(s.fields, answer.columns[0]), printed);
    const data = { plies: [...new Set(answer.rows.map((r) => r.ply))], columns: answer.columns, element: answer.label, place: answer.place };
    const caution = comparisonNote(answer.columns); // Mises, Tresca and the principal stresses are no failure measure (criterion 7)
    if (lines) return said("values", lines.headline, [lines.facts.join(" · "), ...(caution ? [caution] : [])], data);
    const symbols = answer.columns.map((c) => RESULT_COLUMNS[c].symbol);
    const rows = answer.rows.map((r) => `ply ${r.ply} (${r.angle}°): ${r.values.map((v, i) => `${symbols[i]} ${printed(v)}`).join(", ")}`);
    return said("values", `${symbols.join(", ")} at element ${answer.label}`, [...rows, ...(caution ? [caution] : [])], data);
  }
  const blocks = answer.blocks.map((block) => extremeLines(block, answer.region, resultUnit(s.fields!, block.column), printed));
  const data = { columns: answer.blocks.map((b) => b.column), region: answer.region, plies: answer.blocks.map((b) => b.rows[b.best].ply), atGrip: answer.atGrip };
  return blocks.length === 1 ? said("extremes", blocks[0].headline, [blocks[0].facts.join(" · ")], data)
    : said("extremes", `Largest in ${answer.region}`, blocks.map((b) => `${b.headline} · ${b.facts.join(" · ")}`), data);
}

/** The page's own answer to a message on a scene, and the route it took: no model writes any of it. */
export function pageAnswer(text: string, s: Scene, routed: ChatRoute): Said {
  switch (routed.route) {
    case "start-over": return said("said", "A new coupon");
    case "model-file": { // as answerModelFile in coupon-chat.tsx: fixed words, and one button per file offered
      const answer = modelFileAnswer(routed.program, { ansys: s.ansys, readOnly: s.state.readOnly });
      return said("model-file", answer.title, [...answer.lines, ...answer.offers.map((program) => MODEL_FILE_LABELS[program])], { offers: answer.offers, program: routed.program });
    }
    case "term": {
      if (routed.term.ofModel) return said("term", routed.term.term.id === "load" ? "Loads" : "Boundary conditions", [], { term: routed.term.term.id });
      const lines = termLines(routed.term);
      return said("term", lines.title, [lines.means, lines.here], { term: routed.term.term.id });
    }
    case "about": {
      const answer = aboutAnswer(routed.topic, text, { form: s.form, results: !!s.fields, readOnly: s.state.readOnly });
      return said("about", answer.title, answer.lines, { topic: routed.topic });
    }
    case "working": {
      const found = workingFor(s.fields, text);
      if (!s.fields || !found) return said("none", "No working to show yet");
      if (found.kind === "not-worked") return said("refused", "No working for that criterion yet", [`The working of ${found.name} is not written yet. Ask for ${found.others.join(" or ")}.`]);
      // as workingMessage in coupon-chat.tsx: one step asked by its quantity is headed by its title (ADR-0103 amendment 1)
      return said("working", found.step ? found.step.title : `Working: ${found.name}`, [`on ${found.basis}`], { criterion: found.criterion, step: found.step?.id ?? "all" });
    }
    case "why": return said("why", "Answered in words from the results", [], {});
    case "why-none": return said("none", "No results to answer from yet");
    case "summary": {
      const answer = summaryAnswer(s.fields!, routed.quantity, printed);
      return said(answer.found ? "summary" : "refused", answer.title, answer.lines, { quantity: routed.quantity });
    }
    case "value": case "follow-up": return valueAnswer(s, routed.question, text);
    case "failure": {
      const found = s.fields ? failureAnswer(s.fields, text) : null;
      if (!found) return said("none", "No answer to read yet");
      const lines = failureLines(found, printed);
      const confirmed = confirmsFailure(text, found, printed) && lines.confirmed !== null;
      const data = { criterion: found.row.criterion, confirmed, element: found.row.label.split(".").pop(), plies: [found.row.ply] };
      const margin = marginNote(text, found, printed);
      const decides = decidesNote(text);
      const facts = [lines.facts.join(" · "), ...(margin ? [margin] : []), ...(decides ? [decides] : [])];
      if (confirmed) return said("failure", "Yes", [lines.confirmed!, ...facts], data);
      // as failureMessage in coupon-chat.tsx: a loading stated back wrongly is answered No, "does it fail?" opens with Yes or No
      if (lines.confirmed !== null && contradictsFailure(text, found, printed)) return said("failure", "No", [lines.confirmed, ...facts], data);
      const verdict = failureVerdict(text, found);
      if (verdict) return said("failure", verdict, [`${lines.headline}, ${lines.loading.charAt(0).toLowerCase()}${lines.loading.slice(1)}`, ...(lines.applied ? [lines.applied] : []), ...facts], data);
      return said("failure", lines.headline, [lines.loading, ...(lines.applied ? [lines.applied] : []), ...facts], data);
    }
    case "element": {
      const answer = describeElement(s.fields!, routed.element === "last" ? s.state.about : routed.element, s.picked);
      if (answer.kind === "refused") return said("refused", "Not in this model", [answer.text]);
      const number = answer.label?.split(".").pop() ?? null;
      return said("element", number ? `Element ${number}` : "An element", [`One of the ${answer.count} small four-sided pieces the model is divided into.`],
        { element: number, where: answer.where });
    }
    case "read-only": return s.past ? said("said", "A past run is shown as it was solved") : said("said", "An imported model is read as it stands");
    // the setup check answers; on the page set up and checked it is ready, and a setup not yet checked is checked first
    case "ready": return s.state.ready ? said("check", checkTitle(true, 0, true), [], { ready: true }) : said("said", "Checking the setup");
    case "plate-edit": { // as editPlateBy in coupon-chat.tsx: a tension coupon is carried over first, the test's grips kept
      const over = s.form.test === PLATE_TEST ? null : plateFromCoupon(s.form, null);
      const edit = readPlateEdit(text, over?.form ?? s.form, over?.lists ?? emptyPlate(), []);
      if (!edit || !edit.done.length) return said("said", "Not applied", edit?.notes ?? []);
      const kept = over ? [ownWords(over.carried)] : [];
      return said("rows", "Got it", [...edit.done, ...edit.notes, ...kept], { plate: plateValues(edit.lists), carried: !!over });
    }
    case "setup-fixed": {
      const term = routed.term;
      const heading = isConditionOrLoad(term) ? (s.form.test === PLATE_TEST ? "Add it on the model tree" : "Set by the test")
        : term.id === "partition" ? "Already partitioned" : term.id === "step" ? "One static step" : "Not offered yet";
      return said("said", heading, [term.here], { term: term.id });
    }
    case "run": return said("said", "Running the analysis");
    case "check": return said("said", "Checking the setup");
    case "full-form": return said("said", "All inputs");
    // a coupon that holds the engineer's work asks first, with one tap to go (switch-ask.tsx); a blank one opens the section at once. A
    // wing opens its own page under FEA, and no message goes with it (ADR-0118 amendment 1)
    case "section": return hasWork(newProject(s.form))
      ? said("ask", `Open ${routed.target === "wing" ? "FEA for a wing analysis" : TARGET_TITLES[routed.target]}?`,
        [`Your coupon is saved under Projects, as it is now.${routed.target === "wing" ? "" : " Your message goes with you."}`])
      : said("said", `Opens ${TARGET_TITLES[routed.target]}`);
    case "name": return said("rows", "Got it", [`Run by ${text}`], { rows: { filled_by: text } });
    case "general": return said("general", "Answered in words from our theory pages", []); // the API's reader writes it (ADR-0121 amendment 5)
    case "model": return said("model", "Read by the model", [], { asksResults: modelAsksResults(text, s.form, !!s.fields) });
    case "unread": { const words = unreadWords(!!s.fields); return said("redirect", words.title, [words.text]); }
    case "patterns": {
      const read = applyMessage(s.form, text);
      if (read.understood.length) return said("rows", "Got it", read.understood, { rows: read.rows });
      if (read.note) return said("redirect", unitsNamed(text) ? "Another unit system" : "Nothing to change yet", [read.note]);
      return said("redirect", "Not sure what to change", ["Try “[0/90]2s”, “AS4/8552” or “10 kN”."]);
    }
  }
}

/** The FEA assistant's own answer on a blank project (`components/workspace/fea-start.tsx`), before any model: a question in words is
 * answered by the API's reader (`modelAnswer`), so here it only names who answers. */
export function startAnswer(routed: StartRoute): Said {
  switch (routed.route) {
    case "private": { const { title, lines } = privateAnswerOnStart(routed.topic); return said("about", title, lines); }
    case "set-up": return routed.kind === "wing" ? said("said", "Opens Wing analysis", ["The wing's own page under FEA, a new wing from the example."], { kind: "wing" })
      : routed.kind === "repair" ? said("said", "Opens Patch repair", ["The repair's own page under FEA, with the repair this browser holds or the example."], { kind: "repair" })
      : said("said", "Coupon test set up", ["The model tree on the left now holds a coupon's tabs."], { kind: routed.kind });
    case "not-here": return said("said", "You are in FEA", ["Say what to analyse, or ask a question about it."]);
    case "open": return said("said", `Opens ${TARGET_TITLES[routed.target]}`);
    case "general": return said("general", "Answered in words from our theory pages", [], { named: routed.named });
  }
}

/** A talk: the earlier messages, then the question, each routed and answered on the same scene; the chat's own memory of the last
 * question and the element last spoken of is kept as the component keeps it (`thread` and `about` in coupon-chat.tsx). */
export function talk(question: Question, modelReads: boolean): { route: AnyRoute; said: Said; routed: ChatRoute | StartRoute | WingAsk | RepairAsk } {
  const s = scene(question, modelReads);
  let last: { route: AnyRoute; said: Said; routed: ChatRoute | StartRoute | WingAsk | RepairAsk } | null = null;
  let asked: RepairAsk | undefined; // what the repair's chat read the message before as: a fragment leans on it (repair-chat.tsx)
  for (const text of [...(question.after ?? []), question.ask]) {
    if (question.page in REPAIR_HELD) { // the repair's chat reads by its own patterns; no model reads there (ADR-0136)
      const held = REPAIR_HELD[question.page];
      const routed: RepairAsk = readRepairAsk(text, held.report?.kind ?? "flush", asked);
      asked = routed;
      last = { route: routed.route, said: repairAnswer(routed, held), routed };
      continue;
    }
    if (question.page === "wing" || question.page === "wing-caps") { // the wing's chat reads by its own patterns; no model reads there yet (ADR-0128)
      const routed = readWingAsk(text);
      const shown = WING_ANSWERS[question.page];
      last = { route: routed.route, said: wingAnswer(routed, shown.report, shown.wing), routed };
      continue;
    }
    if (question.page === "start") { // the FEA assistant of a blank project, which reads no setup (ADR-0124)
      const routed = routeStart(text);
      last = { route: routed.route, said: startAnswer(routed), routed };
      continue;
    }
    const routed = routeMessage(text, s.state);
    const answer = pageAnswer(text, s, routed);
    if ((routed.route === "value" || routed.route === "follow-up") && (answer.kind === "values" || answer.kind === "extremes")) {
      s.state = { ...s.state, thread: routed.question, about: null };
    }
    if (routed.route === "element" && typeof answer.data.element === "string") s.state = { ...s.state, about: Number(answer.data.element) };
    last = { route: routed.route, said: answer, routed };
  }
  return last!;
}

/** What is wrong with an answer, by the expectations and the rules every answer keeps: none when it holds. */
export function faults(question: Question, answer: Said): string[] {
  return [...expected(question.answer ?? {}, answer), ...rules(question, answer)];
}

/** What the answer misses of what its bank expects of the page's own answer. */
function expected(e: Expected, answer: Said): string[] {
  const out: string[] = [];
  const text = [answer.heading, ...answer.lines].join("\n");
  const data = answer.data;
  if (e.kind !== undefined && answer.kind !== e.kind) out.push(`kind ${answer.kind}, expected ${e.kind}`);
  if (e.heading !== undefined && answer.heading !== e.heading) out.push(`heading “${answer.heading}”, expected “${e.heading}”`);
  if (e.opens !== undefined && !new RegExp(`^${e.opens}\\b`).test(answer.heading)) out.push(`heading “${answer.heading}” does not open with “${e.opens}”`);
  for (const words of e.says ?? []) if (!text.includes(words)) out.push(`does not say “${words}”`);
  for (const words of e.never ?? []) if (text.toLowerCase().includes(words.toLowerCase())) out.push(`says “${words}”`);
  if (e.term !== undefined && data.term !== e.term) out.push(`term ${String(data.term)}, expected ${e.term}`);
  if (e.criterion !== undefined && data.criterion !== e.criterion) out.push(`criterion ${String(data.criterion)}, expected ${e.criterion}`);
  if (e.step !== undefined && data.step !== e.step) out.push(`step ${String(data.step)}, expected ${e.step}`);
  if (e.element !== undefined && data.element !== e.element) out.push(`element ${String(data.element)}, expected ${e.element}`);
  if (e.confirmed !== undefined && data.confirmed !== e.confirmed) out.push(`confirmed ${String(data.confirmed)}, expected ${e.confirmed}`);
  if (e.plies !== undefined && JSON.stringify(data.plies) !== JSON.stringify(e.plies)) out.push(`plies ${JSON.stringify(data.plies)}, expected ${JSON.stringify(e.plies)}`);
  if (e.columns !== undefined && JSON.stringify(data.columns) !== JSON.stringify(e.columns)) out.push(`quantities ${JSON.stringify(data.columns)}, expected ${JSON.stringify(e.columns)}`);
  if (e.change !== undefined && JSON.stringify(data.change) !== JSON.stringify(e.change)) out.push(`change ${JSON.stringify(data.change)}, expected ${JSON.stringify(e.change)}`);
  if (e.sweep !== undefined && JSON.stringify(data.sweep) !== JSON.stringify(e.sweep)) out.push(`sweep ${JSON.stringify(data.sweep)}, expected ${JSON.stringify(e.sweep)}`);
  for (const list of ["supports", "loads"] as const) {
    const want = e.plate?.[list], got = (data.plate as Record<string, unknown[]> | undefined)?.[list];
    if (want !== undefined && JSON.stringify(got) !== JSON.stringify(want)) out.push(`${list} ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
  }
  if (e.rows !== undefined) {
    const rows = (data.rows ?? {}) as Record<string, string>;
    for (const [key, value] of Object.entries(e.rows)) if (rows[key] !== value) out.push(`row ${key} = ${rows[key] ?? "unset"}, expected ${value}`);
  }
  return out;
}

/** The rules every answer keeps, whatever was asked and whoever read it. */
function rules(question: Question, answer: Said): string[] {
  const out: string[] = [];
  const text = [answer.heading, ...answer.lines].join("\n");
  // a question is never a row of the setup: "what is ASTM D3039?" or "how did you get 16740 N?" changes nothing (criterion 1, ADR-0100)
  const changes = answer.kind === "rows" || answer.kind === "preview" || (answer.kind === "proposal" && Object.keys((answer.data.proposals ?? {}) as object).length > 0);
  if (changes && question.kind !== "change" && question.kind !== "command") out.push(`a question changed the setup: ${answer.lines.join(", ")}`);
  // every answer, whatever was asked (criterion 8 and ADR-0091): short, and in the product's own words
  const banned = bannedIn(text);
  if (banned.length) out.push(`names ${banned.join(", ")}`);
  if (answer.heading.length > 60) out.push(`heading of ${answer.heading.length} characters (60 at most)`);
  return out;
}

/** A request the page sends a model's reader in the API, as the page builds it (coupon-chat.tsx): the reading of a question of the results,
 * the setup's proposals, or the answer in words to a question of why. */
export type ModelRequest = { reader: "result-questions" | "proposals" | "result-answers" | "questions"; body: Record<string, unknown> };

/** What the page sends a model for a question, with a model reading as on the hosted site, in the order it sends them: a question of the
 * results is read first, and the setup's proposals are asked only when that reading kept nothing (`readWithModel`). None when the page
 * answers the question itself. The real-model run (`scripts/assistant-live.py`) sends these to the API's own readers. */
export function modelRequests(question: Question): ModelRequest[] {
  const s = scene(question, true);
  const { route } = talk(question, true);
  // the FEA assistant of a blank project sends a question to the theory pages' reader, with the kinds of work it can set up (ADR-0124);
  // the coupon chat sends one of meaning with no kind, since its work is set up (ADR-0121 amendment 5)
  if (route === "general") return [{ reader: "questions", body: { question: question.ask, kinds: question.page === "start" ? [...ASKED_KINDS] : [] } }];
  if (route === "why") return s.facts ? [{ reader: "result-answers", body: { question: question.ask, facts: s.facts } }] : [];
  if (route !== "model") return [];
  const out: ModelRequest[] = [];
  if (s.fields && modelAsksResults(question.ask, s.form, true)) out.push({ reader: "result-questions", body: resultOffer(s.fields, question.ask, s.picked) });
  const plate = question.page === "plate" ? { plate: plateOffer(s.form, emptyPlate(), []) } : {};
  out.push({ reader: "proposals", body: { product: "coupon", message: question.ask, conditions: [], ...couponOffer(s.form, question.page === "plate"), ...plate } });
  return out;
}

/** A reader's answer in the real-model run: the API's response to one request, or none when the call failed. */
export type Reading = { reader: ModelRequest["reader"]; response: Record<string, unknown> | null; error?: string };

/** What the page shows for a question once the API's readers have answered with a real model, as `readWithModel` and `answerWhy` show it:
 * a typed question of the results answered from the stored result, a question asked back, a card of proposals, an answer in words, or,
 * when the model kept nothing, the page's own reading. */
export function modelAnswer(question: Question, readings: Reading[]): Said {
  const s = scene(question, true);
  const text = question.ask;
  let parts: ProposalAnswer["unread"] = [];
  for (const r of readings) {
    if (r.reader === "questions") { // as fea-start.tsx shows it: the prose, the sections it was answered from, and a kind of work offered
      if (!r.response) return said("failed", "The question could not be answered", ["Try again."]);
      const answer = r.response as unknown as GeneralAnswer;
      const { prose, sources } = generalLines(answer);
      if (question.page !== "start") { // as answerMeaning in coupon-chat.tsx: the first sentence as the heading, the sections under Details
        const covered = answer.covered && sources.length > 0;
        const { heading, more } = prose.length ? headed(prose, "Answered in words") : { heading: "Not in our theory pages yet", more: [] };
        return said("general", heading,
          [...more, ...(!prose.length ? ["Ask about the setup instead, for example “is it ready to run?”."] : covered ? ["From our theory pages."] : [])],
          { covered, sources: covered ? sources : [] });
      }
      const offered = answer.start && answer.start !== "none" ? answer.start : null;
      return said("general", prose.length ? "Answered in words" : sources.length ? "Our theory pages hold this" : "Our theory pages do not cover that yet",
        [...prose, ...(sources.length ? [`Read: ${sources.join("; ")}`] : []), ...(offered ? [`Offers: set up a ${offered} test`] : [])],
        { covered: answer.covered, start: offered ?? "none", sources });
    }
    if (r.reader === "result-answers") {
      if (!r.response) return said("failed", "No answer right now", ["That question could not be answered right now. Try again in a moment."]);
      const answer = r.response as unknown as ResultAnswer;
      const lines = whyLines(answer, false, readAt(s.facts));
      return said("why", lines.heading, [...lines.more, lines.note], { covered: answer.covered, sources: lines.sources });
    }
    if (r.reader === "result-questions") {
      const reading = r.response as unknown as ResultReading | null;
      if (!reading) continue; // no answer: the setup's reading goes on
      const request = reading.request;
      if (request?.kind === "failure") return { ...pageAnswer(text, s, { route: "failure" }), data: { request } };
      const asked = request ? questionFrom(request) : null;
      if (asked) { const answer = pageAnswer(text, s, { route: "value", question: asked }); return { ...answer, data: { ...answer.data, request } }; }
      const back = customerText(reading.question);
      if (back) return said("ask", "One question", [back], { request: null });
      continue;
    }
    const answer = r.response as unknown as ProposalAnswer | null;
    if (answer && (answer.proposals.length || answer.question || answer.supports.length || answer.loads.length)) {
      const lines = [...answer.proposals.map((p) => ({ label: p.label.replace(/ \([^)]*\)$/, ""), value: p.value, unit: p.unit ?? "" })), ...plateLines(answer)]
        .map((l) => `${l.label}: ${l.value}${l.unit ? ` ${l.unit}` : ""}`);
      return said("proposal", "Read from your message", [...lines, ...(answer.question ? [answer.question] : []), ...unreadLines(answer.unread).map((u) => `“${u.quote}”: ${u.words}`)],
        { proposals: Object.fromEntries(answer.proposals.map((p) => [p.key, p.value])), supports: answer.supports.map((x) => x.region), loads: answer.loads.map((x) => x.region) });
    }
    parts = answer?.unread ?? [];
  }
  if (asksUnread(text, !!s.fields)) return pageAnswer(text, s, { route: "unread" });
  const patterns = pageAnswer(text, s, { route: "patterns" });
  if (patterns.kind !== "rows" && parts.length) return said("redirect", "Read, but nothing to enter", unreadLines(parts).map((u) => `“${u.quote}”: ${u.words}`));
  return patterns;
}

const sameRegion = (a: string, b: string) => {
  const words = (name: string) => name.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean).sort().join(" ");
  return words(a) === words(b);
};

/** What is wrong with what the page shows after a real model read the question, by what the bank says a model should make of it and the
 * rules every answer keeps. The judge reads the rest (`live.judge`). */
export function liveFaults(question: Question, readings: Reading[], answer: Said): string[] {
  const out = rules(question, answer);
  const live = question.live ?? {};
  const failed = readings.filter((r) => r.error).map((r) => `${r.reader}: ${r.error}`);
  if (failed.length) out.push(`no answer from ${failed.join("; ")}`);
  if (live.request) {
    const got = readings.find((r) => r.reader === "result-questions")?.response?.request as Record<string, unknown> | null | undefined;
    const want = live.request;
    if (want.kind === "none") { if (got) out.push(`read as a ${String(got.kind)} question, expected none`); }
    else if (!got) out.push(`no question of the results read, expected ${want.kind}`);
    else {
      if (got.kind !== want.kind) out.push(`read as ${String(got.kind)}, expected ${want.kind}`);
      const same = (a: unknown, b: unknown[]) => JSON.stringify([...(a as unknown[] ?? [])].sort()) === JSON.stringify([...b].sort());
      if (want.quantities && !same(got.quantities, want.quantities)) out.push(`quantities ${JSON.stringify(got.quantities)}, expected ${JSON.stringify(want.quantities)}`);
      if (want.plies && !same(got.plies, want.plies)) out.push(`plies ${JSON.stringify(got.plies)}, expected ${JSON.stringify(want.plies)}`);
      if (want.element !== undefined && got.element !== want.element) out.push(`element ${String(got.element)}, expected ${String(want.element)}`);
      if (want.sense !== undefined && want.sense !== null && got.sense !== want.sense) out.push(`sense ${String(got.sense)}, expected ${want.sense}`);
    }
  }
  if (live.proposals) {
    const got = (answer.data.proposals ?? {}) as Record<string, string>;
    for (const [key, value] of Object.entries(live.proposals)) {
      const ok = got[key] !== undefined && (got[key] === value || (Number.isFinite(Number(value)) && Number(got[key]) === Number(value)));
      if (!ok) out.push(`proposes ${key} = ${got[key] ?? "nothing"}, expected ${value}`);
    }
  }
  if (live.plate) {
    for (const [list, want] of [["supports", live.plate.supports ?? []], ["loads", live.plate.loads ?? []]] as const) {
      const got = (answer.data[list] ?? []) as string[];
      for (const region of want) if (!got.some((g) => sameRegion(g, region))) out.push(`no ${list === "supports" ? "support" : "load"} on the ${region}; ${list}: ${got.join(", ") || "none"}`);
    }
  }
  if (live.start !== undefined && answer.data.start !== live.start) out.push(`offers ${String(answer.data.start)}, expected ${live.start}`);
  if (live.covered !== undefined && answer.data.covered !== live.covered) out.push(`covered ${String(answer.data.covered)}, expected ${live.covered}`);
  return out;
}

export { ROUTES, START_ROUTES };
