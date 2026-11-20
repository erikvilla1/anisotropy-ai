"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ArrowUp, Box, MessagesSquare } from "lucide-react";
import { takeHandoff } from "@/lib/handoff";
import { readIntent, saysMore, type WorkTarget } from "@/lib/work-intent";
import { workspace } from "@/lib/workspaces";
import { tabStorage } from "@/components/studio/project-context";
import { goTo } from "./go-to";
import { WorkspaceShell } from "./shell";

/** The parts a CAD model will be built from, in the order a feature tree lists them; none exist yet. */
const FEATURES = ["Sketch", "Extrude", "Plies and zones", "Named faces", "Export"];

type Entry = { id: number; role: "user"; text: string } | { id: number; role: "assistant"; title?: string; body: ReactNode };

/** The CAD section (ADR-0124): the same three columns as FEA and Laminate, an empty feature tree, an empty centre, and an assistant that
 * says CAD is being built and opens FEA or Laminate by the same words as every other chat. Nothing here is work, so a section asked for
 * opens at once with the message. */
export function CadWorkspace() {
  const router = useRouter();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const nextId = useRef(1);
  const add = (...items: (Entry extends infer E ? E extends { id: number } ? Omit<E, "id"> : never : never)[]) =>
    setEntries((list) => [...list, ...items.map((item) => ({ ...item, id: nextId.current++ }) as Entry)]);

  const open = (target: WorkTarget, text = "") => goTo(target, target === "coupon" || target === "laminate"
    ? { setUp: text, prompt: saysMore(text) ? text : "" } : { prompt: text }, router.push);
  const choices = (
    <div className="chat-chips">
      <button type="button" data-testid="cad-open" data-target="fea" onClick={() => open("fea")}>Open FEA <ArrowRight size={14} /></button>
      <button type="button" data-testid="cad-open" data-target="laminate" onClick={() => open("laminate")}>Open Laminate <ArrowRight size={14} /></button>
    </div>
  );

  function send(value = input) {
    const text = value.trim();
    if (!text) return;
    setInput("");
    add({ role: "user", text });
    const wanted = readIntent(text);
    if (wanted?.start && wanted.target !== "cad") { open(wanted.target, text); return; }
    add({ role: "assistant", title: "CAD is being built", body: <><p data-testid="cad-reply">Shapes and dimensions will be set here. Until then, a model is set up in FEA and a stack in Laminate.</p>{choices}</> });
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    add({ role: "assistant", title: "CAD is being built", body: <><p>Shapes and dimensions for a model will be drawn here. For now, FEA and Laminate are ready.</p>{choices}</> });
    const carried = takeHandoff(tabStorage());
    if (carried.prompt) send(carried.prompt);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <WorkspaceShell
      kind={workspace("cad").title}
      title={<span className="ws-setup-line" data-testid="project-name">No part yet</span>}
      rail={(
        <div className="studio-form ws-rail-panels ws-tree" data-testid="cad-rail">
          <p className="ws-setup-line" data-state="none">Being built. Nothing can be drawn yet.</p>
          <p className="ws-tree-caption">Feature tree</p>
          <ol className="ws-tree-blank" aria-label="Feature tree, empty">
            {FEATURES.map((f, i) => <li key={f}><span className="ws-panel-step">{i + 1}</span> {f}<span className="ws-panel-note">–</span></li>)}
          </ol>
        </div>
      )}
      stage={<div className="ws-start-stage" data-testid="cad-stage"><Box size={28} aria-hidden="true" /><p>The part shows here once CAD is built.</p></div>}
      assistant={(
        <section className="chat-pane" aria-label="CAD assistant" data-testid="cad-chat">
          <div className="chat-pane-top"><span><span className="status-dot" /> CAD assistant</span></div>
          <div className="chat-scroll" aria-live="polite" aria-relevant="additions">
            {entries.map((e) => e.role === "user" ? <div className="chat-user" key={e.id}>{e.text}</div> : (
              <div className="chat-assistant" key={e.id}>
                <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
                <div>{e.title ? <h4>{e.title}</h4> : null}{e.body}</div>
              </div>
            ))}
          </div>
          <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <textarea aria-label="Message the CAD assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Say what to work on, e.g. “I want to test some coupons”"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
            <div className="composer-footer">
              <span className="chat-note">Enter to send</span>
              <button className="send-button" type="submit" disabled={!input.trim()} aria-label="Send message"><ArrowUp size={18} /></button>
            </div>
          </form>
        </section>
      )}
    />
  );
}
