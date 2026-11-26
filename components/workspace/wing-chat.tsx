"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, CircleAlert, MessagesSquare } from "lucide-react";
import { approvePlan, askPlan, assistantInfo, noPlanner, previewWingChange, putProject, readPlan, StudioError, wingReferences, type AssistantInfo, type Plan,
  type ReferenceSection } from "@/lib/studio-api";
import { previewBasis, previewRows, previewWarnings, readWingAsk, routeWingAsk, wingAnswer, type WingAsk, type WingChangePreview, type WingSaid } from "@/lib/wing-chat";
import { newKindFlow, wingRuns, type KindFlow } from "@/lib/plan-kinds";
import { isUuid, uploadOf } from "@/lib/project-store";
import { wingKey } from "@/lib/wing-versions";
import { bannedIn, sectionProse as prose } from "@/lib/studio-copy";
import type { WingDescription, WingFeCheck } from "@/lib/wing";
import { useWing } from "./wing-context";
import { WingPlanCard } from "./wing-plan";
import { showPanel } from "./panels/step-panel";

const PANEL_TITLES: Record<string, string> = {
  "wing-layup": "Layup", "wing-material": "Material", "wing-loads": "Loads", "wing-geometry": "Geometry", "wing-shape": "Shape for CAD",
};

type Entry =
  | { id: number; role: "user"; text: string }
  | {
    id: number; role: "assistant"; message: string; said: WingSaid;
    /** a change: the wing it was previewed on, the preview once the API answers, and what the engineer did with it */
    from?: WingDescription; preview?: WingChangePreview; outcome?: "applied" | "dismissed";
    /** the sections of our pages the question's words find, once the API answers */
    references?: ReferenceSection[];
    problem?: string; waiting?: boolean;
  }
  /** a sentence planned by the API (ADR-0144, step 5), its card and where it stands; `said` is the message as typed */
  | { id: number; role: "plan"; said: string; flow: KindFlow }
  /** a plan that could not be made, in the page's words */
  | { id: number; role: "problem"; title: string; text: string };

/** Asks whose answer the reference pages explain, beside the wing's own facts. */
const EXPLAINED = new Set(["reference", "rule-limit", "rules", "strengths"]);

/** The check a plan started, as the page follows one: the approval's own answer for it, or, when that cannot be read, the job by its id. */
function planCheck(check: WingFeCheck | null, plan: Plan): WingFeCheck | null {
  if (check) return check;
  return plan.job ? { job_id: plan.job, state: "queued", wing: null, started_at: plan.approved_at ?? "", finished_at: null, stage: null, stages_done: [], stages: [],
    message: null, run_id: null, report: null } : null;
}

/** The wing's chat (ADR-0128), under the answer in words: a change of plies is read from the message and previewed by the engine on a copy
 * of the wing, which changes only when the engineer taps Apply (a new version, by the assistant, with the message); a question about the
 * wing is answered from the engine's report the page holds; a question of why, how or which test from our reference pages. Where a model
 * reads and the wing project is kept, a sentence of a change of plies and a run, a check or an answer is planned by the API (ADR-0144,
 * step 5) and shown on the plan's card, approved once; one change alone stays with the patterns and the Apply tap. What the patterns
 * cannot read is said plainly, with examples. */
export function WingChat() {
  const { apiBaseUrl, project, kept, wing, answer, replace, versions, adoptPlan } = useWing();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState<AssistantInfo | null>(null);
  const [planning, setPlanning] = useState(false);
  const next = useRef(1);
  const composer = useRef<HTMLTextAreaElement>(null);
  const plannerOff = useRef(false); // no planner here, or the day's plans are used: messages are read as before
  const planAsking = useRef<string | null>(null); // the sentence a plan's question back belongs to
  const live = useRef({ entries, project });
  live.current = { entries, project };
  const update = (id: number, change: Partial<Extract<Entry, { role: "assistant" }>>) =>
    setEntries((list) => list.map((e) => (e.id === id && e.role === "assistant" ? { ...e, ...change } : e)));
  const updateFlow = useCallback((id: number, change: (flow: KindFlow) => KindFlow) =>
    setEntries((list) => list.map((e) => (e.id === id && e.role === "plan" ? { ...e, flow: change(e.flow) } : e))), []);
  const nextId = () => { next.current += 1; return next.current; };

  useEffect(() => {
    if (!apiBaseUrl) return;
    let current = true;
    void assistantInfo(apiBaseUrl).then((info) => { if (current) setModel(info); });
    return () => { current = false; };
  }, [apiBaseUrl]);

  function send() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    const planner = !!apiBaseUrl && !!model?.proposes && kept && isUuid(project.id) && !plannerOff.current;
    const asked = planAsking.current; // a plan's question back is answered by this message
    planAsking.current = null;
    if (planner && asked) { void planFor(message, `${asked.replace(/[.\s]+$/, "")}. ${message}`); return; }
    const ask: WingAsk = routeWingAsk(message, planner);
    if (ask.route === "wing-plan") { void planFor(message, message); return; }
    answerUsual(message, ask);
  }

  /** A message read by the page's own patterns, as before the planner. */
  function answerUsual(message: string, ask: WingAsk = readWingAsk(message)) {
    const said = wingAnswer(ask, answer?.report ?? null, wing);
    next.current += 2;
    const id = next.current;
    const entry: Entry = { id, role: "assistant", message, said, waiting: said.kind === "preview" || (EXPLAINED.has(said.kind) && !!apiBaseUrl) };
    if (said.kind === "preview") entry.from = wing;
    setEntries((list) => [...list, { id: id - 1, role: "user", text: message }, entry]);
    if (ask.route === "wing-change" && ask.change) {
      if (!apiBaseUrl) { update(id, { waiting: false, problem: "The analysis service is not set up on this page." }); return; }
      previewWingChange(apiBaseUrl, wing, ask.change)
        .then((preview) => update(id, { preview, waiting: false }))
        .catch((error) => update(id, { waiting: false, problem: error instanceof StudioError ? error.message : "The change could not be previewed. Try again." }));
    } else if (EXPLAINED.has(said.kind) && apiBaseUrl) {
      wingReferences(apiBaseUrl, message)
        .then((references) => update(id, { references, waiting: false }))
        .catch(() => update(id, { references: [], waiting: false }));
    }
  }

  /** A sentence planned by the API on the wing project as it stands (ADR-0144, step 5): the project goes to the server first, so the plan is
   * worked out on the wing the page shows. With no planner here the sentence is read as before, and the planner is not asked again this
   * session. `said` is the message as typed, null when a plan is asked again from its card; `ask` is the sentence planned. */
  async function planFor(said: string | null, ask: string) {
    const echo = said === null ? null : nextId();
    if (echo !== null) setEntries((list) => [...list, { id: echo, role: "user", text: said! }]);
    const usual = () => {
      plannerOff.current = true;
      if (echo !== null) setEntries((list) => list.filter((e) => e.id !== echo));
      answerUsual(said ?? ask);
    };
    setPlanning(true);
    const held = live.current.project;
    let plan: Plan;
    try {
      await putProject(apiBaseUrl, held.id, uploadOf(held));
      plan = await askPlan(apiBaseUrl, held.id, ask);
    } catch (error) {
      setPlanning(false);
      if (noPlanner(error)) { usual(); return; }
      setEntries((list) => [...list, { id: nextId(), role: "problem", title: "No plan right now",
        text: error instanceof StudioError ? error.message : "The plan could not be made. Try again." }]);
      return;
    }
    setPlanning(false);
    if (plan.state === "unavailable") { usual(); return; }
    if (plan.state === "capped") plannerOff.current = true; // the day's plans are used: messages are read as before until tomorrow
    if (plan.state === "question") planAsking.current = ask;
    setEntries((list) => [...list, { id: nextId(), role: "plan", said: said ?? ask, flow: newKindFlow(plan) }]);
  }

  /** The plan approved (ADR-0144, step 5): the server makes the changes of plies, works the wing by hand and starts the check; the page
   * takes the wing it left as a version by the assistant with the sentence as why, shows the hand calculation and follows the check. A
   * wing changed since the plan (409) changes nothing, and the plan can be made again. */
  async function approve(id: number) {
    const entry = live.current.entries.find((e) => e.id === id);
    if (!entry || entry.role !== "plan" || entry.flow.stage !== "proposed") return;
    const plan = entry.flow.plan;
    const held = live.current.project;
    updateFlow(id, (f) => ({ ...f, stage: "approving", problem: null, since: Date.now() }));
    try {
      const approval = await approvePlan(apiBaseUrl, held.id, plan.id, plan.base);
      const left = approval.project.content.wing;
      if (!left || typeof left !== "object" || Array.isArray(left)) throw new StudioError("The changed wing could not be read. Reload the page to see it.");
      const runs = wingRuns(approval.runs);
      adoptPlan({ wing: left as WingDescription, why: plan.ask, answer: runs.analyze, check: planCheck(runs.check, approval.plan) });
      updateFlow(id, (f) => ({ ...f, stage: "approved", plan: approval.plan, runs: approval.runs, check: planCheck(runs.check, approval.plan),
        left: wingKey(left as WingDescription) }));
    } catch (error) {
      if (error instanceof StudioError && error.status === 409) {
        let now: Plan | null = null;
        try { now = await readPlan(apiBaseUrl, held.id, plan.id); } catch { /* said as a changed wing */ }
        const already = now !== null && (now.approved_at !== null || !["proposed", "question"].includes(now.state));
        updateFlow(id, (f) => ({ ...f, stage: "stale", problem: already ? "This plan was approved already."
          : "The wing changed since this plan was made, so nothing was changed. Plan it again on the wing as it is now." }));
        return;
      }
      updateFlow(id, (f) => ({ ...f, stage: "proposed", problem: error instanceof StudioError ? error.message : "The plan could not be approved. Try again." }));
    }
  }

  /** The sentence planned back in the message box, to change and send again. */
  function edit(id: number, said: string) {
    updateFlow(id, (f) => (f.stage === "proposed" ? { ...f, stage: "edited" } : f));
    setInput(said);
    window.setTimeout(() => composer.current?.focus(), 0);
  }

  function apply(entry: Extract<Entry, { role: "assistant" }>) {
    if (!entry.preview) return;
    versions.attribute("assistant", entry.message); // the version this makes says who made it and from which message
    replace(entry.preview.wing);
    update(entry.id, { outcome: "applied" });
  }

  return (
    <div className="wing-chat" data-testid="wing-chat">
      {entries.length || planning ? (
        <div className="wing-chat-scroll" aria-live="polite" aria-relevant="additions">
          {entries.map((e) => e.role === "user"
            ? <div className="chat-user" key={e.id}>{e.text}</div>
            : (
              <div className="chat-assistant" key={e.id} data-testid="wing-chat-answer" data-kind={e.role === "assistant" ? e.said.kind : e.role}>
                <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
                <div>
                  {e.role === "plan" ? (
                    <WingPlanCard flow={e.flow} onFlow={(change) => updateFlow(e.id, change)} onApprove={() => void approve(e.id)} onEdit={() => edit(e.id, e.flow.plan.ask)}
                      onPlanAgain={() => void planFor(null, e.flow.plan.ask)} onUsual={() => answerUsual(e.said)} />
                  ) : e.role === "problem" ? (
                    <><h4>{e.title}</h4><p className="chat-problem" role="alert" data-testid="plan-failed">{e.text}</p></>
                  ) : (
                    <Answer entry={e} stale={!!e.from && wingKey(e.from) !== wingKey(wing)} onApply={() => apply(e)} onDismiss={() => update(e.id, { outcome: "dismissed" })} />
                  )}
                </div>
              </div>
            ))}
          {planning ? (
            <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
              <div><p className="chat-typing" data-testid="chat-planning">Planning the steps…</p></div></div>
          ) : null}
        </div>
      ) : null}
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea ref={composer} aria-label="Message the wing assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the wing, or one change, e.g. “add 2 0° plies to the spar caps from the root to 40% span”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Nothing changes until you tap Apply or Approve</span>
          <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
        </div>
      </form>
    </div>
  );
}

function Answer({ entry, stale, onApply, onDismiss }: { entry: Extract<Entry, { role: "assistant" }>; stale: boolean; onApply(): void; onDismiss(): void }) {
  const { said, preview } = entry;
  if (said.kind === "preview") {
    if (entry.problem) return <><h4>Not previewed</h4><p className="chat-problem" role="alert">{entry.problem}</p></>;
    if (!preview) return <><h4>{said.heading}</h4><p>{said.lines[0]}</p><p className="chat-typing">Working the wing as it is and as changed…</p></>;
    return <Preview preview={preview} outcome={entry.outcome} stale={stale} onApply={onApply} onDismiss={onDismiss} />;
  }
  // a section is shown only in the product's own words (ADR-0091): one that names a tool of ours is left out, and its equations and tables
  const references = (entry.references ?? []).filter((s) => !bannedIn(`${s.title}\n${s.text}`).length && prose(s.text).length);
  const reference = said.kind === "reference";
  const first = references[0];
  const heading = reference ? (first ? first.title : entry.waiting ? "Looking in our reference pages…" : "Our pages do not cover that yet") : said.heading;
  return (
    <>
      <h4 data-testid="wing-chat-heading">{heading}</h4>
      {reference && first ? <p>{prose(first.text)[0]}</p> : null}
      {said.lines.map((line) => <p key={line} className={reference ? "chat-note" : undefined}>{line}</p>)}
      {reference && !first && !entry.waiting ? <p className="chat-note">Ask about a design rule, a test method or an allowable, for example “what ply drop ratio should I use?”.</p> : null}
      {first ? (
        <details className="chat-details" open={false}>
          <summary>{reference ? `From our pages: ${documentName(first.document)}, ${first.title}` : `Why: ${documentName(first.document)}, ${first.title}`}</summary>
          {prose(first.text).slice(reference ? 1 : 0).map((p) => <p key={p.slice(0, 40)}>{p}</p>)}
          {references.slice(1).map((s) => <p key={s.id} className="chat-note">See also: {documentName(s.document)}, {s.title}</p>)}
        </details>
      ) : null}
      {said.panel ? <button type="button" className="studio-text-button" onClick={() => showPanel(said.panel!)}>Open {PANEL_TITLES[said.panel] ?? "the step"}</button> : null}
    </>
  );
}

function Preview({ preview, outcome, stale, onApply, onDismiss }: { preview: WingChangePreview; outcome?: "applied" | "dismissed"; stale: boolean; onApply(): void; onDismiss(): void }) {
  const rows = previewRows(preview);
  const warnings = previewWarnings(preview);
  return (
    <div data-testid="wing-preview">
      <h4>Preview: {outcome === "applied" ? "applied" : outcome === "dismissed" ? "not applied" : "not applied yet"}</h4>
      <p data-testid="wing-preview-words">{preview.words}</p>
      <p className="chat-note" data-testid="wing-preview-basis">{previewBasis(preview)}</p>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num studio-table-compact" data-testid="wing-preview-table">
          <thead><tr><th scope="col">By the hand calculation</th><th scope="col" className="studio-num-head">As it is</th><th scope="col" className="studio-num-head">Changed</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.label}><th scope="row" className="studio-text-cell">{r.label}</th><td className="studio-num">{r.before}</td>
              <td className="studio-num" data-better={r.better === null ? undefined : String(r.better)}>{r.after}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {warnings.length ? (
        <ul className="chat-issues chat-warnings" data-testid="wing-preview-warnings">{warnings.map((w) => <li key={w}><CircleAlert size={14} /> <span>{w}</span></li>)}</ul>
      ) : <p className="chat-note">The changed part meets every design rule.</p>}
      {outcome ? null : stale ? <p className="chat-note">The wing changed after this preview: ask again to preview the change on it.</p> : (
        <div className="chat-actions">
          <button type="button" className="studio-button" onClick={onApply} data-testid="wing-apply">Apply</button>
          <button type="button" className="studio-text-button" onClick={onDismiss}>Dismiss</button>
        </div>
      )}
      {outcome === "applied" ? <p className="chat-note">Applied as a new version: History has the one before.</p> : null}
    </div>
  );
}

const DOCUMENTS: Record<string, string> = { "Design rules for laminates": "Design rules", "Test methods behind a strength": "Test methods", "Allowables and design values": "Allowables" };
const documentName = (document: string): string => DOCUMENTS[document] ?? document;
