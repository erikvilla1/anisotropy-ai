/** The question banks of the assistant (ADR-0121): how a bank is read, what is on the page when a question is asked, and what the page
 * answers, in the words and numbers the chat shows. The banks are the JSON files beside this one; `tests/assistant-questions.test.ts`
 * holds the page to them, `api/tests/test_assistant_questions.py` the theory search, and `mcp-server/tests/test_questions.py` the MCP
 * server's tools. Nothing here computes a result: every number is read from the stored results the browser tests use. */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Fields, ProposalAnswer, ResultAnswer, ResultReading } from "../../lib/studio-api";
import { asksUnread, modelAsksResults, routeMessage, ROUTES, type ChatRoute, type ChatState, type RouteName } from "../../lib/chat-route";
import { aboutAnswer, checkTitle, unreadWords } from "../../lib/chat-about";
import { answerResultQuestion, comparisonNote, describeElement, extremeLines, RESULT_COLUMNS, questionFrom, resultOffer, resultUnit, thresholdVerdict, valueLines, type ResultQuestion } from "../../lib/result-question";
import { confirmsFailure, contradictsFailure, failureAnswer, failureLines, failureVerdict, marginNote } from "../../lib/result-failure";
import { summaryAnswer } from "../../lib/result-summary";
import { isConditionOrLoad, termLines } from "../../lib/fea-terms";
import { workingFor } from "../../lib/result-working";
import { applyMessage, unitsNamed } from "../../lib/studio-chat";
import { blankForm, exampleForm, PLATE_TEST, type StudioForm } from "../../lib/studio-form";
import { printed } from "../../lib/studio-colors";
import { couponOffer, plateLines, plateOffer, unreadLines } from "../../lib/proposals";
import { factsOf, whyLines } from "../../lib/result-why";
import { emptyPlate } from "../../lib/studio-plate";
import { bannedIn, customerText } from "../../lib/studio-copy";

export const FOLDER = "tests/assistant-questions";

/** The kind of question, which sets the shape of a good answer (the `chat-answer-quality` skill, criterion 1). */
export const KINDS = ["value", "which", "yes-no", "what-is", "why", "change", "command", "off-topic"] as const;
/** How it is typed: as written in a manual, with typos, a fragment that leans on the message before, loose words a model must read, another
 * program's words, units, or a bare word or two. */
export const STYLES = ["plain", "typo", "fragment", "loose", "jargon", "units", "terse"] as const;
/** What is on the page when it is asked. */
export const PAGES = ["blank", "setup", "ready", "results", "imported", "past", "plate"] as const;

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
  /** The plies and the quantities a value answer reads. */
  plies?: number[];
  columns?: string[];
  /** The element a value or element answer names, by its number. */
  element?: string;
  /** A failure answer that confirms the engineer's own statement of it ("Yes"). */
  confirmed?: boolean;
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
  /** Who answers with a model reading messages, as on the hosted site. */
  route: RouteName;
  /** Who answers with no model, when that is pinned; otherwise the same route, or for a model's route the setup's patterns or "unread". */
  offline?: RouteName;
  answer?: Expected;
  /** The theory sections a question of why finds, best first (ADR-0102). */
  sections?: string[];
  /** The MCP server's tool a client should call for it, the arguments, and words its answer holds (ADR-0107). */
  mcp?: { tool: string; args: Record<string, unknown>; says?: string[]; refused?: boolean;
    /** What the client's conversation holds before the question, in the real-model run: the coupon stated ("setup"), or stated and solved
     * ("solved", the default for a tool that reads a result). */
    context?: "setup" | "solved" };
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
const RESULTS = { fields: studio("fields.json") as Fields, facts: !!studio("explanation.json").facts, explanation: studio("explanation.json") };
const IMPORTED = { fields: imported("fields.json") as Fields, facts: !!imported("explanation.json").facts, explanation: imported("explanation.json") };

/** The page a question is asked on: the setup, the results shown and the chat's state, with or without a model reading. */
export type Scene = { form: StudioForm; fields: Fields | null; facts: Record<string, unknown> | null; state: ChatState; past: boolean; imported: boolean;
  picked: number | null };

export function scene(question: Question, modelReads: boolean): Scene {
  const example = exampleForm("2026-11-19");
  const results = question.page === "results" || question.page === "past" ? RESULTS : question.page === "imported" ? IMPORTED : null;
  const form = question.page === "blank" ? blankForm() : question.page === "plate" ? { ...example, test: PLATE_TEST } : example;
  const fields = results?.fields ?? null;
  const picked = question.picked !== undefined && fields ? fields.mesh.element_labels.findIndex((l) => l.split(".").pop() === String(question.picked)) : -1;
  return {
    form, fields, facts: factsOf(results?.explanation) ?? null, past: question.page === "past", imported: question.page === "imported", picked: picked >= 0 ? picked : null,
    state: {
      form, readOnly: question.page === "imported" || question.page === "past", results: !!fields, facts: !!results?.facts, api: true, modelReads,
      onPlate: question.page === "plate" && modelReads, ready: question.page !== "blank" && question.page !== "setup", step: (question.asking as ChatState["step"]) ?? null,
      about: null, thread: null, laminate: true,
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
      return said("working", `Working: ${found.name}`, [`on ${found.basis}`], { criterion: found.criterion });
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
      const facts = [lines.facts.join(" · "), ...(margin ? [margin] : [])];
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
    case "setup-fixed": {
      const term = routed.term;
      const heading = isConditionOrLoad(term) ? (s.form.test === PLATE_TEST ? "Add it on the model tree" : "Set by the test")
        : term.id === "partition" ? "Already partitioned" : term.id === "step" ? "One static step" : "Not offered yet";
      return said("said", heading, [term.here], { term: term.id });
    }
    case "run": return said("said", "Running the analysis");
    case "check": return said("said", "Checking the setup");
    case "full-form": return said("said", "All inputs");
    case "laminate": return said("said", "The laminate calculator");
    case "name": return said("rows", "Got it", [`Run by ${text}`], { rows: { filled_by: text } });
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

/** A talk: the earlier messages, then the question, each routed and answered on the same scene; the chat's own memory of the last
 * question and the element last spoken of is kept as the component keeps it (`thread` and `about` in coupon-chat.tsx). */
export function talk(question: Question, modelReads: boolean): { route: RouteName; said: Said; routed: ChatRoute } {
  const s = scene(question, modelReads);
  let last: { route: RouteName; said: Said; routed: ChatRoute } | null = null;
  for (const text of [...(question.after ?? []), question.ask]) {
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
  if (e.element !== undefined && data.element !== e.element) out.push(`element ${String(data.element)}, expected ${e.element}`);
  if (e.confirmed !== undefined && data.confirmed !== e.confirmed) out.push(`confirmed ${String(data.confirmed)}, expected ${e.confirmed}`);
  if (e.plies !== undefined && JSON.stringify(data.plies) !== JSON.stringify(e.plies)) out.push(`plies ${JSON.stringify(data.plies)}, expected ${JSON.stringify(e.plies)}`);
  if (e.columns !== undefined && JSON.stringify(data.columns) !== JSON.stringify(e.columns)) out.push(`quantities ${JSON.stringify(data.columns)}, expected ${JSON.stringify(e.columns)}`);
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
  const changes = answer.kind === "rows" || (answer.kind === "proposal" && Object.keys((answer.data.proposals ?? {}) as object).length > 0);
  if (changes && question.kind !== "change" && question.kind !== "command") out.push(`a question changed the setup: ${answer.lines.join(", ")}`);
  // every answer, whatever was asked (criterion 8 and ADR-0091): short, and in the product's own words
  const banned = bannedIn(text);
  if (banned.length) out.push(`names ${banned.join(", ")}`);
  if (answer.heading.length > 60) out.push(`heading of ${answer.heading.length} characters (60 at most)`);
  return out;
}

/** A request the page sends a model's reader in the API, as the page builds it (coupon-chat.tsx): the reading of a question of the results,
 * the setup's proposals, or the answer in words to a question of why. */
export type ModelRequest = { reader: "result-questions" | "proposals" | "result-answers"; body: Record<string, unknown> };

/** What the page sends a model for a question, with a model reading as on the hosted site, in the order it sends them: a question of the
 * results is read first, and the setup's proposals are asked only when that reading kept nothing (`readWithModel`). None when the page
 * answers the question itself. The real-model run (`scripts/assistant-live.py`) sends these to the API's own readers. */
export function modelRequests(question: Question): ModelRequest[] {
  const s = scene(question, true);
  const { route } = talk(question, true);
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
    if (r.reader === "result-answers") {
      if (!r.response) return said("failed", "No answer right now", ["That question could not be answered right now. Try again in a moment."]);
      const answer = r.response as unknown as ResultAnswer;
      const lines = whyLines(answer, false);
      return said("why", lines.prose.length ? "Answered in words" : "Not answered in words", [...lines.prose, lines.note], { covered: answer.covered, sources: lines.sources });
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
  if (live.covered !== undefined && answer.data.covered !== live.covered) out.push(`covered ${String(answer.data.covered)}, expected ${live.covered}`);
  return out;
}

export { ROUTES };
