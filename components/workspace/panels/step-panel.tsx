"use client";

import type { ReactNode } from "react";
import type { PanelState } from "@/lib/workspace-panels";

const WORD: Record<PanelState, string> = { pass: "checked", warn: "warning", fail: "failed", missing: "needs input", pending: "not judged", none: "" };

/** One step of the setup (ADR-0062): a panel that folds, with the worst state of the checklist items that judge its rows as its badge
 * (a laminate panel is "checked" once its step is stated). Every panel opens by default; the engineer folds what is done. A numbered step
 * shows its number before its title, so the order to fill them in reads at a glance (ADR-0062 amendment 1). */
export function StepPanel({ id, title, step, state = "none", open = true, note, children }: {
  id: string; title: string; step?: number | null; state?: PanelState; open?: boolean; note?: ReactNode; children: ReactNode;
}) {
  return (
    <details className="ws-panel" open={open} id={`panel-${id}`} data-testid={`panel-${id}`} data-state={state}>
      <summary>
        {step ? <span className="ws-panel-step" aria-hidden="true">{step}</span> : null}
        <span className="ws-panel-title">{title}</span>
        {note ? <span className="ws-panel-note">{note}</span> : null}
        {state !== "none" ? <span className={`studio-badge studio-badge-${state}`}>{WORD[state]}</span> : null}
      </summary>
      <div className="ws-panel-body">{children}</div>
    </details>
  );
}

/** Opens a panel and brings it into view: what a failed checklist item's link and the assistant's suggestions do. */
export function showPanel(id: string) {
  const element = document.getElementById(`panel-${id}`);
  if (!element) return;
  (element as HTMLDetailsElement).open = true;
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}
