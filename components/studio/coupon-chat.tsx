"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Calculator, Check, CircleAlert, FlaskConical, Layers3, MessagesSquare, Play, RotateCcw, Sparkles, SlidersHorizontal, TableProperties } from "lucide-react";
import { allCouponTests, answerGeneral, answerResult, offeredHere, assistantInfo, couponValues, isActive, listCoupons, proposeRows, readResultRequest, sameResults, StudioError, type AssistantInfo, type CheckAnswer, type ImportedModel, type CouponSummary, type Fields,
  type GeneralAnswer, type JobStatus, type ProposalAnswer, type ResultAnswer, type UnreadPart } from "@/lib/studio-api";
import { confirmsFailure, contradictsFailure, failureAnswer, failureLines, failureVerdict, marginNote, plyWords, type FailureAnswer } from "@/lib/result-failure";
import { summaryAnswer, type SummaryQuantity } from "@/lib/result-summary";
import { factsOf, generalLines, headed, readAt, whyLines } from "@/lib/result-why";
import { isConditionOrLoad, termLines, type FeaTerm, type TermQuestion } from "@/lib/fea-terms";
import { appliedOf } from "@/lib/applied";
import { workingFor, workingOf, type FoundWorking } from "@/lib/result-working";
import dynamic from "next/dynamic";
import { couponOffer, couponRowsFrom, plateLines, plateOffer, plateWith, unreadLines } from "@/lib/proposals";
import { plateValues, regionsHere, type PlateLists } from "@/lib/studio-plate";
import { answerResultQuestion, comparisonNote, describeElement, extremeLines, extremeWords, questionFrom, RESULT_COLUMNS,
  resultOffer, resultUnit, thresholdVerdict, valueLines, type ElementFacts, type ResultExtremes, type ResultQuestion, type ResultValues } from "@/lib/result-question";
import { ProposalCard, UnreadList, type ProposalLine } from "./proposal-card";
import { CheckIssues } from "./check-fix";
import {
  blankForm, buildValues, exampleForm, fieldByLabel, formFromValues, libraryOptions, mergeRows, PLATE_TEST, UNIT_SYSTEMS, unitLabels, unitsOf, unitWords, type StudioForm,
} from "@/lib/studio-form";
import {
  applyMessage, COMMON_MATERIALS, couponLines, isBending, unitsNamed, labelOf, libraryConstants, LAYUP_CHOICES, layupNotation, layupRows, libraryThickness, LOAD_CHIPS,
  missingIn, nextStep, parseLayup, PUSH_CHIPS, SIZE_CHIPS, stepOfKey, switchUnits, TEST_CHOICES, type ChatStep,
} from "@/lib/studio-chat";
import { chatTool, toolNamed } from "@/lib/chat-tools";
import { ASKING, asksUnread, modelAsksResults, routeMessage, type SectionAsked } from "@/lib/chat-route";
import { aboutAnswer, checkTitle, unreadWords, type AboutTopic } from "@/lib/chat-about";
import { printed } from "@/lib/studio-colors";
import { answerStat, CRITERION_NAMES, modeWords } from "@/lib/studio-answer";
import { panel, panelOfKey, panelOfStep, panelToFix, type PanelId } from "@/lib/workspace-panels";
import { tab, TAB_OF_STEP, tabOfKey, tabToFix, type TabId } from "@/lib/model-tree";
import { revealPanel, showPanel } from "@/components/workspace/panels/step-panel";
import { takeHandoff } from "@/lib/handoff";
import { hasWork } from "@/lib/project-store";
import { saysMore, TARGET_TITLES } from "@/lib/work-intent";
import { SwitchAsk } from "@/components/workspace/switch-ask";
import { tabStorage, useProject } from "./project-context";
import { resultsOnPage } from "./use-imported-model";
import { runWhen } from "@/lib/run-history";
import { TOW_TEST } from "@/lib/studio-tow";
import { ENABLED, hiddenReason, isTestEnabled, isUnsymmetricLayup, understoodWithout, withoutHidden } from "@/lib/enabled-tests";
import { tensionValues } from "@/lib/tension-screen";
import { ANALYSIS_UNAVAILABLE, checkText, customerText, importProblemWords, runHeadline, runProblem, setWords, stepOfStage, verificationOf } from "@/lib/studio-copy";

const RUN_BY_KEY = "anisotropy.studio.run_by";

/** The typeset steps of a working (ADR-0103) load when one is first shown: the typesetter stays out of the workspace's first load. */
const WorkingSteps = dynamic(() => import("./working-steps").then((module) => module.WorkingSteps), {
  ssr: false, loading: () => <p className="chat-note" role="status">Typesetting the working…</p>,
});

/** `stage` marks an entry said while an imported model or a past run had the stage: the conversation about what is shown, which is all
 * the chat shows while it is (ADR-0109 amendment 1). */
type Entry = { stage?: boolean } & (
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; kind: "text"; title?: string; body?: ReactNode; tone?: "problem" }
  | { id: number; role: "assistant"; kind: "ask"; step: ChatStep | "reopen" }
  | { id: number; role: "assistant"; kind: "check"; answer: CheckAnswer; asked?: boolean }
  | { id: number; role: "assistant"; kind: "job"; job: string }
  | { id: number; role: "assistant"; kind: "result"; job: string }
  | { id: number; role: "assistant"; kind: "proposal"; answer: ProposalAnswer }
  // a value read from the results on the page (ADR-0099): the answer as read, the fields it was read from, and whether they were a preview
  | { id: number; role: "assistant"; kind: "values"; answer: ResultValues; from: Fields; preview: boolean; verdict?: string | null }
  // where a quantity is largest in those results (ADR-0100): stored values picked out, by the page's patterns or a model's reading
  | { id: number; role: "assistant"; kind: "extremes"; answer: ResultExtremes; from: Fields; preview: boolean; reader: "patterns" | "model"; verdict?: string | null }
  // the working behind the answer, as the package wrote it (ADR-0103): the chain asked for, the fields it is of, and whether they were a preview
  | { id: number; role: "assistant"; kind: "working"; found: Extract<FoundWorking, { kind: "chain" }>; from: Fields; preview: boolean }
  // which ply fails first, whether the coupon fails and at what loading: the package's own answer (ADR-0099 amendment 1)
  // `confirmed`: the message stated the answer back, right, and asked if it is so, so the answer opens with "Yes" (ADR-0099 amendment 3)
  | { id: number; role: "assistant"; kind: "failure"; found: FailureAnswer; from: Fields; preview: boolean; reader: "patterns" | "model"; confirmed: boolean; asked?: string }
  // what an element is and where it sits, said from the fields (ADR-0099 amendment 3)
  | { id: number; role: "assistant"; kind: "element"; answer: ElementFacts; from: Fields }
  // a question of why, answered in words from the results' fact sheet and our theory pages (ADR-0102)
  | { id: number; role: "assistant"; kind: "why"; answer: ResultAnswer; preview: boolean; place: string | null }
  // another section asked for while the coupon holds work: one tap to go, the coupon kept (ADR-0124)
  | { id: number; role: "assistant"; kind: "switch"; target: Switchable; carried: string });
/** The sections a coupon's chat opens on request (ADR-0124). */
type Switchable = "laminate" | "cad";
/** The project's own cards: a question, a check, a run and its results, a proposal. Their buttons act on the project. */
const PROJECT_KINDS = new Set(["ask", "check", "job", "result", "proposal"]);
type Without<T> = T extends unknown ? Omit<T, "id"> : never;
type NewEntry = Without<Entry>;

/** What another page handed over: a message typed on the home page, the start screen or another section (session storage, or ?prompt=
 * when storage is blocked), the message that set a blank FEA project up as a coupon (ADR-0124), and a library material (?material=),
 * each used once. */
function readHandoff(): { prompt: string; setUp: string; material: string } {
  const params = new URLSearchParams(window.location.search);
  const carried = takeHandoff(tabStorage());
  const prompt = carried.prompt || params.get("prompt") || "";
  const material = libraryOptions.some((m) => m.id === params.get("material")) ? params.get("material")! : "";
  if (params.has("prompt") || params.has("material")) {
    params.delete("prompt"); params.delete("material");
    window.history.replaceState(null, "", window.location.pathname + (params.size ? `?${params}` : ""));
  }
  return { prompt: prompt.trim().slice(0, 2000), setUp: carried.setUp, material };
}

function today(): string { return new Date().toISOString().slice(0, 10); }
function remembered(key: string): string { try { return window.localStorage.getItem(key) ?? ""; } catch { return ""; } }
function remember(key: string, value: string) { try { window.localStorage.setItem(key, value); } catch { /* storage blocked: the name is simply not kept */ } }
const materialName = (id: string) => libraryOptions.find((m) => m.id === id)?.name ?? id;
/** An estimate as a row value: four significant figures, written out (680000 psi, not 6.800e+5), so the row reads as typed. */
const estimated = (value: number) => String(Number(value.toPrecision(4)));
const libraryEntry = (id: string) => libraryOptions.find((m) => m.id === id);

/** Where an answer is on the model (ADR-0099): its element, its ply and face when it holds one row, and the first quantity asked for as
 * the field the model is coloured by. */
function placeOf(answer: ResultValues | ResultExtremes) {
  if (answer.kind === "extremes") { // the first quantity's overall extreme
    const block = answer.blocks[0], row = block.rows[block.best];
    return { element: row.element, ply: row.ply, face: row.face, field: RESULT_COLUMNS[block.column]?.field };
  }
  const one = answer.rows.length === 1 ? answer.rows[0] : null;
  return { element: answer.element, ply: one ? one.ply : null, face: one ? one.face : null, field: RESULT_COLUMNS[answer.columns[0]]?.field };
}
/** Where a first-ply failure is on the model: its element and ply, coloured by that ply's failure index in its criterion. */
const failurePlace = (row: FailureAnswer["row"]) => ({ element: row.element, ply: row.ply, face: row.face, field: "failure_index_ply", criterion: row.criterion });
const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1);

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

/** A suggestion that opens a panel on the left: the rows live there (ADR-0062, part 5); a step panel of the full form, or a tab of the
 * model tree (ADR-0111). */
function PanelLink({ id, children }: { id: PanelId | TabId; children: ReactNode }) {
  return <button type="button" data-panel={id} onClick={() => showPanel(id)}><SlidersHorizontal size={14} /> {children}</button>;
}

/** The coupon assistant (ADR-0055; ADR-0062, part 5): a conversation beside the panels, on the one project they share. It offers one-click
 * choices, reads a typed line into the rows, checks and runs the setup, and for anything else names the panel that asks for it. */
export function CouponChat({ apiBaseUrl, onSwitch }: {
  apiBaseUrl: string;
  /** Opens another section with the message carried (ADR-0124): Laminate, a stack under loads per unit width (ADR-0060), or CAD. */
  onSwitch?: (target: Switchable, carried: string) => void;
}) {
  const { project, form, setForm: storeForm, plate, setPlate, run: runner, restored, allTests, plates, picked, showPlace, imported, past, setProposed, versions } = useProject(); // the rows and the run live in the project (ADR-0062)
  const projectRef = useRef(project);
  projectRef.current = project;
  const lastSaid = useRef<string | null>(null); // the engineer's last message: the reason a change it led to is kept with its version (ADR-0113)
  const plateRef = useRef(plate); // a plate's supports and loads (ADR-0054), read when a message is sent and when the setup is checked
  plateRef.current = plate;
  // the results on the page: what a question about a value is answered from (ADR-0099); an imported model's while it is open (ADR-0105),
  // a past run's while one is (ADR-0109)
  const shown = resultsOnPage(runner, imported, past);
  /** What it takes to have results to ask about, said where a question finds none. */
  const resultsFirst = () => (shown.imported ? "This model has no results: import one that solves, then ask again."
    : shown.past ? "This run's results are not open yet. Ask again in a moment."
    : checked?.state === "ready" ? "Say “run”, then ask again." : "Finish the setup and run it, then ask again.");
  // the tension screen's chat (ADR-0090): the material and the layup, the rest chosen by the software; every test's steps with the switch on.
  // A ref, since the first question waits for the API's answer and is asked before the page renders it
  const simpleRef = useRef(!allTests);
  simpleRef.current = !allTests;
  // a plate goes with its supports and loads, every row sent, on the full form and on the model tree alike (ADR-0089 amendment 7)
  const valuesOf = (rows: StudioForm, lists: PlateLists = plateRef.current) => (simpleRef.current && rows.test !== PLATE_TEST ? tensionValues(rows)
    : buildValues(rows, rows.test === PLATE_TEST ? plateValues(lists) : undefined));
  /** Whether a plate's regions are offered to a message: every test is, or a plate is, and the coupon is one. */
  const platesRef = useRef(plates);
  platesRef.current = plates;
  const plateHere = () => formRef.current.test === PLATE_TEST && (allTests || platesRef.current);
  /** Whether every row of the coupon as it stands is offered (ADR-0089): the switch, or a founder's plate (amendment 7). */
  const offersAll = () => allTests || plateHere();
  const { checking, checked, job, fields, problem } = runner;
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
  // the thread of the talk about the results (ADR-0099 amendment 3): the last question answered, which a follow-up of a few words leans
  // on, and the number of the element last spoken of, which "it" stands for
  const thread = useRef<ResultQuestion | null>(null);
  const about = useRef<number | null>(null);
  const onStage = useRef(false); // whether an imported model or a past run has the stage, for the entries said while it does
  useEffect(() => { onStage.current = shown.readOnly; }, [shown.readOnly]);
  const add = useCallback((...items: NewEntry[]) => {
    const made = items.map((item) => ({ stage: onStage.current, ...item, id: nextId.current++ }) as Entry);
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
      add({ role: "assistant", kind: "text", stage: false, title: restored ? "Picked up where you left off" : "Picked up from the panels", // the project's, also when a past run opens with the page
        body: <p>Your inputs are kept. Here is what is still needed.</p> });
      proceed(start);
      return;
    }
    // a library material sent from its page, or a message typed on the home page, starts the conversation
    const handoff = readHandoff();
    if (handoff.setUp) { // a blank FEA project set up as a coupon (ADR-0124): the message that did it heads the talk, which reads on
      add(...(handoff.setUp === handoff.prompt ? [] : [{ role: "user", text: handoff.setUp } as NewEntry]),
        { role: "assistant", kind: "text", title: "Coupon test set up", body: <p data-testid="chat-set-up">The model tree on the left now holds a coupon&apos;s tabs. Ask anything about FEA here too.</p> });
    }
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

  // a model brought in as a file (ADR-0105): said once per answer, with what can be asked of it, or why it was not read or not solved
  const announced = useRef<ImportedModel | null>(null);
  useEffect(() => {
    const brought = imported.model;
    if (!imported.open || !brought || announced.current === brought) return;
    announced.current = brought;
    const why = importProblemWords(brought);
    if (brought.state === "solved") {
      add({ role: "assistant", kind: "text", title: "Model imported",
        body: <p data-testid="chat-imported" data-state="solved">{brought.name}: {brought.reading?.elements} elements{brought.reading?.layup ? `, ${brought.reading.layup}` : ""}, solved as the file states it.
          {" "}Ask about its results: “where is the stress highest?”, “why does it fail there?” or “show me the formula”.</p> });
    } else {
      add({ role: "assistant", kind: "text", tone: "problem", title: brought.state === "read" ? "Model read, not solved" : "File not read",
        body: <p data-testid="chat-imported" data-state={brought.state}>{brought.name}: {why}</p> });
    }
  }, [imported.open, imported.model, add]);

  // a past analysis opened again (ADR-0109): said once per run, with what can be asked of it
  const opened = useRef<string | null>(null);
  useEffect(() => {
    const job = past.job;
    if (!past.open || !job || !past.fields || opened.current === job.job_id) return;
    opened.current = job.job_id;
    add({ role: "assistant", kind: "text", title: "Past run opened",
      body: <p data-testid="chat-past">{job.coupon}, {runWhen(job.finished_at ?? job.started_at)}. Ask about its results: “which ply fails first?” or “where is the stress highest?”.</p> });
  }, [past.open, past.job, past.fields, add]);

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

  /** `asked` when the engineer asked whether it is ready ("is my setup ok?"): the answer then opens with Yes or No. */
  async function check(values: StudioForm, lists?: PlateLists, asked = false) {
    setActive(null);
    if (!apiBaseUrl) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "Analysis unavailable",
        body: <p>Analysis is not available on this page. The setup can be stated but not checked or run.</p> });
      return;
    }
    try {
      const answer = await runner.check(valuesOf(values, lists));
      add({ role: "assistant", kind: "check", answer, asked });
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
    void offeredHere(apiBaseUrl).then((offered) => {
      if (offered.all || (offered.plates && next.test === PLATE_TEST)) { proceedWith(next); return; } // a founder's plate (ADR-0089 amendment 7)
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
        body: allTests ? <><p>Pick the held and loaded regions under Boundary conditions and loads, or click an element on the model.</p>
          <Chips><PanelLink id="loads">Open Boundary conditions and loads</PanelLink></Chips></>
          : <><p>Say which edge or face is held and which is loaded, for example “fix the left edge and pull the right edge with 10 kN”, or click
            it on the model. Each goes under Boundary conditions or Loads on the left.</p>
          <Chips><PanelLink id="conditions">Open Boundary conditions</PanelLink><PanelLink id="loads">Open Loads</PanelLink></Chips></> });
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
    versions.attribute("you", echo);
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

  /** Another section asked for (ADR-0124): opened at once with the message carried when the coupon holds nothing of the engineer's,
   * asked once when it does; a wing is not here yet. */
  function openSection(target: SectionAsked, text: string) {
    if (target === "wing") {
      add({ role: "assistant", kind: "text", title: "Wing analysis is not here yet", body: <p data-testid="chat-kind-missing">It is being built. This project stays a coupon test.</p> });
      return;
    }
    if (!onSwitch) return;
    const carried = saysMore(text) ? text : "";
    if (!hasWork(projectRef.current)) { onSwitch(target, carried); return; }
    setActive(null);
    add({ role: "assistant", kind: "switch", target, carried });
  }

  function startOver() {
    setProposed(null);
    const fresh = { ...blankForm(unitsOf(formRef.current)), date: today(), filled_by: formRef.current.filled_by };
    versions.attribute("you", "Start over");
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
    const id = allTests ? panelOfStep(step) : TAB_OF_STEP[step]; // the full form's step panel, or the model tree's tab (ADR-0111)
    const title = allTests ? panel(panelOfStep(step)).title : tab(TAB_OF_STEP[step]).title;
    const named = toolNamed(text) === "coupon";
    add(...(echoed ? [] : [{ role: "user", text } as NewEntry]), { role: "assistant", kind: "text", title: "Not sure what to change",
      body: <div data-testid="chat-redirect" data-panel={id}>
        <p>{named ? "This workspace sets up and solves test coupons. " : ""}
          {step === "review" ? "Everything is stated: say “check”." : `Next: ${QUESTIONS[step].title.toLowerCase().replace(/\?$/, "")} (${title}).`} Try “[0/90]2s”, “AS4/8552” or “10 kN”.</p>
        <Chips><PanelLink id={id}>Open {title}</PanelLink>{step !== "review" ? <button type="button" onClick={() => ask(step)}>Ask me here</button> : null}</Chips>
      </div> });
  }

  /** A question about a value of the results (ADR-0099), answered from the fields the page shows: the page reads the place and the
   * quantity, looks the rows up and prints them as the probe table does. The question is the page's own reading, or a model's in the
   * same typed form (ADR-0100); either way no number is typed by a model. `from` is the results the question was asked of. */
  function answerQuestion(text: string, question: ResultQuestion, from: { fields: Fields | null; live: boolean } = shown, reader: "patterns" | "model" = "patterns", echoed = false) {
    if (!echoed) add({ role: "user", text });
    if (!from.fields) {
      add({ role: "assistant", kind: "text", title: "No results to read yet",
        body: <p data-testid="chat-value-none">Stresses and strains come from a solved model. {resultsFirst()}</p> });
      return;
    }
    const answer = answerResultQuestion(from.fields, question, picked);
    if (answer.kind === "ask" || answer.kind === "refused") {
      add({ role: "assistant", kind: "text", tone: answer.kind === "refused" ? "problem" : undefined, title: answer.kind === "ask" ? "Which element?" : "Not in this model",
        body: <p data-testid={`chat-value-${answer.kind}`}>{answer.kind === "ask" ? answer.text.replace(/^Which element\? /, "") : answer.text}</p> });
      return;
    }
    thread.current = question;
    about.current = null; // the talk has moved from an element to a value: "it" is no longer the element
    // "is ply 2 above 1000 MPa?" opens with Yes or No, from the one value the answer gives (ADR-0099 amendment 4)
    const column = answer.kind === "extremes" ? answer.blocks[0]?.column : answer.columns[0];
    const verdict = column ? thresholdVerdict(text, answer, resultUnit(from.fields, column), printed) : null;
    if (answer.kind === "extremes") add({ role: "assistant", kind: "extremes", answer, from: from.fields, preview: from.live, reader, verdict });
    else add({ role: "assistant", kind: "values", answer, from: from.fields, preview: from.live, verdict });
    showPlace(placeOf(answer));
  }

  /** The reaction, the largest displacement or the modulus of the result (ADR-0099 amendment 4), as the result card prints it. */
  function answerSummary(text: string, quantity: SummaryQuantity, from: Fields) {
    const said = summaryAnswer(from, quantity, printed);
    add({ role: "user", text }, { role: "assistant", kind: "text", title: said.title, body: (
      <div data-testid="chat-summary" data-quantity={quantity}>
        {said.lines.map((line, i) => <p key={line} className={i ? "chat-note" : undefined}>{line}</p>)}
      </div>
    ) });
  }

  /** What an element is, or where one sits (ADR-0099 amendment 3): said from the fields, in place of a question back about quantities.
   * "It" is the element last spoken of, else the one clicked; with neither, what elements are in general. */
  function answerElement(text: string, asked: number | "picked" | "last" | null, from: Fields) {
    const which = asked === "last" ? about.current : asked;
    const answer = describeElement(from, which, picked);
    add({ role: "user", text });
    if (answer.kind === "refused") {
      add({ role: "assistant", kind: "text", tone: "problem", title: "Not in this model", body: <p data-testid="chat-value-refused">{answer.text}</p> });
      return;
    }
    if (answer.element !== null && answer.label) {
      about.current = Number(answer.label.split(".").pop());
      showPlace({ element: answer.element, ply: null, face: null });
    }
    add({ role: "assistant", kind: "element", answer, from });
  }

  /** A loose question, read by the model into the same typed question (ADR-0100) while results are on the page and the setup's own
   * patterns read nothing in it. True when the message was answered here; false when it asks nothing of the results, so the setup's
   * reading goes on. The model is shown the offer alone, never a result. */
  async function readQuestionWithModel(text: string): Promise<boolean> {
    const from = shown;
    if (!from.fields || !modelAsksResults(text, formRef.current, true)) return false;
    let reading;
    try { reading = await readResultRequest(apiBaseUrl, resultOffer(from.fields, text, picked)); }
    catch { return false; } // no answer: the setup's reading says so once, as it does today
    if (reading.request?.kind === "failure") { answerFailure(text, from, "model", true); return true; }
    const question = reading.request ? questionFrom(reading.request) : null;
    if (question) { answerQuestion(text, question, from, "model", true); return true; }
    const back = customerText(reading.question); // the product's own words (ADR-0091), or nothing
    if (!back) return false;
    add({ role: "assistant", kind: "text", title: "One question", body: <p data-testid="chat-value-question">{back}</p> });
    return true;
  }

  /** A question of failure (ADR-0099 amendment 1): which ply fails first, whether the coupon fails, at what loading. The answer is the
   * package's own (ADR-0085), in the gauge section where the coupon has one; the page's patterns or a model read only that it was asked. */
  function answerFailure(text: string, from: { fields: Fields | null; live: boolean } = shown, reader: "patterns" | "model" = "patterns", echoed = false) {
    if (!echoed) add({ role: "user", text });
    const found = from.fields ? failureAnswer(from.fields, text) : null;
    if (!from.fields || !found) {
      add({ role: "assistant", kind: "text", title: "No answer to read yet",
        body: <p data-testid="chat-failure-none">{!from.fields ? `Which ply fails first comes from a solved model. ${resultsFirst()}`
          : "This result carries no first-ply failure. Run the analysis again, then ask."}</p> });
      return;
    }
    add({ role: "assistant", kind: "failure", found, from: from.fields, preview: from.live, reader, confirmed: confirmsFailure(text, found, printed), asked: text });
    showPlace(failurePlace(found.row));
  }

  /** A question about the results that nothing here read: what can be asked, in place of a guess at the setup. */
  function unread(text: string, echoed = false) {
    const words = unreadWords(!!shown.fields); // with no results, what can be asked of the setup (ADR-0121 amendment 2)
    add(...(echoed ? [] : [{ role: "user", text } as NewEntry]), { role: "assistant", kind: "text", title: words.title,
      body: <p data-testid="chat-value-unread">{words.text}</p> });
  }

  /** Who the assistant is, the setup's units, whether inches or a material of one's own are offered, which layup, what a coupon needs,
   * whether von Mises suits a ply (ADR-0121 amendment 2): fixed words, and nothing changes. Another unit system named comes with its switch. */
  function answerAbout(text: string, topic: AboutTopic) {
    const said = aboutAnswer(topic, text, { form: formRef.current, results: !!shown.fields, readOnly: shown.readOnly });
    const named = topic === "units-other" ? unitsNamed(text) : null;
    add({ role: "user", text }, { role: "assistant", kind: "text", title: said.title, body: (
      <div data-testid="chat-about" data-topic={topic}>
        {said.lines.map((line) => <p key={line}>{line}</p>)}
        {named && named !== unitsOf(formRef.current) ? <Chips><button type="button" onClick={() => switchTo(named)}>Switch to {unitWords(named)}</button></Chips> : null}
      </div>
    ) });
  }

  /** A question of why, answered in words (ADR-0102): the API puts the shown result's fact sheet beside the sections of our theory pages
   * the question finds, and keeps a model's answer only when every number in it is the results' or the question's. No row changes. */
  async function answerWhy(text: string, facts: Record<string, unknown>, preview: boolean) {
    add({ role: "user", text });
    setReading(true);
    let answer: ResultAnswer | null = null;
    try { answer = await answerResult(apiBaseUrl, text, facts); } catch { /* said below */ } finally { setReading(false); }
    if (answer) add({ role: "assistant", kind: "why", answer, preview, place: readAt(facts) });
    else add({ role: "assistant", kind: "text", title: "No answer right now", body: <p data-testid="chat-why-failed">That question could not be answered right now. Try again in a moment.</p> });
  }

  /** What something is or means, asked with no result on the page (ADR-0121 amendment 5): answered in words from our theory pages by
   * the reader FEA's own assistant asks before a setup (ADR-0124), the first sentence as the heading and the sections folded under
   * Details, as an answer of why is shown (ADR-0102 amendment 1). Nothing in the setup changes. */
  async function answerMeaning(text: string) {
    add({ role: "user", text });
    setReading(true);
    let answer: GeneralAnswer | null = null;
    try { answer = await answerGeneral(apiBaseUrl, text, []); } catch { /* said below */ } finally { setReading(false); }
    if (!answer) {
      add({ role: "assistant", kind: "text", title: "No answer right now", body: <p data-testid="chat-general-failed">That question could not be answered right now. Try again in a moment.</p> });
      return;
    }
    const { prose, sources } = generalLines(answer); // in the product's own words (ADR-0091)
    const covered = answer.covered && sources.length > 0;
    const { heading, more } = prose.length ? headed(prose, "Answered in words") : { heading: "Not in our theory pages yet", more: [] };
    add({ role: "assistant", kind: "text", title: heading, body: (
      <div data-testid="chat-general" data-covered={covered}>
        {more.map((line, i) => <p key={i} data-testid="chat-general-sentence">{line}</p>)}
        {!prose.length ? <p>Ask about the setup instead, for example “is it ready to run?”.</p> : covered ? <p className="chat-note">From our theory pages.</p> : null}
        {covered ? <details><summary>Details</summary><p data-testid="chat-general-sources">Our theory pages: {sources.join("; ")}.</p></details> : null}
      </div>
    ) });
  }

  /** The working behind the answer (ADR-0103), when the engineer asks for it: the package's own steps for the criterion named, else the
   * earliest. No model reads the request and nothing is computed here. */
  function showWorking(text: string) {
    const from = shown;
    add({ role: "user", text });
    const found = workingFor(from.fields, text);
    if (!from.fields || !found) {
      add({ role: "assistant", kind: "text", title: "No working to show yet",
        body: <p data-testid="chat-working-none">{!from.fields ? `The working is written with a solved model. ${resultsFirst()}`
          : "This result carries no working. Run the analysis again, then ask."}</p> });
      return;
    }
    if (found.kind === "not-worked") {
      add({ role: "assistant", kind: "text", title: "No working for that criterion yet",
        body: <p data-testid="chat-working-none">The working of {found.name} is not written yet. Ask for {found.others.join(" or ")}.</p> });
      return;
    }
    add({ role: "assistant", kind: "working", found, from: from.fields, preview: from.live });
  }

  /** What the model on the page holds: an imported model's, or the checked setup's. A past run is shown without one (ADR-0109). */
  function appliedNow() {
    const preview = shown.imported ? imported.model?.preview ?? null : shown.past ? null : checked?.preview ?? null;
    return preview ? appliedOf(preview) : null;
  }

  /** A question of what an Abaqus word means, answered from the glossary (ADR-0110): the word as the heading, what it is in one line, what
   * Anisotropy does with it in a second. "What are the boundary conditions?" lists this model's own. */
  function answerTerm(text: string, asked: TermQuestion) {
    if (asked.ofModel) { answerApplied(text, asked.term, null); return; }
    const lines = termLines(asked);
    add({ role: "user", text }, { role: "assistant", kind: "text", title: lines.title, body: (
      <div data-testid="chat-term" data-term={asked.term.id}>
        <p><strong>{lines.means}</strong></p>
        <p className="chat-note">{lines.here}</p>
      </div>
    ) });
  }

  /** This model's boundary conditions or loads, one line each as the list under the model says them (ADR-0110). `title` replaces the
   * heading when the message asked to add one where the setup fixes them. */
  function answerApplied(text: string, term: FeaTerm, title: string | null) {
    const applied = appliedNow();
    const loads = term.id === "load" || ["concentrated-force", "pressure", "shell-edge-load"].includes(term.id);
    const both = title !== null; // a request to add one is answered with everything the setup holds
    const lines = applied ? [...(!loads || both ? applied.conditions.map((c) => c.words) : []), ...(loads || both ? applied.loads.map((l) => l.words) : [])] : [];
    const onPlate = formRef.current.test === PLATE_TEST && !shown.readOnly;
    const note = shown.imported ? "They are the file’s own, so nothing is changed by talking."
      : shown.past ? "A past run is shown without them. Choose “Use these inputs” to see them."
      : !applied ? "They are drawn on the model and listed under it once the setup is checked."
      : onPlate ? "Add one by naming a region, for example “fix the left edge” or “10 kN tension on the right edge”."
      : `A coupon’s are set by its test, as in the test machine. Change the load under ${allTests ? "Boundary conditions and loads" : "Loads"}${allTests ? "; for boundary conditions of your own, choose Plate" : plates ? "; for boundary conditions of your own, choose Plate under Test" : ""}.`;
    add({ role: "user", text }, { role: "assistant", kind: "text", title: title ?? (loads ? "Loads" : "Boundary conditions"), body: (
      <div data-testid="chat-applied" data-term={term.id}>
        {lines.length ? <ul className="chat-understood">{lines.map((line) => <li key={line}>{line}</li>)}</ul> : null}
        <p className="chat-note">{note}{lines.length ? " Each is drawn on the model and listed under it." : ""}</p>
      </div>
    ) });
  }

  /** A request to add something the setup does not take from a message (ADR-0110): a coupon's boundary conditions and loads are its test's,
   * a model comes partitioned, there is one step and no interaction. Said once; no row changes. */
  function answerSetup(text: string, term: FeaTerm) {
    if (isConditionOrLoad(term)) {
      const onPlate = formRef.current.test === PLATE_TEST;
      if (onPlate) { // a plate with no model to read the message: its panel takes them
        add({ role: "user", text }, { role: "assistant", kind: "text", title: allTests ? "Add it under Boundary conditions and loads" : "Add it on the model tree", body: (
          <div data-testid="chat-setup" data-term={term.id}><p>Pick the region and the directions it holds, or the force or pressure on it. Each is drawn on the model as you add it.</p>
            <Chips>{allTests ? <PanelLink id="loads">Open Boundary conditions and loads</PanelLink>
              : <><PanelLink id="conditions">Open Boundary conditions</PanelLink><PanelLink id="loads">Open Loads</PanelLink></>}</Chips></div>
        ) });
        return;
      }
      answerApplied(text, term, "Set by the test");
      return;
    }
    const regions = formRef.current.test === PLATE_TEST ? plateOffer(formRef.current, plateRef.current, []).regions.map((r) => r.name) : [];
    const said = term.id === "partition" && regions.length
      ? { title: "Already partitioned", body: `The plate comes split into its regions: ${regions.join(", ")}. Name one or click it on the model.` }
      : term.id === "partition" ? { title: "Already partitioned", body: term.here }
      : term.id === "step" ? { title: "One static step", body: term.here }
      : { title: "Not offered yet", body: term.here };
    add({ role: "user", text }, { role: "assistant", kind: "text", title: said.title, body: <p data-testid="chat-setup" data-term={term.id}>{said.body}</p> });
  }

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    lastSaid.current = text;
    const current = entries.find((e) => e.id === active);
    // who answers is the page's fixed order (ADR-0121), in one place the question banks try (lib/chat-route.ts)
    const routed = routeMessage(text, {
      form: formRef.current, readOnly: shown.readOnly, results: !!shown.fields, facts: !!factsOf(shown.explanation), api: !!apiBaseUrl,
      modelReads: !!model?.proposes, onPlate: onPlateNow, ready: checked?.state === "ready", about: about.current, thread: thread.current, sections: !!onSwitch,
      step: current && current.role === "assistant" && current.kind === "ask" ? current.step : null,
    });
    switch (routed.route) {
      case "start-over": add({ role: "user", text }); startOver(); return;
      case "term": answerTerm(text, routed.term); return;
      case "about": answerAbout(text, routed.topic); return;
      case "working": showWorking(text); return;
      case "why": void answerWhy(text, factsOf(shown.explanation)!, shown.live); return;
      case "why-none":
        add({ role: "user", text }, { role: "assistant", kind: "text", title: "No results to answer from yet",
          body: <p data-testid="chat-why-none">{shown.fields ? "This result cannot be explained in words. Run the analysis again, then ask."
            : `A question of why is answered from a solved model. ${resultsFirst()}`}</p> });
        return;
      case "summary": answerSummary(text, routed.quantity, shown.fields!); return;
      case "value": case "follow-up": answerQuestion(text, routed.question); return;
      case "failure": answerFailure(text); return;
      case "element": answerElement(text, routed.element, shown.fields!); return;
      case "read-only": void readOfImported(text); return;
      case "ready": add({ role: "user", text }); void check(formRef.current, undefined, true); return;
      case "setup-fixed": answerSetup(text, routed.term); return;
      case "run": void run(); return;
      case "check": add({ role: "user", text }); void check(formRef.current); return;
      case "full-form": add({ role: "user", text }); showPanel("advanced"); return;
      case "section": add({ role: "user", text }); openSection(routed.target, text); return; // at once when the coupon holds no work, else one tap (ADR-0124)
      case "name": answer(text, { filled_by: text }); return;
      case "general": void answerMeaning(text); return;
      case "model": void readWithModel(text); return;
      case "unread": unread(text); return;
      case "patterns": readWithPatterns(text); return;
    }
  }

  /** A message while an imported model (ADR-0105) or a past run (ADR-0109) has the stage that the page's own patterns read no question
   * in: a model may still read it as a question of the results (ADR-0100). Anything else is answered once: what is shown is read as it
   * stands, so nothing is changed by talking, and the coupon's rows behind it are left alone. */
  async function readOfImported(text: string) {
    add({ role: "user", text });
    if (model?.proposes && apiBaseUrl && shown.fields) {
      setReading(true);
      try { if (await readQuestionWithModel(text)) return; } catch { /* said below */ } finally { setReading(false); }
    }
    if (shown.fields && ASKING.test(text)) { unread(text, true); return; }
    if (shown.past) {
      add({ role: "assistant", kind: "text", title: "A past run is shown as it was solved",
        body: <p data-testid="chat-past-read-only">Nothing is changed by talking here. Ask about its results, or choose “Use these inputs” to change them and run again.</p> });
      return;
    }
    add({ role: "assistant", kind: "text", title: "An imported model is read as it stands",
      body: <p data-testid="chat-import-read-only">Its boundary conditions, loads and mesh are the file’s, so nothing is changed by talking yet. Ask about its results, or go back to the coupon to set one up.</p> });
  }

  /** The model reads the message into the rows on offer (ADR-0088); what the source guard keeps waits in a card for the engineer's tick.
   * With nothing kept, or no answer, the page's own patterns read it, as they do with no model. */
  async function readWithModel(text: string) {
    add({ role: "user", text });
    setReading(true);
    let answer: ProposalAnswer | null = null;
    let failed: string | null = null;
    try { if (await readQuestionWithModel(text)) { setReading(false); return; } } catch { /* the setup's reading goes on */ }
    // a plate also offers its regions and the place clicked, so "hold this edge" and "10 kN in tension here" can be read (ADR-0101)
    const onPlate = plateHere() ? { plate: plateOffer(formRef.current, plateRef.current, here().map((r) => r.name)) } : {};
    try { answer = await proposeRows(apiBaseUrl, { product: "coupon", message: text, conditions: [], ...couponOffer(formRef.current, offersAll()), ...onPlate }); }
    catch (error) { failed = error instanceof StudioError ? error.message : "the model did not answer"; }
    finally { setReading(false); }
    if (answer && (answer.proposals.length || answer.question || answer.supports.length || answer.loads.length)) {
      add({ role: "assistant", kind: "proposal", answer });
      // a plate's proposed boundary conditions and loads are drawn dashed on the model until they are applied (ADR-0110)
      setProposed(answer.supports.length || answer.loads.length ? { supports: answer.supports, loads: answer.loads } : null);
      return;
    }
    const reason = failed ?? answer?.reason;
    if (reason) { // a model that does not answer is not asked again this session: each message would wait for it and fail the same way
      setModel(null);
      add({ role: "assistant", kind: "text", title: "Reading simple phrases only",
        body: <p className="chat-note">Free-text reading is unavailable right now, so short phrases like the examples are read from here on. Reload to try again.</p> });
    }
    const parts = answer?.unread ?? [];
    if (asksUnread(text, !!shown.fields)) unread(text, true); // a question nothing read is not a row of the setup (ADR-0121 amendment 2)
    else readWithPatterns(text, true, parts.length ? () => notUsed(parts) : undefined);
  }

  /** What the model could not use of a message the patterns read nothing of (ADR-0088 amendment 1): the engineer's words, each with why. */
  function notUsed(parts: UnreadPart[]) {
    add({ role: "assistant", kind: "text", title: "Read, but nothing to enter",
      body: <div data-testid="chat-not-used"><UnreadList lines={unreadLines(parts)} /></div> });
  }

  /** The proposals the engineer ticked go into the rows, and the conversation moves on. A plate's ticked supports and loads go into its
   * lists (ADR-0101), and the setup is checked with them, so the model on the page shows what is now held and loaded. */
  function applyProposals(answer: ProposalAnswer, ticked: Set<string>) {
    setProposed(null); // applied: what was ticked is drawn solid from the next check
    const { rows, notes } = couponRowsFrom(answer.proposals.filter((p) => ticked.has(p.key)));
    if (notes.length) add({ role: "assistant", kind: "text", tone: "problem", title: "Not applied", body: <ul className="chat-understood">{notes.map((n) => <li key={n}>{n}</li>)}</ul> });
    const lists = plateWith(plateRef.current, answer, ticked);
    const onPlate = lists.supports.length > plateRef.current.supports.length || lists.loads.length > plateRef.current.loads.length;
    if (!Object.keys(rows).length && !onPlate) return;
    const next: StudioForm = Object.keys(rows).length ? mergeRows(formRef.current, rows) : formRef.current; // a new test clears a standard it is not under (ADR-0072)
    versions.attribute("assistant", lastSaid.current); // applied from the message, ticked by the engineer
    if (next !== formRef.current) setForm(next);
    if (onPlate) setPlate(lists);
    clearRun();
    if (onPlate) revealTab(allTests ? "loads" : lists.supports.length > plateRef.current.supports.length ? "conditions" : "loads");
    else reveal(Object.keys(rows));
    if (onPlate && next.test === PLATE_TEST) void check(next, lists);
    else proceed(next);
  }

  /** The plate's own regions the clicked element belongs to, on the mesh the page shows: what "here" means in a message (ADR-0101). */
  function here() {
    return regionsHere(picked, shown.fields?.mesh ?? checked?.preview?.mesh ?? null, formRef.current);
  }

  /** The card's lines: each value with the unit it goes in with, and how it was written when the API converted it within the system. */
  function proposalLines(answer: ProposalAnswer): ProposalLine[] {
    return [...answer.proposals.map((p) => ({
      id: p.key, label: p.label.replace(/ \([^)]*\)$/, ""), value: p.key === "library" ? materialName(p.value) : p.value, unit: p.unit ?? "", quote: p.quote,
      note: p.written_unit && p.written_unit !== p.unit ? `written ${p.written_value} ${p.written_unit}` : undefined,
    })), ...plateLines(answer)];
  }

  /** The message read by the page's fixed patterns (ADR-0055); `echoed` when the user's words are already in the conversation. `nothing`
   * answers in place of the pointer to the next panel when the patterns read none of it (what the model could not use, amendment 1). */
  function readWithPatterns(text: string, echoed = false, nothing?: () => void) {
    const you: NewEntry[] = echoed ? [] : [{ role: "user", text }];
    const read = applyMessage(formRef.current, text);
    const { rows, notes: hiddenNotes, dropped } = withoutHidden(read.rows, offersAll()); // what the studio does not offer yet stays out (ADR-0089)
    const understood = understoodWithout(read.understood, dropped);
    const note = read.note;
    if (hiddenNotes.length) {
      add(...you, { role: "assistant", kind: "text", tone: "problem", title: "Not offered yet",
        body: <ul className="chat-understood" data-testid="chat-not-available">{hiddenNotes.map((n) => <li key={n}>{n}</li>)}</ul> });
      if (!understood.length) return;
      you.length = 0;
    }
    if (!understood.length) {
      if (note) add(...you, { role: "assistant", kind: "text", title: unitsNamed(text) ? "Another unit system" : "Nothing to change yet", tone: "problem", body: <p>{note}</p> });
      else if (nothing) nothing();
      else redirect(text, echoed);
      return;
    }
    add(...you, { role: "assistant", kind: "text", title: "Got it", body: <>
      <ul className="chat-understood">{understood.map((u) => <li key={u}><Check size={13} /> {u}</li>)}</ul>{note ? <p className="chat-note">{note}</p> : null}</> });
    const next: StudioForm = mergeRows(formRef.current, rows); // a new test clears a standard it is not under (ADR-0072)
    versions.attribute("assistant", text);
    setForm(next); clearRun();
    reveal(Object.keys(rows));
    proceed(next);
  }

  /** Opens, on the left, the panel or tab a message just changed and marks it (ADR-0111): the change is seen where it lives. */
  function reveal(keys: string[]) {
    const target = keys.map((key) => (allTests ? panelOfKey(key) : tabOfKey(key))).find((id) => id !== null);
    if (target) revealTab(target);
  }
  const revealTab = (id: string) => { window.setTimeout(() => revealPanel(id), 0); };

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
              {onSwitch ? (
                <button type="button" className="chat-choice chat-choice-wide" data-testid="laminate-choice" onClick={() => { add({ role: "user", text: TARGET_TITLES.laminate }); openSection("laminate", ""); }}>
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
            <Chips><PanelLink id={allTests ? "layup" : "material"}>My own constants, under {allTests ? "Layup and material" : "Material"}</PanelLink></Chips>
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
            <PanelLink id={allTests ? "layup" : "material"}>Measured values, under {allTests ? "Layup and material" : "Material"}</PanelLink>
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
            {allTests ? <Chips><PanelLink id="layup">Ply by ply, under Layup and material</PanelLink></Chips> : null}
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
            <PanelLink id="loads">Another travel, under Boundary conditions and loads</PanelLink>
          </Chips>
        ) : (
          <>
            <p className="chat-note">Boundary condition: the bottom grip is fixed. Load: the top grip {form.test === "unnotched compression" ? "pushes" : "pulls"} along the coupon.</p>
            <Chips>
              {(LOAD_CHIPS[units] ?? []).map((chip) => (
                <button type="button" key={chip.words} onClick={() => answer(chip.words.replace(/^(\w+) /, "$1 of "), { control: chip.control, value: chip.value })}>{chip.words}</button>
              ))}
              <PanelLink id="loads">Another load, under {allTests ? "Boundary conditions and loads" : "Loads"}</PanelLink>
            </Chips>
          </>
        );
      case "name":
        return <Chips><PanelLink id="run">Enter it under Run</PanelLink></Chips>;
      case "review":
        return null;
    }
  }

  function checkMessage(result: CheckAnswer, latest: boolean, asked = false): ReactNode {
    const items = result.checklist.items;
    const blocking = items.filter((i) => i.state === "fail" || i.state === "missing");
    const warnings = items.filter((i) => i.state === "warn");
    const passed = items.filter((i) => i.state === "pass").length;
    const stepsFor = (rows: string[]) => [...new Set(rows.map((label) => stepOfKey(fieldByLabel[label]?.key ?? "")))];
    const fixLink = (item: CheckAnswer["checklist"]["items"][number], word = "Fix under") => {
      const target = allTests ? panelToFix(item) : tabToFix(item); // the full form's step panel, or the model tree's tab (ADR-0111)
      const title = target ? (allTests ? panel(target as PanelId).title : tab(target as TabId).title) : "";
      const step = stepsFor(item.rows).find((s): s is ChatStep => s !== null);
      return target ? <button type="button" className="chat-link" data-panel={target} onClick={() => showPanel(target)}>{word} {title}</button>
        : step ? <button type="button" className="chat-link" onClick={() => ask(step)}>Fix</button> : null;
    };
    return (
      <div data-testid="chat-check" data-state={result.state}>
        <h4>{checkTitle(result.state === "ready", blocking.length, asked)}</h4>
        <p>{passed} of {items.length} checks passed.</p>
        {blocking.length ? (
          // each item takes its rows in place on the latest check (ADR-0062 amendment 2); its link still opens the panel that holds them
          <CheckIssues items={blocking} form={form} units={unitsOf(form)} live={latest && !checking} allTests={allTests} onApply={(rows, echo) => answer(echo, rows)}
            link={(item) => fixLink(item)} />
        ) : null}
        {warnings.length ? (
          <ul className="chat-issues chat-warnings">
            {/* a warning says where it is dealt with, as an item to fix does (ADR-0111 amendment 2) */}
            {warnings.map((item) => <li key={item.id}><CircleAlert size={14} /> <span><strong>{item.label}:</strong> {checkText(item)} {fixLink(item, "Open")}</span></li>)}
          </ul>
        ) : null}
        <details className="chat-details"><summary>All checks</summary>
          <ul className="chat-allchecks">{items.map((i) => <li key={i.id} data-state={i.state}>{i.state === "pass" ? "✓" : i.state === "warn" ? "!" : "✕"} {i.label}: {checkText(i)}</li>)}</ul>
        </details>
        {latest && result.state === "ready" ? (
          <div className="chat-actions">
            <button type="button" className="chat-primary" onClick={run} disabled={isActive(job?.state)} data-testid="chat-run"><Play size={14} /> Run analysis</button>
            <button type="button" className="chat-secondary" onClick={() => showPanel(allTests ? "mesh" : "geometry")}><SlidersHorizontal size={14} /> Edit the setup</button>
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
    const stat = answerStat(fields, printed); // the answer the page leads with (ADR-0085); a result written before it keeps the whole model's first failure
    const check = job ? verificationOf(job.result, s.calculix ?? null, !allTests) : null;
    return (
      <div data-testid="chat-result">
        <h4>Results</h4>
        <div className="chat-stats">
          <div><span>Reaction</span><strong data-testid="chat-reaction">{printed(Math.abs(s.reaction.value))} {lab.force}</strong><small>{s.reaction.sense}, {setWords(s.reaction.set)}</small></div>
          <div><span>Largest displacement</span><strong>{printed(s.max_displacement.value)} {lab.length}</strong><small>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}</small></div>
          {stat ? (
            <div className={stat.fails ? "chat-stat-bad" : undefined} data-testid="chat-result-answer" data-fails={stat.fails}><span>First-ply failure</span><strong>{stat.verdict}</strong>
              <small>R = {stat.factor}, {stat.facts}</small></div>
          ) : earliest ? (
            <div className={earliest.factor < 1 ? "chat-stat-bad" : undefined}><span>First-ply failure</span><strong>R = {printed(earliest.factor)}</strong>
              <small>{CRITERION_NAMES[s.earliest ?? ""] ?? s.earliest}, ply {earliest.ply} · {earliest.angle}°</small></div>
          ) : <div><span>First-ply failure</span><strong>–</strong><small>no criterion selected</small></div>}
        </div>
        {stat ? (stat.outside ? <p className="chat-note" data-testid="chat-result-outside">{stat.outside}</p> : null)
          : earliest?.touches_grip ? <p className="chat-note">The first failure is at a grip edge.</p> : null}
        {check ? <p className={check.verified ? "chat-ok" : "chat-note"} data-testid="chat-result-line">{check.verified ? <Check size={13} /> : null} {check.line}</p> : null}
        {job && job.state !== "done" ? <p className="chat-note">{runHeadline(job)}{job.state !== "running" ? "."
          : stepOfStage(job.stage) === "report" ? "…" : job.result ? ". The report follows." : "…"}</p> : null}
        <p className="chat-note" data-testid="chat-ask-hint">Ask for a value: “stress in ply {earliest?.ply ?? 1} at element {(earliest?.label ?? fields.mesh.element_labels[0] ?? "1").split(".").pop()}”, click an element and ask “strain here”, or ask “where is the shear stress highest?”.</p>
        <Chips>
          {workingOf(fields) ? <button type="button" data-testid="chat-result-working" onClick={() => showWorking("Show the working")}>Show the working</button> : null}
          <button type="button" onClick={() => ask("layup")}>Change the layup</button>
          <button type="button" onClick={() => ask("loading")}>Change the load</button>
          <button type="button" onClick={() => ask("material")}>Try another material</button>
          <button type="button" onClick={startOver}>New coupon</button>
        </Chips>
      </div>
    );
  }

  /** The values of an answer (ADR-0099): one value as a sentence, more as a table of the plies asked for, with the place, how the values
   * are taken, and whether they are a preview's. Show frames the place while the results it was read from are still the page's. */
  function valuesMessage(entry: Extract<Entry, { kind: "values" }>): ReactNode {
    const { answer, from, preview } = entry;
    const lab = from.labels;
    const lines = valueLines(answer, resultUnit(from, answer.columns[0]), printed);
    const faces = answer.rows.some((r) => r.face);
    const current = sameResults(shown.fields, from);
    const one = answer.rows.length === 1 ? answer.rows[0] : null;
    const read = [...new Set(answer.rows.map((r) => r.ply))]; // the plies read: one, some (a comparison) or every one
    const sets = answer.sets.map((name) => setWords(name) === name ? `${name} set` : setWords(name).replace(/^the /, "")); // a set with no words of its own is named as a set
    const centre = answer.place === "gauge centre";
    // at the gauge centre the place is already said; the sets it belongs to would say it twice
    const glance = [...(lines ? lines.facts : centre ? ["gauge centre"] : []), ...(centre ? [] : sets), ...(preview ? ["preview, run the analysis to verify"] : [])];
    const caution = comparisonNote(answer.columns);
    return (
      <div data-testid="chat-values" data-element={answer.label} data-place={answer.place} data-source={preview ? "live" : "run"}>
        {entry.verdict ? <h4 data-testid="chat-value-verdict">{entry.verdict}</h4> : null}
        {lines ? (entry.verdict ? <p data-testid="chat-value"><strong>{lines.headline}</strong></p> : <h4 data-testid="chat-value">{lines.headline}</h4>)
          : <h4>Element {answer.label}{one ? `, ply ${one.ply} (${one.angle}°)` : read.length < from.mesh.plies ? `, plies ${read.join(", ")}` : ", every ply"}</h4>}
        {lines ? null : (
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-num studio-table-compact" data-testid="chat-values-table">
              <thead><tr><th scope="col">Ply</th>{faces ? <th scope="col">Face</th> : null}
                {answer.columns.map((c) => <th key={c} scope="col">{RESULT_COLUMNS[c].symbol}{resultUnit(from, c) ? <><br /><span className="studio-muted">{resultUnit(from, c)}</span></> : null}</th>)}</tr></thead>
              <tbody>{answer.rows.map((r) => (
                <tr key={`${r.ply}-${r.face ?? ""}`} data-ply={r.ply}><th scope="row">{r.ply} · {r.angle}°</th>{faces ? <td className="studio-text-cell">{r.face}</td> : null}
                  {r.values.map((v, i) => <td key={answer.columns[i]}>{v === null ? "–" : printed(v)}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {glance.length ? <p className="chat-note" data-testid="chat-value-facts">{glance.join(" · ")}</p> : null}
        {centre ? <p className="chat-note" data-testid="chat-value-default">No element was named, so this is the gauge centre. Click an element, or ask “where is it highest?”, for another place.</p> : null}
        {caution ? <p className="chat-note" data-testid="chat-value-caution">{caution}</p> : null}
        <details className="chat-details"><summary>Details</summary>
          <p className="chat-note" data-testid="chat-values-note">Element {answer.label} at ({printed(answer.centroid[0])}, {printed(answer.centroid[1])} {lab.length}). {answer.note}</p>
        </details>
        <Chips>
          <button type="button" disabled={!current} data-testid="chat-values-show"
            onClick={() => showPlace(placeOf(answer))}>Show on the model</button>
        </Chips>
        {!current ? <p className="chat-note">The setup has changed since: ask again.</p> : null}
      </div>
    );
  }

  /** The working behind an answer (ADR-0103): which ply of which element, by which criterion, then each step typeset. */
  function workingMessage(entry: Extract<Entry, { kind: "working" }>): ReactNode {
    const { found, from, preview } = entry;
    const figures = workingOf(from)?.digits.given ?? 6;
    return (
      <div data-testid="chat-working" data-criterion={found.criterion} data-source={preview ? "live" : "run"}>
        <h4>The working: {found.name}</h4>
        <p data-testid="chat-working-where">The first ply to fail in {found.basis}: {found.chain.where}, at {printed(found.chain.factor)} times the applied loading.</p>
        <WorkingSteps chain={found.chain} figures={figures} />
        <p className="chat-note" data-testid="chat-working-note">Inputs are shown to {figures} figures, results to 4.{preview ? " Preview: run the analysis to verify." : ""}</p>
        {found.others.length ? <Chips>{found.others.map((name) => <button key={name} type="button" onClick={() => showWorking(`Show the working for ${name}`)}>Working for {name}</button>)}</Chips> : null}
        {shown.fields !== from ? <p className="chat-note">The setup has changed since: ask again.</p> : null}
      </div>
    );
  }

  /** An answer in words to a question of why (ADR-0102): its first sentence as the heading, the rest under it, and what it rests on in one
   * line with the theory sections by name folded under Details (amendment 1). */
  function whyMessage(entry: Extract<Entry, { kind: "why" }>): ReactNode {
    const lines = whyLines(entry.answer, entry.preview, entry.place);
    return (
      <div data-testid="chat-why" data-answered={lines.prose.length ? "yes" : "no"} data-covered={entry.answer.covered ? "yes" : "no"} data-source={entry.preview ? "live" : "run"}>
        <h4 data-testid="chat-why-answer">{lines.heading}</h4>
        {lines.more.map((sentence, i) => <p key={i} data-testid="chat-why-sentence">{sentence}</p>)}
        <p className="chat-note" data-testid="chat-why-note">{lines.note}</p>
        {lines.prose.length && lines.sources.length ? <details className="chat-details" data-testid="chat-why-sources"><summary>Details</summary>
          <p className="chat-note">Our theory pages: {lines.sources.join("; ")}.</p></details> : null}
        {lines.prose.length && workingOf(shown.fields) ? <Chips><button type="button" data-testid="chat-why-working" onClick={() => showWorking("Show the working")}>Show the working</button></Chips> : null}
      </div>
    );
  }

  /** What an element is and where one sits (ADR-0099 amendment 3): the count, the number and the centre are the fields' own, and where it
   * lies is by the package's own reading of the gauge section. */
  function elementMessage(entry: Extract<Entry, { kind: "element" }>): ReactNode {
    const { answer, from } = entry;
    const current = sameResults(shown.fields, from);
    const number = answer.label?.split(".").pop() ?? null;
    const sets = answer.sets.map((name) => setWords(name)).filter((words, i) => words !== answer.sets[i]);
    const where = answer.where === "gauge" ? "in the gauge section, where the answer is read"
      : answer.where === "grip" ? "at a grip's clamped edge, where values grow with a finer mesh and are not relied on"
      : sets.length ? `in ${sets[0]}` : "outside the gauge section";
    return (
      <div data-testid="chat-element" data-element={answer.label ?? ""} data-where={answer.where ?? ""}>
        <h4>{number ? `Element ${number}` : "An element"}</h4>
        <p data-testid="chat-element-what">{number ? "One" : "Each is one"} of the {answer.count} small four-sided pieces the model is divided into, the mesh. Every ply's stresses and strains are worked out at each piece's centre.</p>
        {number && answer.centroid ? <p data-testid="chat-element-where">It sits at ({printed(answer.centroid[0])}, {printed(answer.centroid[1])} {from.labels.length}), {where}.</p>
          : <p className="chat-note">Click one on the model to see where it is.</p>}
        {number && answer.element !== null ? <Chips>
          <button type="button" disabled={!current} data-testid="chat-element-show" onClick={() => showPlace({ element: answer.element as number, ply: null, face: null })}>Show on the model</button>
          <button type="button" disabled={!current} data-testid="chat-element-stress" onClick={() => send(`stress at element ${number}`)}>Stress here</button>
        </Chips> : null}
      </div>
    );
  }

  /** Which ply fails first (ADR-0099 amendment 1), kept short: the ply as the heading, the loading and the verdict in one line, what it
   * rests on in one line of labels. Each criterion's row, where the gauge section is read and the earlier failure at a grip are folded
   * under "Details", as the answer card says them. */
  function failureMessage(entry: Extract<Entry, { kind: "failure" }>): ReactNode {
    const { found, from, preview, reader } = entry;
    const { answer, row } = found;
    const current = sameResults(shown.fields, from);
    const L = from.labels.length ?? "";
    const lines = failureLines(found, printed);
    // "does it fail?" opens with Yes or No; a loading stated back wrongly is answered No; a margin asked for is said not to be worked out
    const asked = entry.asked ?? "";
    const verdict = entry.confirmed ? null : failureVerdict(asked, found);
    const denied = !entry.confirmed && lines.confirmed !== null && contradictsFailure(asked, found, printed);
    const margin = marginNote(asked, found, printed);
    const reading = answer.basis === "gauge" ? from.summary.gauge_reading : null;
    const outside = answer.outside;
    return (
      <div data-testid="chat-failure" data-reader={reader} data-source={preview ? "live" : "run"} data-basis={answer.basis} data-criterion={row.criterion} data-fails={row.fails}>
        {entry.confirmed && lines.confirmed ? <><h4 data-testid="chat-failure-yes">Yes</h4><p data-testid="chat-failure-loading"><strong>{lines.confirmed}</strong></p></>
          : denied ? <><h4 data-testid="chat-failure-no">No</h4><p data-testid="chat-failure-loading"><strong>{lines.confirmed}</strong></p></>
          : verdict ? <><h4 data-testid="chat-failure-verdict">{verdict}</h4>
            <p data-testid="chat-failure-loading"><strong>{lines.headline}, {lines.loading.charAt(0).toLowerCase()}{lines.loading.slice(1)}</strong></p>
            {lines.applied ? <p className="chat-note" data-testid="chat-failure-applied">{lines.applied}</p> : null}</>
          : <><h4 data-testid="chat-failure-ply">{lines.headline}</h4><p data-testid="chat-failure-loading"><strong>{lines.loading}</strong></p>
            {lines.applied ? <p className="chat-note" data-testid="chat-failure-applied">{lines.applied}</p> : null}</>}
        {margin ? <p className="chat-note" data-testid="chat-failure-margin">{margin}</p> : null}
        <p className="chat-note" data-testid="chat-failure-facts">{lines.facts.join(" · ")}{preview ? " · preview, run the analysis to verify" : ""}</p>
        {found.missing ? <p className="chat-note" data-testid="chat-failure-missing">{found.missing} is not in this result, so the governing criterion is shown.</p> : null}
        <details className="chat-details" data-testid="chat-failure-details"><summary>Details</summary>
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-compact" data-testid="chat-failure-table">
              <thead><tr><th scope="col">Criterion</th><th scope="col" className="studio-num-head">R</th><th scope="col">Ply</th><th scope="col">Verdict</th></tr></thead>
              <tbody>{answer.rows.map((r) => (
                <tr key={r.criterion} data-criterion={r.criterion} className={r.criterion === row.criterion ? "studio-earliest" : undefined}>
                  <th scope="row">{r.name}{r.earliest ? " (governs)" : ""}</th><td className="studio-num">{printed(r.factor)}</td>
                  <td className="studio-text-cell">{r.ply} · {r.angle}°</td><td>{r.fails ? "fails" : "holds"}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <p className="chat-note" data-testid="chat-failure-note">
            R is the load factor at first-ply failure, the onset of damage.
            {reading ? ` Read at least ${printed(reading.stand_off)} ${L} from each tab line.` : ""}
            {outside ? ` ${outside.touches_grip ? "At a grip edge" : outside.near_tab ? "Beside a tab line" : `Outside ${answer.basisWords}`} ${outside.name} is reached at ${printed(outside.factor)} ×, in ${plyWords(outside)}${outside.touches_grip || outside.near_tab ? "; that value grows with a finer mesh, so it is not the answer" : ""}.` : ""}
          </p>
        </details>
        <Chips>
          <button type="button" disabled={!current} data-testid="chat-failure-show" onClick={() => showPlace(failurePlace(row))}>Show on the model</button>
          {current && workingOf(from) ? <button type="button" data-testid="chat-failure-working" onClick={() => showWorking(`Show the working for ${row.name}`)}>Show the working</button> : null}
        </Chips>
        {!current ? <p className="chat-note">The setup has changed since: ask again.</p> : null}
      </div>
    );
  }

  /** Where a quantity is largest (ADR-0100), kept short (ADR-0099 amendment 2): one quantity as the heading with its value and a line of
   * labels; several as one row each. Each ply's own extreme, the elements and how the values are taken are folded under "Details"; a
   * largest value at a grip edge is flagged in one line, since it is not a value to rely on. */
  function extremesMessage(entry: Extract<Entry, { kind: "extremes" }>): ReactNode {
    const { answer, from, preview, reader } = entry;
    const current = sameResults(shown.fields, from);
    const [first] = answer.blocks;
    const single = answer.blocks.length === 1;
    const region = answer.region.replace(/^the /, "");
    const where = (row: ResultExtremes["blocks"][number]["rows"][number]) => `${row.label}${row.face ? `, ${row.face} face` : ""}`;
    const lines = single ? extremeLines(first, answer.region, resultUnit(from, first.column), printed) : null;
    const glance = [...(lines ? lines.facts : []), ...(preview ? ["preview, run the analysis to verify"] : [])];
    const extremeCaution = comparisonNote(answer.blocks.map((b) => b.column));
    return (
      <div data-testid="chat-extremes" data-reader={reader} data-source={preview ? "live" : "run"} data-region={answer.region}>
        {entry.verdict ? <h4 data-testid="chat-value-verdict">{entry.verdict}</h4> : null}
        {lines ? (entry.verdict ? <p data-testid="chat-extreme"><strong>{lines.headline}</strong></p> : <h4 data-testid="chat-extreme">{lines.headline}</h4>)
          : <h4>Largest in {answer.region}</h4>}
        {lines ? null : (
          <div className="studio-table-scroll">
            <table className="studio-table studio-table-num studio-table-compact" data-testid="chat-extremes-table">
              <thead><tr><th scope="col">Quantity</th><th scope="col">Value</th><th scope="col">Ply</th></tr></thead>
              <tbody>{answer.blocks.map((b) => {
                const r = b.rows[b.best];
                return (
                  <tr key={b.column} data-column={b.column}><th scope="row">{capital(extremeWords(b.column, b.sense))}</th>
                    <td>{printed(r.value)}{resultUnit(from, b.column) ? ` ${resultUnit(from, b.column)}` : ""}</td>
                    <td className="studio-text-cell">{r.ply} · {r.angle}°</td></tr>
                );
              })}</tbody>
            </table>
          </div>
        )}
        {glance.length ? <p className="chat-note" data-testid="chat-extreme-facts">{glance.join(" · ")}</p> : null}
        {answer.atGrip ? <p className="chat-note" data-testid="chat-extremes-grip">At a grip edge, so it grows with a finer mesh. Ask for the gauge section.</p> : null}
        {extremeCaution ? <p className="chat-note" data-testid="chat-extremes-caution">{extremeCaution}</p> : null}
        <details className="chat-details" data-testid="chat-extremes-details"><summary>Details</summary>
          <div className="studio-table-scroll">
            {single ? (
              <table className="studio-table studio-table-num studio-table-compact" data-testid="chat-extremes-table">
                <thead><tr><th scope="col">Ply</th><th scope="col">{RESULT_COLUMNS[first.column].symbol}{resultUnit(from, first.column) ? <><br /><span className="studio-muted">{resultUnit(from, first.column)}</span></> : null}</th>
                  <th scope="col">Element</th></tr></thead>
                <tbody>{first.rows.map((r, i) => (
                  <tr key={r.ply} data-ply={r.ply} className={i === first.best ? "studio-earliest" : undefined}><th scope="row">{r.ply} · {r.angle}°</th><td>{printed(r.value)}</td><td>{where(r)}</td></tr>
                ))}</tbody>
              </table>
            ) : (
              <table className="studio-table studio-table-compact" data-testid="chat-extremes-places">
                <thead><tr><th scope="col">Quantity</th><th scope="col">Element</th><th scope="col">Tied plies</th></tr></thead>
                <tbody>{answer.blocks.map((b) => (
                  <tr key={b.column} data-column={b.column}><th scope="row">{capital(extremeWords(b.column, b.sense))}</th><td>{where(b.rows[b.best])}</td>
                    <td className="studio-text-cell">{b.tied.length ? b.tied.join(", ") : "–"}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <p className="chat-note" data-testid="chat-extremes-note">{capital(region)}: {answer.elements} elements read. {answer.note}</p>
        </details>
        <Chips>
          <button type="button" disabled={!current} data-testid="chat-extremes-show" onClick={() => showPlace(placeOf(answer))}>Show on the model</button>
        </Chips>
        {!current ? <p className="chat-note">The setup has changed since: ask again.</p> : null}
      </div>
    );
  }

  function render(entry: Entry, latestCheck: number | undefined): ReactNode {
    // while an imported model or a past run has the stage, the chat shows the conversation about it alone: the project's own cards (its
    // questions, checks, runs and proposals) and what was said before wait behind it, since their buttons would act on the project, not on
    // what is shown (ADR-0109 amendment 1)
    if (shown.readOnly && (!entry.stage || (entry.role === "assistant" && PROJECT_KINDS.has(entry.kind)))) return null;
    if (entry.role === "user") return <div className="chat-user" key={entry.id}>{entry.text}</div>;
    let content: ReactNode;
    if (entry.kind === "ask") {
      const q = QUESTIONS[entry.step];
      const isLive = entry.id === active && !checking;
      content = <div data-step={entry.step} data-testid={isLive ? "chat-question" : undefined}><h4>{q.title}</h4>{isLive && q.text ? <p>{q.text}</p> : null}{askWidget(entry.step, isLive)}</div>;
    } else if (entry.kind === "text") content = <div className={entry.tone === "problem" ? "chat-problem" : undefined}>{entry.title ? <h4>{entry.title}</h4> : null}{entry.body}</div>;
    else if (entry.kind === "check") content = checkMessage(entry.answer, entry.id === latestCheck && checked === entry.answer, entry.asked);
    else if (entry.kind === "job") content = job?.job_id === entry.job ? <ChatRun job={job} /> : <p className="chat-note">An earlier run.</p>;
    else if (entry.kind === "values") content = valuesMessage(entry);
    else if (entry.kind === "extremes") content = extremesMessage(entry);
    else if (entry.kind === "why") content = whyMessage(entry);
    else if (entry.kind === "failure") content = failureMessage(entry);
    else if (entry.kind === "element") content = elementMessage(entry);
    else if (entry.kind === "working") content = workingMessage(entry);
    else if (entry.kind === "switch") {
      content = <SwitchAsk target={entry.target} kept="coupon" onGo={() => onSwitch?.(entry.target, entry.carried)}
        onStay={() => add({ role: "assistant", kind: "text", title: "Staying here", body: <p>Your coupon is as it was.</p> })} />;
    }
    else if (entry.kind === "proposal") {
      content = <ProposalCard lines={proposalLines(entry.answer)} conditions={entry.answer.conditions} question={entry.answer.question}
        dropped={entry.answer.dropped.map((d) => ({ ...d, key: labelOf(d.key, unitsOf(form)).replace(/ \([^)]*\)$/, "") }))}
        unread={unreadLines(entry.answer.unread)}
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
  const onPlateNow = (allTests || plates) && form.test === PLATE_TEST && !!model?.proposes; // a plate's regions are read from a message by a model only
  const hereNow = onPlateNow ? here() : [];
  return (
    <section className="chat-pane" aria-label="FEA assistant" data-testid="coupon-chat">
      <div className="chat-pane-top">
        <span><span className="status-dot" /> FEA assistant <span className="chat-tag" data-testid="chat-kind">{TARGET_TITLES.coupon}</span></span>
        <span>
          {allTests && !shown.readOnly ? <button type="button" className="chat-link" onClick={() => showPanel("advanced")}><TableProperties size={13} /> All inputs</button> : null}
          {shown.readOnly ? null : <button type="button" className="icon-button" aria-label="Start a new coupon" title="Start a new coupon" onClick={startOver}><RotateCcw size={14} /></button>}
        </span>
      </div>
      <div className="chat-scroll" ref={body} aria-live="polite" aria-relevant="additions">
        {entries.map((e) => render(e, latestCheck))}
        {reading ? <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span><div><p className="chat-typing" data-testid="chat-reading">Reading your message…</p></div></div> : null}
        {checking && !shown.readOnly ? <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span><div><p className="chat-typing">Checking the setup…</p></div></div> : null}
        {/* on the tension screen the rail says an outage, once (audit fea-run-48); every other problem is said here */}
        {problem && (allTests || problem !== ANALYSIS_UNAVAILABLE) ? <p className="studio-alert" role="alert">{problem}</p> : null}
      </div>
      {onPlateNow && picked !== null && hereNow.length ? (
        <p className="chat-note chat-here" data-testid="chat-here">“Here” is the element you clicked: {hereNow.map((r) => r.name).join(", ")}.</p>
      ) : null}
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message the coupon assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={shown.imported ? "Ask about this model’s results, e.g. “where is the stress highest?”" : shown.past ? "Ask about this run’s results, e.g. “which ply fails first?”" : onPlateNow ? "Hold or load a region, e.g. “hold this edge” or “10 kN in tension on the top edge”" : "Describe the coupon or one change, e.g. “make it [0/90]2s”"}
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
      {problem ? <p className="chat-problem">{problem}</p> : isActive(job.state) ? <p className="chat-note">Progress is shown in the centre of the page.</p> : null}
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
