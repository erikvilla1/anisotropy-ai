"use client";

import type { Checklist } from "@/lib/studio-form";
import { RequirementTable } from "./requirement-table";

const MARK: Record<string, string> = { pass: "✓", warn: "!", fail: "✕", missing: "○", pending: "…" };
const WORD: Record<string, string> = { pass: "passed", warn: "warning", fail: "failed", missing: "needs input", pending: "not judged yet" };

/** The checklist of a coupon's setup, or of a fibre tow record (ADR-0074), which says so through `title`, `ready`, `waiting` and `subject`. */
export function ChecklistPanel({ checklist, checking, title = "Setup check", ready = "ready to solve", waiting, subject }: {
  checklist: Checklist | null; checking: boolean; title?: string; ready?: string; waiting?: string; subject?: string;
}) {
  if (checking) return <div className="studio-panel" data-testid="checklist" role="status"><h3>{title}</h3><p className="studio-muted">Checking…</p></div>;
  if (!checklist) {
    return (
      <div className="studio-panel" data-testid="checklist">
        <h3>{title}</h3>
        <p className="studio-muted">{waiting ?? "Select Check setup. Every item is judged by the same rules the run follows: a failed or missing item blocks the solve; a warning does not."}</p>
      </div>
    );
  }
  const blocked = checklist.items.filter((item) => item.state === "fail" || item.state === "missing").length;
  return (
    <div className="studio-panel" data-testid="checklist" data-state={checklist.state}>
      <h3>{title} <span className={`studio-badge studio-badge-${checklist.state}`}>{checklist.state === "ready" ? ready : `blocked: ${blocked} item${blocked === 1 ? "" : "s"}`}</span></h3>
      {checklist.designation ? <p className="studio-muted">Coupon {checklist.designation}{checklist.coupon_exists ? `, ${checklist.attempts} attempt${checklist.attempts === 1 ? "" : "s"} so far` : ", new"}.</p> : null}
      <ol className="studio-checklist">
        {checklist.items.map((item) => (
          <li key={item.id} data-state={item.state} data-item={item.id}>
            <span className="studio-check-mark" aria-hidden="true">{MARK[item.state]}</span>
            <span className="studio-check-body">
              <strong>{item.label}</strong> <span className="studio-muted">({WORD[item.state]})</span>
              {item.message ? <span className="studio-check-message">{item.message}</span> : null}
              {item.rows.length ? <span className="studio-check-rows">Rows: {item.rows.join(", ")}</span> : null}
              {item.requirements?.length ? (
                <details className="ws-check-requirements">
                  <summary>Each requirement of the standard, with its clause</summary>
                  <RequirementTable requirements={item.requirements} judged subject={subject} />
                </details>
              ) : null}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
