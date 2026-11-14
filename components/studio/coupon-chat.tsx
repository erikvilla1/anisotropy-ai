"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Calculator, Check, CircleAlert, FlaskConical, Layers3, MessagesSquare, Play, RotateCcw, Sparkles, SlidersHorizontal, TableProperties } from "lucide-react";
import { allCouponTests, assistantInfo, couponValues, isActive, listCoupons, proposeRows, StudioError, type AssistantInfo, type CheckAnswer, type CouponSummary, type JobStatus,
  type ProposalAnswer } from "@/lib/studio-api";
import { couponOffer, couponRowsFrom } from "@/lib/proposals";
import { ProposalCard, type ProposalLine } from "./proposal-card";
import { CheckIssues } from "./check-fix";
import {
  blankForm, buildValues, exampleForm, fieldByLabel, formFromValues, libraryOptions, mergeRows, PLATE_TEST, UNIT_SYSTEMS, unitLabels, unitsOf, unitWords, type StudioForm,
} from "@/lib/studio-form";
import {
  applyMessage, COMMON_MATERIALS, couponLines, isBending, isSwitchRequest, unitsNamed, labelOf, libraryConstants, LAYUP_CHOICES, layupNotation, layupRows, libraryThickness, LOAD_CHIPS,
  missingIn, nextStep, parseLayup, PUSH_CHIPS, SIZE_CHIPS, stepOfKey, switchUnits, TEST_CHOICES, type ChatStep,
} from "@/lib/studio-chat";
import { chatTool, toolNamed } from "@/lib/chat-tools";
import { printed } from "@/lib/studio-colors";
import { CRITERION_NAMES } from "@/lib/studio-answer";
import { panel, panelOfStep, panelToFix, type PanelId } from "@/lib/workspace-panels";
import { showPanel } from "@/components/workspace/panels/step-panel";
import { handoffKey } from "../home-composer";
import { useProject } from "./project-context";
import { TOW_TEST } from "@/lib/studio-tow";
import { ENABLED, hiddenReason, isTestEnabled, isUnsymmetricLayup, understoodWithout, withoutHidden } from "@/lib/enabled-tests";
import { tensionValues } from "@/lib/tension-screen";
import { ANALYSIS_UNAVAILABLE, checkText, runHeadline, runProblem, setWords, stepOfStage, verificationOf } from "@/lib/studio-copy";

const RUN_BY_KEY = "anisotropy.studio.run_by";

type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; kind: "text"; title?: string; body?: ReactNode; tone?: "problem" }
  | { id: number; role: "assistant"; kind: "ask"; step: ChatStep | "reopen" }
  | { id: number; role: "assistant"; kind: "check"; answer: CheckAnswer }
  | { id: number; role: "assistant"; kind: "job"; job: string }
  | { id: number; role: "assistant"; kind: "result"; job: string }
  | { id: number; role: "assistant"; kind: "proposal"; answer: ProposalAnswer };
type Without<T> = T extends unknown ? Omit<T, "id"> : never;
type NewEntry = Without<Entry>;

/** What another page handed over: a message typed on the home page (session storage, or ?prompt= when storage is blocked) and a
 * library material (?material=), each used once. */
function readHandoff(): { prompt: string; material: string } {
  const params = new URLSearchParams(window.location.search);
  let prompt = params.get("prompt") ?? "";
  try {
    const stored = window.sessionStorage.getItem(handoffKey);
    if (stored) {
      window.sessionStorage.removeItem(handoffKey);
      const payload = JSON.parse(stored) as { prompt?: unknown };
      if (typeof payload.prompt === "string") prompt = payload.prompt;
    }
  } catch { /* storage blocked: the address carries the message */ }
  const material = libraryOptions.some((m) => m.id === params.get("material")) ? params.get("material")! : "";
  if (params.has("prompt") || params.has("material")) window.history.replaceState(null, "", window.location.pathname);
  return { prompt: prompt.trim().slice(0, 2000), material };
}

function today(): string { return new Date().toISOString().slice(0, 10); }
function remembered(key: string): string { try { return window.localStorage.getItem(key) ?? ""; } catch { return ""; } }
function remember(key: string, value: string) { try { window.localStorage.setItem(key, value); } catch { /* storage blocked: the name is simply not kept */ } }
const materialName = (id: string) => libraryOptions.find((m) => m.id === id)?.name ?? id;
/** An estimate as a row value: four significant figures, written out (680000 psi, not 6.800e+5), so the row reads as typed. */
const estimated = (value: number) => String(Number(value.toPrecision(4)));
const libraryEntry = (id: string) => libraryOptions.find((m) => m.id === id);

const QUESTIONS: Record<ChatStep | "reopen", { title: string; text?: string }> = {
  test: { title: "What are we analysing?", text: "Pick a test, or describe the coupon in one line, e.g. “unnotched tension, ASTM D3039, IM7/8552, [45/0/-45/90]s, 1 mm pull”." },
  material: { title: "Which material?", text: "Pick one from the library, or enter your own under Layup and material." },
  shear: { title: "Out-of-plane shear moduli", text: "G13 and G23 are not in the library. Use the tape estimate (G13 = G12, G23 = E2/3) or enter measured values." },
  layup: { title: "What is the layup?", text: "Bottom ply first. 0° runs along the load." },
  geometry: { title: "Coupon size", text: "Length runs along the load, e.g. “250 x 25 mm, 56 mm tabs”." },
  loading: { title: "How is it loaded?" },
  name: { title: "Who is running it?", text: "Your name goes on the report." },
  review: { title: "Checking the setup" },
  reopen: { title: "Reopen a saved coupon", text: "Running it again adds a new run." },
};

function Chips({ children }: { children: ReactNode }) { return <div className="chat-chips">{children}</div>; }

/** A suggestion that opens a panel on the left: the rows live there (ADR-0062, part 5). */
function PanelLink({ id, children }: { id: PanelId; children: ReactNode }) {
  return <button type="button" data-panel={id} onClick={() => showPanel(id)}><SlidersHorizontal size={14} /> {children}</button>;
}

/** The coupon assistant (ADR-0055; ADR-0062, part 5): a conversation beside the panels, on the one project they share. It offers one-click
 * choices, reads a typed line into the rows, checks and runs the setup, and for anything else names the panel that asks for it. */
export function CouponChat({ apiBaseUrl, onLaminate }: {
  apiBaseUrl: string;
  /** Opens the laminate workspace (ADR-0060): a stack under loads per unit width, no coupon around it. */
  onLaminate?: () => void;
}) {
  const { form, setForm: storeForm, run: runner, restored, allTests } = useProject(); // the rows and the run live in the project (ADR-0062)
  // the tension screen's chat (ADR-0090): the material and the layup, the rest chosen by the software; every test's steps with the switch on.
  // A ref, since the first question waits for the API's answer and is asked before the page renders it
  const simpleRef = useRef(!allTests);
  simpleRef.current = !allTests;
  const valuesOf = (rows: StudioForm) => (simpleRef.current ? tensionValues(rows) : buildValues(rows));
  const { checking, checked, job, fields, explanation, problem } = runner;
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<number | null>(null); // the question whose controls are live
  const [input, setInput] = useState("");
  const [coupons, setCoupons] = useState<CouponSummary[]>([]);
  const [model, setModel] = useState<AssistantInfo | null>(null); // a model that reads messages, when the API has one (ADR-0088)
  const [reading, setReading] = useState(false);
  const nextId = useRef(1);
  const body = useRef<HTMLDivElement>(null);
  const formRef = useRef(form);
  useEffect(() => { formRef.current = form; }, [form]); // rows edited on the panels are the chat's rows too
  const live = useRef<{ active: number | null; entries: Entry[] }>({ active: null, entries: [] });
  useEffect(() => { live.current = { active, entries }; }, [active, entries]);
  const started = useRef(false);

  const setForm = useCallback((next: StudioForm) => { formRef.current = next; storeForm(next); }, [storeForm]);
  const add = useCallback((...items: NewEntry[]) => {
    const made = items.map((item) => ({ ...item, id: nextId.current++ }) as Entry);
    setEntries((list) => [...list, ...made]);
    return made;
  }, []);
  const ask = useCallback((step: ChatStep | "reopen") => {
    const [entry] = add({ role: "assistant", kind: "ask", step });
    setActive(entry.id);
  }, [add]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let current = true;
    void allCouponTests(apiBaseUrl).then((all) => { if (current) begin(all); }); // which chat this is waits for the API's switch (ADR-0089)
    return () => { current = false; started.current = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function begin(all: boolean) {
    simpleRef.current = !all;
    const name = remembered(RUN_BY_KEY);
    const start: StudioForm = { ...formRef.current, filled_by: formRef.current.filled_by || name, date: formRef.current.date || today() };
    setForm(start);
    const tensionRows = ["library", "ply_1", "own_name"].some((key) => (start[key] ?? "").trim()); // the tension screen names the test itself
    if (simpleRef.current ? tensionRows : start.test) {
      add({ role: "assistant", kind: "text", title: restored ? "Picked up where you left off" : "Picked up from the panels",
        body: <p>Your inputs are kept. Here is what is still needed.</p> });
      proceed(start);
      return;
    }
    // a library material sent from its page, or a message typed on the home page, starts the conversation
    const handoff = readHandoff();
    if (handoff.material) {
      setForm({ ...start, library: handoff.material });
      add({ role: "assistant", kind: "text", title: `Material: ${materialName(handoff.material)}`, body: <p>From the material library. Change it any time.</p> });
    }
    ask(simpleRef.current ? nextStep(start, true) : "test");
    if (handoff.prompt) send(handoff.prompt);
  }

  useEffect(() => {
    if (!apiBaseUrl) return;
    let current = true;
    void assistantInfo(apiBaseUrl).then((info) => { if (current) setModel(info); });
    return () => { current = false; };
  }, [apiBaseUrl]);

  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listCoupons(apiBaseUrl, controller.signal).then(setCoupons).catch(() => setCoupons([]));
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" }); }, [entries, checking, fields, reading]);

  // a row typed on a panel answers the open question: move on, and when nothing is missing offer the check
  useEffect(() => {
    const current = live.current.entries.find((e) => e.id === live.current.active);
    if (!current || current.role !== "assistant" || current.kind !== "ask" || current.step === "review" || current.step === "reopen") return;
    if (form.test === TOW_TEST) { proceed(form); return; } // a fibre tow picked on a panel: hand over to its panels once (ADR-0074)
    if (missingIn(current.step, form, simpleRef.current).length) return;
    const step = nextStep(form, simpleRef.current);
    if (step !== "review") { ask(step); return; }
    setActive(null);
    add({ role: "assistant", kind: "text", title: "Ready to check",
      body: <><p>Everything is stated.</p><Chips><button type="button" onClick={() => void check(formRef.current)}><Check size={14} /> Check setup</button></Chips></> });
  }, [form]); // eslint-disable-line react-hooks/exhaustive-deps

  async function check(values: StudioForm) {
    setActive(null);
    if (!apiBaseUrl) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "Analysis unavailable",
        body: <p>Analysis is not available on this page. The setup can be stated but not checked or run.</p> });
      return;
    }
    try {
      const answer = await runner.check(valuesOf(values));
      add({ role: "assistant", kind: "check", answer });
    } catch (error) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The setup could not be checked", body: <p>{error instanceof StudioError ? error.message : "Try again."}</p> });
    }
  }

  /** Ask the next missing thing, or check the setup once nothing is missing. A test the studio does not offer yet (ADR-0089) goes on only
   * when the API says the switch shows every test; it is asked here, once per address, since a restored project may arrive before the
   * answer. */
  function proceed(next: StudioForm) {
    const hidden = hiddenReason(next, false);
    if (!hidden) { proceedWith(next); return; }
    void allCouponTests(apiBaseUrl).then((all) => {
      if (all) { proceedWith(next); return; }
      setActive(null);
      add({ role: "assistant", kind: "text", tone: "problem", title: "Not offered yet",
        body: <><p data-testid="chat-not-available">{hidden} Your inputs are kept.</p>
          <Chips><button type="button" onClick={loadExample}><FlaskConical size={14} /> Start from the IM7/8552 tension example</button>
            <button type="button" onClick={() => ask("test")}>Pick the test</button></Chips></> });
    });
  }

  function proceedWith(next: StudioForm) {
    if (next.test === TOW_TEST) { // a fibre tow record is no coupon: its rows and specimens are the tow panels' (ADR-0074)
      setActive(null);
      add({ role: "assistant", kind: "text", title: "Fibre tow tests use the panels",
        body: <><p>Enter the fibre, the test and each specimen&apos;s forces on the left, then Calculate.</p>
          <Chips><button type="button" onClick={() => showPanel("tow-fibre")}><SlidersHorizontal size={14} /> Open The fibre tow</button></Chips></> });
      return;
    }
    if (next.test === PLATE_TEST) {
      setActive(null);
      add({ role: "assistant", kind: "text", title: "Plates are set up on the model",
        body: <><p>Pick the held and loaded regions under Loads and supports, or click an element on the model.</p>
          <Chips><PanelLink id="loads">Open Loads and supports</PanelLink></Chips></> });
      return;
    }
    const step = nextStep(next, simpleRef.current);
    if (step === "review") void check(next);
    else ask(step);
  }

  /** A changed setup leaves the last results behind; a run still going keeps its progress. */
  function clearRun() {
    runner.clearChecked();
    runner.clearResults();
  }

  /** Apply rows from a click, echo what the engineer chose, and move on. */
  function answer(echo: string, rows: StudioForm) {
    const next: StudioForm = mergeRows(formRef.current, rows); // a new test clears a standard it is not under (ADR-0072)
    if (rows.filled_by) remember(RUN_BY_KEY, rows.filled_by.trim());
    setForm(next);
    clearRun();
    add({ role: "user", text: echo });
    proceed(next);
  }

  /** The coupon restated in another system (ADR-0061): the rows with a unit are cleared, since a number typed in mm is not one in inches
   * and the page converts nothing; the engine reads every number in the system picked. */
  function switchTo(units: string) {
    if (!UNIT_SYSTEMS.includes(units) || units === unitsOf(formRef.current)) return;
    const { form: next, cleared } = switchUnits(formRef.current, units);
    setForm(next); clearRun();
    add({ role: "user", text: `Units: ${unitWords(units)}` });
    if (cleared.length) {
      add({ role: "assistant", kind: "text", title: `Now stated in ${unitWords(units)}`,
        body: <p>Cleared {cleared.map((key) => labelOf(key, units).replace(/ \(.*\)$/, "")).join(", ")}: give them again in {unitWords(units)}.</p> });
      proceed(next);
    }
  }

  function startOver() {
    const fresh = { ...blankForm(unitsOf(formRef.current)), date: today(), filled_by: formRef.current.filled_by };
    setForm(fresh); runner.reset();
    setEntries([]);
    ask(simpleRef.current ? "material" : "test");
  }

  function loadExample() {
    const next = { ...exampleForm(today()), filled_by: formRef.current.filled_by };
    setForm(next); clearRun();
    add({ role: "user", text: "Start from the IM7/8552 example" },
      { role: "assistant", kind: "text", title: "IM7/8552 example loaded",
        body: <p>Unnotched tension, 250 × 25 mm, 56 mm tabs, [45/0/-45/90]s, 1 mm pull. Type a change, e.g. “make it [0/90]2s”.</p> });
    proceed(next);
  }

  async function reopen(name: string) {
    if (!name) return;
    try {
      const values = await couponValues(apiBaseUrl, name);
      const next = { ...formFromValues(values), filled_by: formRef.current.filled_by, date: today() };
      setForm(next); clearRun();
      add({ role: "user", text: `Reopen ${name}` });
      proceed(next);
    } catch (error) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "That coupon could not be opened", body: <p>{error instanceof StudioError ? error.message : "Try again."}</p> });
    }
  }

  async function run() {
    const answerNow = checked;
    if (!apiBaseUrl || !answerNow || answerNow.state !== "ready") return;
    const name = formRef.current.filled_by.trim() || (simpleRef.current ? remembered(RUN_BY_KEY) || "studio" : ""); // the tension screen asks no name
    if (!name) { ask("name"); return; }
    setActive(null);
    add({ role: "user", text: "Run the analysis" });
    try {
      await runner.solve(valuesOf(formRef.current), name, answerNow.checklist.coupon_exists); // the effect below follows the job
    } catch (error) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The analysis could not start", body: <p>{error instanceof StudioError ? error.message : "Try again."}</p> });
    }
  }

  useEffect(() => {
    // a run started here or on the panels (the tension screen's Run analysis): the conversation follows it, once per job (ADR-0091)
    if (!job) return;
    if (live.current.entries.some((e) => e.role === "assistant" && e.kind === "job" && e.job === job.job_id)) return;
    setActive(null);
    add({ role: "assistant", kind: "job", job: job.job_id });
  }, [job?.job_id, add]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // once per job, as soon as its fields are read: the entry follows the fields themselves, not the hook's bookkeeping of first reads
    if (!fields || !job) return;
    if (!live.current.entries.some((e) => e.role === "assistant" && e.kind === "result" && e.job === job.job_id)) add({ role: "assistant", kind: "result", job: job.job_id });
  }, [fields, job, add]);

  /** A message that names no value: the panel on the left that asks for the next thing, and a few phrases that would be read. */
  function redirect(text: string, echoed = false) {
    const step = nextStep(formRef.current, simpleRef.current);
    const id = panelOfStep(step);
    const title = panel(id).title;
    const named = toolNamed(text) === "coupon";
    add(...(echoed ? [] : [{ role: "user", text } as NewEntry]), { role: "assistant", kind: "text", title: "Not sure what to change",
      body: <div data-testid="chat-redirect" data-panel={id}>
        <p>{named ? "This workspace sets up and solves test coupons. " : ""}
          {step === "review" ? "Everything is stated: say “check”." : `Next: ${QUESTIONS[step].title.toLowerCase().replace(/\?$/, "")} (${title}).`} Try “[0/90]2s”, “AS4/8552” or “10 kN”.</p>
        <Chips><PanelLink id={id}>Open {title}</PanelLink>{step !== "review" ? <button type="button" onClick={() => ask(step)}>Ask me here</button> : null}</Chips>
      </div> });
  }

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    if (/^(start over|reset|new coupon|restart)\b/i.test(text)) { add({ role: "user", text }); startOver(); return; }
    if (/^(run|solve|go|run it|run analysis)\b/i.test(text) && checked?.state === "ready") { void run(); return; }
    if (/^(check|check setup)\b/i.test(text)) { add({ role: "user", text }); void check(formRef.current); return; }
    if (/full form|spreadsheet|all (the )?rows|advanced/i.test(text)) { add({ role: "user", text }); showPanel("advanced"); return; }
    if (onLaminate && toolNamed(text) === "laminate") { add({ role: "user", text }); onLaminate(); return; }
    const current = entries.find((e) => e.id === active);
    const step = current && current.role === "assistant" && current.kind === "ask" ? current.step : null;
    if (step === "name" && !/\d/.test(text)) { answer(text, { filled_by: text }); return; }
    // another unit system named: the chat's own switch handles it (ADR-0061), since a proposal is read in the coupon's system
    const named = unitsNamed(text);
    if (model?.proposes && apiBaseUrl && !isSwitchRequest(text) && (named === null || named === unitsOf(formRef.current))) { void readWithModel(text); return; }
    readWithPatterns(text);
  }

  /** The model reads the message into the rows on offer (ADR-0088); what the source guard keeps waits in a card for the engineer's tick.
   * With nothing kept, or no answer, the page's own patterns read it, as they do with no model. */
  async function readWithModel(text: string) {
    add({ role: "user", text });
    setReading(true);
    let answer: ProposalAnswer | null = null;
    let failed: string | null = null;
    try { answer = await proposeRows(apiBaseUrl, { product: "coupon", message: text, conditions: [], ...couponOffer(formRef.current, allTests) }); }
    catch (error) { failed = error instanceof StudioError ? error.message : "the model did not answer"; }
    finally { setReading(false); }
    if (answer && (answer.proposals.length || answer.question)) { add({ role: "assistant", kind: "proposal", answer }); return; }
    const reason = failed ?? answer?.reason;
    if (reason) { // a model that does not answer is not asked again this session: each message would wait for it and fail the same way
      setModel(null);
      add({ role: "assistant", kind: "text", title: "Reading simple phrases only",
        body: <p className="chat-note">Free-text reading is unavailable right now, so short phrases like the examples are read from here on. Reload to try again.</p> });
    }
    readWithPatterns(text, true);
  }

  /** The proposals the engineer ticked go into the rows, and the conversation moves on. */
  function applyProposals(answer: ProposalAnswer, ticked: Set<string>) {
    const { rows, notes } = couponRowsFrom(answer.proposals.filter((p) => ticked.has(p.key)));
    if (notes.length) add({ role: "assistant", kind: "text", tone: "problem", title: "Not applied", body: <ul className="chat-understood">{notes.map((n) => <li key={n}>{n}</li>)}</ul> });
    if (!Object.keys(rows).length) return;
    const next: StudioForm = mergeRows(formRef.current, rows); // a new test clears a standard it is not under (ADR-0072)
    setForm(next); clearRun();
    proceed(next);
  }

  /** The card's lines: each value with the unit it goes in with, and how it was written when the API converted it within the system. */
  function proposalLines(answer: ProposalAnswer): ProposalLine[] {
    return answer.proposals.map((p) => ({
      id: p.key, label: p.label.replace(/ \([^)]*\)$/, ""), value: p.key === "library" ? materialName(p.value) : p.value, unit: p.unit ?? "", quote: p.quote,
      note: p.written_unit && p.written_unit !== p.unit ? `written ${p.written_value} ${p.written_unit}` : undefined,
    }));
  }

  /** The message read by the page's fixed patterns (ADR-0055); `echoed` when the user's words are already in the conversation. */
  function readWithPatterns(text: string, echoed = false) {
    const you: NewEntry[] = echoed ? [] : [{ role: "user", text }];
    const read = applyMessage(formRef.current, text);
    const { rows, notes: hiddenNotes, dropped } = withoutHidden(read.rows, allTests); // what the studio does not offer yet stays out (ADR-0089)
    const understood = understoodWithout(read.understood, dropped);
    const note = read.note;
    if (hiddenNotes.length) {
      add(...you, { role: "assistant", kind: "text", tone: "problem", title: "Not offered yet",
        body: <ul className="chat-understood" data-testid="chat-not-available">{hiddenNotes.map((n) => <li key={n}>{n}</li>)}</ul> });
      if (!understood.length) return;
      you.length = 0;
    }
    if (!understood.length) {
      if (note) add(...you, { role: "assistant", kind: "text", title: "Another unit system", tone: "problem", body: <p>{note}</p> });
      else redirect(text, echoed);
      return;
    }
    add(...you, { role: "assistant", kind: "text", title: "Got it", body: <>
      <ul className="chat-understood">{understood.map((u) => <li key={u}><Check size={13} /> {u}</li>)}</ul>{note ? <p className="chat-note">{note}</p> : null}</> });
    const next: StudioForm = mergeRows(formRef.current, rows); // a new test clears a standard it is not under (ADR-0072)
    setForm(next); clearRun();
    proceed(next);
  }

  function askWidget(step: ChatStep | "reopen", isLive: boolean): ReactNode {
    if (!isLive) return null;
    const units = unitsOf(form);
    const lab = unitLabels(units);
    switch (step) {
      case "test":
        return (
          <>
            <p className="chat-inline chat-units">
              <label htmlFor="chat-units">Stated in</label>
              <select id="chat-units" aria-label="Units" value={units} onChange={(e) => switchTo(e.target.value)} data-testid="chat-units">
                {UNIT_SYSTEMS.map((u) => <option key={u} value={u}>{unitWords(u)}</option>)}
              </select>
              <span className="chat-note">Results come back in these units.</span>
            </p>
            <div className="chat-choice-grid">
              {onLaminate ? (
                <button type="button" className="chat-choice chat-choice-wide" data-testid="laminate-choice" onClick={onLaminate}>
                  <strong><Calculator size={14} /> {chatTool("laminate").title}</strong><span>{chatTool("laminate").detail}</span>
                </button>
              ) : null}
              <p className="chat-choice-head" data-testid="coupon-tool"><strong>{chatTool("coupon").title}</strong> <span>{chatTool("coupon").detail}</span></p>
              {TEST_CHOICES.filter((c) => isTestEnabled(c.test, allTests)).map((c) => (
                <button type="button" key={c.test} className="chat-choice" onClick={() => answer(c.title, { test: c.test })}>
                  <strong>{c.title}</strong><span>{c.detail}</span>
                </button>
              ))}
            </div>
            <Chips>
              <button type="button" onClick={loadExample}><FlaskConical size={14} /> Start from the IM7/8552 example</button>
              {coupons.length ? <button type="button" onClick={() => ask("reopen")}><RotateCcw size={14} /> Reopen a saved coupon</button> : null}
              <PanelLink id="test">Set up on the panels</PanelLink>
            </Chips>
          </>
        );
      case "reopen":
        return (
          <div className="chat-list">
            {coupons.map((c) => isTestEnabled(c.test, allTests) ? (
              <button type="button" key={c.name} onClick={() => reopen(c.name)}>
                <strong>{c.name}</strong><span>{c.test}, {c.layup}; {c.attempts} run{c.attempts === 1 ? "" : "s"}</span>
              </button>
            ) : (
              <button type="button" key={c.name} disabled data-testid="coupon-not-available">
                <strong>{c.name}</strong><span>{c.test}: not offered yet</span>
              </button>
            ))}
          </div>
        );
      case "material":
        return (
          <>
            <Chips>
              {COMMON_MATERIALS.filter((id) => libraryEntry(id)).map((id) => (
                <button type="button" key={id} onClick={() => answer(materialName(id), { library: id })}><Layers3 size={14} /> {materialName(id)}</button>
              ))}
            </Chips>
            <div className="chat-inline">
              <select aria-label="Another library material" defaultValue="" onChange={(e) => e.target.value && answer(materialName(e.target.value), { library: e.target.value })}>
                <option value="">Another library material…</option>
                {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </div>
            <Chips><PanelLink id="layup">My own constants, under Layup and material</PanelLink></Chips>
          </>
        );
      case "shear": {
        const constants = form.library ? libraryConstants(form.library, units) : { G12: Number(form.own_G12), E2: Number(form.own_E2) };
        const estimate = constants && Number.isFinite(constants.G12) && Number.isFinite(constants.E2) && constants.G12 > 0 && constants.E2 > 0
          ? { G13: estimated(constants.G12), G23: estimated(constants.E2 / 3) } : null;
        return (
          <Chips>
            {estimate ? (
              <button type="button" onClick={() => answer(`Tape estimate: G13 = ${estimate.G13} ${lab.stress}, G23 = ${estimate.G23} ${lab.stress}`,
                { G13: estimate.G13, G23: estimate.G23, notes: [formRef.current.notes, "G13 = G12 and G23 = E2/3 by the tape estimate (studio chat)."].filter(Boolean).join(" ") })}>
                <Sparkles size={14} /> Use the tape estimate: G13 = {estimate.G13}, G23 = {estimate.G23} {lab.stress}
              </button>
            ) : null}
            <PanelLink id="layup">Measured values, under Layup and material</PanelLink>
          </Chips>
        );
      }
      case "layup": {
        const needThickness = libraryThickness(form) === null;
        return (
          <>
            <Chips>
              {LAYUP_CHOICES.map((c) => {
                const layup = parseLayup(c.notation)!;
                return <button type="button" key={c.notation} onClick={() => answer(c.notation, { ...layupRows(layup), ...(needThickness ? {} : { ply_thickness: "" }) })}>
                  <Layers3 size={14} /> {c.title} <code>{c.notation}</code></button>;
              })}
            </Chips>
            <LayupInput needThickness={needThickness} form={form} allTests={allTests} onApply={(notation, rows) => answer(notation, rows)} />
            {!needThickness ? <p className="chat-note">Ply thickness {printed(libraryThickness(form))} {lab.length} (library).</p> : null}
            <Chips><PanelLink id="layup">Ply by ply, under Layup and material</PanelLink></Chips>
          </>
        );
      }
      case "geometry":
        return (
          <Chips>
            {!isBending(form) && SIZE_CHIPS[units] ? (
              <button type="button" onClick={() => answer(SIZE_CHIPS[units].words, SIZE_CHIPS[units].rows)}>
                <Layers3 size={14} /> {SIZE_CHIPS[units].words}</button>
            ) : null}
            <PanelLink id="geometry">The size, under Geometry</PanelLink>
          </Chips>
        );
      case "loading":
        return isBending(form) ? (
          <Chips>
            {(PUSH_CHIPS[units] ?? []).map((v) => <button type="button" key={v} onClick={() => answer(`Push the nose ${v} ${lab.length}`, { control: "displacement", value: v })}>Push {v} {lab.length}</button>)}
            <PanelLink id="loads">Another travel, under Loads and supports</PanelLink>
          </Chips>
        ) : (
          <>
            <p className="chat-note">Bottom grip held, top grip {form.test === "unnotched compression" ? "pushes" : "pulls"}.</p>
            <Chips>
              {(LOAD_CHIPS[units] ?? []).map((chip) => (
                <button type="button" key={chip.words} onClick={() => answer(chip.words.replace(/^(\w+) /, "$1 of "), { control: chip.control, value: chip.value })}>{chip.words}</button>
              ))}
              <PanelLink id="loads">Another load, under Loads and supports</PanelLink>
            </Chips>
          </>
        );
      case "name":
        return <Chips><PanelLink id="run">Enter it under Run</PanelLink></Chips>;
      case "review":
        return null;
    }
  }

  function checkMessage(result: CheckAnswer, latest: boolean): ReactNode {
    const items = result.checklist.items;
    const blocking = items.filter((i) => i.state === "fail" || i.state === "missing");
    const warnings = items.filter((i) => i.state === "warn");
    const passed = items.filter((i) => i.state === "pass").length;
    const stepsFor = (rows: string[]) => [...new Set(rows.map((label) => stepOfKey(fieldByLabel[label]?.key ?? "")))];
    return (
      <div data-testid="chat-check" data-state={result.state}>
        <h4>{result.state === "ready" ? "Ready to run" : `${blocking.length} thing${blocking.length === 1 ? "" : "s"} to fix before running`}</h4>
        <p>{passed} of {items.length} checks passed.</p>
        {blocking.length ? (
          // each item takes its rows in place on the latest check (ADR-0062 amendment 2); its link still opens the panel that holds them
          <CheckIssues items={blocking} form={form} units={unitsOf(form)} live={latest && !checking} allTests={allTests} onApply={(rows, echo) => answer(echo, rows)}
            link={(item) => {
              const target = panelToFix(item);
              const step = stepsFor(item.rows).find((s): s is ChatStep => s !== null);
              return target ? <button type="button" className="chat-link" data-panel={target} onClick={() => showPanel(target)}>Fix under {panel(target).title}</button>
                : step ? <button type="button" className="chat-link" onClick={() => ask(step)}>Fix</button> : null;
            }} />
        ) : null}
        {warnings.length ? (
          <ul className="chat-issues chat-warnings">
            {warnings.map((item) => <li key={item.id}><CircleAlert size={14} /> <span><strong>{item.label}:</strong> {checkText(item)}</span></li>)}
          </ul>
        ) : null}
        <details className="chat-details"><summary>All checks</summary>
          <ul className="chat-allchecks">{items.map((i) => <li key={i.id} data-state={i.state}>{i.state === "pass" ? "✓" : i.state === "warn" ? "!" : "✕"} {i.label}: {checkText(i)}</li>)}</ul>
        </details>
        {latest && result.state === "ready" ? (
          <div className="chat-actions">
            <button type="button" className="chat-primary" onClick={run} disabled={isActive(job?.state)} data-testid="chat-run"><Play size={14} /> Run analysis</button>
            <button type="button" className="chat-secondary" onClick={() => showPanel(allTests ? "mesh" : "tension-change")}><SlidersHorizontal size={14} /> Change settings</button>
          </div>
        ) : null}
      </div>
    );
  }

  function resultMessage(jobId: string): ReactNode {
    if (job?.job_id !== jobId) return <p className="chat-note">Results of an earlier run; the setup has changed since.</p>;
    if (!fields) return <p className="chat-note">Loading results…</p>;
    const s = fields.summary, lab = fields.labels;
    const earliest = s.earliest ? s.fpf[s.earliest] : null;
    const check = job ? verificationOf(job.result, s.calculix ?? null) : null;
    return (
      <div data-testid="chat-result">
        <h4>Results</h4>
        <div className="chat-stats">
          <div><span>Reaction</span><strong data-testid="chat-reaction">{printed(Math.abs(s.reaction.value))} {lab.force}</strong><small>{s.reaction.sense}, {setWords(s.reaction.set)}</small></div>
          <div><span>Largest displacement</span><strong>{printed(s.max_displacement.value)} {lab.length}</strong><small>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}</small></div>
          {earliest ? (
            <div className={earliest.factor < 1 ? "chat-stat-bad" : undefined}><span>First-ply failure</span><strong>R = {printed(earliest.factor)}</strong>
              <small>{CRITERION_NAMES[s.earliest ?? ""] ?? s.earliest}, ply {earliest.ply} · {earliest.angle}°</small></div>
          ) : <div><span>First-ply failure</span><strong>–</strong><small>no criterion selected</small></div>}
        </div>
        {earliest?.touches_grip ? <p className="chat-note">The first failure is at a grip edge.</p> : null}
        {check ? <p className={check.verified ? "chat-ok" : "chat-note"} data-testid="chat-result-line">{check.verified ? <Check size={13} /> : null} {check.line}</p> : null}
        {job && job.state !== "done" ? <p className="chat-note">{runHeadline(job)}{job.state !== "running" ? "."
          : stepOfStage(job.stage) === "report" ? "…" : job.result ? ". The report follows." : "…"}</p> : null}
        <Chips>
          <button type="button" onClick={() => ask("layup")}>Change the layup</button>
          <button type="button" onClick={() => ask("loading")}>Change the load</button>
          <button type="button" onClick={() => ask("material")}>Try another material</button>
          <button type="button" onClick={startOver}>New coupon</button>
        </Chips>
      </div>
    );
  }

  function render(entry: Entry, latestCheck: number | undefined): ReactNode {
    if (entry.role === "user") return <div className="chat-user" key={entry.id}>{entry.text}</div>;
    let content: ReactNode;
    if (entry.kind === "ask") {
      const q = QUESTIONS[entry.step];
      const isLive = entry.id === active && !checking;
      content = <div data-step={entry.step} data-testid={isLive ? "chat-question" : undefined}><h4>{q.title}</h4>{isLive && q.text ? <p>{q.text}</p> : null}{askWidget(entry.step, isLive)}</div>;
    } else if (entry.kind === "text") content = <div className={entry.tone === "problem" ? "chat-problem" : undefined}>{entry.title ? <h4>{entry.title}</h4> : null}{entry.body}</div>;
    else if (entry.kind === "check") content = checkMessage(entry.answer, entry.id === latestCheck && checked === entry.answer);
    else if (entry.kind === "job") content = job?.job_id === entry.job ? <ChatRun job={job} /> : <p className="chat-note">An earlier run.</p>;
    else if (entry.kind === "proposal") {
      content = <ProposalCard lines={proposalLines(entry.answer)} conditions={entry.answer.conditions} question={entry.answer.question}
        dropped={entry.answer.dropped.map((d) => ({ ...d, key: labelOf(d.key, unitsOf(form)).replace(/ \([^)]*\)$/, "") }))}
        onApply={(ticked) => applyProposals(entry.answer, ticked)} />;
    }
    else content = resultMessage(entry.job);
    return (
      <div className="chat-assistant" key={entry.id}>
        <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
        <div>{content}</div>
      </div>
    );
  }

  const latestCheck = [...entries].reverse().find((e) => e.role === "assistant" && e.kind === "check")?.id;
  return (
    <section className="chat-pane" aria-label="Coupon assistant" data-testid="coupon-chat">
      <div className="chat-pane-top">
        <span><span className="status-dot" /> Coupon assistant</span>
        <span>
          {allTests ? <button type="button" className="chat-link" onClick={() => showPanel("advanced")}><TableProperties size={13} /> All inputs</button> : null}
          <button type="button" className="icon-button" aria-label="Start a new coupon" title="Start a new coupon" onClick={startOver}><RotateCcw size={14} /></button>
        </span>
      </div>
      <div className="chat-scroll" ref={body} aria-live="polite" aria-relevant="additions">
        {entries.map((e) => render(e, latestCheck))}
        {reading ? <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span><div><p className="chat-typing" data-testid="chat-reading">Reading your message…</p></div></div> : null}
        {checking ? <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span><div><p className="chat-typing">Checking the setup…</p></div></div> : null}
        {/* on the tension screen the rail says an outage, once (audit fea-run-48); every other problem is said here */}
        {problem && (allTests || problem !== ANALYSIS_UNAVAILABLE) ? <p className="studio-alert" role="alert">{problem}</p> : null}
      </div>
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message the coupon assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Describe the coupon or one change, e.g. “make it [0/90]2s”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Enter to send · “check” · “run” · “start over”</span>
          <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
        </div>
      </form>
    </section>
  );
}

/** The run in the conversation: one line, the state in a word and a stopped run's plain reason; the steps are on the centre's card. */
function ChatRun({ job }: { job: JobStatus }) {
  const problem = runProblem(job);
  return (
    <div data-testid="chat-job" data-state={job.state}>
      <h4>Analysis: {runHeadline(job)}</h4>
      {problem ? <p className="chat-problem">{problem}</p> : isActive(job.state) ? <p className="chat-note">Progress is shown above the model.</p> : null}
    </div>
  );
}

/** The coupon in a few fields, as stated so far: the strip above the workspace's stage. `fallback` names what a blank field will be. */
export function CouponSpec({ form, fallback = {} }: { form: StudioForm; fallback?: Record<string, string> }) {
  const lines = couponLines(form);
  return (
    <dl className="chat-spec" data-testid="chat-spec">
      {lines.map(([k, v]) => <div key={k} data-filled={v || fallback[k] ? "yes" : "no"}><dt>{k}</dt><dd>{v || fallback[k] || "–"}</dd></div>)}
    </dl>
  );
}

function LayupInput({ needThickness, form, allTests, onApply }: { needThickness: boolean; form: StudioForm; allTests: boolean; onApply: (notation: string, rows: StudioForm) => void }) {
  const length = unitLabels(unitsOf(form)).length;
  const [text, setText] = useState(() => layupNotation(form));
  const [thickness, setThickness] = useState(form.ply_thickness ?? "");
  const [error, setError] = useState("");
  return (
    <form className="chat-inline" onSubmit={(e) => {
      e.preventDefault();
      const layup = parseLayup(text);
      if (!layup) { setError("Use the form [45/0/-45/90]s, [0/90]2s or [±45]2s (up to 16 plies)."); return; }
      // a layup that bends as it is pulled waits while the list is closed, in the setup check's words (ADR-0089 amendment 4, audit repository-2)
      if (!allTests && isUnsymmetricLayup(layup)) { setError(ENABLED.unsymmetric ?? "Use a layup that reads the same from both faces."); return; }
      if (needThickness && !thickness.trim()) { setError("Enter the cured ply thickness too."); return; }
      onApply(text.replace(/\s+/g, ""), { ...layupRows(layup), ...(needThickness ? { ply_thickness: thickness.trim() } : { ply_thickness: "" }) });
    }}>
      <input type="text" aria-label="Layup" placeholder="[45/0/-45/90]s" value={text} onChange={(e) => { setText(e.target.value); setError(""); }} autoComplete="off" />
      {needThickness ? <input type="text" aria-label={`Cured ply thickness (${length})`} placeholder={`ply thickness, ${length}`} inputMode="decimal" value={thickness}
        onChange={(e) => { setThickness(e.target.value); setError(""); }} className="chat-small-input" /> : null}
      <button type="submit" className="chat-primary">Use layup</button>
      {error ? <span className="chat-error" role="alert">{error}</span> : null}
    </form>
  );
}
