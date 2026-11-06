"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, MessagesSquare, PanelRightClose } from "lucide-react";
import { WORKSPACE_ROOT } from "@/lib/workspaces";

/** The three columns of a workspace (ADR-0062): the setup panels on the left, the model and the results in the centre, the assistant on the
 * right, which folds away. Below 1280 px the assistant drops under the other two; below 1100 px everything stacks. */
export function WorkspaceShell({ title, kind, rail, stage, assistant }: {
  title: ReactNode; kind: string; rail: ReactNode; stage: ReactNode; assistant: ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="ws-shell" data-assistant={open ? "open" : "closed"} data-testid="workspace-shell">
      <header className="ws-topbar">
        <Link className="chat-link" href={WORKSPACE_ROOT}><ArrowLeft size={13} /> All projects</Link>
        <div className="ws-title">{title}<span>{kind}</span></div>
        <button type="button" className="chat-link" aria-pressed={open} onClick={() => setOpen((o) => !o)} data-testid="assistant-toggle">
          {open ? <><PanelRightClose size={13} /> Hide assistant</> : <><MessagesSquare size={13} /> Show assistant</>}
        </button>
      </header>
      <div className="ws-columns">
        <aside className="ws-rail" aria-label="Setup" data-testid="ws-rail">{rail}</aside>
        <section className="ws-stage" aria-label="Model and results" data-testid="ws-stage">{stage}</section>
        {open ? <aside className="ws-assistant" aria-label="Assistant" data-testid="ws-assistant">{assistant}</aside> : null}
      </div>
    </div>
  );
}
