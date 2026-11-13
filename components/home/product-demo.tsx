"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import { ArrowUpRight, Check, FileText, Layers3 } from "lucide-react";
import { demoRun, demoScale, standardName } from "@/lib/demo-run";
import { COMMON_MATERIALS } from "@/lib/studio-chat";
import { legendGradient } from "@/lib/studio-colors";
import { DOWNLOAD_LABELS, RUN_STEPS } from "@/lib/studio-copy";
import { libraryOptions } from "@/lib/studio-form";
import { ASSISTANT, BEAT_COPY, DEMO_HEAD, FIELD_LABEL, FILES_HEAD, OPEN_WORKSPACE, recordedLine, resultLines, summaryCells } from "./product-demo-copy";
import type { DemoSceneHandle } from "./product-demo-scene";
import { BEAT_IDS, DEMO_CLOCK_PER_SECOND, DEMO_STOPS, DEMO_TOTAL, finalView, layupScript, sameView, viewAt, type BeatId, type DemoView } from "./product-demo-timeline";
import { useTourDriver } from "./tour-driver";
import "@/app/home-demo.css";

/** The view loads only in the browser: three.js needs a WebGL context (the pattern of components/home/scene.tsx). */
const ProductDemoScene = dynamic(() => import("./product-demo-scene").then((module) => module.ProductDemoSceneCanvas), { ssr: false });

/** Stepped on a desktop-sized window whose visitor has not asked for reduced motion; an ordinary section otherwise. */
const PINNED_QUERY = "(min-width: 1024px) and (min-height: 600px) and (prefers-reduced-motion: no-preference)";
function useMediaQuery(query: string): boolean {
  const subscribe = (notify: () => void) => {
    const media = window.matchMedia(query);
    media.addEventListener("change", notify);
    return () => media.removeEventListener("change", notify);
  };
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false);
}

/** Where each beat's words stand: under the model, or in a block at one side with the model at the other (Scale's arrangement). */
const SIDE: Record<BeatId, "under" | "left" | "right"> = { describe: "under", model: "left", analysis: "right", report: "under" };
/** The three files the workspace lists first for a run. */
const FILES = DOWNLOAD_LABELS.slice(0, 3).map(([, label]) => label);
const materialName = (id: string) => libraryOptions.find((option) => option.id === id)?.name ?? id;

/** The home page's demonstration of the product (ADR-0094): the coupon workspace in four beats, in a white box the size of the
 * hero's clip, directly under it. Each beat uses the workspace's own names and shapes, cut down for a first look: the assistant's
 * question and chips, the setup's summary, the run's stages with the stress field, and the files. Nothing is asked of the API:
 * the model, the field's colours and every number are one recorded run of the solver on a public example (lib/demo-run.ts).
 *
 * On a desktop the box holds the window while it stands in its middle, and one scroll gesture plays one whole beat
 * (components/home/tour-driver.ts); the page scrolls to it and away from it as any page does. The centre model changes place
 * and orientation between beats in one eased move, and the words change sides (product-demo-timeline.ts). With reduced motion
 * or a small window the beats lie one under another and no gesture is taken. */
export function ProductDemo() {
  const box = useRef<HTMLDivElement>(null);
  const pinned = useMediaQuery(PINNED_QUERY);
  const run = demoRun;
  const script = useMemo(() => layupScript(run.coupon.layup, run.coupon.angles.length), [run]);
  const material = materialName(run.coupon.library);
  const cells = useMemo(() => summaryCells(run, material), [run, material]);
  const counts = useMemo(() => ({ cells: cells.length, stages: RUN_STEPS.length, files: FILES.length }), [cells]);
  const start = useMemo(() => viewAt(0, script, counts), [script, counts]);
  const whole = useMemo(() => finalView(script, counts), [script, counts]);
  const [played, setPlayed] = useState<DemoView | null>(null);
  const [viewWanted, setViewWanted] = useState(false);
  const handle = useMemo<DemoSceneHandle>(() => ({ clock: 0, redraw: null }), []);
  const view = pinned ? played ?? start : whole;

  // The clock: the driver plays it one beat a gesture and reports each frame. The 3D view reads it from the handle.
  useTourDriver(box, pinned, ({ clock }) => {
    handle.clock = clock;
    handle.redraw?.();
    const next = viewAt(clock, script, counts);
    setPlayed((current) => (current && sameView(current, next) ? current : next));
  }, {
    stops: DEMO_STOPS,
    clockPerSecond: DEMO_CLOCK_PER_SECOND,
    // The box holds the window while it stands in the window's middle.
    anchor: () => Math.round(((window.innerHeight || 0) - (box.current?.offsetHeight ?? 0)) / 2),
    settleWithin: 160,
  });
  // Not stepped: every beat is finished, and the view shows the run's end.
  useEffect(() => {
    if (pinned) return;
    handle.clock = DEMO_TOTAL;
    handle.redraw?.();
  }, [pinned, handle]);

  // The view is not mounted with the page: stepped, once the browser is idle after the load or at the first scroll; not
  // stepped, when the box comes within a screen of the window.
  useEffect(() => {
    if (viewWanted) return;
    const want = () => setViewWanted(true);
    if (pinned) {
      let idle = 0;
      const timer = window.setTimeout(() => {
        if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(want, { timeout: 1500 });
        else want();
      }, 1200);
      window.addEventListener("scroll", want, { once: true, passive: true });
      return () => {
        window.clearTimeout(timer);
        if (idle && typeof window.cancelIdleCallback === "function") window.cancelIdleCallback(idle);
        window.removeEventListener("scroll", want);
      };
    }
    if (!box.current || typeof IntersectionObserver === "undefined") { want(); return; }
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) want(); }, { rootMargin: "100% 0px" });
    observer.observe(box.current);
    return () => observer.disconnect();
  }, [pinned, viewWanted]);

  const scale = useMemo(() => demoScale(run), [run]);
  const result = useMemo(() => resultLines(run), [run]);
  const typed = run.coupon.layup.slice(0, view.layupChars);
  const cards: Record<BeatId, React.ReactNode> = {
    describe: (
      <div className="demo-card demo-assistant" data-testid="demo-assistant">
        <p className="demo-card-head"><span className="demo-dot" aria-hidden="true" />{ASSISTANT.name}</p>
        <p className="demo-question">{ASSISTANT.question}</p>
        <ul className="demo-chips" aria-label="Materials">
          {COMMON_MATERIALS.map((id) => (
            <li key={id} data-picked={view.picked && id === run.coupon.library ? "true" : undefined}>
              {view.picked && id === run.coupon.library ? <Check size={14} aria-hidden="true" /> : <Layers3 size={14} aria-hidden="true" />} {materialName(id)}
            </li>
          ))}
        </ul>
        <div className="demo-fields">
          <p className="demo-field"><span>{ASSISTANT.standard}</span><strong data-picked={view.standard ? "true" : undefined}>{view.standard ? standardName(run) : "–"}</strong></p>
          <p className="demo-field"><span>{ASSISTANT.layup}</span><strong className="demo-typed" data-testid="demo-layup">{typed}{pinned && view.layupChars < run.coupon.layup.length ? <i aria-hidden="true" /> : null}</strong></p>
        </div>
      </div>
    ),
    model: (
      <dl className="demo-card demo-summary" data-testid="demo-summary">
        {cells.map(([name, value], index) => (
          <div key={name} data-filled={index < view.cells ? "true" : undefined}>
            <dt>{name}</dt>
            <dd>{index < view.cells ? value : "–"}</dd>
          </div>
        ))}
      </dl>
    ),
    analysis: (
      <div className="demo-card demo-run" data-testid="demo-run">
        <ol className="demo-stages" aria-label="The run">
          {RUN_STEPS.map((step, index) => (
            <li key={step.id} data-state={index < view.stage ? "done" : index === view.stage ? "current" : "waiting"}>
              <span aria-hidden="true">{index < view.stage ? <Check size={12} /> : null}</span>{step.label}
            </li>
          ))}
        </ol>
        <div className="demo-legend" data-shown={view.legend ? "true" : undefined} data-testid="demo-legend">
          <p>{FIELD_LABEL}, {run.field.unit}</p>
          <span className="demo-legend-bar" style={{ background: legendGradient(scale, 0) }} aria-hidden="true" />
          <p className="demo-legend-ends"><span>{Math.round(scale.min)}</span><span>0</span><span>{Math.round(scale.max)}</span></p>
        </div>
        <div className="demo-result" data-shown={view.result ? "true" : undefined} data-testid="demo-result">
          <p><strong>{result.first}</strong></p>
          <p>{result.when}</p>
        </div>
      </div>
    ),
    report: (
      <div className="demo-card demo-report" data-testid="demo-report">
        <p className="demo-card-head">{FILES_HEAD}</p>
        <ul className="demo-files">
          {FILES.map((name, index) => (
            <li key={name} data-shown={index < view.files ? "true" : undefined}><FileText size={15} aria-hidden="true" /> {name}</li>
          ))}
        </ul>
        <Link className="demo-open" href="/workspace/fea">{OPEN_WORKSPACE} <ArrowUpRight size={16} aria-hidden="true" /></Link>
      </div>
    ),
  };

  return (
    <section className="product-demo" id="demo" aria-labelledby="demo-title" data-mode={pinned ? "pinned" : "static"}>
      <div className="product-demo-box" ref={box}>
        <div className="product-demo-head">
          <p className="demo-label">{DEMO_HEAD.label}</p>
          <h2 id="demo-title">{DEMO_HEAD.title}</h2>
        </div>
        <div className="product-demo-view">{viewWanted ? <ProductDemoScene handle={handle} script={script} /> : null}</div>
        <ol className="product-demo-beats">
          {BEAT_IDS.map((id, index) => {
            const active = !pinned || view.beat === index;
            const shown = pinned ? (view.beat === index ? view.words : 0) : 1;
            return (
              <li className="product-demo-beat" key={id} data-beat={id} data-side={SIDE[id]} data-active={active ? "true" : "false"}
                aria-hidden={pinned && !active ? true : undefined} style={{ "--shown": shown } as CSSProperties}>
                <div className="product-demo-words">
                  <p className="demo-label">{BEAT_COPY[id].label}</p>
                  <h3>{BEAT_COPY[id].title}</h3>
                  <p>{BEAT_COPY[id].text}</p>
                </div>
                {cards[id]}
              </li>
            );
          })}
        </ol>
        <p className="product-demo-recorded" data-testid="demo-recorded" data-shown={!pinned || view.beat >= 2 ? "true" : undefined}>{recordedLine(run)}</p>
      </div>
    </section>
  );
}
