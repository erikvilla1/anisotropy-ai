"use client";

import { useState, type ReactNode } from "react";
import { Check, Quote, X } from "lucide-react";

/** One value the model read, as the card shows it: the row, the value with the unit it goes in with, a note (how it was written when the
 * API converted it), and the words it came from. `blocked` says why it cannot go in as it stands, and leaves it unticked. */
export type ProposalLine = { id: string; label: string; value: string; unit: string; note?: string; quote: string; blocked?: string };

/** The model's reading of a message, for the engineer to confirm (ADR-0088): every value ticked by default except one that cannot go in,
 * the conditions it would turn on, a question when it asks one, and what the source guard did not take, with why. Nothing enters the
 * problem until Apply; the card then keeps what was applied. */
export function ProposalCard({ lines, conditions, question, dropped, model, onApply }: {
  lines: ProposalLine[];
  conditions: { id: string; title: string; quote: string }[];
  question: string | null;
  dropped: { key: string; reason: string }[];
  model: string | null;
  onApply: (ids: Set<string>) => void;
}) {
  const ids = [...lines.filter((l) => !l.blocked).map((l) => l.id), ...conditions.map((c) => `condition:${c.id}`)];
  const [ticked, setTicked] = useState<Set<string>>(() => new Set(ids));
  const [done, setDone] = useState<"applied" | "ignored" | null>(null);
  const toggle = (id: string) => setTicked((set) => { const next = new Set(set); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const row = (id: string, label: string, body: ReactNode, quote: string, blocked?: string) => (
    <li key={id} data-key={id} className={blocked ? "proposal-blocked" : undefined}>
      <label>
        <input type="checkbox" checked={ticked.has(id)} disabled={done !== null || !!blocked} onChange={() => toggle(id)} aria-label={`Take ${label}`} />
        <span className="proposal-what"><strong>{label}</strong> {body}</span>
      </label>
      <span className="proposal-quote"><Quote size={11} /> {quote}</span>
      {blocked ? <span className="chat-note">{blocked}</span> : null}
    </li>
  );
  return (
    <div className="proposal-card" data-testid="proposal-card" data-state={done ?? "open"}>
      <p className="chat-note">Read by {model ?? "the model"} from your words. Nothing enters the problem until you apply it: untick anything it misread.</p>
      {lines.length || conditions.length ? (
        <ul className="proposal-lines">
          {lines.map((l) => row(l.id, l.label, <>
            <code>{l.value}{l.unit ? ` ${l.unit}` : ""}</code>{l.note ? <span className="proposal-written"> ({l.note})</span> : null}</>, l.quote, l.blocked))}
          {conditions.map((c) => row(`condition:${c.id}`, `Add a ${c.title.toLowerCase()}`, null, c.quote))}
        </ul>
      ) : null}
      {question ? <p className="proposal-question" data-testid="proposal-question">{question}</p> : null}
      {dropped.length ? (
        <details className="proposal-dropped" data-testid="proposal-dropped">
          <summary>Not taken ({dropped.length}): the words do not hold them</summary>
          <ul>{dropped.map((d, i) => <li key={`${d.key}-${i}`}><code>{d.key}</code> {d.reason}</li>)}</ul>
        </details>
      ) : null}
      {done ? (
        <p className="chat-note" data-testid="proposal-done">{done === "applied" ? `Applied ${ticked.size} of ${ids.length}.` : "Ignored; nothing changed."}</p>
      ) : lines.length || conditions.length ? (
        <div className="chat-chips">
          <button type="button" data-testid="proposal-apply" disabled={!ticked.size} onClick={() => { setDone("applied"); onApply(new Set(ticked)); }}>
            <Check size={14} /> Apply {ticked.size === ids.length ? "all" : `${ticked.size} of ${ids.length}`}
          </button>
          <button type="button" data-testid="proposal-ignore" onClick={() => setDone("ignored")}><X size={14} /> Ignore</button>
        </div>
      ) : null}
    </div>
  );
}
