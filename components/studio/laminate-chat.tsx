"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, ArrowUp, Check, Layers3, Play, RotateCcw, Sparkles } from "lucide-react";
import { solveLaminate, StudioError, type LaminateAnswer } from "@/lib/studio-api";
import { libraryOptions } from "@/lib/studio-form";
import { COMMON_MATERIALS } from "@/lib/studio-chat";
import {
  blankDraft, buildProblem, CONSTANT_NAMES, libraryNameOf, libraryThicknessOf, LOAD_NAMES, loadsWithZeros, missingIn, nextStep, printedUnit, problemLines,
  readConstants, readLayupLine, readLibraryMaterial, readLoads, readSystem, REPORT_SYSTEMS, STRENGTH_NAMES, systemUnit, unitsOf,
  type ConstantName, type Kind, type LaminateDraft, type LaminateStep, type LoadName, type OwnConstants, type Quantity, type ReportUnits,
} from "@/lib/laminate-chat";
import { LaminateResults } from "./laminate-results";

type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; kind: "text"; title?: string; body?: ReactNode; tone?: "problem" }
  | { id: number; role: "assistant"; kind: "ask"; step: LaminateStep }
  | { id: number; role: "assistant"; kind: "answer"; stamp: number };
type NewEntry = Entry extends infer E ? (E extends unknown ? Omit<E, "id"> : never) : never;

/** The layups offered as one click. In a laminate problem 0° runs along x, the direction of Nx, as in the textbooks. */
const LAYUP_CHOICES: { notation: string; title: string }[] = [
  { notation: "[45/0/-45/90]s", title: "Quasi-isotropic" },
  { notation: "[0/90]2s", title: "Cross-ply" },
  { notation: "[45/-45]2s", title: "Angle-ply" },
  { notation: "[0]8", title: "Unidirectional, fibres along x" },
];

const QUESTIONS: Record<LaminateStep, { title: string; text: string }> = {
  units: { title: "Which units is the problem stated in?", text: "Pick the system. A number typed with its own unit, like 10300 MPa or 0.0049 in, keeps that unit; the engine converts, never this page." },
  material: { title: "Which material?", text: "Pick one from the library, with its cited constants and strengths, or type the constants the problem gives, e.g. “E1 147 GPa, E2 10.3, G12 7, nu12 0.27, F1t 2280, F1c 1725, F2t 57, F2c 228, F6 76 MPa”. Without strengths no failure is predicted." },
  layup: { title: "What is the layup?", text: "Laminate notation, bottom ply first, e.g. [0/45/-45/90]s, and the ply thickness. Here 0° runs along x, the direction of Nx, as in the textbooks (a coupon test counts from across the width)." },
  loads: { title: "What loads does it carry?", text: "Force and moment resultants per unit width, e.g. “Nx = 100 N/mm, everything else zero”. Every one of the six is stated; nothing is assumed." },
  review: { title: "Ready to solve", text: "The engine solves the stack by classical lamination theory: the A, B, D matrices, the mid-plane strains and curvatures, every ply's stresses and first-ply failure." },
};

const blankOwn = (): OwnConstants => ({
  name: "", source: "", E1: { value: "", unit: "" }, E2: { value: "", unit: "" }, G12: { value: "", unit: "" }, nu12: "",
  F1t: { value: "", unit: "" }, F1c: { value: "", unit: "" }, F2t: { value: "", unit: "" }, F2c: { value: "", unit: "" }, F6: { value: "", unit: "" },
});
const KIND_OF: Record<ConstantName, Kind | null> = { E1: "modulus", E2: "modulus", G12: "modulus", nu12: null, F1t: "stress", F1c: "stress", F2t: "stress", F2c: "stress", F6: "stress" };
const LABELS: Record<ConstantName, string> = { E1: "E₁", E2: "E₂", G12: "G₁₂", nu12: "ν₁₂", F1t: "F1t", F1c: "F1c", F2t: "F2t", F2c: "F2c", F6: "F6" };

/** One value with its unit menu, the unit list the engine's table gives for the kind. */
function QuantityField({ id, label, kind, quantity, system, onChange, disabled }: {
  id: string; label: ReactNode; kind: Kind; quantity: Quantity; system: ReportUnits; onChange: (q: Quantity) => void; disabled?: boolean;
}) {
  const unit = quantity.unit || systemUnit(system, kind);
  return (
    <label htmlFor={id} className="lam-field">
      <span>{label}</span>
      <span className="lam-field-row">
        <input id={id} type="text" inputMode="decimal" autoComplete="off" value={quantity.value} disabled={disabled} onChange={(e) => onChange({ value: e.target.value, unit })} />
        <select aria-label={`${typeof label === "string" ? label : id} unit`} value={unit} disabled={disabled} onChange={(e) => onChange({ value: quantity.value, unit: e.target.value })}>
          {unitsOf(kind).map((u) => <option key={u} value={u}>{printedUnit(u)}</option>)}
        </select>
      </span>
    </label>
  );
}

function ConstantsCard({ own, system, onApply }: { own: OwnConstants; system: ReportUnits; onApply: (own: OwnConstants) => void }) {
  const [draft, setDraft] = useState<OwnConstants>(own);
  const set = (name: ConstantName, q: Quantity | string) => setDraft({ ...draft, [name]: q });
  return (
    <form className="chat-rows lam-card" data-testid="constants-card" onSubmit={(e) => { e.preventDefault(); onApply(draft); }}>
      <div className="lam-grid3">
        {CONSTANT_NAMES.map((name) => {
          const kind = KIND_OF[name];
          const id = `lam-${name}`;
          if (kind === null) {
            return (
              <label key={name} htmlFor={id} className="lam-field"><span>{LABELS[name]} <small>no unit</small></span>
                <input id={id} type="text" inputMode="decimal" autoComplete="off" value={draft.nu12 as string} onChange={(e) => set("nu12", e.target.value)} /></label>
            );
          }
          const q = draft[name] as Quantity;
          return <QuantityField key={name} id={id} label={LABELS[name]} kind={kind} quantity={q} system={system} onChange={(next) => set(name, next)} />;
        })}
      </div>
      <div className="chat-rows-grid">
        <label htmlFor="lam-name" className="lam-field"><span>Material name</span>
          <input id="lam-name" type="text" autoComplete="off" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
        <label htmlFor="lam-source" className="lam-field"><span>Where the numbers come from <small>optional</small></span>
          <input id="lam-source" type="text" autoComplete="off" value={draft.source} onChange={(e) => setDraft({ ...draft, source: e.target.value })} /></label>
      </div>
      <p className="chat-note">Give all five strengths or none. Each value keeps the unit on its menu.</p>
      <button type="submit" className="chat-primary">Use these constants</button>
    </form>
  );
}

function LayupCard({ draft, system, onApply }: { draft: LaminateDraft; system: ReportUnits; onApply: (notation: string, thickness: Quantity | null) => void }) {
  const [text, setText] = useState(draft.layup?.notation ?? "");
  const recorded = draft.material && "library" in draft.material ? libraryThicknessOf(draft.material.library) : null;
  const [thickness, setThickness] = useState<Quantity>(draft.thickness ?? { value: "", unit: systemUnit(system, "length") });
  const [error, setError] = useState("");
  return (
    <form className="chat-inline lam-layup" data-testid="layup-card" onSubmit={(e) => {
      e.preventDefault();
      const line = readLayupLine(text.trim().startsWith("[") ? text : `[${text}]`, system);
      if (!line.layup) { setError(line.refused[0] ?? "Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s."); return; }
      if (recorded === null && !thickness.value.trim()) { setError("Give the ply thickness too."); return; }
      onApply(line.layup.notation, thickness.value.trim() ? thickness : null);
    }}>
      <input type="text" aria-label="Layup" placeholder="[45/0/-45/90]s" value={text} onChange={(e) => { setText(e.target.value); setError(""); }} autoComplete="off" />
      <QuantityField id="lam-thickness" label={recorded === null ? "Ply thickness" : "Ply thickness (optional)"} kind="length" quantity={thickness} system={system} onChange={(q) => { setThickness(q); setError(""); }} />
      <button type="submit" className="chat-primary">Use layup</button>
      {recorded !== null && !thickness.value.trim() ? <span className="chat-note">Ply thickness {Number(recorded.toPrecision(4))} mm, from the library record; type one to use another.</span> : null}
      {error ? <span className="chat-error" role="alert">{error}</span> : null}
    </form>
  );
}

function LoadsCard({ loads, system, onApply }: { loads: Record<LoadName, Quantity> | null; system: ReportUnits; onApply: (loads: Record<LoadName, Quantity>) => void }) {
  const blank = (name: LoadName): Quantity => ({ value: "", unit: systemUnit(system, name.startsWith("N") ? "N" : "M") });
  const [draft, setDraft] = useState<Record<LoadName, Quantity>>(loads ?? (Object.fromEntries(LOAD_NAMES.map((n) => [n, blank(n)])) as Record<LoadName, Quantity>));
  const [error, setError] = useState("");
  const blanks = LOAD_NAMES.filter((n) => !draft[n].value.trim());
  return (
    <form className="chat-rows lam-card" data-testid="loads-card" onSubmit={(e) => {
      e.preventDefault();
      if (blanks.length) { setError(`Give ${blanks.join(", ")} too, or click “the rest are zero”.`); return; }
      onApply(draft);
    }}>
      <div className="lam-grid3">
        {LOAD_NAMES.map((name) => (
          <QuantityField key={name} id={`lam-${name}`} label={<>{name[0]}<sub>{name.slice(1)}</sub></>} kind={name.startsWith("N") ? "N" : "M"} quantity={draft[name]} system={system}
            onChange={(q) => { setDraft({ ...draft, [name]: q }); setError(""); }} />
        ))}
      </div>
      <div className="chat-actions">
        <button type="submit" className="chat-primary">Use these loads</button>
        {blanks.length ? <button type="button" className="chat-secondary" onClick={() => { setDraft(loadsWithZeros(Object.fromEntries(LOAD_NAMES.filter((n) => draft[n].value.trim()).map((n) => [n, draft[n]])), system)); setError(""); }}>The rest are zero</button> : null}
      </div>
      <p className="chat-note">N are forces per unit width, M moments per unit width. Compression and reversed moments are negative.</p>
      {error ? <span className="chat-error" role="alert">{error}</span> : null}
    </form>
  );
}

function Chips({ children }: { children: ReactNode }) { return <div className="chat-chips">{children}</div>; }

/** The chat's laminate problems (ADR-0060; ADR-0055 amendment 2): units, material, layup and loads, each value with its own unit,
 * solved by the engine through `POST /v1/laminates/solve`; the answer beside the conversation in the units the engineer picks. */
export function LaminateChat({ apiBaseUrl, onBack }: { apiBaseUrl: string; onBack: () => void }) {
  const [draft, setDraftState] = useState<LaminateDraft>(blankDraft);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [ownMaterial, setOwnMaterial] = useState(false);
  const [solving, setSolving] = useState(false);
  const [answer, setAnswer] = useState<LaminateAnswer | null>(null);
  const [stamp, setStamp] = useState(0);
  const [problem, setProblem] = useState("");
  const nextId = useRef(1);
  const body = useRef<HTMLDivElement>(null);
  const draftRef = useRef(draft);
  const started = useRef(false);

  const setDraft = (next: LaminateDraft) => { draftRef.current = next; setDraftState(next); };
  const add = (...items: NewEntry[]) => {
    const made = items.map((item) => ({ ...item, id: nextId.current++ }) as Entry);
    setEntries((list) => [...list, ...made]);
    return made;
  };
  const ask = (step: LaminateStep) => { const [entry] = add({ role: "assistant", kind: "ask", step }); setActive(entry.id); };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    add({ role: "user", text: "Laminate response" });
    ask("units");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" }); }, [entries, solving]);

  function proceed(next: LaminateDraft) { ask(nextStep(next)); }

  /** Apply what a click or a card gave, echo it, and move on. */
  function answerWith(echo: string, next: LaminateDraft) {
    setDraft(next);
    setAnswer(null);
    add({ role: "user", text: echo });
    proceed(next);
  }

  function startOver() {
    setDraft(blankDraft()); setAnswer(null); setOwnMaterial(false); setProblem("");
    setEntries([]);
    add({ role: "user", text: "New problem" });
    ask("units");
  }

  async function solve(reportUnits?: ReportUnits) {
    const built = buildProblem(draftRef.current, reportUnits ?? (answer?.report_units as ReportUnits | undefined));
    if (built.errors) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "Something is still missing", body: <ul className="chat-understood">{built.errors.map((e) => <li key={e}>{e}</li>)}</ul> });
      return;
    }
    if (!apiBaseUrl) {
      add({ role: "assistant", kind: "text", tone: "problem", title: "The engine is not connected",
        body: <p>This page was built without the API address (NEXT_PUBLIC_ANISOTROPY_API_URL), so I can take the problem down but cannot solve it.</p> });
      return;
    }
    setActive(null); setSolving(true); setProblem("");
    try {
      const solved = await solveLaminate(apiBaseUrl, built.problem);
      setAnswer(solved);
      if (!reportUnits) { const next = stamp + 1; setStamp(next); add({ role: "assistant", kind: "answer", stamp: next }); }
    } catch (error) {
      const message = error instanceof StudioError ? error.message : "The solve failed.";
      if (reportUnits) setProblem(message);
      else add({ role: "assistant", kind: "text", tone: "problem", title: "The engine refused the problem", body: <p>{message}</p> });
    } finally {
      setSolving(false);
    }
  }

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    if (/^(start over|reset|new problem|restart)\b/i.test(text)) { startOver(); return; }
    if (/^(back|coupon|coupons|back to coupons)\b/i.test(text)) { add({ role: "user", text }); onBack(); return; }
    const current = entries.find((e) => e.id === active);
    const step = current && current.role === "assistant" && current.kind === "ask" ? current.step : nextStep(draftRef.current);
    if (/^(solve|run|go|solve it)\b/i.test(text) && nextStep(draftRef.current) === "review") { add({ role: "user", text }); void solve(); return; }
    let next: LaminateDraft = { ...draftRef.current };
    const understood: string[] = [];
    const refused: string[] = [];
    const named = readSystem(text);
    if (named && (step === "units" || !next.system)) { next.system = named; understood.push(`units: ${REPORT_SYSTEMS.find((s) => s.id === named)?.title}`); }
    const system = next.system;
    if (!system) {
      add({ role: "user", text }, { role: "assistant", kind: "text", title: "Which units first?", body: <p>Pick the system the problem is stated in, or name it: SI, mm and MPa, US customary or psi.</p> });
      return;
    }
    const library = readLibraryMaterial(text);
    if (library) { next.material = { library }; understood.push(`material: ${libraryNameOf(library)}`); }
    else {
      const read = readConstants(text, system);
      refused.push(...read.refused);
      if (read.understood.length) {
        const own = next.material && "own" in next.material ? { ...next.material.own } : blankOwn();
        for (const [name, q] of Object.entries(read.constants)) (own as unknown as Record<string, Quantity | string>)[name] = q;
        next.material = { own };
        setOwnMaterial(true);
        understood.push(...read.understood);
      }
    }
    const line = readLayupLine(text, system);
    refused.push(...line.refused);
    if (line.layup) { next.layup = line.layup; understood.push(...line.understood.filter((u) => u.startsWith("layup"))); }
    if (line.thickness) { next.thickness = line.thickness; understood.push(...line.understood.filter((u) => u.startsWith("ply thickness"))); }
    const loads = readLoads(text, system);
    refused.push(...loads.refused);
    if (Object.keys(loads.loads).length) {
      const merged = { ...(next.loads ?? {}), ...loads.loads } as Partial<Record<LoadName, Quantity>>;
      next.loads = loads.othersZero ? loadsWithZeros(merged, system) : LOAD_NAMES.every((n) => merged[n]) ? merged as Record<LoadName, Quantity>
        : (Object.fromEntries(LOAD_NAMES.map((n) => [n, merged[n] ?? { value: "", unit: systemUnit(system, n.startsWith("N") ? "N" : "M") }])) as Record<LoadName, Quantity>);
      understood.push(...loads.understood);
    }
    if (!understood.length) {
      add({ role: "user", text }, { role: "assistant", kind: "text", tone: refused.length ? "problem" : undefined, title: refused.length ? "A unit does not fit" : "I could not read a laminate value in that",
        body: refused.length ? <ul className="chat-understood">{refused.map((r) => <li key={r}>{r}</li>)}</ul>
          : <p>Try the options above, or a phrase like “AS4/8552”, “E1 147 GPa, E2 10.3, G12 7, nu12 0.27”, “[0/90]2s, 0.125 mm plies” or “Nx = 100 N/mm, everything else zero”. Type “back” for the coupon tests.</p> });
      return;
    }
    add({ role: "user", text }, { role: "assistant", kind: "text", title: "Got it",
      body: <><ul className="chat-understood">{understood.map((u) => <li key={u}><Check size={13} /> {u}</li>)}</ul>
        {refused.length ? <ul className="chat-understood chat-refused">{refused.map((r) => <li key={r}>{r}</li>)}</ul> : null}</> });
    setDraft(next); setAnswer(null);
    proceed(next);
  }

  function askWidget(step: LaminateStep, live: boolean): ReactNode {
    if (!live) return null;
    const system = (draft.system || "SI") as ReportUnits;
    switch (step) {
      case "units":
        return (
          <>
            <div className="chat-choice-grid">
              {REPORT_SYSTEMS.map((s) => (
                <button type="button" key={s.id} className="chat-choice" data-system={s.id} onClick={() => answerWith(s.title, { ...draftRef.current, system: s.id })}>
                  <strong>{s.title}</strong><span>{s.detail}</span>
                </button>
              ))}
            </div>
            <Chips><button type="button" onClick={onBack}><ArrowLeft size={14} /> Back to the coupon tests</button></Chips>
          </>
        );
      case "material":
        return ownMaterial ? (
          <ConstantsCard own={draft.material && "own" in draft.material ? draft.material.own : blankOwn()} system={system}
            onApply={(own) => answerWith(`My own constants: ${own.name.trim() || "unnamed"}`, { ...draftRef.current, material: { own } })} />
        ) : (
          <>
            <Chips>
              {COMMON_MATERIALS.filter((id) => libraryOptions.some((m) => m.id === id)).map((id) => (
                <button type="button" key={id} onClick={() => answerWith(libraryNameOf(id), { ...draftRef.current, material: { library: id } })}><Layers3 size={14} /> {libraryNameOf(id)}</button>
              ))}
            </Chips>
            <div className="chat-inline">
              <select aria-label="Another library material" defaultValue="" onChange={(e) => e.target.value && answerWith(libraryNameOf(e.target.value), { ...draftRef.current, material: { library: e.target.value } })}>
                <option value="">Another library material…</option>
                {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
              <button type="button" className="chat-link" onClick={() => setOwnMaterial(true)}>Type my own constants</button>
            </div>
          </>
        );
      case "layup":
        return (
          <>
            <Chips>
              {LAYUP_CHOICES.map((c) => (
                <button type="button" key={c.notation} onClick={() => {
                  const line = readLayupLine(c.notation, system);
                  if (line.layup) answerWith(c.notation, { ...draftRef.current, layup: line.layup });
                }}><Layers3 size={14} /> {c.title} <code>{c.notation}</code></button>
              ))}
            </Chips>
            <LayupCard draft={draft} system={system} onApply={(notation, thickness) => {
              const line = readLayupLine(notation, system);
              if (line.layup) answerWith(thickness ? `${notation}, ${thickness.value} ${printedUnit(thickness.unit)} plies` : notation, { ...draftRef.current, layup: line.layup, thickness });
            }} />
          </>
        );
      case "loads":
        return (
          <>
            <Chips>
              <button type="button" onClick={() => answerWith(`Nx = 100 ${printedUnit(systemUnit(system, "N"))}, the rest zero`, { ...draftRef.current, loads: loadsWithZeros({ Nx: { value: "100", unit: systemUnit(system, "N") } }, system) })}>
                Nx = 100 {printedUnit(systemUnit(system, "N"))} only</button>
            </Chips>
            <LoadsCard loads={draft.loads} system={system} onApply={(loads) => answerWith(
              LOAD_NAMES.filter((n) => Number(loads[n].value) !== 0).map((n) => `${n} = ${loads[n].value} ${printedUnit(loads[n].unit)}`).join(", ") || "No load",
              { ...draftRef.current, loads })} />
          </>
        );
      case "review": {
        const lines = problemLines(draft);
        return (
          <div className="lam-review" data-testid="laminate-review">
            <dl className="studio-summary">{lines.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}</dl>
            <div className="chat-inline">
              <label htmlFor="lam-f12" className="lam-field"><span>Tsai-Wu f12* <small>optional, between -1 and 1</small></span>
                <input id="lam-f12" type="text" inputMode="decimal" autoComplete="off" className="chat-small-input" placeholder="-0.5" value={draft.f12_star}
                  onChange={(e) => setDraft({ ...draftRef.current, f12_star: e.target.value })} /></label>
              <label className="lam-field lam-check"><input type="checkbox" data-testid="lam-strain-limits" checked={draft.strain_limits}
                onChange={(e) => setDraft({ ...draftRef.current, strain_limits: e.target.checked })} />
                <span>Maximum strain too <small>limits derived from the strengths (strength over modulus, linear to failure)</small></span></label>
            </div>
            <div className="chat-actions">
              <button type="button" className="chat-primary" data-testid="laminate-solve" onClick={() => { add({ role: "user", text: "Solve" }); void solve(); }} disabled={solving}><Play size={14} /> Solve</button>
              <button type="button" className="chat-secondary" onClick={() => ask("material")}>Change the material</button>
              <button type="button" className="chat-secondary" onClick={() => ask("layup")}>Change the layup</button>
              <button type="button" className="chat-secondary" onClick={() => ask("loads")}>Change the loads</button>
            </div>
          </div>
        );
      }
    }
  }

  function answerMessage(entryStamp: number): ReactNode {
    if (!answer || entryStamp !== stamp) return <p className="chat-note">An earlier answer; the problem has changed since.</p>;
    return (
      <div data-testid="laminate-answer">
        <h4>Solved</h4>
        {answer.prose.slice(0, 2).map((sentence, i) => <p key={i}>{sentence}</p>)}
        {answer.prose.length > 3 ? <p>{answer.prose[3]}</p> : null}
        <p className="chat-note">The matrices, every ply's stresses and each criterion are on the right, in the units you pick there.</p>
        <Chips>
          <button type="button" onClick={() => ask("loads")}>Change the loads</button>
          <button type="button" onClick={() => ask("layup")}>Change the layup</button>
          <button type="button" onClick={() => ask("material")}>Try another material</button>
          <button type="button" onClick={startOver}><RotateCcw size={14} /> New problem</button>
        </Chips>
      </div>
    );
  }

  function render(entry: Entry): ReactNode {
    if (entry.role === "user") return <div className="chat-user" key={entry.id}>{entry.text}</div>;
    let content: ReactNode;
    if (entry.kind === "ask") {
      const q = QUESTIONS[entry.step];
      const live = entry.id === active && !solving;
      content = <div data-step={entry.step} data-testid={live ? "chat-question" : undefined}><h4>{q.title}</h4>{live ? <p>{q.text}</p> : null}{askWidget(entry.step, live)}</div>;
    } else if (entry.kind === "text") content = <div className={entry.tone === "problem" ? "chat-problem" : undefined}>{entry.title ? <h4>{entry.title}</h4> : null}{entry.body}</div>;
    else content = answerMessage(entry.stamp);
    return (
      <div className="chat-assistant" key={entry.id}>
        <span className="message-avatar"><Sparkles size={15} /></span>
        <div>{content}</div>
      </div>
    );
  }

  const lines = problemLines(draft);
  return (
    <div className="chat-studio" data-testid="laminate-chat">
      <section className="chat-pane" aria-label="Laminate assistant">
        <div className="chat-pane-top">
          <span><span className="status-dot" /> Laminate assistant</span>
          <span>
            <button type="button" className="chat-link" onClick={onBack}><ArrowLeft size={13} /> Coupon tests</button>
            <button type="button" className="icon-button" aria-label="Start a new problem" title="Start a new problem" onClick={startOver}><RotateCcw size={14} /></button>
          </span>
        </div>
        <div className="chat-scroll" ref={body} aria-live="polite" aria-relevant="additions">
          {entries.map(render)}
          {solving ? <div className="chat-assistant"><span className="message-avatar"><Sparkles size={15} /></span><div><p className="chat-typing">Solving the stack…</p></div></div> : null}
          {problem ? <p className="studio-alert" role="alert">{problem}</p> : null}
        </div>
        <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <textarea aria-label="Message the laminate assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="State the problem or change one thing, e.g. “[0/90]2s, 0.125 mm plies” or “Nx = 100 N/mm, everything else zero”"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
          <div className="composer-footer">
            <span className="chat-note">Enter to send · “solve” · “new problem” · “back”</span>
            <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
          </div>
        </form>
      </section>
      <section className="chat-bench" aria-label="The problem and its answer">
        <dl className="chat-spec lam-spec" data-testid="laminate-spec">
          {lines.map(([k, v]) => <div key={k} data-filled={v ? "yes" : "no"}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}
        </dl>
        {answer ? <LaminateResults answer={answer} busy={solving} onReport={(system) => void solve(system)} /> : (
          <div className="studio-empty" data-testid="empty-answer">
            <h3>The answer appears here</h3>
            <p>Once the problem is stated, the engine solves it in seconds: the A, B, D matrices, the strains, every ply&apos;s stresses and first-ply failure, in the units you pick.</p>
          </div>
        )}
      </section>
    </div>
  );
}
