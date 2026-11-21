"use client";

import type { ReactNode } from "react";
import type { PanelState } from "@/lib/workspace-panels";

const WORD: Record<PanelState, string> = { pass: "checked", warn: "warning", fail: "failed", missing: "needs input", pending: "not judged", none: "" };

/** One step of the setup (ADR-0062): a panel that folds, with the worst state of the checklist items that judge its rows as its badge.
 * A panel no checklist judges names its passed state itself (`word`: a laminate step is "complete" once stated, Solve "solved"), so
 * "checked" is said only where a check ran. Every panel opens by default; the engineer folds what is done. A numbered step shows its
 * number before its title, so the order to fill them in reads at a glance (ADR-0062 amendment 1). */
export function StepPanel({ id, title, step, state = "none", word, open = true, note, onToggle, children }: {
  id: string; title: string; step?: number | null; state?: PanelState; word?: string; open?: boolean; note?: ReactNode;
  /** told when the engineer opens or folds the panel: a tab of the model tree lights its part of the model while it is open (ADR-0111) */
  onToggle?: (open: boolean) => void; children: ReactNode;
}) {
  return (
    <details className="ws-panel" open={open} id={`panel-${id}`} data-testid={`panel-${id}`} data-state={state}
      onToggle={onToggle ? (e) => onToggle((e.currentTarget as HTMLDetailsElement).open) : undefined}>
      <summary>
        {step ? <span className="ws-panel-step" aria-hidden="true">{step}</span> : null}
        <span className="ws-panel-title">{title}</span>
        {note ? <span className="ws-panel-note">{note}</span> : null}
        {state !== "none" ? <span className={`studio-badge studio-badge-${state}`}>{state === "pass" && word ? word : WORD[state]}</span> : null}
      </summary>
      <div className="ws-panel-body">{children}</div>
    </details>
  );
}

/** The event a panel opened from elsewhere sends, its id the detail: the canvas shell opens the model tree for it (ADR-0111 amendment 3). */
export const PANEL_EVENT = "ws:panel";

/** Opens a panel and brings it into view: what a failed checklist item's link and the assistant's suggestions do. */
export function showPanel(id: string) {
  const element = document.getElementById(`panel-${id}`);
  if (!element) return;
  (element as HTMLDetailsElement).open = true;
  window.dispatchEvent(new CustomEvent(PANEL_EVENT, { detail: id }));
  element.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Opens a panel the assistant just changed and marks it for a moment, without moving the page more than it must (ADR-0111): the engineer
 * sees which tab of the model a message changed. */
export function revealPanel(id: string) {
  const element = document.getElementById(`panel-${id}`);
  if (!element) return;
  (element as HTMLDetailsElement).open = true;
  window.dispatchEvent(new CustomEvent(PANEL_EVENT, { detail: id }));
  element.scrollIntoView({ behavior: "smooth", block: "nearest" });
  element.classList.remove("ws-panel-changed");
  void (element as HTMLElement).offsetWidth; // restart the mark when the same panel changes twice
  element.classList.add("ws-panel-changed");
  window.setTimeout(() => element.classList.remove("ws-panel-changed"), 1800);
}
