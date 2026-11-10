"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft, ArrowUp, Check, Layers3, Play, RotateCcw, SlidersHorizontal, Sparkles } from "lucide-react";
import { libraryOptions } from "@/lib/studio-form";
import { COMMON_MATERIALS } from "@/lib/studio-chat";
import {
  libraryNameOf, LOAD_NAMES, loadsWithZeros, missingIn, nextStep, printedUnit, problemLines, readConstants, readLayupLine, readLibraryMaterial, readLoads,
  readSystem, REPORT_SYSTEMS, systemUnit, type LaminateDraft, type LaminateStep, type LoadName, type Quantity, type ReportUnits,
} from "@/lib/laminate-chat";
import { blankOwn } from "@/components/workspace/panels/laminate-fields";
import { showPanel } from "@/components/workspace/panels/step-panel";
import { useLaminate } from "./laminate-context";

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

/** The panel on the left that holds each step's rows (ADR-0062, part 5): what a suggestion opens. */
const PANEL_OF: Record<LaminateStep, { id: string; title: string }> = {
  units: { id: "units", title: "Units" }, material: { id: "material", title: "Material" }, layup: { id: "layup", title: "Layup" },
  loads: { id: "loads", title: "Loads" }, review: { id: "solve", title: "Solve" },
};

const QUESTIONS: Record<LaminateStep, { title: string; text: string }> = {
  units: { title: "Which units is the problem stated in?", text: "Pick the system. A number typed with its own unit, like 10300 MPa or 0.0049 in, keeps that unit; the engine converts, never this page." },
  material: { title: "Which material?", text: "Pick one from the library, with its cited constants and strengths, or type the constants the problem gives, e.g. “E1 147 GPa, E2 10.3, G12 7, nu12 0.27, F1t 2280, F1c 1725, F2t 57, F2c 228, F6 76 MPa”. Without strengths no failure is predicted." },
  layup: { title: "What is the layup?", text: "Laminate notation, bottom ply first, e.g. [0/45/-45/90]s, and the ply thickness. Here 0° runs along x, the direction of Nx, as in the textbooks; a coupon counts from its length, the direction it is pulled, so 0° is along the main axis in both workspaces." },
  loads: { title: "What loads does it carry?", text: "Force and moment resultants per unit width, e.g. “Nx = 100 N/mm, everything else zero”. Every one of the six is stated; nothing is assumed." },
  review: { title: "Ready to solve", text: "The engine solves the stack by classical lamination theory: the A, B, D matrices, the mid-plane strains and curvatures, every ply's stresses and first-ply failure." },
};

function Chips({ children }: { children: ReactNode }) { return <div className="chat-chips">{children}</div>; }

function PanelLink({ step, children }: { step: LaminateStep; children: ReactNode }) {
  return <button type="button" data-panel={PANEL_OF[step].id} onClick={() => showPanel(PANEL_OF[step].id)}><SlidersHorizontal size={14} /> {children}</button>;
}

/** The laminate assistant (ADR-0060; ADR-0062, part 5): a conversation beside the panels, on the one draft they share. It offers one-click
 * choices, reads a typed line, and for anything else names the panel that asks for it; every value goes to the engine as typed. */
export function LaminateChat({ onBack }: { onBack: () => void }) {
  const { draft, setDraft: storeDraft, answer, solving, stamp, solve, reset, restored } = useLaminate();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const nextId = useRef(1);
  const body = useRef<HTMLDivElement>(null);
  const draftRef = useRef(draft);
  useEffect(() => { draftRef.current = draft; }, [draft]);
  const live = useRef<{ active: number | null; entries: Entry[] }>({ active: null, entries: [] });
  useEffect(() => { live.current = { active, entries }; }, [active, entries]);
  const started = useRef(false);

  const setDraft = (next: LaminateDraft) => { draftRef.current = next; storeDraft(next); };
  const add = (...items: NewEntry[]) => {
    const made = items.map((item) => ({ ...item, id: nextId.current++ }) as Entry);
    setEntries((list) => [...list, ...made]);
    return made;
  };
  const ask = (step: LaminateStep) => { const [entry] = add({ role: "assistant", kind: "ask", step }); setActive(entry.id); };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (draft.system) {
      add({ role: "assistant", kind: "text", title: restored ? "Picked up where you left off" : "The problem so far", body: <p>Here is what is still needed; the panels on the left hold every row.</p> });
      ask(nextStep(draft));
    } else {
      add({ role: "user", text: "Laminate response" });
      ask("units");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" }); }, [entries, solving]);

  // a row typed on a panel answers the open question: move on to the next one
  useEffect(() => {
    const current = live.current.entries.find((e) => e.id === live.current.active);
    if (!current || current.role !== "assistant" || current.kind !== "ask" || current.step === "review") return;
    if (missingIn(current.step, draft).length) return;
    ask(nextStep(draft));
  }, [draft]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (stamp > 0) add({ role: "assistant", kind: "answer", stamp }); }, [stamp]); // eslint-disable-line react-hooks/exhaustive-deps

  function proceed(next: LaminateDraft) { ask(nextStep(next)); }

  /** Apply what a click gave, echo it, and move on. */
  function answerWith(echo: string, next: LaminateDraft) {
    setDraft(next);
    add({ role: "user", text: echo });
    proceed(next);
  }

  function startOver() {
    reset();
    setEntries([]);
    add({ role: "user", text: "New problem" });
    ask("units");
  }

  async function solveNow() {
    setActive(null);
    add({ role: "user", text: "Solve" });
    const outcome = await solve();
    if (outcome.ok) return;
    if ("errors" in outcome) add({ role: "assistant", kind: "text", tone: "problem", title: "Something is still missing", body: <ul className="chat-understood">{outcome.errors.map((e) => <li key={e}>{e}</li>)}</ul> });
    else add({ role: "assistant", kind: "text", tone: "problem", title: "The engine refused the problem", body: <p>{outcome.refused}</p> });
  }

  /** A message that names no value: the panel on the left that asks for the next thing, and a few phrases that would be read. */
  function redirect(text: string) {
    const step = nextStep(draftRef.current);
    const where = PANEL_OF[step];
    add({ role: "user", text }, { role: "assistant", kind: "text", title: "Pick a step on the left, or describe one thing",
      body: <div data-testid="chat-redirect" data-panel={where.id}>
        <p>{step === "review" ? "Everything is stated: solve it under Solve, or say “solve”." : `The next thing to state is ${QUESTIONS[step].title.toLowerCase().replace(/\?$/, "")}, under the ${where.title} panel.`} Or
          type a phrase like “AS4/8552”, “E1 147 GPa, E2 10.3, G12 7, nu12 0.27”, “[0/90]2s, 0.125 mm plies” or “Nx = 100 N/mm, everything else zero”. Type “back” for the coupon tests.</p>
        <Chips><PanelLink step={step}>Open {where.title}</PanelLink>{step !== "review" ? <button type="button" onClick={() => ask(step)}>Ask me here</button> : null}</Chips>
      </div> });
  }

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    if (/^(start over|reset|new problem|restart)\b/i.test(text)) { startOver(); return; }
    if (/^(back|coupon|coupons|back to coupons)\b/i.test(text)) { add({ role: "user", text }); onBack(); return; }
    const current = entries.find((e) => e.id === active);
    const step = current && current.role === "assistant" && current.kind === "ask" ? current.step : nextStep(draftRef.current);
    if (/^(solve|run|go|solve it)\b/i.test(text)) {
      if (nextStep(draftRef.current) === "review") { void solveNow(); } else redirect(text);
      return;
    }
    const next: LaminateDraft = { ...draftRef.current };
    const understood: string[] = [];
    const refused: string[] = [];
    const named = readSystem(text);
    if (named && (step === "units" || !next.system)) { next.system = named; understood.push(`units: ${REPORT_SYSTEMS.find((s) => s.id === named)?.title}`); }
    const system = next.system;
    if (!system) {
      add({ role: "user", text }, { role: "assistant", kind: "text", title: "Which units first?", body: <><p>Pick the system the problem is stated in, or name it: SI, mm and MPa, US customary or psi.</p><Chips><PanelLink step="units">Open Units</PanelLink></Chips></> });
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
      if (refused.length) {
        add({ role: "user", text }, { role: "assistant", kind: "text", tone: "problem", title: "A unit does not fit", body: <ul className="chat-understood">{refused.map((r) => <li key={r}>{r}</li>)}</ul> });
      } else redirect(text);
      return;
    }
    add({ role: "user", text }, { role: "assistant", kind: "text", title: "Got it",
      body: <><ul className="chat-understood">{understood.map((u) => <li key={u}><Check size={13} /> {u}</li>)}</ul>
        {refused.length ? <ul className="chat-understood chat-refused">{refused.map((r) => <li key={r}>{r}</li>)}</ul> : null}</> });
    setDraft(next);
    proceed(next);
  }

  function askWidget(step: LaminateStep, isLive: boolean): ReactNode {
    if (!isLive) return null;
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
        return (
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
            </div>
            <Chips><PanelLink step="material">My own constants, under Material</PanelLink></Chips>
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
            <Chips><PanelLink step="layup">The layup and the ply thickness, under Layup</PanelLink></Chips>
          </>
        );
      case "loads":
        return (
          <>
            <Chips>
              <button type="button" onClick={() => answerWith(`Nx = 100 ${printedUnit(systemUnit(system, "N"))}, the rest zero`, { ...draftRef.current, loads: loadsWithZeros({ Nx: { value: "100", unit: systemUnit(system, "N") } }, system) })}>
                Nx = 100 {printedUnit(systemUnit(system, "N"))} only</button>
              <PanelLink step="loads">All six loads, under Loads</PanelLink>
            </Chips>
          </>
        );
      case "review": {
        const lines = problemLines(draft);
        return (
          <div className="lam-review" data-testid="laminate-review">
            <dl className="studio-summary">{lines.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v || "–"}</dd></div>)}</dl>
            <p className="chat-note">Tsai-Wu&apos;s f12* and maximum strain are options under Solve.</p>
            <div className="chat-actions">
              <button type="button" className="chat-primary" data-testid="laminate-solve" onClick={() => void solveNow()} disabled={solving}><Play size={14} /> Solve</button>
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
        <p className="chat-note">The matrices, every ply&apos;s stresses and each criterion are in the centre, in the units you pick there.</p>
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
      const isLive = entry.id === active && !solving;
      content = <div data-step={entry.step} data-testid={isLive ? "chat-question" : undefined}><h4>{q.title}</h4>{isLive ? <p>{q.text}</p> : null}{askWidget(entry.step, isLive)}</div>;
    } else if (entry.kind === "text") content = <div className={entry.tone === "problem" ? "chat-problem" : undefined}>{entry.title ? <h4>{entry.title}</h4> : null}{entry.body}</div>;
    else content = answerMessage(entry.stamp);
    return (
      <div className="chat-assistant" key={entry.id}>
        <span className="message-avatar"><Sparkles size={15} /></span>
        <div>{content}</div>
      </div>
    );
  }

  return (
    <section className="chat-pane" aria-label="Laminate assistant" data-testid="laminate-chat">
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
  );
}
