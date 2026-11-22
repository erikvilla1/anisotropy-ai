"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ComponentType, type ReactNode } from "react";
import Link from "next/link";
import {
  Anchor, ArrowDownToLine, Bandage, Blend, Box, ChartColumn, Check, CircleDashed, ClipboardCheck, Droplet, FileText, FlaskConical, Footprints, Grid3x3,
  History, House, Layers, ListTree, MessagesSquare, PanelRightClose, PanelTop, Plane, Play, Ruler, Shapes, SlidersHorizontal, SquareDashed, Tag, Wind, X,
} from "lucide-react";
import { WORKSPACE_ROOT } from "@/lib/workspaces";
import { CanvasSlotsProvider, type CanvasSlots, type FreeArea, type SlotName } from "./canvas-slots";
import { PANEL_EVENT } from "./panels/step-panel";

/** The icon of each tab of a model tree on the icon rail (ADR-0111 amendment 3), by its id without the wing's `wing-` or the repair's
 * `repair-` prefix; a tab not listed takes the plain square. */
const TAB_ICONS: Record<string, ComponentType<{ size?: number; "aria-hidden"?: boolean }>> = {
  test: FlaskConical, project: Tag, geometry: Ruler, material: Shapes, layup: Layers, step: Footprints, conditions: Anchor, loads: ArrowDownToLine,
  mesh: Grid3x3, validate: ClipboardCheck, run: Play, solve: Play, outputs: ChartColumn, results: ChartColumn, history: History, advanced: SlidersHorizontal,
  wing: Plane, aero: Wind, supports: Anchor, fe: Grid3x3, shape: Box,
  repair: Bandage, laminate: Layers, damage: CircleDashed, patch: Blend, cover: PanelTop, adhesive: Droplet, report: FileText,
};
const iconOf = (id: string) => TAB_ICONS[id] ?? TAB_ICONS[id.replace(/^(wing|repair)-/, "")] ?? SquareDashed;

export type TreeTab = { id: string; title: string; state?: string };
/** One of the project's stages under its name in the card (ADR-0134 amendment 1): Set up, Mesh, Solve, Results, each done, under way or
 * still to do. */
export type Stage = { label: string; state: "done" | "now" | "todo" };

const NARROW = "(max-width: 899px)";
const sameFree = (a: FreeArea | null, b: FreeArea) => !!a && a.left === b.left && a.right === b.right && a.top === b.top && a.bottom === b.bottom;

/** The tabs of the tree as drawn: every step panel at the tree's top level, its title and its checklist state. */
function readTabs(root: HTMLElement): TreeTab[] {
  return [...root.querySelectorAll<HTMLDetailsElement>("details.ws-panel[id^='panel-']")]
    .filter((panel) => !panel.parentElement?.closest("details.ws-panel"))
    .map((panel) => ({
      id: panel.id.slice("panel-".length),
      title: panel.querySelector(":scope > summary .ws-panel-title")?.textContent?.trim() || panel.id.slice("panel-".length),
      state: panel.dataset.state ?? "none",
    }));
}

const typing = (target: EventTarget | null) => {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
};

/** The FEA workspace in layout D (ADR-0134 and its amendment 1): the model across the whole window, with the logo, an icon rail that opens
 * the model tree as a flyout (ADR-0111 amendment 3), the assistant full height on the right and a results card under the model floating over
 * it. The card holds the project with its stages, the legend with the View menu, and the short answer; a stage puts its parts into it
 * through slots (`canvas-slots.tsx`), and the model is framed in the part of the window the floating panels leave clear. The tree is open
 * while a project is set up and closes once when `results` first turns true; the engineer's own opening or closing stands after that. T
 * opens and closes the tree, / puts the cursor in the chat, Esc closes the details and then the tree. Below 900 px the card and the chat are
 * one sheet under the model, switched between by two buttons; the tree opens over the page. */
export function CanvasShell({ title, kind, tree, stage, assistant, status, stages = [], results = false, keepTree = false, blankTabs = [] }: {
  title: ReactNode; kind: string; tree: ReactNode; stage: ReactNode; assistant: ReactNode;
  /** the project's stages, ticked as they are done (ADR-0134 amendment 1) */
  stages?: readonly Stage[];
  /** under the project's name in the card: what the project is at, before the stage's own stages */
  status?: ReactNode;
  /** whether a run's results are shown: their first showing closes the tree once */
  results?: boolean;
  /** a project worked again on every change (the wing): on a wide screen its first results leave the tree open */
  keepTree?: boolean;
  /** the tabs the rail shows while the tree draws none (a project not set up yet) */
  blankTabs?: readonly TreeTab[];
}) {
  // open as the page is built, so the browser's first drawing matches it; a narrow screen closes it before the first paint, except on a
  // project not set up yet, whose first question (what is analysed) is in the tree
  const [treeOpen, setTreeOpen] = useState(true);
  const blank = blankTabs.length > 0;
  const [assistantOpen, setAssistantOpen] = useState(true);
  // on a narrow screen the card and the chat are one sheet at the model's foot: the chat while a project is set up, the card from the
  // first results (ADR-0134); on a wide one both show and this changes nothing
  const [sheet, setSheet] = useState<"card" | "chat">("chat");
  const [details, setDetails] = useState(false);
  const [tabs, setTabs] = useState<TreeTab[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const touched = useRef(false); // the engineer opened or closed the tree: no longer closed for them
  const treeRoot = useRef<HTMLElement>(null);
  const [places, setPlaces] = useState<Partial<Record<SlotName, HTMLElement | null>>>({});
  const refs = useMemo(() => {
    // one ref callback per place, kept for the page's life: a new one at every drawing would empty and fill the place each time
    const made: Partial<Record<SlotName, (el: HTMLElement | null) => void>> = {};
    const at = (name: SlotName) => (made[name] ??= (el: HTMLElement | null) => setPlaces((p) => (p[name] === el ? p : { ...p, [name]: el })));
    return { at, project: at("project"), view: at("view"), answer: at("answer"), details: at("details"), over: at("over") };
  }, []);
  const shell = useRef<HTMLDivElement>(null);
  const rail = useRef<HTMLElement>(null);
  const card = useRef<HTMLElement>(null);
  const [free, setFree] = useState<FreeArea | null>(null);

  // on a narrow screen the tree covers the page: closed from the start unless the project is blank, and closed once the project is set up
  const wasBlank = useRef(blank);
  useLayoutEffect(() => {
    if (window.matchMedia("(max-width: 899px)").matches && !blank) setTreeOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, as the page first shows
  }, []);
  useEffect(() => {
    if (wasBlank.current && !blank && window.matchMedia("(max-width: 899px)").matches) setTreeOpen(false);
    wasBlank.current = blank;
  }, [blank]);

  // the tree's first results close it once, unless the engineer has opened or closed it themselves; on a narrow screen, where the tree
  // covers the page, they close it whoever opened it, so the results are seen
  const hadResults = useRef(results);
  useEffect(() => {
    const narrow = window.matchMedia("(max-width: 899px)").matches;
    if (results && !hadResults.current && ((!touched.current && !keepTree) || narrow)) setTreeOpen(false);
    if (results && !hadResults.current) setSheet("card");
    if (!results) setDetails(false);
    hadResults.current = results;
  }, [results, keepTree]);

  // the part of the window the model is framed in, clear of the panels floating over it (ADR-0134 amendment 1): measured as the window,
  // the card or the tree change size, and given to the scene (its camera) and to the page (its CSS) alike
  useLayoutEffect(() => {
    const root = shell.current;
    if (!root) return;
    const measure = () => {
      const stageBox = root.querySelector<HTMLElement>(".cv-stage")?.getBoundingClientRect();
      if (!stageBox) return;
      let next: FreeArea;
      if (window.matchMedia(NARROW).matches) next = { left: 8, right: 8, top: 52, bottom: 8 };
      else {
        const side = (treeOpen ? treeRoot.current : rail.current)?.getBoundingClientRect();
        const chat = root.querySelector<HTMLElement>(".cv-chat, .cv-chat-show")?.getBoundingClientRect();
        const under = card.current?.getBoundingClientRect();
        next = {
          left: Math.round(side ? side.right - stageBox.left + 24 : 24),
          right: Math.round(chat ? stageBox.right - chat.left + 24 : 24),
          top: 64,
          bottom: Math.round(under ? stageBox.bottom - under.top + 16 : 24),
        };
      }
      (["left", "right", "top", "bottom"] as const).forEach((edge) => root.style.setProperty(`--free-${edge[0]}`, `${next[edge]}px`));
      setFree((before) => (sameFree(before, next) ? before : next));
    };
    measure();
    const watch = new ResizeObserver(measure);
    [root, card.current, treeRoot.current].forEach((el) => { if (el) watch.observe(el); });
    return () => watch.disconnect();
  }, [treeOpen, assistantOpen]);

  // the rail's buttons follow the tree as drawn: its panels, their titles and their states
  useEffect(() => {
    const root = treeRoot.current;
    if (!root) return;
    const read = () => setTabs((before) => {
      const now = readTabs(root);
      return JSON.stringify(now) === JSON.stringify(before) ? before : now;
    });
    read();
    const watch = new MutationObserver(read);
    watch.observe(root, { subtree: true, childList: true, attributes: true, attributeFilter: ["data-state", "id"] });
    return () => watch.disconnect();
  }, []);

  const toggleTree = useCallback((open?: boolean) => {
    touched.current = true;
    setTreeOpen((o) => (open === undefined ? !o : open));
  }, []);

  /** A tab's button: opens the tree on that tab, or closes the tree when that tab is the one open. */
  const openTab = (id: string) => {
    touched.current = true;
    if (treeOpen && active === id) { setTreeOpen(false); return; }
    setActive(id);
    setTreeOpen(true);
    window.requestAnimationFrame(() => {
      const panel = document.getElementById(`panel-${id}`) as HTMLDetailsElement | null;
      if (!panel) return;
      panel.open = true;
      panel.scrollIntoView({ block: "start" });
    });
  };

  // a panel the assistant or a link opens (step-panel.tsx) opens the tree first, so the engineer sees which tab changed
  useEffect(() => {
    const onPanel = (event: Event) => {
      const id = (event as CustomEvent<string>).detail;
      setActive(id);
      setTreeOpen(true);
      window.requestAnimationFrame(() => document.getElementById(`panel-${id}`)?.scrollIntoView({ block: "nearest" }));
    };
    window.addEventListener(PANEL_EVENT, onPanel);
    return () => window.removeEventListener(PANEL_EVENT, onPanel);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "Escape") {
        if (details) { setDetails(false); event.preventDefault(); return; }
        if (treeOpen && !typing(event.target)) { toggleTree(false); event.preventDefault(); }
        return;
      }
      if (typing(event.target)) return;
      if (event.key === "t" || event.key === "T") { event.preventDefault(); toggleTree(); }
      else if (event.key === "/") {
        event.preventDefault();
        setAssistantOpen(true);
        setSheet("chat");
        window.requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>("#ws-assistant textarea")?.focus());
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [details, treeOpen, toggleTree]);

  const slots = useMemo<CanvasSlots>(() => ({ places, register: refs.at, details, setDetails, free }), [places, refs, details, free]);
  const shown = tabs.length ? tabs : blankTabs;
  return (
    <CanvasSlotsProvider value={slots}>
      <div ref={shell} className="ws-shell cv-shell" data-layout="canvas" data-tree={treeOpen ? "open" : "closed"} data-assistant={assistantOpen ? "open" : "closed"}
        data-details={details ? "open" : "closed"} data-results={results} data-testid="workspace-shell">
        {/* the logo, floating over the model's top left corner: the way back to the projects (ADR-0134 amendment 1) */}
        <Link className="wordmark cv-brand" href={WORKSPACE_ROOT} aria-label="All projects" title="All projects" data-testid="cv-brand">
          <span className="brand-mark" aria-hidden="true" /><span className="brand-name" aria-hidden="true">Anisotropy</span>
        </Link>
        <nav ref={rail} className="cv-icons" aria-label="Model tree tabs" data-testid="tree-icons">
          <button type="button" className="cv-icon cv-icon-tree" aria-expanded={treeOpen} aria-controls="ws-rail" onClick={() => toggleTree()} data-testid="tree-toggle"
            title={treeOpen ? "Close the model tree (T)" : "Open the model tree (T)"}>
            <ListTree size={18} aria-hidden={true} /><span className="sr-only">{treeOpen ? "Close the model tree" : "Open the model tree"}</span>
          </button>
          <span className="cv-icons-sep" aria-hidden="true" />
          {shown.map((tab) => {
            const Icon = iconOf(tab.id);
            return (
              <button key={tab.id} type="button" className="cv-icon" title={tab.title} data-state={tab.state ?? "none"} data-testid={`tree-tab-${tab.id}`}
                aria-pressed={treeOpen && active === tab.id} onClick={() => openTab(tab.id)}>
                <Icon size={17} aria-hidden={true} /><span className="sr-only">{tab.title} tab</span>
              </button>
            );
          })}
        </nav>
        <Link className="cv-home" href="/" title="Back to website" data-testid="cv-home"><House size={17} aria-hidden={true} /><span className="sr-only">Back to website</span></Link>

        <aside ref={treeRoot} className="cv-tree ws-rail" id="ws-rail" aria-label="Model tree" data-testid="ws-rail" hidden={!treeOpen}>
          <div className="cv-tree-top">
            <span>Model</span>
            <button type="button" className="icon-button" onClick={() => toggleTree(false)} title="Close the model tree (Esc)" data-testid="tree-close">
              <X size={15} aria-hidden={true} /><span className="sr-only">Close the model tree</span>
            </button>
          </div>
          {tree}
        </aside>

        <section className="cv-stage ws-stage" aria-label="Model" data-testid="ws-stage">
          {stage}
          <div className="cv-over" ref={refs.over} />
          <div className="cv-details" id="ws-details" hidden={!details} data-testid="ws-details" role="region" aria-label="Details">
            <div className="cv-details-top">
              <span>Details</span>
              <button type="button" className="icon-button" onClick={() => setDetails(false)} title="Close the details (Esc)" data-testid="details-close">
                <X size={15} aria-hidden={true} /><span className="sr-only">Close the details</span>
              </button>
            </div>
            <div className="cv-details-body" ref={refs.details} />
          </div>
        </section>

        <div className="cv-sheet" data-sheet={sheet} data-testid="ws-sheet">
        <div className="cv-sheet-tabs" role="group" aria-label="Under the model">
          <button type="button" aria-pressed={sheet === "card"} onClick={() => setSheet("card")} data-testid="sheet-card">{results ? "Results" : "Project"}</button>
          <button type="button" aria-pressed={sheet === "chat"} onClick={() => { setAssistantOpen(true); setSheet("chat"); }} data-testid="sheet-chat">Assistant</button>
        </div>
        <section ref={card} className="cv-card" aria-label="Project and results" data-testid="ws-card">
          <div className="cv-card-grid">
            <div className="cv-col cv-project">
              <div className="cv-project-head">
                <p className="cv-eyebrow-plain">Project</p>
                <div className="ws-title cv-title">{title}</div>
                <p className="cv-kind" data-testid="cv-kind"><span>{kind}</span></p>
              </div>
              {stages.length ? (
                <ol className="cv-stages" aria-label="Stages" data-testid="cv-stages">
                  {stages.map((st) => (
                    <li key={st.label} data-state={st.state}>
                      <span className="cv-stage-mark" aria-hidden="true">{st.state === "done" ? <Check size={10} strokeWidth={3} /> : null}</span>
                      {st.label}<span className="sr-only">{st.state === "done" ? ", done" : st.state === "now" ? ", under way" : ", to do"}</span>
                    </li>
                  ))}
                </ol>
              ) : null}
              {status}
              <div className="cv-slot" ref={refs.project} />
            </div>
            <div className="cv-col cv-view cv-slot" ref={refs.view} />
            <div className="cv-col cv-answer cv-slot" ref={refs.answer} />
          </div>
        </section>

        {assistantOpen ? (
          <aside className="cv-chat ws-assistant" id="ws-assistant" aria-label="Assistant" data-testid="ws-assistant">
            <button type="button" className="icon-button cv-chat-fold" aria-expanded={true} aria-controls="ws-assistant" onClick={() => setAssistantOpen(false)}
              data-testid="assistant-toggle" title="Hide the assistant">
              <PanelRightClose size={15} aria-hidden={true} /><span className="sr-only">Hide assistant</span>
            </button>
            {assistant}
          </aside>
        ) : (
          <button type="button" className="cv-chat-show" aria-expanded={false} onClick={() => setAssistantOpen(true)} data-testid="assistant-toggle">
            <MessagesSquare size={15} aria-hidden={true} /> <span>Show assistant</span>
          </button>
        )}
        </div>
      </div>
    </CanvasSlotsProvider>
  );
}
