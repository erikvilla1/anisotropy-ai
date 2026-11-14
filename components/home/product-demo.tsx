"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import { ArrowRight, Check, FileText, Rotate3d } from "lucide-react";
import { demoWing, RAINBOW_GRADIENT } from "@/lib/demo-wing";
import { DOWNLOAD_LABELS, RUN_STEPS } from "@/lib/studio-copy";
import { libraryOptions } from "@/lib/studio-form";
import { BEAT_COPY, BEND_NOTE, DEMO_HEAD, FILES_HEAD, OPEN_WORKSPACE, TURN_HINT, resultLines, wingFacts, wingParts } from "./product-demo-copy";
import type { DemoSceneHandle } from "./product-demo-scene";
import { BEAT_IDS, DEMO_CLOCK_PER_SECOND, DEMO_STOPS, DEMO_TOTAL, finalView, sameView, viewAt, type BeatId, type DemoView } from "./product-demo-timeline";
import { useScrollStage } from "./scroll-stage";
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

/** The scroll a beat takes, as a share of the stage's height, and how far before the stage holds the window the first beat
 * starts (ADR-0095 amendment 10). The section is the stage and a zone for every beat tall: app/home-demo.css reads the
 * product of the two as `--demo-track`, written on the section below. */
const ZONE = 0.5;
const LEAD = 0.08;

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
 * On a desktop the stage stays in the window while the page scrolls past it, freely, and where the scroll stands says
 * which beat plays (components/home/scroll-stage.ts, ADR-0095 amendment 10): a beat starts as the scroll reaches its zone
 * and plays on its own, a fast scroll runs through the beats it leaves behind, and scrolling back up unplays them, down to
 * the hero. The model changes place and orientation between beats in one eased move, and the words change sides
 * (product-demo-timeline.ts). With reduced motion or a small window the beats lie one under another, finished. */
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
  const [finished, setFinished] = useState(false); // the clock stands at the last beat's end
  const handle = useMemo<DemoSceneHandle>(() => ({ clock: 0, redraw: null }), []);
  const view = pinned ? played ?? start : whole;

  // The clock: the stage plays it to the beat the scroll asks for and reports each frame. The 3D view reads it from the
  // handle.
  useScrollStage(box, pinned, ({ clock }) => {
    handle.clock = clock;
    handle.redraw?.();
    setFinished(clock >= DEMO_TOTAL);
    const next = viewAt(clock, counts);
    setPlayed((current) => (current && sameView(current, next) ? current : next));
  }, { stops: DEMO_STOPS, clockPerSecond: DEMO_CLOCK_PER_SECOND, zone: ZONE, lead: LEAD });

  // Where the words that stand under the wing begin, for the view to keep the wing over them (ADR-0098 amendment 4): the
  // highest of those beats' blocks, measured again whenever the stage or a block changes size.
  useEffect(() => {
    const stage = box.current;
    if (!stage || !pinned || typeof ResizeObserver === "undefined") {
      handle.under = undefined;
      handle.redraw?.();
      return;
    }
    const blocks = [...stage.querySelectorAll<HTMLElement>('.product-demo-beat[data-side="under"]')];
    const measure = () => {
      handle.under = blocks.length ? Math.min(...blocks.map((block) => block.offsetTop)) : undefined;
      handle.redraw?.();
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(stage);
    blocks.forEach((block) => observer.observe(block));
    return () => observer.disconnect();
  }, [pinned, handle]);

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

  // While the demo stands finished (or where it does not play at all), the wing can be turned by hand (ADR-0098 amendment
  // 1): a drag that starts on the stage itself, not on a card or the words, turns it about its upright axis and tips it.
  // Scrolled back into an earlier beat it is the demo's again; the view lets the turn go as the clock leaves the end.
  const turnable = !pinned || finished;
  const drag = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);
  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!turnable || event.button !== 0 || !viewWanted) return;
    if (event.target instanceof Element && event.target.closest("a, button, .demo-card, .product-demo-words, .product-demo-head")) return;
    const turn = handle.turn ?? (handle.turn = { yaw: 0, pitch: 0 });
    drag.current = { x: event.clientX, y: event.clientY, yaw: turn.yaw, pitch: turn.pitch };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.dataset.turning = "true";
    // While the pointer holds the wing its axes are drawn, and the words step back (app/home-demo.css).
    handle.turning = true;
    handle.redraw?.();
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const from = drag.current;
    if (!from || !handle.turn) return;
    handle.turn.yaw = from.yaw + (event.clientX - from.x) * 0.006;
    handle.turn.pitch = Math.max(-1.2, Math.min(1.2, from.pitch - (event.clientY - from.y) * 0.005));
    event.currentTarget.dataset.turned = "true";
    handle.redraw?.();
  };
  const onPointerEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    drag.current = null;
    delete event.currentTarget.dataset.turning;
    handle.turning = false;
    handle.redraw?.();
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const field = wing.field;
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
        {field ? (
          <div className="demo-legend" data-shown={view.legend ? "true" : undefined} data-testid="demo-legend">
            <p>{field.label}{field.unit ? `, ${field.unit}` : ""}</p>
            <span className="demo-legend-bar" style={{ background: RAINBOW_GRADIENT }} aria-hidden="true" />
            <p className="demo-legend-ends"><span>{legendEnd(field.min, field.unit)}</span><span>{legendEnd(field.max, field.unit)}</span></p>
          </div>
        ) : null}
        {result ? (
          <div className="demo-result" data-shown={view.result ? "true" : undefined} data-testid="demo-result">
            <p><strong>{result.first}</strong></p>
            <p>{result.when}</p>
            {wing.displacement ? <p className="demo-result-note">{BEND_NOTE}</p> : null}
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
        <Link className="demo-open" href="/workspace/fea">{OPEN_WORKSPACE} <ArrowRight size={16} aria-hidden="true" /></Link>
      </div>
    ),
  };

  return (
    <section className="product-demo" id="demo" aria-labelledby="demo-title" data-mode={pinned ? "pinned" : "static"}
      style={{ "--demo-track": BEAT_IDS.length * ZONE } as CSSProperties}>
      <div className="product-demo-box" ref={box} data-turnable={turnable ? "true" : undefined}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerEnd} onPointerCancel={onPointerEnd}>
        <div className="product-demo-head">
          <p className="demo-label">{DEMO_HEAD.label}</p>
          <h2 id="demo-title">{DEMO_HEAD.title}</h2>
        </div>
        <div className="product-demo-view">{viewWanted ? <ProductDemoScene handle={handle} /> : null}</div>
        <p className="product-demo-hint" data-shown={turnable ? "true" : undefined}><Rotate3d size={14} aria-hidden="true" /> {TURN_HINT}</p>
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
