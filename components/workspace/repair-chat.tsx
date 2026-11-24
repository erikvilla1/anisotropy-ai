"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowUp, MessagesSquare } from "lucide-react";
import { previewRepairChange, repairReferences, StudioError, sweepRepair, type ReferenceSection } from "@/lib/studio-api";
import {
  previewPlace, previewRows, readRepairAsk, repairAnswer, sweepHeading, sweepTable,
  type RepairAsk, type RepairChangePreview, type RepairHeld, type RepairSaid, type RepairSweepAnswer,
} from "@/lib/repair-chat";
import { bondWords, kindOf, LET_GO_IS_NOT_THE_STRENGTH, NOT_THE_STRENGTH, sameRepair, sliceWords, type RepairDescription } from "@/lib/repair";
import { bannedIn } from "@/lib/studio-copy";
import { REPAIR_HREF } from "@/lib/workspaces";
import { useRepair } from "./repair-context";
import { showPanel } from "./panels/step-panel";

const PANEL_TITLES: Record<string, string> = {
  "repair-damage": "the steps", "repair-patch": "Patch", "repair-cover": "Cover plies", "repair-adhesive": "Adhesive", "repair-loads": "Panel and load",
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
  };
type Said = Extract<Entry, { role: "assistant" }>;

/** The repair's chat (ADR-0136), under the answer in words: a change is read from the message and previewed by the engine on a copy of
 * the repair, which changes only when the engineer taps Apply, and an applied change can be undone; a sweep is worked by hand at every
 * value, and its pick, solved as a slice, is applied the same way; a question about the result is answered from the report and the
 * solved slice the page holds, and one about the bond letting go from the bond followed (ADR-0137), which the chat can start; a
 * question of why, how or what a thing is from our reference pages. No model reads a message here:
 * what the patterns cannot read is said plainly, with examples. */
export function RepairChat() {
  const { apiBaseUrl, repair, answer, replace, solve, solveStale, solveSlice, cutFaces, bond, bondStale, bondNeeds, followBond } = useRepair();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const next = useRef(1);
  const last = useRef<RepairAsk | undefined>(undefined); // what the message before was read as
  // a message just sent is brought to the top of the column, so its answer is read from its first line as it arrives
  const newest = useRef<HTMLDivElement>(null);
  const asked = entries.filter((e) => e.role === "user").length;
  const arrived = entries.filter((e) => e.role === "assistant" && !e.waiting).length; // an answer that came after its message grows the column
  useEffect(() => { if (asked) newest.current?.scrollIntoView({ block: "start", behavior: "auto" }); }, [asked, arrived]);
  const lastAsked = [...entries].reverse().find((e) => e.role === "user")?.id;
  const update = (id: number, change: Partial<Said>) => setEntries((list) => list.map((e) => (e.id === id && e.role === "assistant" ? { ...e, ...change } : e)));
  const offline = "The analysis service is not set up on this page.";

  function startSolve(id?: number) {
    showPanel("repair-solve");
    void solveSlice().then(() => { if (id !== undefined) update(id, { solved: true }); });
  }

  function startBond(id?: number) {
    showPanel("repair-solve");
    void followBond().then(() => { if (id !== undefined) update(id, { solved: true }); });
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
    const ask: RepairAsk = readRepairAsk(message, kindOf(repair), last.current); // a fragment leans on the message before it
    last.current = ask;
    const held: RepairHeld = { repair, report: answer?.report ?? null, slice: solve && !solveStale ? solve.report : null, sliceStale: !!solve && solveStale, needs: answer?.needs ?? [],
      bond: bond && !bondStale ? bond.report : null, bondStale: !!bond && bondStale, bondNeeds };
    let said = repairAnswer(ask, held);
    const id = next.current + 1;
    next.current += 2;
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
    }
  }

  function apply(entry: Said, next: RepairDescription | null | undefined) {
    if (!next) return;
    replace(next);
    update(entry.id, { outcome: "applied", from: repair }); // the repair it replaces, so Undo puts it back
  }

  return (
    <div className="wing-chat repair-chat" data-testid="repair-chat">
      {entries.length ? (
        <div className="wing-chat-scroll" aria-live="polite" aria-relevant="additions">
          {entries.map((e) => e.role === "user"
            ? <div className="chat-user" key={e.id} ref={e.id === lastAsked ? newest : undefined}>{e.text}</div>
            : (
              <div className="chat-assistant" key={e.id} data-testid="repair-chat-answer" data-kind={e.said.kind}>
                <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
                <div>
                  <Answer entry={e} stale={!!e.from && !e.outcome && !sameRepair(e.from, repair)} current={sameRepair(repair, e.preview?.repair ?? e.sweep?.picked ?? repair)}
                    onApply={(next) => apply(e, next)} onDismiss={() => update(e.id, { outcome: "dismissed" })}
                    onUndo={() => { if (e.from) { replace(e.from); update(e.id, { outcome: "undone" }); } }} onSolve={() => startSolve()} onFollow={() => startBond()} />
                </div>
              </div>
            ))}
        </div>
      ) : null}
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message the repair assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the repair, one change, or a sweep, e.g. “add a step” or “make each step 0.5 in”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Nothing changes until you tap Apply</span>
          <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
        </div>
      </form>
    </div>
  );
}

type Handlers = { onApply(next: RepairDescription | null | undefined): void; onDismiss(): void; onUndo(): void; onSolve(): void; onFollow(): void };

function Answer({ entry, stale, current, onApply, onDismiss, onUndo, onSolve, onFollow }: { entry: Said; stale: boolean; current: boolean } & Handlers) {
  const { said } = entry;
  if (said.kind === "preview" || said.kind === "sweep") {
    if (entry.problem) return <><h4>{said.kind === "sweep" ? "Not swept" : "Not previewed"}</h4><p className="chat-problem" role="alert" data-testid="repair-chat-problem">{entry.problem}</p></>;
    if (entry.preview) return <Preview preview={entry.preview} outcome={entry.outcome} stale={stale} current={current} onApply={() => onApply(entry.preview?.repair)} onDismiss={onDismiss} onUndo={onUndo} />;
    if (entry.sweep) return <Sweep sweep={entry.sweep} outcome={entry.outcome} stale={stale} current={current} onApply={() => onApply(entry.sweep?.picked)} onDismiss={onDismiss} onUndo={onUndo} />;
    const loaded = said.kind === "sweep" && !!(said.data.sweep as { load?: number } | undefined)?.load;
    return (
      <><h4>{said.heading}</h4><p>{said.lines[0]}</p>
        <p className="chat-typing">{said.kind === "preview" ? "Working the repair as it is and as changed…" : loaded ? "Working the repair at every value, then solving the pick as a slice: a few seconds…" : "Working the repair at every value…"}</p></>
    );
  }
  if (said.kind === "solve") return <Solved entry={entry} />;
  if (said.kind === "bond") return <Followed entry={entry} />;
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

type Worked = { outcome?: "applied" | "dismissed" | "undone"; stale: boolean; current: boolean; onApply(): void; onDismiss(): void; onUndo(): void };

/** What the engineer may do with a preview or a pick: apply it or not; once applied, undo it while the repair is still the one applied. */
function Outcome({ outcome, stale, current, pick, onApply, onDismiss, onUndo }: Worked & { pick?: boolean }) {
  if (outcome === "applied") {
    return (
      <p className="chat-note" data-testid="repair-applied">Applied: the repair is worked again.{" "}
        {current ? <button type="button" className="studio-text-button" onClick={onUndo} data-testid="repair-undo">Undo</button> : "It has changed since."}</p>
    );
  }
  if (outcome === "undone") return <p className="chat-note" data-testid="repair-undone">Undone: the repair is as it was.</p>;
  if (outcome === "dismissed") return null;
  if (stale) return <p className="chat-note">The repair changed after this was worked: ask again to work it on the repair as it stands.</p>;
  return (
    <div className="chat-actions">
      <button type="button" className="studio-button" onClick={onApply} data-testid="repair-apply">{pick ? "Apply the pick" : "Apply"}</button>
      <button type="button" className="studio-text-button" onClick={onDismiss}>Dismiss</button>
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

function Sweep({ sweep, outcome, stale, current, onApply, onDismiss, onUndo }: { sweep: RepairSweepAnswer } & Worked) {
  const table = sweepTable(sweep);
  // the answer first, in a sentence or two; what was swept, what could not be worked and the rest are folded under it with the table
  const rest = sweep.words.filter((line) => !sweep.answer.includes(line));
  return (
    <div data-testid="repair-sweep">
      <h4 data-testid="repair-sweep-heading">{sweepHeading(sweep)}</h4>
      {sweep.answer.map((line) => <p key={line} data-testid="repair-sweep-words">{line}</p>)}
      {sweep.check ? <p data-testid="repair-sweep-check" data-holds={sweep.check.close ? "close" : sweep.check.holds === null ? "unchecked" : String(sweep.check.holds)}>{sweep.check.words.join(" ")}</p> : null}
      {sweep.cautions.map((line) => <p key={line} className="chat-note" data-testid="repair-sweep-caution">{line}</p>)}
      <details className="chat-details" open={sweep.answer.length === 0 ? true : undefined}>
        <summary>Details: the {table.rows.length} values</summary>
        {rest.map((line) => <p key={line} className="chat-note" data-testid="repair-sweep-rest">{line}</p>)}
        <div className="studio-table-scroll">
          <table className="studio-table studio-table-num studio-table-compact" data-testid="repair-sweep-table">
            <thead><tr>{table.head.map((h, i) => <th key={h} scope="col" className={i ? "studio-num-head" : undefined}>{h}</th>)}</tr></thead>
            <tbody>{table.rows.map((row) => (
              <tr key={row.cells[0]} data-pick={row.pick ? "true" : undefined} data-current={row.current ? "true" : undefined}>
                <th scope="row" className="studio-text-cell">{row.cells[0]}{row.pick ? " (pick)" : row.current ? " (as it is)" : ""}</th>
                {row.refused !== null
                  ? <td className="studio-text-cell" colSpan={table.head.length - 1}>Not worked: {row.refused}</td>
                  : row.cells.slice(1).map((cell, i) => <td key={`${table.head[i + 1]}`} className="studio-num">{cell}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      </details>
      {sweep.pick !== null ? <Outcome outcome={outcome} stale={stale} current={current} pick onApply={onApply} onDismiss={onDismiss} onUndo={onUndo} /> : null}
    </div>
  );
}

/** A section's paragraphs of plain prose, its sources last: headings, equations, tables and lists of code are left to the page they
 * come from. */
function prose(text: string): string[] {
  return text.split(/\n{2,}/).map((p) => p.trim().replace(/\s*\n\s*/g, " "))
    .filter((p) => p && !/^(?:#|\||```|\$\$|- |\d+\. )/.test(p) && !/\$|\\[a-z]+|`/.test(p));
}
