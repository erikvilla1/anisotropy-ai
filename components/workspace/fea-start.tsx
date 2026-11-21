"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp, Boxes, MessagesSquare, Plus } from "lucide-react";
import { putHandoff, takeHandoff } from "@/lib/handoff";
import { MODEL_TREE } from "@/lib/model-tree";
import { answerGeneral, StudioError, type GeneralAnswer } from "@/lib/studio-api";
import { generalLines } from "@/lib/result-why";
import { applyMessage } from "@/lib/studio-chat";
import { blankForm } from "@/lib/studio-form";
import { readRepair, routeStart, saysMore, TARGET_TITLES, type WorkTarget } from "@/lib/work-intent";
import { ASKED_KINDS, FEA_KINDS, feaKind, REPAIR_HREF, type FeaKind } from "@/lib/workspaces";
import { tabStorage, useProject } from "@/components/studio/project-context";
import { goTo } from "./go-to";

/** Whether the coupon chat's own patterns read rows in a message, so it is worth carrying to it (ADR-0124). */
const couponReads = (text: string): boolean => applyMessage({ ...blankForm(), date: "" }, text).understood.length > 0;

/** Sets the open FEA project up for a kind of work in place (ADR-0124): its name and history stay, the kind's own chat takes over with
 * the message that set it up at its head, and the message itself when it says more than the kind. A wing is a project of its own kind
 * (ADR-0122): it opens on its own page under FEA, this blank project left as it was (ADR-0118 amendment 1). A patch repair opens on
 * its own page too, with the repair this browser holds or the example (ADR-0135). */
function useSetUp() {
  const { setAnalysis } = useProject();
  const router = useRouter();
  return useCallback((kind: FeaKind["id"], said: string) => {
    if (kind === "wing") { goTo("wing", {}, router.push); return; }
    if (kind === "repair") { router.push(REPAIR_HREF); return; }
    putHandoff(tabStorage(), { setUp: said, prompt: saysMore(said, couponReads) ? said : "" });
    setAnalysis(kind);
  }, [setAnalysis, router]);
}

/** The left column of an FEA project not set up yet (ADR-0124): the model tree with nothing in it, what it can be set up for, and the
 * import of a model built elsewhere where that is offered (ADR-0105). */
export function FeaStartRail() {
  const { apiBaseUrl, imports, imported } = useProject();
  const setUp = useSetUp();
  return (
    <div className="studio-form ws-rail-panels ws-tree" data-testid="fea-start-rail">
      <div className="ws-tree-head">
        <p className="ws-setup-line" data-state="none">Nothing is set up yet. Tell the assistant what you want to analyse, or pick it here.</p>
      </div>
      <fieldset className="ws-question" data-testid="fea-start-kinds">
        <legend>What are you analysing?</legend>
        <div className="ws-choices">
          {FEA_KINDS.map((kind) => (
            <button type="button" key={kind.id} className="ws-choice ws-start-kind" data-kind={kind.id} onClick={() => setUp(kind.id, kind.title)}>
              <Plus size={14} aria-hidden="true" />
              <span className="ws-choice-title">{kind.title}</span>
              <span className="ws-choice-detail">{kind.detail}</span>
            </button>
          ))}
        </div>
        {imports && apiBaseUrl ? (
          <div className="studio-buttons"><button type="button" className="studio-text-button" onClick={imported.show} data-testid="import-open">Import a model</button></div>
        ) : null}
      </fieldset>
      <p className="ws-tree-caption">Model tree</p>
      <ol className="ws-tree-blank" data-testid="fea-start-tree" aria-label="Model tree, empty">
        {MODEL_TREE.map((t, i) => <li key={t.id}><span className="ws-panel-step">{i + 1}</span> {t.title}<span className="ws-panel-note">–</span></li>)}
      </ol>
    </div>
  );
}

/** The centre of an FEA project not set up yet: empty, and says what fills it. */
export function FeaStartStage() {
  return (
    <div className="ws-start-stage" data-testid="fea-start-stage">
      <Boxes size={28} aria-hidden="true" />
      <p>Your model shows here once it is set up.</p>
    </div>
  );
}

type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; title?: string; body: ReactNode; testId?: string };
type NewEntry = Entry extends infer E ? E extends { id: number } ? Omit<E, "id"> : never : never;

const QUESTIONS = ["What is a mesh convergence study?", "Why do the failure criteria give different answers?"];

/** The FEA assistant of a project not set up yet (ADR-0124): it answers a question about finite elements from our theory pages, and sets
 * the project up when asked ("I want to test some coupons"); a wing asked for opens on its own page (ADR-0118 amendment 1). Another
 * section asked for opens at once, since nothing here is work yet. What is read is fixed words (`readIntent`); only a question goes to
 * the API. */
export function FeaStartChat() {
  const { apiBaseUrl } = useProject();
  const router = useRouter();
  const setUp = useSetUp();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [asking, setAsking] = useState(false);
  const busy = useRef(false); // a question in flight: read by chips made before it was asked
  const nextId = useRef(1);
  const body = useRef<HTMLDivElement>(null);
  const add = useCallback((...items: NewEntry[]) => {
    setEntries((list) => [...list, ...items.map((item) => ({ ...item, id: nextId.current++ }) as Entry)]);
  }, []);

  const offer = (target: WorkTarget, label = `Set up a ${TARGET_TITLES[target].toLowerCase()}`) => (
    target === "coupon" || target === "wing"
      ? <button type="button" key={target} data-testid="fea-start-offer" data-target={target} onClick={() => setUp(target, TARGET_TITLES[target])}><Plus size={14} /> {label}</button>
      : target === "laminate" || target === "cad"
        ? <button type="button" key={target} data-testid="fea-start-offer" data-target={target} onClick={() => goTo(target, {}, router.push)}>Open {TARGET_TITLES[target]}</button>
        : null
  );

  function notHereYet() {
    add({ role: "assistant", title: "You are in FEA", testId: "fea-start-kind-missing",
      body: <><p>Say what to analyse, or ask a question about it.</p>
        <div className="chat-chips">{offer("coupon")}{offer("wing")}</div></> });
  }

  /** The repair's page, offered under an answer to a question that names a patch repair: it has no chat to answer it yet (ADR-0135). */
  const offerRepair = () => (
    <button type="button" key="repair" data-testid="fea-start-offer" data-target="repair" onClick={() => setUp("repair", feaKind("repair").title)}><Plus size={14} /> Open {feaKind("repair").title}</button>
  );

  async function ask(text: string, named: WorkTarget | null) {
    const repair = readRepair(text) === "about";
    if (!apiBaseUrl) {
      add({ role: "assistant", title: "Answers are not available on this page", testId: "fea-start-answer",
        body: <><p>Questions are answered by the analysis service, which this page cannot reach. You can still set up a model.</p>
          <div className="chat-chips">{offer("coupon")}</div></> });
      return;
    }
    setAsking(true); busy.current = true;
    let answer: GeneralAnswer | null = null;
    let failed = "";
    try { answer = await answerGeneral(apiBaseUrl, text, [...ASKED_KINDS]); }
    catch (error) { failed = error instanceof StudioError ? error.message : "Try again."; }
    finally { setAsking(false); busy.current = false; }
    if (!answer) {
      add({ role: "assistant", title: "The question could not be answered", testId: "fea-start-answer", body: <p className="chat-problem">{failed}</p> });
      return;
    }
    // what to set up next: the kind the question named in fixed words, or the one the model read in it; offered, never done on its own
    const offered = (named && named !== "fea" ? named : null) ?? (answer.start === "coupon" || answer.start === "wing" ? answer.start : null);
    const { prose, sources } = generalLines(answer); // in the product's own words (ADR-0091)
    add({ role: "assistant", testId: "fea-start-answer", body: (
      <div data-testid="fea-start-answer-body" data-covered={answer.covered} data-writer={answer.writer}>
        {prose.length ? prose.map((line, i) => <p key={i}>{line}</p>)
          : sources.length ? <p>Our theory pages hold this. Read:</p> : <p>Our theory pages do not cover that yet.</p>}
        {sources.length ? <ul className="chat-understood" data-testid="fea-start-sources">{sources.map((s) => <li key={s}>{s}</li>)}</ul> : null}
        {offered || repair ? <div className="chat-chips">{offered ? offer(offered) : null}{repair ? offerRepair() : null}</div> : null}
      </div>
    ) });
  }

  function send(value = input) {
    const text = value.trim();
    if (!text || busy.current) return;
    setInput("");
    add({ role: "user", text });
    // who answers is a fixed order, in one place the question banks try (lib/work-intent.ts, ADR-0121)
    const routed = routeStart(text);
    switch (routed.route) {
      case "set-up": setUp(routed.kind, text); return;
      case "not-here": notHereYet(); return;
      case "open": goTo(routed.target, { prompt: saysMore(text) ? text : "" }, router.push); return; // nothing here is work yet: it opens at once
      case "general": void ask(text, routed.named); return;
    }
  }

  // the first words, and a message carried from the start screen, the home page or another section, read once (ADR-0124)
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    add({ role: "assistant", title: "What do you want to analyse?", testId: "fea-start-intro", body: (
      <><p>Ask anything about finite element analysis of composites, or tell me what to set up, e.g. “I want to test some coupons”.</p>
        <div className="chat-chips">
          {FEA_KINDS.map((kind) => <button type="button" key={kind.id} data-testid="fea-start-chip" onClick={() => send(`Set up a ${feaKind(kind.id).title.toLowerCase()}`)}><Plus size={14} /> {kind.title}</button>)}
          {QUESTIONS.map((q) => <button type="button" key={q} onClick={() => send(q)}>{q}</button>)}
        </div></>
    ) });
    const carried = takeHandoff(tabStorage());
    if (carried.prompt) send(carried.prompt);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { body.current?.scrollTo({ top: body.current.scrollHeight, behavior: "smooth" }); }, [entries, asking]);

  return (
    <section className="chat-pane" aria-label="FEA assistant" data-testid="fea-start-chat">
      <div className="chat-pane-top">
        <span><span className="status-dot" /> FEA assistant</span>
      </div>
      <div className="chat-scroll" ref={body} aria-live="polite" aria-relevant="additions">
        {entries.map((e) => e.role === "user" ? <div className="chat-user" key={e.id}>{e.text}</div> : (
          <div className="chat-assistant" key={e.id} data-testid={e.testId}>
            <span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span>
            <div>{e.title ? <h4>{e.title}</h4> : null}{e.body}</div>
          </div>
        ))}
        {asking ? <div className="chat-assistant"><span className="message-avatar" aria-hidden="true"><MessagesSquare size={15} /></span><div><p className="chat-typing" data-testid="fea-start-reading">Reading your question…</p></div></div> : null}
      </div>
      <form className="chat-composer chat-studio-composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message the FEA assistant" rows={2} maxLength={2000} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about FEA, or say what to analyse, e.g. “I want to test some coupons”"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />
        <div className="composer-footer">
          <span className="chat-note">Enter to send</span>
          <button className="send-button" type="submit" disabled={!input.trim() || asking} aria-label="Send message"><ArrowUp size={18} /></button>
        </div>
      </form>
    </section>
  );
}
