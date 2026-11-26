"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUp, MessagesSquare } from "lucide-react";
import { approveRepairPlan, askRepairPlan, assistantInfo, noPlanner, previewRepairChange, readRepairPlan, repairReferences, StudioError, sweepRepair,
  type AssistantInfo, type Plan, type ReferenceSection } from "@/lib/studio-api";
import {
  previewPlace, previewRows, readRepairAsk, repairAnswer, routeRepairAsk,
  type RepairAsk, type RepairChangePreview, type RepairSaid, type RepairSweepAnswer,
} from "@/lib/repair-chat";
import { newKindFlow, repairRuns, type KindFlow } from "@/lib/plan-kinds";
import { bondWords, CARRIES_IS_NOT_THE_STRENGTH, kindOf, LET_GO_IS_NOT_THE_STRENGTH, NOT_THE_STRENGTH, PLIES_NO_ANSWER, pliesProgress, pliesWords, sameRepair, sliceWords,
  type RepairDescription } from "@/lib/repair";
import { bannedIn, sectionProse as prose } from "@/lib/studio-copy";
import { REPAIR_HREF } from "@/lib/workspaces";
import { heldOf, pliesUnderWay, useRepair } from "./repair-context";
import { RepairPlanCard } from "./repair-plan";
import { Outcome, Sweep, type Worked } from "./repair-sweep";
import { showPanel } from "./panels/step-panel";

const PANEL_TITLES: Record<string, string> = {
  "repair-laminate": "Laminate", "repair-damage": "the steps", "repair-patch": "Patch", "repair-cover": "Cover plies", "repair-adhesive": "Adhesive", "repair-loads": "Panel and load",
  "repair-solve": "Solve", "repair-report": "Report and shape",
};

type Entry =
  | { id: number; role: "user"; text: string }
  | {
    id: number; role: "assistant"; message: string; said: RepairSaid;
    /** a change or a sweep: the repair it was worked on, the API's answer, and what the engineer did with it */
    from?: RepairDescription; preview?: RepairChangePreview; sweep?: RepairSweepAnswer; outcome?: "applied" | "dismissed" | "undone";
    /** the sections of our pages the question's words find, once the API answers */
    references?: ReferenceSection[];
    /** a solve, or a run of the bond, started from the chat has ended */
    solved?: boolean;
    problem?: string; waiting?: boolean;
  }
  /** a sentence planned by the API (ADR-0144, step 5), its card and where it stands; `said` is the message as typed */
  | { id: number; role: "plan"; said: string; flow: KindFlow }
  /** a plan that could not be made, in the page's words */
  | { id: number; role: "problem"; title: string; text: string };
type Said = Extract<Entry, { role: "assistant" }>;

/** The repair's chat (ADR-0136), under the answer in words: a change is read from the message and previewed by the engine on a copy of
 * the repair, which changes only when the engineer taps Apply, and an applied change can be undone; a sweep is worked by hand at every
 * value, and its pick, solved as a slice, is applied the same way; a question about the result is answered from the report and the
 * solved slice the page holds, one about the bond letting go from the bond followed (ADR-0140) and one about the load the repair
 * carries from the run with its plies damaging (ADR-0141), both of which the chat can start; a question of why, how or what a thing is from our reference pages.
 * Where a model reads, a sentence of a change or a sweep with a solve, the bond or an answer is planned by the API with the repair the
 * page holds (ADR-0144, step 5) and shown on the plan's card, approved once; a change or a sweep alone stays with the patterns and the
 * Apply tap. What the patterns cannot read is said plainly, with examples. */
export function RepairChat() {
  const repairContext = useRepair();
  const { apiBaseUrl, repair, answer, replace, cutFaces, adoptPlan } = repairContext;
  const { solveSlice, followBond, carryPlies } = repairContext;
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState<AssistantInfo | null>(null);
  const [planning, setPlanning] = useState(false);
  const next = useRef(1);
  const composer = useRef<HTMLTextAreaElement>(null);
  const last = useRef<RepairAsk | undefined>(undefined); // what the message before was read as
  const plannerOff = useRef(false); // no planner here, or the day's plans are used: messages are read as before
  const planAsking = useRef<string | null>(null); // the sentence a plan's question back belongs to
  const live = useRef({ entries, repair });
  live.current = { entries, repair };
  // a message just sent is brought to the top of the column, so its answer is read from its first line as it arrives
  const newest = useRef<HTMLDivElement>(null);
  const asked = entries.filter((e) => e.role === "user").length;
  const arrived = entries.filter((e) => e.role !== "user" && !(e.role === "assistant" && e.waiting)).length; // an answer that came after its message grows the column
  useEffect(() => { if (asked) newest.current?.scrollIntoView({ block: "start", behavior: "auto" }); }, [asked, arrived]);
  const lastAsked = [...entries].reverse().find((e) => e.role === "user")?.id;
  const update = (id: number, change: Partial<Said>) => setEntries((list) => list.map((e) => (e.id === id && e.role === "assistant" ? { ...e, ...change } : e)));
  const updateFlow = useCallback((id: number, change: (flow: KindFlow) => KindFlow) =>
    setEntries((list) => list.map((e) => (e.id === id && e.role === "plan" ? { ...e, flow: change(e.flow) } : e))), []);
  const nextId = () => { next.current += 1; return next.current; };
  const offline = "The analysis service is not set up on this page.";

  useEffect(() => {
    if (!apiBaseUrl) return;
    let current = true;
    void assistantInfo(apiBaseUrl).then((info) => { if (current) setModel(info); });
    return () => { current = false; };
  }, [apiBaseUrl]);

  function startSolve(id?: number) {
    showPanel("repair-solve");
    void solveSlice().then(() => { if (id !== undefined) update(id, { solved: true }); });
  }

  function startBond(id?: number) {
    showPanel("repair-solve");
    void followBond().then(() => { if (id !== undefined) update(id, { solved: true }); });
  }

  function startPlies(id?: number) {
    showPanel("repair-solve");
    void carryPlies().then(() => { if (id !== undefined) update(id, { solved: true }); }); // started: the run itself goes on as a job
  }

  function undo(): Said | null {
    const last = [...entries].reverse().find((e): e is Said => e.role === "assistant" && e.outcome === "applied" && !!e.from);
    if (!last?.from) return null;
    replace(last.from);
    update(last.id, { outcome: "undone" });
    return last;
  }

  function send() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    const planner = !!apiBaseUrl && !!model?.proposes && !plannerOff.current;
    const asking = planAsking.current; // a plan's question back is answered by this message
    planAsking.current = null;
    if (planner && asking) { last.current = undefined; void planFor(message, `${asking.replace(/[.\s]+$/, "")}. ${message}`); return; }
    const ask: RepairAsk = routeRepairAsk(message, kindOf(repair), last.current, planner); // a fragment leans on the message before it
    if (ask.route === "repair-plan") { last.current = undefined; void planFor(message, message); return; }
    answerUsual(message, ask);
  }

  /** A message read by the page's own patterns, as before the planner. */
  function answerUsual(message: string, ask: RepairAsk = readRepairAsk(message, kindOf(repair), last.current)) {
    last.current = ask;
    let said = repairAnswer(ask, heldOf(repairContext));
    next.current += 2;
    const id = next.current;
    if (said.kind === "undo") {
      const undone = undo();
      said = { ...said, heading: undone ? "Undone" : "Nothing to undo", lines: [undone ? `The repair is as it was before “${undone.message}”.` : "No change from this chat is applied."] };
    }
    const works = said.kind === "preview" || said.kind === "sweep";
    const entry: Said = { id, role: "assistant", message, said, waiting: works || (said.kind === "reference" && !!apiBaseUrl) };
    if (works) entry.from = repair;
    setEntries((list) => [...list, { id: id - 1, role: "user", text: message }, entry]);
    const failed = (fallback: string) => (error: unknown) => update(id, { waiting: false, problem: error instanceof StudioError ? error.message : fallback });
    if (ask.route === "repair-change" && ask.change) {
      if (!apiBaseUrl) { update(id, { waiting: false, problem: offline }); return; }
      previewRepairChange(apiBaseUrl, repair, ask.change).then((preview) => update(id, { preview, waiting: false })).catch(failed("The change could not be previewed. Try again."));
    } else if (ask.route === "repair-sweep" && ask.sweep) {
      if (!apiBaseUrl) { update(id, { waiting: false, problem: offline }); return; }
      sweepRepair(apiBaseUrl, repair, ask.sweep, cutFaces).then((sweep) => update(id, { sweep, waiting: false })).catch(failed("The sweep could not be run. Try again."));
    } else if (said.kind === "reference" && apiBaseUrl) {
      repairReferences(apiBaseUrl, message).then((references) => update(id, { references, waiting: false })).catch(() => update(id, { references: [], waiting: false }));
    } else if (said.kind === "solve") {
      startSolve(id);
    } else if (said.kind === "bond") {
      startBond(id);
    } else if (said.kind === "plies") {
      startPlies(id);
    }
  }

  /** A sentence planned by the API on the repair the page holds (ADR-0144, step 5): a repair is not a kept project, so the description
   * goes with it. With no planner here the sentence is read as before, and the planner is not asked again this session. `said` is the
   * message as typed, null when a plan is asked again from its card; `ask` is the sentence planned. */
  async function planFor(said: string | null, ask: string) {
    const echo = said === null ? null : nextId();
    if (echo !== null) setEntries((list) => [...list, { id: echo, role: "user", text: said! }]);
    const usual = () => {
      plannerOff.current = true;
      if (echo !== null) setEntries((list) => list.filter((e) => e.id !== echo));
      answerUsual(said ?? ask);
    };
    setPlanning(true);
    let plan: Plan;
    try {
      plan = await askRepairPlan(apiBaseUrl, ask, live.current.repair);
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

  /** The plan approved (ADR-0144, step 5) with the repair the page holds: the server makes the changes, works the sweep, takes its pick,
   * solves the slice and follows the bond inside the request, seconds up to about two minutes; the repair it leaves becomes the page's,
   * with the solve and the bond kept as the page keeps its own. A repair changed since the plan (409) changes nothing. */
  async function approve(id: number) {
    const entry = live.current.entries.find((e) => e.id === id);
    if (!entry || entry.role !== "plan" || entry.flow.stage !== "proposed") return;
    const plan = entry.flow.plan;
    updateFlow(id, (f) => ({ ...f, stage: "approving", problem: null, since: Date.now() }));
    try {
      const approval = await approveRepairPlan(apiBaseUrl, plan.id, live.current.repair, plan.base);
      const runs = repairRuns(approval.plan, approval.runs);
      adoptPlan({ repair: approval.repair, solve: runs.solve ? { cutFaces: runs.cutFaces, solve: runs.solve } : null, bond: runs.bond });
      updateFlow(id, (f) => ({ ...f, stage: "approved", plan: approval.plan, runs: approval.runs, left: JSON.stringify(approval.repair) }));
    } catch (error) {
      if (error instanceof StudioError && error.status === 409) {
        let now: Plan | null = null;
        try { now = await readRepairPlan(apiBaseUrl, plan.id); } catch { /* said as a changed repair */ }
        const already = now !== null && (now.approved_at !== null || !["proposed", "question"].includes(now.state));
        updateFlow(id, (f) => ({ ...f, stage: "stale", problem: already ? "This plan was approved already."
          : "The repair changed since this plan was made, so nothing was changed. Plan it again on the repair as it is now." }));
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

  function apply(entry: Said, next: RepairDescription | null | undefined) {
    if (!next) return;
    replace(next);
    update(entry.id, { outcome: "applied", from: repair }); // the repair it replaces, so Undo puts it back
  }

  return (
    <div className="wing-chat repair-chat" data-testid="repair-chat">
      {entries.length || planning ? (
        <div className="wing-chat-scroll" aria-live="polite" aria-relevant="additions">
          {entries.map((e) => e.role === "user"
            ? <div className="chat-user" key={e.id} ref={e.id === lastAsked ? newest : undefined}>{e.text}</div>
            : (
              <div className="chat-assistant" key={e.id} data-testid="repair-chat-answer" data-kind={e.role === "assistant" ? e.said.kind : e.role}>
                <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
                <div>
                  {e.role === "plan" ? (
                    <RepairPlanCard flow={e.flow} onFlow={(change) => updateFlow(e.id, change)} onApprove={() => void approve(e.id)}
                      onEdit={() => edit(e.id, e.flow.plan.ask)} onPlanAgain={() => void planFor(null, e.flow.plan.ask)} onUsual={() => answerUsual(e.said)} />
                  ) : e.role === "problem" ? (
                    <><h4>{e.title}</h4><p className="chat-problem" role="alert" data-testid="plan-failed">{e.text}</p></>
                  ) : (
                    <Answer entry={e} stale={!!e.from && !e.outcome && !sameRepair(e.from, repair)} current={sameRepair(repair, e.preview?.repair ?? e.sweep?.picked ?? repair)}
                      onApply={(next) => apply(e, next)} onDismiss={() => update(e.id, { outcome: "dismissed" })}
                      onUndo={() => { if (e.from) { replace(e.from); update(e.id, { outcome: "undone" }); } }} onSolve={() => startSolve()} onFollow={() => startBond()} onCarry={() => startPlies()} />
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
        <textarea ref={composer} aria-label="Message the repair assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the repair, one change, or a sweep, e.g. “add a step” or “make each step 0.5 in”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Nothing changes until you tap Apply or Approve</span>
          <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
        </div>
      </form>
    </div>
  );
}

type Handlers = { onApply(next: RepairDescription | null | undefined): void; onDismiss(): void; onUndo(): void; onSolve(): void; onFollow(): void; onCarry(): void };

function Answer({ entry, stale, current, onApply, onDismiss, onUndo, onSolve, onFollow, onCarry }: { entry: Said; stale: boolean; current: boolean } & Handlers) {
  const { said } = entry;
  if (said.kind === "preview" || said.kind === "sweep") {
    if (entry.problem) return <><h4>{said.kind === "sweep" ? "Not swept" : "Not previewed"}</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{entry.problem}</p></>;
    if (entry.preview) return <Preview preview={entry.preview} outcome={entry.outcome} stale={stale} current={current} onApply={() => onApply(entry.preview?.repair)} onDismiss={onDismiss} onUndo={onUndo} />;
    if (entry.sweep) {
      return <Sweep sweep={entry.sweep} worked={{ outcome: entry.outcome, stale, current, onApply: () => onApply(entry.sweep?.picked), onDismiss, onUndo }} />;
    }
    const loaded = said.kind === "sweep" && !!(said.data.sweep as { load?: number } | undefined)?.load;
    return (
      <><h4>{said.heading}</h4><p>{said.lines[0]}</p>
        <p className="chat-typing">{said.kind === "preview" ? "Working the repair as it is and as changed…" : loaded ? "Working the repair at every value, then solving the pick as a slice: a few seconds…" : "Working the repair at every value…"}</p></>
    );
  }
  if (said.kind === "solve") return <Solved entry={entry} />;
  if (said.kind === "bond") return <Followed entry={entry} />;
  if (said.kind === "plies") return <Carried entry={entry} />;
  // a section is shown only in the product's own words (ADR-0091): one that names a tool of ours is left out, and its equations and tables
  const references = (entry.references ?? []).filter((s) => !bannedIn(`${s.title}\n${s.text}`).length && prose(s.text).length);
  const reference = said.kind === "reference";
  const first = references[0];
  const heading = reference ? (first ? first.title : entry.waiting ? "Looking in our reference pages…" : "Our pages do not cover that yet") : said.heading;
  return (
    <>
      <h4 data-testid="repair-chat-heading">{heading}</h4>
      {reference && first ? <p>{prose(first.text)[0]}</p> : null}
      {said.lines.map((line) => <p key={line} className={reference ? "chat-note" : undefined}>{line}</p>)}
      {reference && !first && !entry.waiting ? <p className="chat-note">Ask why the shear stress peaks where it does, what peel stress is, or what a sweep&apos;s pick means.</p> : null}
      {first ? (
        <details className="chat-details" open={false}>
          <summary>From our pages: {first.document}, {first.title}</summary>
          {prose(first.text).slice(1).map((p) => <p key={p.slice(0, 40)}>{p}</p>)}
          {references.slice(1).map((s) => <p key={s.id} className="chat-note">See also: {s.document}, {s.title}</p>)}
        </details>
      ) : null}
      <div className="chat-actions">
        {said.offer === "solve" ? <button type="button" className="studio-button" onClick={onSolve} data-testid="repair-chat-solve">Solve the slice</button> : null}
        {said.offer === "bond" ? <button type="button" className="studio-button" onClick={onFollow} data-testid="repair-chat-bond">Follow the bond</button> : null}
        {said.offer === "plies" ? <button type="button" className="studio-button" onClick={onCarry} data-testid="repair-chat-plies">Carry the repair</button> : null}
        {said.offer === "report" ? <Link className="studio-button" href={`${REPAIR_HREF}/report`} target="_blank" rel="noopener">Open the report</Link> : null}
        {said.panel ? <button type="button" className="studio-text-button" onClick={() => showPanel(said.panel!)}>Open {PANEL_TITLES[said.panel] ?? "the step"}</button> : null}
      </div>
    </>
  );
}

/** A solve started from the chat: said while it runs, then worded from the solved slice the page holds, or the reason it has none. */
function Solved({ entry }: { entry: Said }) {
  const { solve, solveStale, solving, solveProblem } = useRepair();
  if (!entry.solved || solving) return <><h4>{entry.said.heading}</h4><p className="chat-typing">{entry.said.lines[0]}</p></>;
  if (solveProblem) return <><h4>Not solved</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{solveProblem}</p></>;
  if (!solve || solveStale) return <><h4>The repair changed since</h4><p>Solve the slice again for the repair as it stands.</p></>;
  const words = sliceWords(solve.report);
  return (
    <div data-testid="repair-chat-solved">
      <h4>{words.first ? words.first.replace(/\.$/, "") : "The slice is solved"}</h4>
      <p>{words.shear}</p>
      <p>{words.peel}</p>
      <p className="chat-note">{NOT_THE_STRENGTH}</p>
    </div>
  );
}

/** A run of the bond started from the chat: said while it runs, then worded from the followed bond the page holds, or the reason it
 * has none. */
function Followed({ entry }: { entry: Said }) {
  const { bond, bondStale, following, bondProblem } = useRepair();
  if (!entry.solved || following) return <><h4>{entry.said.heading}</h4><p className="chat-typing">{entry.said.lines[0]}</p></>;
  if (bondProblem) return <><h4>Not followed</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{bondProblem}</p></>;
  if (!bond || bondStale) return <><h4>The repair changed since</h4><p>Follow the bond again for the repair as it stands.</p></>;
  const words = bondWords(bond.report);
  return (
    <div data-testid="repair-chat-followed">
      <h4>{words.headline}</h4>
      <p>{words.softens}</p>
      {words.extent ? <p>{words.extent}</p> : <p>{words.short}</p>}
      {bond.report.let_go ? <p className="chat-note">{LET_GO_IS_NOT_THE_STRENGTH}</p> : null}
    </div>
  );
}

/** A run with the plies damaging started from the chat: a job, so the answer follows it as the page does, says what it is doing while
 * it is under way, and is then worded from the run the page holds, or gives the reason it has none. */
function Carried({ entry }: { entry: Said }) {
  const { plies, pliesStale, carrying, pliesProblem } = useRepair();
  if (pliesProblem) return <><h4>Not carried</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{pliesProblem}</p></>;
  if (!entry.solved || carrying || !plies) return <><h4>{entry.said.heading}</h4><p className="chat-typing">{entry.said.lines[0]}</p></>;
  if (pliesStale) return <><h4>The repair changed since</h4><p>Carry it again for the repair as it stands.</p></>;
  if (pliesUnderWay(plies)) return <><h4>{entry.said.heading}</h4><p className="chat-typing" data-testid="repair-chat-carrying">{pliesProgress(plies)}</p><p className="chat-note">{entry.said.lines[0]}</p></>;
  if (plies.state !== "done" || !plies.report) return <><h4>Not carried</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{plies.message ?? PLIES_NO_ANSWER}</p></>;
  const words = pliesWords(plies.report);
  return (
    <div data-testid="repair-chat-carried">
      <h4>{words.headline}</h4>
      <p>{words.bracket}</p>
      <p>{words.softens}</p>
      {words.gives ? <p>{words.gives}</p> : null}
      <p className="chat-note">{CARRIES_IS_NOT_THE_STRENGTH}</p>
    </div>
  );
}

function Preview({ preview, outcome, stale, current, onApply, onDismiss, onUndo }: { preview: RepairChangePreview } & Worked) {
  const rows = previewRows(preview);
  return (
    <div data-testid="repair-preview">
      <h4>Preview: {outcome === "applied" ? "applied" : outcome === "undone" ? "undone" : outcome === "dismissed" ? "not applied" : "not applied yet"}</h4>
      <p data-testid="repair-preview-words">{preview.words}</p>
      <div className="studio-table-scroll">
        <table className="studio-table studio-table-num studio-table-compact" data-testid="repair-preview-table">
          <thead><tr><th scope="col">By the hand calculation</th><th scope="col" className="studio-num-head">As it is</th><th scope="col" className="studio-num-head">Changed</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.label}><th scope="row" className="studio-text-cell">{r.label}</th><td className="studio-num">{r.before}</td>
              <td className="studio-num" data-better={r.better === null ? undefined : String(r.better)}>{r.after}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {previewPlace(preview) ? <p data-testid="repair-preview-place">{previewPlace(preview)}</p> : null}
      {preview.after.elastic_limit_load !== null ? <p className="chat-note">{NOT_THE_STRENGTH}</p> : null}
      <Outcome outcome={outcome} stale={stale} current={current} onApply={onApply} onDismiss={onDismiss} onUndo={onUndo} />
    </div>
  );
}

