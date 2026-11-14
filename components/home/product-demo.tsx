"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import { ArrowUpRight, Check, FileText } from "lucide-react";
import { demoWing, wingScale } from "@/lib/demo-wing";
import { legendGradient } from "@/lib/studio-colors";
import { DOWNLOAD_LABELS, RUN_STEPS } from "@/lib/studio-copy";
import { libraryOptions } from "@/lib/studio-form";
import { BEAT_COPY, DEMO_HEAD, FILES_HEAD, OPEN_WORKSPACE, resultLines, wingFacts, wingParts } from "./product-demo-copy";
import type { DemoSceneHandle } from "./product-demo-scene";
import { BEAT_IDS, DEMO_CLOCK_PER_SECOND, DEMO_STOPS, DEMO_TOTAL, finalView, sameView, viewAt, type BeatId, type DemoView } from "./product-demo-timeline";
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
/** An end of the legend: a share as a percentage when the field has no unit, the rounded value otherwise. */
const legendEnd = (value: number, unit: string) => (unit ? String(Math.round(value)) : `${Math.round(value * 100)} %`);

/** The home page's demonstration of the product (ADR-0095, ADR-0098): one composite wing in four beats, on a black stage as
 * wide as the hero's clip and a window tall, which the hero hands over to (components/home/hero-handover.tsx). The wing stands
 * whole, comes apart into its parts, takes the analysis's colours part by part, and closes again. The cards beside it are the
 * workspace's shapes cut down for a first look: a summary strip, the run's stages with the legend, and the files. Nothing is
 * asked of the API: the mesh, the colours and every number are one recorded analysis of an example wing (lib/demo-wing.ts).
 * The wing is ahead of the product, which analyses coupons today: the lead's choice of 2026-11-14.
 *
 * On a desktop the stage holds the window while it fills it, and one scroll gesture plays one whole beat
 * (components/home/tour-driver.ts); the page scrolls to it and away from it as any page does. The model changes place and
 * orientation between beats in one eased move, and the words change sides (product-demo-timeline.ts). With reduced motion
 * or a small window the beats lie one under another and no gesture is taken. */
export function ProductDemo() {
  const box = useRef<HTMLDivElement>(null);
  const pinned = useMediaQuery(PINNED_QUERY);
  const wing = demoWing;
  const material = materialName(wing.wing.library);
  const facts = useMemo(() => wingFacts(wing, material), [wing, material]);
  const parts = useMemo(() => wingParts(wing), [wing]);
  const counts = useMemo(() => ({ facts: facts.length, parts: parts.length, stages: RUN_STEPS.length, files: FILES.length }), [facts, parts]);
  const start = useMemo(() => viewAt(0, counts), [counts]);
  const whole = useMemo(() => finalView(counts), [counts]);
  const [played, setPlayed] = useState<DemoView | null>(null);
  const [viewWanted, setViewWanted] = useState(false);
  const handle = useMemo<DemoSceneHandle>(() => ({ clock: 0, redraw: null }), []);
  const view = pinned ? played ?? start : whole;

  // The clock: the driver plays it one beat a gesture and reports each frame. The 3D view reads it from the handle.
  useTourDriver(box, pinned, ({ clock }) => {
    handle.clock = clock;
    handle.redraw?.();
    const next = viewAt(clock, counts);
    setPlayed((current) => (current && sameView(current, next) ? current : next));
  }, {
    stops: DEMO_STOPS,
    clockPerSecond: DEMO_CLOCK_PER_SECOND,
    // The stage is a window tall and holds the window with its top edge on the window's (the driver's own line).
    settleWithin: 160,
    // With the page at its top the stage lies behind the hero (ADR-0095 amendment 4): that is where it is out of sight.
    hiddenFrom: () => {
      const stage = box.current;
      const opening = stage?.closest(".home-opening");
      return stage && opening ? stage.getBoundingClientRect().top - opening.getBoundingClientRect().top : window.innerHeight;
    },
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

  const field = wing.field;
  const scale = useMemo(() => (field ? wingScale(field) : null), [field]);
  const result = useMemo(() => resultLines(wing), [wing]);
  const strip = (rows: [string, string][], filled: number, testId: string) => (
    <dl className="demo-card demo-summary" data-testid={testId}>
      {rows.map(([name, value], index) => (
        <div key={name} data-filled={index < filled ? "true" : undefined}>
          <dt>{name}</dt>
          <dd>{index < filled ? value : "–"}</dd>
        </div>
      ))}
    </dl>
  );
  const cards: Record<BeatId, React.ReactNode> = {
    describe: strip(facts, view.facts, "demo-facts"),
    model: strip(parts, view.parts, "demo-parts"),
    analysis: (
      <div className="demo-card demo-run" data-testid="demo-run">
        <ol className="demo-stages" aria-label="The run">
          {RUN_STEPS.map((step, index) => (
            <li key={step.id} data-state={index < view.stage ? "done" : index === view.stage ? "current" : "waiting"}>
              <span aria-hidden="true">{index < view.stage ? <Check size={12} /> : null}</span>{step.label}
            </li>
          ))}
        </ol>
        {field && scale ? (
          <div className="demo-legend" data-shown={view.legend ? "true" : undefined} data-testid="demo-legend">
            <p>{field.label}{field.unit ? `, ${field.unit}` : ""}</p>
            <span className="demo-legend-bar" style={{ background: legendGradient(scale, 0) }} aria-hidden="true" />
            <p className="demo-legend-ends"><span>{legendEnd(field.min, field.unit)}</span><span>{legendEnd(field.max, field.unit)}</span></p>
          </div>
        ) : null}
        {result ? (
          <div className="demo-result" data-shown={view.result ? "true" : undefined} data-testid="demo-result">
            <p><strong>{result.first}</strong></p>
            <p>{result.when}</p>
          </div>
        ) : null}
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
        <div className="product-demo-view">{viewWanted ? <ProductDemoScene handle={handle} /> : null}</div>
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
      </div>
    </section>
  );
}
