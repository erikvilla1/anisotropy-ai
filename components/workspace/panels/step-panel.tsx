"use client";

import type { ReactNode } from "react";
import type { PanelId, PanelState } from "@/lib/workspace-panels";

const WORD: Record<PanelState, string> = { pass: "checked", warn: "warning", fail: "failed", missing: "needs input", pending: "not judged", none: "" };

/** One step of the setup (ADR-0062): a panel that folds, with the worst state of the checklist items that judge its rows as its badge.
 * Every panel opens by default; the engineer folds what is done. */
export function StepPanel({ id, title, state = "none", open = true, note, children }: {
  id: PanelId; title: string; state?: PanelState; open?: boolean; note?: ReactNode; children: ReactNode;
}) {
  return (
    <details className="ws-panel" open={open} id={`panel-${id}`} data-testid={`panel-${id}`} data-state={state}>
      <summary>
        <span className="ws-panel-title">{title}</span>
        {note ? <span className="ws-panel-note">{note}</span> : null}
        {state !== "none" ? <span className={`studio-badge studio-badge-${state}`}>{WORD[state]}</span> : null}
      </summary>
      <div className="ws-panel-body">{children}</div>
    </details>
  );
}

/** Opens a panel and brings it into view: what a failed checklist item's link does. */
export function showPanel(id: PanelId) {
  const element = document.getElementById(`panel-${id}`);
  if (!element) return;
  (element as HTMLDetailsElement).open = true;
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}
