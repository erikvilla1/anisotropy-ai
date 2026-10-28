"use client";

import type { Checklist } from "@/lib/studio-form";

const MARK: Record<string, string> = { pass: "✓", warn: "!", fail: "✕", missing: "○", pending: "…" };
const WORD: Record<string, string> = { pass: "passed", warn: "warning", fail: "failed", missing: "needs input", pending: "not judged yet" };

export function ChecklistPanel({ checklist, checking }: { checklist: Checklist | null; checking: boolean }) {
  if (checking) return <div className="studio-panel" data-testid="checklist" role="status"><h3>Setup check</h3><p className="studio-muted">Checking the setup…</p></div>;
  if (!checklist) {
    return (
      <div className="studio-panel" data-testid="checklist">
        <h3>Setup check</h3>
        <p className="studio-muted">Select Check setup. Every item is judged by the same rules the run follows: a failed or missing item blocks the solve; a warning does not.</p>
      </div>
    );
  }
  const blocked = checklist.items.filter((item) => item.state === "fail" || item.state === "missing").length;
  return (
    <div className="studio-panel" data-testid="checklist" data-state={checklist.state}>
      <h3>Setup check <span className={`studio-badge studio-badge-${checklist.state}`}>{checklist.state === "ready" ? "ready to solve" : `blocked: ${blocked} item${blocked === 1 ? "" : "s"}`}</span></h3>
      {checklist.designation ? <p className="studio-muted">Coupon {checklist.designation}{checklist.coupon_exists ? `, ${checklist.attempts} attempt${checklist.attempts === 1 ? "" : "s"} so far` : ", new"}.</p> : null}
      <ol className="studio-checklist">
        {checklist.items.map((item) => (
          <li key={item.id} data-state={item.state} data-item={item.id}>
            <span className="studio-check-mark" aria-hidden="true">{MARK[item.state]}</span>
            <span className="studio-check-body">
              <strong>{item.label}</strong> <span className="studio-muted">({WORD[item.state]})</span>
              {item.message ? <span className="studio-check-message">{item.message}</span> : null}
              {item.rows.length ? <span className="studio-check-rows">Rows: {item.rows.join(", ")}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
