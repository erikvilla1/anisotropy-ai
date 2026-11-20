"use client";

import { useRef, useState } from "react";
import { ArrowUp, CircleAlert, MessagesSquare } from "lucide-react";
import { previewWingChange, StudioError, wingReferences, type ReferenceSection } from "@/lib/studio-api";
import { previewBasis, previewRows, previewWarnings, readWingAsk, wingAnswer, type WingAsk, type WingChangePreview, type WingSaid } from "@/lib/wing-chat";
import { wingKey } from "@/lib/wing-versions";
import { bannedIn } from "@/lib/studio-copy";
import type { WingDescription } from "@/lib/wing";
import { useWing } from "./wing-context";
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
  };

/** Asks whose answer the reference pages explain, beside the wing's own facts. */
const EXPLAINED = new Set(["reference", "rule-limit", "rules", "strengths"]);

/** The wing's chat (ADR-0128), under the answer in words: a change of plies is read from the message and previewed by the engine on a copy
 * of the wing, which changes only when the engineer taps Apply (a new version, by the assistant, with the message); a question about the
 * wing is answered from the engine's report the page holds; a question of why, how or which test from our reference pages. No model reads
 * a message here yet: what the patterns cannot read is said plainly, with examples. */
export function WingChat() {
  const { apiBaseUrl, wing, answer, replace, versions } = useWing();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const next = useRef(1);
  const update = (id: number, change: Partial<Extract<Entry, { role: "assistant" }>>) =>
    setEntries((list) => list.map((e) => (e.id === id && e.role === "assistant" ? { ...e, ...change } : e)));

  function send() {
    const message = input.trim();
    if (!message) return;
    setInput("");
    const ask: WingAsk = readWingAsk(message);
    const said = wingAnswer(ask, answer?.report ?? null, wing);
    const id = next.current + 1;
    next.current += 2;
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

  function apply(entry: Extract<Entry, { role: "assistant" }>) {
    if (!entry.preview) return;
    versions.attribute("assistant", entry.message); // the version this makes says who made it and from which message
    replace(entry.preview.wing);
    update(entry.id, { outcome: "applied" });
  }

  return (
    <div className="wing-chat" data-testid="wing-chat">
      {entries.length ? (
        <div className="wing-chat-scroll" aria-live="polite" aria-relevant="additions">
          {entries.map((e) => e.role === "user"
            ? <div className="chat-user" key={e.id}>{e.text}</div>
            : (
              <div className="chat-assistant" key={e.id} data-testid="wing-chat-answer" data-kind={e.said.kind}>
                <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
                <div><Answer entry={e} stale={!!e.from && wingKey(e.from) !== wingKey(wing)} onApply={() => apply(e)} onDismiss={() => update(e.id, { outcome: "dismissed" })} /></div>
              </div>
            ))}
        </div>
      ) : null}
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message the wing assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the wing, or one change, e.g. “add 2 0° plies to the spar caps from the root to 40% span”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Nothing changes until you tap Apply</span>
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
/** A section's paragraphs of plain prose: headings, equations, tables and lists of code are left to the page they come from. */
function prose(text: string): string[] {
  return text.split(/\n{2,}/).map((p) => p.trim().replace(/\s*\n\s*/g, " "))
    .filter((p) => p && !/^(?:#|\||```|\$\$|- |\d+\. )/.test(p) && !/\$|\\[a-z]+|`/.test(p));
}
