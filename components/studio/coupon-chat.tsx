"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowUp, Check, CircleAlert, FlaskConical, Layers3, Play, RotateCcw, Sparkles, SlidersHorizontal, TableProperties } from "lucide-react";
import {
  checkSetup, couponValues, fetchExplanation, fetchFields, getJob, listCoupons, POLL_MS, startSolve, StudioError,
  type CheckAnswer, type CouponSummary, type Explanation, type Fields, type JobStatus,
} from "@/lib/studio-api";
import { blankForm, buildValues, exampleForm, fieldByKey, formFromValues, libraryOptions, PLATE_TEST, type StudioForm } from "@/lib/studio-form";
import {
  COMMON_MATERIALS, couponLines, isBending, labelOf, libraryConstants, LAYUP_CHOICES, layupNotation, layupRows, libraryThickness, missingIn, nextStep,
  parseLayup, readMessage, stepOfKey, TEST_CHOICES, type ChatStep,
} from "@/lib/studio-chat";
import { printed } from "@/lib/studio-colors";
import { handoffKey } from "../home-composer";
import { PreviewScene } from "./coupon-studio";
import { JobProgress } from "./job-progress";
import { ResultsView } from "./results-view";

const RUN_BY_KEY = "anisotropy.studio.run_by";
const EXAMPLE_SIZE = { length: "250", width: "25", tab_length: "56", size_from: "the public IM7/8552 example" };

type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; kind: "text"; title?: string; body?: ReactNode; tone?: "problem" }
  | { id: number; role: "assistant"; kind: "ask"; step: ChatStep | "advanced" | "reopen" }
  | { id: number; role: "assistant"; kind: "check"; answer: CheckAnswer }
  | { id: number; role: "assistant"; kind: "job"; job: string }
  | { id: number; role: "assistant"; kind: "result"; job: string };
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
const libraryEntry = (id: string) => libraryOptions.find((m) => m.id === id);

const QUESTIONS: Record<ChatStep | "advanced" | "reopen", { title: string; text?: string }> = {
  test: { title: "What are we testing?", text: "Pick a test, or describe the whole coupon in one line, e.g. “open-hole tension, IM7/8552, [45/0/-45/90]s, 36 x 250 mm, 6 mm hole, 1 mm pull”." },
  material: { title: "Which material?", text: "Pick one from the library, with its cited constants and strengths, or give your own." },
  shear: { title: "Out-of-plane shear moduli", text: "The engine needs G13 and G23, which the library does not list. Without measured values, the usual tape estimate is G13 = G12 and G23 = E2 / 3; the choice is noted on the coupon." },
  layup: { title: "What is the layup?", text: "Type it in laminate notation, bottom ply first, or pick one. Angles are measured from x, across the coupon's width: 90° runs along the load, 0° across it." },
  geometry: { title: "Coupon size", text: "The coupon's length runs along the load." },
  loading: { title: "How is it loaded?" },
  name: { title: "Who is running it?", text: "Your name goes in the attempt log and the CalculiX record, and is remembered in this browser. A material we have not run before also needs a short code for the coupon's name, such as IM7; leave it blank to reuse the one we have." },
  review: { title: "Checking the setup" },
  advanced: { title: "Mesh, failure criteria and grips", text: "These have working defaults; change them only if you need to." },
  reopen: { title: "Reopen a saved coupon", text: "It loads as it was last run; solving it again adds the next attempt." },
};

/** A small form inside a chat message: the given rows, typed into a draft and applied together. */
function RowsCard({ keys, form, onApply, submit = "Continue", disabled, extra }: {
  keys: string[]; form: StudioForm; onApply: (rows: StudioForm) => void; submit?: string; disabled?: boolean; extra?: ReactNode;
}) {
  const seed = keys.map((k) => `${k}=${form[k] ?? ""}`).join("\n");
  const [draft, setDraft] = useState<StudioForm>(() => Object.fromEntries(keys.map((k) => [k, form[k] ?? ""])));
  useEffect(() => { setDraft(Object.fromEntries(keys.map((k) => [k, form[k] ?? ""]))); }, [seed]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <form className="chat-rows" onSubmit={(e) => { e.preventDefault(); onApply(draft); }}>
      <div className="chat-rows-grid">
        {keys.map((key) => {
          const field = fieldByKey[key];
          const id = `chat-${key}`;
          const words = field?.kind === "list" ? field.words : [];
          return (
            <label key={key} htmlFor={id} className={key === "size_from" || key === "own_source" ? "chat-row-wide" : undefined}>
              <span>{labelOf(key)}{field?.required ? "" : <small> optional</small>}</span>
              {words.length ? (
                <select id={id} value={draft[key]} disabled={disabled} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}>
                  {field?.required ? null : <option value="">(blank)</option>}
                  {words.map((w) => <option key={w} value={w}>{w}</option>)}
                </select>
              ) : (
                <input id={id} type="text" value={draft[key]} disabled={disabled} autoComplete="off"
                  inputMode={field && ["number", "whole", "angle"].includes(field.kind) ? "decimal" : undefined}
                  onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
              )}
            </label>
          );
        })}
      </div>
      {extra}
      <button type="submit" className="chat-primary" disabled={disabled}>{submit}</button>
    </form>
  );
}

function Chips({ children }: { children: ReactNode }) { return <div className="chat-chips">{children}</div>; }

export function CouponChat({ apiBaseUrl, initialForm, onFormChange, onOpenForm }: {
  apiBaseUrl: string; initialForm?: StudioForm | null; onFormChange?: (form: StudioForm) => void; onOpenForm: () => void;
}) {
  const [form, setFormState] = useState<StudioForm>(() => initialForm ?? { ...blankForm(), date: today() });
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<number | null>(null); // the question whose controls are live
  const [input, setInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [checked, setChecked] = useState<CheckAnswer | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fields, setFields] = useState<Fields | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [coupons, setCoupons] = useState<CouponSummary[]>([]);
  const [ownMaterial, setOwnMaterial] = useState(false);
  const [problem, setProblem] = useState("");
  const nextId = useRef(1);
  const body = useRef<HTMLDivElement>(null);
  const formRef = useRef(form);
  const fieldsLoaded = useRef<string | null>(null);
  const started = useRef(false);

  const setForm = useCallback((next: StudioForm) => { formRef.current = next; setFormState(next); onFormChange?.(next); }, [onFormChange]);
  const add = useCallback((...items: NewEntry[]) => {
    const made = items.map((item) => ({ ...item, id: nextId.current++ }) as Entry);
    setEntries((list) => [...list, ...made]);
    return made;
  }, []);
  const ask = useCallback((step: ChatStep | "advanced" | "reopen") => {
    const [entry] = add({ role: "assistant", kind: "ask", step });
    setActive(entry.id);
  }, [add]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const name = remembered(RUN_BY_KEY);
    const start = { ...formRef.current, filled_by: formRef.current.filled_by || name, date: formRef.current.date || today() };
    setForm(start);
    if (initialForm && initialForm.test) {
      add({ role: "assistant", kind: "text", title: "Picked up from the full form", body: <p>I have the rows you filled in. Here is what is still needed, then I check the setup.</p> });
      proceed(start);
      return;
    }
    // a library material sent from its page, or a message typed on the home page, starts the conversation
    const handoff = readHandoff();
    if (handoff.material) {
      setForm({ ...start, library: handoff.material });
      add({ role: "assistant", kind: "text", title: `Material: ${materialName(handoff.material)}`, body: <p>Taken from the library page; change it any time.</p> });
    }
    ask("test");
    if (handoff.prompt) send(handoff.prompt);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listCoupons(apiBaseUrl, controller.signal).then(setCoupons).catch(() => setCoupons([]));
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" }); }, [entries, checking, fields]);

  async function check(values: StudioForm) {
    setActive(null);
    if (!apiBaseUrl) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The engine is not connected",
        body: <p>This page was built without the API address (NEXT_PUBLIC_ANISOTROPY_API_URL), so I can take the setup down but cannot check or run it.</p> });
      return;
    }
    setChecking(true); setProblem("");
    try {
      const answer = await checkSetup(apiBaseUrl, buildValues(values));
      setChecked(answer);
      add({ role: "assistant", kind: "check", answer });
    } catch (error) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The setup check did not answer", body: <p>{error instanceof StudioError ? error.message : "The setup check failed."}</p> });
    } finally {
      setChecking(false);
    }
  }

  /** Ask the next missing thing, or check the setup once nothing is missing. */
  function proceed(next: StudioForm) {
    if (next.test === PLATE_TEST) {
      setActive(null);
      add({ role: "assistant", kind: "text", title: "Plates are set up on the model",
        body: <><p>A plate is held and loaded by picking its edges and faces on the 3D model, which the full form does today.</p>
          <Chips><button type="button" onClick={onOpenForm}><TableProperties size={14} /> Open the full form</button></Chips></> });
      return;
    }
    const step = nextStep(next);
    if (step === "review") void check(next);
    else ask(step);
  }

  /** A changed setup leaves the last results behind; a run still going keeps its progress. */
  function clearRun() {
    setChecked(null);
    if (job?.state === "running") return;
    setJob(null); setFields(null); setExplanation(null); fieldsLoaded.current = null;
  }

  /** Apply rows from a click or a card, echo what the engineer chose, and move on. */
  function answer(echo: string, rows: StudioForm) {
    const next: StudioForm = { ...formRef.current, ...rows };
    if (rows.filled_by) remember(RUN_BY_KEY, rows.filled_by.trim());
    setForm(next);
    clearRun();
    add({ role: "user", text: echo });
    proceed(next);
  }

  function startOver() {
    const fresh = { ...blankForm(), date: today(), filled_by: formRef.current.filled_by };
    setForm(fresh); setChecked(null); setJob(null); setFields(null); setExplanation(null); setOwnMaterial(false); fieldsLoaded.current = null;
    setEntries([]);
    ask("test");
  }

  function loadExample() {
    const next = { ...exampleForm(today()), filled_by: formRef.current.filled_by };
    setForm(next); clearRun();
    add({ role: "user", text: "Start from the IM7/8552 example" },
      { role: "assistant", kind: "text", title: "Loaded the public IM7/8552 example",
        body: <p>Unnotched tension, 250 × 25 mm with 56 mm tabs, [45/0/-45/90]s, pulled 1 mm. Change anything by typing it, e.g. “make it [0/90]2s”.</p> });
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
      add({ role: "assistant", kind: "text", tone: "problem", title: "That coupon could not be read", body: <p>{error instanceof StudioError ? error.message : "Unknown error."}</p> });
    }
  }

  async function run() {
    const answerNow = checked;
    if (!apiBaseUrl || !answerNow || answerNow.state !== "ready") return;
    const name = formRef.current.filled_by.trim();
    if (!name) { ask("name"); return; }
    setProblem(""); setFields(null); setExplanation(null); fieldsLoaded.current = null; setActive(null);
    add({ role: "user", text: "Run the analysis" });
    try {
      const startedJob = await startSolve(apiBaseUrl, buildValues(formRef.current), name, answerNow.checklist.coupon_exists);
      setJob(startedJob);
      add({ role: "assistant", kind: "job", job: startedJob.job_id });
    } catch (error) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The run could not start", body: <p>{error instanceof StudioError ? error.message : "Unknown error."}</p> });
    }
  }

  useEffect(() => {
    if (!job || !apiBaseUrl || job.state !== "running") return;
    const timer = window.setTimeout(async () => {
      try { setJob(await getJob(apiBaseUrl, job.job_id)); }
      catch (error) { setProblem(error instanceof StudioError ? error.message : "The job's status could not be read."); }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [job, apiBaseUrl]);

  useEffect(() => {
    if (!job || !apiBaseUrl || !("fields" in job.outputs)) return;
    const stamp = `${job.job_id}:${"explanation" in job.outputs}`;
    if (fieldsLoaded.current === stamp) return;
    const first = fieldsLoaded.current === null || !fieldsLoaded.current.startsWith(job.job_id);
    fieldsLoaded.current = stamp;
    (async () => {
      try {
        setFields(await fetchFields(apiBaseUrl, job.job_id));
        setExplanation("explanation" in job.outputs ? await fetchExplanation(apiBaseUrl, job.job_id) : null);
        if (first) add({ role: "assistant", kind: "result", job: job.job_id });
      } catch (error) {
        setProblem(error instanceof StudioError ? error.message : "The results could not be read.");
      }
    })();
  }, [job, apiBaseUrl, add]);

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    if (/^(start over|reset|new coupon|restart)\b/i.test(text)) { add({ role: "user", text }); startOver(); return; }
    if (/^(run|solve|go|run it|run analysis)\b/i.test(text) && checked?.state === "ready") { void run(); return; }
    if (/^(check|check setup)\b/i.test(text)) { add({ role: "user", text }); void check(formRef.current); return; }
    if (/full form|spreadsheet|all (the )?rows/i.test(text)) { add({ role: "user", text }); onOpenForm(); return; }
    const current = entries.find((e) => e.id === active);
    const step = current && current.role === "assistant" && current.kind === "ask" ? current.step : null;
    if (step === "name" && !/\d/.test(text)) { answer(text, { filled_by: text }); return; }
    const { rows, understood } = readMessage(text);
    if (!understood.length) {
      add({ role: "user", text }, { role: "assistant", kind: "text", title: "I could not read a coupon value in that",
        body: <p>I set up and run coupon tests: try the options above, or a phrase like “open-hole tension”, “250 x 25 mm, 56 mm tabs”, “[0/90]2s”, “AS4/8552” or “10 kN”. Type “full form” for every row.</p> });
      return;
    }
    add({ role: "user", text }, { role: "assistant", kind: "text", title: "Got it", body: <ul className="chat-understood">{understood.map((u) => <li key={u}><Check size={13} /> {u}</li>)}</ul> });
    const next: StudioForm = { ...formRef.current, ...rows };
    setForm(next); clearRun();
    proceed(next);
  }

  function askWidget(step: ChatStep | "advanced" | "reopen", live: boolean): ReactNode {
    if (!live) return null;
    switch (step) {
      case "test":
        return (
          <>
            <div className="chat-choice-grid">
              {TEST_CHOICES.map((c) => (
                <button type="button" key={c.test} className="chat-choice" onClick={() => answer(c.title, { test: c.test })}>
                  <strong>{c.title}</strong><span>{c.detail}</span>
                </button>
              ))}
            </div>
            <Chips>
              <button type="button" onClick={loadExample}><FlaskConical size={14} /> Start from the IM7/8552 example</button>
              {coupons.length ? <button type="button" onClick={() => ask("reopen")}><RotateCcw size={14} /> Reopen a saved coupon</button> : null}
              <button type="button" onClick={onOpenForm}><TableProperties size={14} /> Plate, or every row: full form</button>
            </Chips>
          </>
        );
      case "reopen":
        return (
          <div className="chat-list">
            {coupons.map((c) => (
              <button type="button" key={c.name} onClick={() => reopen(c.name)}>
                <strong>{c.name}</strong><span>{c.test}, {c.layup}; {c.attempts} attempt{c.attempts === 1 ? "" : "s"}{c.status ? `, ${c.status}` : ""}</span>
              </button>
            ))}
          </div>
        );
      case "material":
        return ownMaterial ? (
          <RowsCard keys={["own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c", "own_F6", "own_source"]} form={form}
            onApply={(rows) => answer(`My own material: ${rows.own_name || "unnamed"}`, { ...rows, library: "" })}
            extra={<p className="chat-note">Give all five strengths or none; without them no failure is predicted. Your numbers stay with this coupon and never enter the library.</p>} />
        ) : (
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
              <button type="button" className="chat-link" onClick={() => setOwnMaterial(true)}>Use my own constants</button>
            </div>
          </>
        );
      case "shear": {
        const constants = form.library ? libraryConstants(form.library) : { G12: Number(form.own_G12), E2: Number(form.own_E2) };
        const estimate = constants && Number.isFinite(constants.G12) && Number.isFinite(constants.E2) && constants.G12 > 0 && constants.E2 > 0
          ? { G13: printed(constants.G12), G23: printed(constants.E2 / 3) } : null;
        return (
          <>
            {estimate ? (
              <Chips>
                <button type="button" onClick={() => answer(`Tape estimate: G13 = ${estimate.G13} MPa, G23 = ${estimate.G23} MPa`,
                  { G13: estimate.G13, G23: estimate.G23, notes: [formRef.current.notes, "G13 = G12 and G23 = E2/3 by the tape estimate (studio chat)."].filter(Boolean).join(" ") })}>
                  <Sparkles size={14} /> Use the tape estimate: G13 = {estimate.G13}, G23 = {estimate.G23} MPa
                </button>
              </Chips>
            ) : null}
            <RowsCard keys={["G13", "G23"]} form={form} submit="Use these values" onApply={(rows) => answer(`G13 = ${rows.G13} MPa, G23 = ${rows.G23} MPa`, rows)} />
          </>
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
            <LayupInput needThickness={needThickness} form={form} onApply={(notation, rows) => answer(notation, rows)} />
            {!needThickness ? <p className="chat-note">Ply thickness {printed(libraryThickness(form))} mm, from the library.</p> : null}
          </>
        );
      }
      case "geometry": {
        const keys = missingIn("geometry", { ...form, length: "", width: "", size_from: "", tab_length: "", span: "", overhang: "", load_span: "", hole_diameter: "" });
        return (
          <>
            {!isBending(form) ? (
              <Chips>
                <button type="button" onClick={() => answer("250 × 25 mm, 56 mm tabs (the example's size)", EXAMPLE_SIZE)}>
                  <Layers3 size={14} /> 250 × 25 mm, 56 mm tabs (the example's size)</button>
              </Chips>
            ) : null}
            <RowsCard keys={keys} form={form} onApply={(rows) => answer(keys.filter((k) => k !== "size_from").map((k) => `${labelOf(k).replace(/ \(.*\)$/, "")} ${rows[k]} mm`).join(", "), rows)}
              extra={<p className="chat-note">Where the size comes from: a standard (e.g. ASTM D3039), a drawing, or your own design.</p>} />
          </>
        );
      }
      case "loading":
        return isBending(form) ? (
          <>
            <Chips>
              {["1", "2", "5"].map((v) => <button type="button" key={v} onClick={() => answer(`Push the nose ${v} mm`, { control: "displacement", value: v })}>Push {v} mm</button>)}
            </Chips>
            <RowsCard keys={["value"]} form={form} submit="Use this travel (mm)" onApply={(rows) => answer(`Push the nose ${rows.value} mm`, { control: "displacement", value: rows.value })} />
          </>
        ) : (
          <>
            <p className="chat-note">The bottom grip is held; the top grip {form.test === "unnotched compression" ? "pushes" : "pulls"}.</p>
            <Chips>
              <button type="button" onClick={() => answer("Displacement of 1 mm", { control: "displacement", value: "1" })}>Displacement 1 mm</button>
              <button type="button" onClick={() => answer("Displacement of 0.5 mm", { control: "displacement", value: "0.5" })}>Displacement 0.5 mm</button>
              <button type="button" onClick={() => answer("Force of 10 kN", { control: "force", value: "10000" })}>Force 10 kN</button>
            </Chips>
            <RowsCard keys={["control", "value"]} form={{ ...form, control: form.control || "displacement" }} submit="Use this load"
              onApply={(rows) => answer(`${rows.control === "force" ? "Force" : "Displacement"} of ${rows.value} ${rows.control === "force" ? "N" : "mm"}`, rows)}
              extra={<p className="chat-note">Displacement in mm, force in N.</p>} />
          </>
        );
      case "name":
        return <RowsCard keys={["filled_by", "material_code"]} form={form} submit="Continue" onApply={(rows) => {
          const name = rows.filled_by?.trim(), code = rows.material_code?.trim() ?? "";
          if (name) answer(code ? `${name}; material code ${code}` : name, { filled_by: name, material_code: code });
        }} />;
      case "advanced":
        return <RowsCard keys={["element_size", "criteria", "f12_star", ...(isBending(form) ? [] : ["grips", "region"])]} form={form} submit="Apply and check again"
          onApply={(rows) => answer(`Settings: element size ${rows.element_size} mm, criteria ${rows.criteria}${rows.grips ? `, grips ${rows.grips}` : ""}`, rows)}
          extra={<p className="chat-note">Grips “coupling” tie each tab to a reference point, as in Abaqus; “nodal” holds every gripped node. Tsai-Wu needs f12* between -1 and 1.</p>} />;
      case "review":
        return null;
    }
  }

  function checkMessage(result: CheckAnswer, latest: boolean): ReactNode {
    const items = result.checklist.items;
    const blocking = items.filter((i) => i.state === "fail" || i.state === "missing");
    const warnings = items.filter((i) => i.state === "warn");
    const passed = items.filter((i) => i.state === "pass").length;
    const stepsFor = (rows: string[]) => [...new Set(rows.map((label) => stepOfKey(Object.values(fieldByKey).find((f) => f.label === label)?.key ?? "")))];
    return (
      <div data-testid="chat-check" data-state={result.state}>
        <h4>{result.state === "ready" ? <>Ready to run{result.designation ? <> <code>{result.designation}</code></> : null}</> : `${blocking.length} thing${blocking.length === 1 ? "" : "s"} to fix before running`}</h4>
        <p>{passed} of {items.length} checks passed{result.checklist.coupon_exists ? `; this coupon has ${result.checklist.attempts} attempt${result.checklist.attempts === 1 ? "" : "s"} already, so running adds the next one` : result.designation ? "; a new coupon" : ""}. The same rules run before the solve.</p>
        {blocking.length ? (
          <ul className="chat-issues">
            {blocking.map((item) => {
              const steps = stepsFor(item.rows);
              const step = steps.find((s): s is ChatStep => s !== null);
              return (
                <li key={item.id} data-item={item.id}>
                  <CircleAlert size={14} /> <span><strong>{item.label}:</strong> {item.message}</span>
                  {latest ? (step ? <button type="button" className="chat-link" onClick={() => ask(step)}>Fix</button>
                    : <button type="button" className="chat-link" onClick={onOpenForm}>Fix in the full form</button>) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
        {warnings.length ? (
          <ul className="chat-issues chat-warnings">
            {warnings.map((item) => <li key={item.id}><CircleAlert size={14} /> <span><strong>{item.label}:</strong> {item.message}</span></li>)}
          </ul>
        ) : null}
        <details className="chat-details"><summary>Every check</summary>
          <ul className="chat-allchecks">{items.map((i) => <li key={i.id} data-state={i.state}>{i.state === "pass" ? "✓" : i.state === "warn" ? "!" : "✕"} {i.label}: {i.message}</li>)}</ul>
        </details>
        {latest && result.state === "ready" ? (
          <div className="chat-actions">
            <button type="button" className="chat-primary" onClick={run} disabled={job?.state === "running"} data-testid="chat-run"><Play size={14} /> Run analysis</button>
            <button type="button" className="chat-secondary" onClick={() => ask("advanced")}><SlidersHorizontal size={14} /> Mesh, criteria, grips</button>
          </div>
        ) : null}
      </div>
    );
  }

  function resultMessage(jobId: string): ReactNode {
    if (job?.job_id !== jobId) return <p className="chat-note">The results of an earlier run; the setup has changed since.</p>;
    if (!fields) return <p className="chat-note">Reading the results…</p>;
    const s = fields.summary, lab = fields.labels;
    const earliest = s.earliest ? s.fpf[s.earliest] : null;
    return (
      <div data-testid="chat-result">
        <h4>Results{job?.coupon ? <> for <code>{job.coupon}</code></> : null}</h4>
        <div className="chat-stats">
          <div><span>Reaction</span><strong data-testid="chat-reaction">{printed(Math.abs(s.reaction.value))} {lab.force}</strong><small>{s.reaction.sense}, {s.reaction.set}</small></div>
          <div><span>Largest displacement</span><strong>{printed(s.max_displacement.value)} {lab.length}</strong><small>{s.applied.control} {printed(s.applied.value)} {s.applied.unit}</small></div>
          {earliest ? (
            <div className={earliest.factor < 1 ? "chat-stat-bad" : undefined}><span>First-ply failure</span><strong>R = {printed(earliest.factor)}</strong>
              <small>{s.earliest?.replace("_", " ")}, ply {earliest.ply} ({earliest.angle}°), {earliest.mode}</small></div>
          ) : <div><span>First-ply failure</span><strong>–</strong><small>no criterion asked for</small></div>}
        </div>
        {earliest ? <p>R is the factor on the applied load at which the first ply fails{earliest.touches_grip ? "; this one sits at a gripped tab edge, so read it as first damage at the grip" : ""}.</p> : null}
        {explanation?.sentences.length ? <p>{explanation.sentences[0]}</p> : null}
        {job?.state === "done" && job.message ? <p className="chat-ok"><Check size={13} /> {job.message}</p> : null}
        {job?.state === "running" ? <p className="chat-note">CalculiX, the record and the package are still running; the files appear on the right when they are written.</p> : null}
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
      const live = entry.id === active && !checking;
      content = <div data-step={entry.step} data-testid={live ? "chat-question" : undefined}><h4>{q.title}</h4>{live && q.text ? <p>{q.text}</p> : null}{askWidget(entry.step, live)}</div>;
    } else if (entry.kind === "text") content = <div className={entry.tone === "problem" ? "chat-problem" : undefined}>{entry.title ? <h4>{entry.title}</h4> : null}{entry.body}</div>;
    else if (entry.kind === "check") content = checkMessage(entry.answer, entry.id === latestCheck && checked === entry.answer);
    else if (entry.kind === "job") content = job?.job_id === entry.job ? <JobProgress job={job} /> : <p className="chat-note">An earlier run.</p>;
    else content = resultMessage(entry.job);
    return (
      <div className="chat-assistant" key={entry.id}>
        <span className="message-avatar"><Sparkles size={15} /></span>
        <div>{content}</div>
      </div>
    );
  }

  const latestCheck = [...entries].reverse().find((e) => e.role === "assistant" && e.kind === "check")?.id;
  const lines = couponLines(form);
  const viewerLink = job ? `/studio/view?job=${encodeURIComponent(job.job_id)}` : null;
  return (
    <div className="chat-studio" data-testid="coupon-chat">
      <section className="chat-pane" aria-label="Coupon assistant">
        <div className="chat-pane-top">
          <span><span className="status-dot" /> Coupon assistant</span>
          <span>
            <button type="button" className="chat-link" onClick={onOpenForm}><TableProperties size={13} /> Full form</button>
            <button type="button" className="icon-button" aria-label="Start a new coupon" title="Start a new coupon" onClick={startOver}><RotateCcw size={14} /></button>
          </span>
        </div>
        <div className="chat-scroll" ref={body} aria-live="polite" aria-relevant="additions">
          {entries.map((e) => render(e, latestCheck))}
          {checking ? <div className="chat-assistant"><span className="message-avatar"><Sparkles size={15} /></span><div><p className="chat-typing">Checking the setup against the run's rules…</p></div></div> : null}
          {problem ? <p className="studio-alert" role="alert">{problem}</p> : null}
        </div>
        <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <textarea aria-label="Message the coupon assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Describe the coupon or change one thing, e.g. “make it [0/90]2s” or “10 kN”"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
          <div className="composer-footer">
            <span className="chat-note">Enter to send · “start over” · “full form”</span>
            <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
          </div>
        </form>
      </section>
      <section className="chat-bench" aria-label="Model and results">
        <dl className="chat-spec" data-testid="chat-spec">
          {lines.map(([k, v]) => <div key={k} data-filled={v ? "yes" : "no"}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}
        </dl>
        {fields ? (
          <>
            {viewerLink ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer">Open the viewer in a new window</a></p> : null}
            <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={checked?.preview ?? null} />
          </>
        ) : checked?.preview ? <PreviewScene preview={checked.preview} /> : (
          <div className="studio-empty" data-testid="empty-scene">
            <h3>The model appears here</h3>
            <p>Once the setup is complete I check it and draw the mesh, the held end and the load. After the run, every ply's stresses show here in 3D.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function LayupInput({ needThickness, form, onApply }: { needThickness: boolean; form: StudioForm; onApply: (notation: string, rows: StudioForm) => void }) {
  const [text, setText] = useState(() => layupNotation(form));
  const [thickness, setThickness] = useState(form.ply_thickness ?? "");
  const [error, setError] = useState("");
  return (
    <form className="chat-inline" onSubmit={(e) => {
      e.preventDefault();
      const layup = parseLayup(text);
      if (!layup) { setError("Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s, up to 16 plies listed."); return; }
      if (needThickness && !thickness.trim()) { setError("Give the cured ply thickness too."); return; }
      onApply(text.replace(/\s+/g, ""), { ...layupRows(layup), ...(needThickness ? { ply_thickness: thickness.trim() } : { ply_thickness: "" }) });
    }}>
      <input type="text" aria-label="Layup" placeholder="[45/0/-45/90]s" value={text} onChange={(e) => { setText(e.target.value); setError(""); }} autoComplete="off" />
      {needThickness ? <input type="text" aria-label="Cured ply thickness (mm)" placeholder="ply thickness, mm" inputMode="decimal" value={thickness}
        onChange={(e) => { setThickness(e.target.value); setError(""); }} className="chat-small-input" /> : null}
      <button type="submit" className="chat-primary">Use layup</button>
      {error ? <span className="chat-error" role="alert">{error}</span> : null}
    </form>
  );
}
