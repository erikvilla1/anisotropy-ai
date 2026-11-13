"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import { ArrowDown } from "lucide-react";
import { LaminateScene } from "./scene";
import { AbdGrid, FailurePanel, PropertyRow, SpecsList, StackList } from "./laminate-panels";
import { useEngineAnswers, useEngineEntry, type EngineEntry } from "./engine-answers";
import { useTourDriver } from "./tour-driver";
import { STEPS, finalView, layupScript, sameView, span, viewAt, type TourView } from "./tour-timeline";
import { buildAnalysisRequest, CalculationError, loadNames, requestAnalysis, type AnalysisRequest, type LoadName } from "@/lib/laminate-api";
import { defaultHeroState, heroForm, zeroLoads } from "@/lib/home-calculator";
import { expandLayup } from "@/lib/layup";
import { findLibraryOption, libraryOptions, type LibraryOption } from "@/lib/material-library-options";
import { angleSlots } from "@/lib/studio-colors";
import "@/app/home-tour.css";

/** The tour is one stage that holds the window and plays a step per scroll gesture ("pinned") on a desktop-sized window
 * whose visitor has not asked for reduced motion; everywhere else it is an ordinary section with every step in view. The
 * same query is written in app/home-tour.css. */
const PINNED_QUERY = "(min-width: 1024px) and (min-height: 600px) and (prefers-reduced-motion: no-preference)";
/** The tour's example load, the one the page's tests use: Nx in N/m. */
const TOUR_LOAD: { name: LoadName; value: string } = { name: "Nx", value: "25000" };
/** How long a step has been reached before the tour asks the engine for it, so a visitor who turns straight back asks nothing. */
const DWELL_MS = 400;
const TIMEOUT_MS = 20_000;
/** The pinned tour's 3D view is not part of the page's load: it is mounted when the browser is idle this long after the tour
 * itself, by when the page's load-in is over, or at the visitor's first scroll if that comes sooner. */
const VIEW_AFTER_MS = 2500;

function useMediaQuery(query: string): boolean {
  const subscribe = useCallback((listener: () => void) => {
    const media = window.matchMedia(query);
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches, () => false);
}

/** The run the tour replays: the calculator's own opening state (lib/home-calculator.ts), unloaded and under the example load,
 * built into requests exactly as the calculator builds them. */
function tourRun() {
  const state = defaultHeroState();
  const parsed = expandLayup(state.layup);
  const angles = parsed.layup?.angles ?? [];
  const requestOf = (loads: Record<LoadName, string>) => {
    const form = heroForm({ ...state, loads }, angles);
    return form ? buildAnalysisRequest(form).request ?? null : null;
  };
  const unloaded = requestOf(zeroLoads());
  const loaded = requestOf({ ...zeroLoads(), [TOUR_LOAD.name]: TOUR_LOAD.value });
  return {
    state, angles, option: findLibraryOption(state.library),
    script: layupScript(state.layup, angles.length, parsed.layup?.symmetric ?? false),
    unloaded, unloadedJson: unloaded ? JSON.stringify(unloaded) : null,
    loaded, loadedJson: loaded ? JSON.stringify(loaded) : null,
  };
}

const signed = (angle: number) => (angle > 0 ? `+${angle}` : String(angle));
/** While the tour steers the view, the pointer passing over it does not light a ply: the list beside it still does. */
const ignoreHover = () => {};

/** What the engine's line says, in the calculator's own words. */
function engineLine(apiBaseUrl: string, entry: EngineEntry | undefined): string {
  if (!apiBaseUrl) return "Calculations are unavailable on this site.";
  if (entry?.state === "answer") return `Engine ${entry.result.engine_version}${entry.result.run_id ? ` · run ${entry.result.run_id.slice(0, 8)}` : ""}`;
  if (entry?.state === "failed") return "The engine did not answer.";
  if (entry?.state === "pending") return "Calculating…";
  return "Waiting for the engine.";
}

/** A field of the calculator as the tour shows it: read-only, filled as its step plays. The live fields are in the calculator below. */
function TourField({ label, value, hint, caret = false, quiet = false }: { label: ReactNode; value: string; hint?: string; caret?: boolean; quiet?: boolean }) {
  return (
    <div className={quiet ? "tour-field is-quiet" : "tour-field"}>
      <span className="tour-field-label">{label}</span>
      <span className="tour-field-box" data-caret={caret ? "true" : undefined}>{value}</span>
      {hint ? <span className="tour-hint">{hint}</span> : null}
    </div>
  );
}

const CONSTANT_KEYS = ["E1_GPa", "E2_GPa", "G12_GPa", "nu12", "density_kg_per_m3", "Vf_percent"] as const;

/** The library record with its constants typed in part: each value is the record's own text, cut where the typing has reached. */
function typedOption(option: LibraryOption, typed: number): LibraryOption {
  if (typed >= 1) return option;
  const next: LibraryOption = { ...option };
  CONSTANT_KEYS.forEach((key, index) => {
    const value = option[key];
    if (value === null) return;
    const share = span(typed, index / 9, (index + 4) / 9);
    (next as Record<(typeof CONSTANT_KEYS)[number], string | null>)[key] = value.slice(0, Math.round(value.length * share));
  });
  return next;
}

const MaterialCard = memo(function MaterialCard({ option, picked, constants }: { option: LibraryOption; picked: boolean; constants: number }) {
  const listed = useMemo(() => {
    const index = libraryOptions.findIndex((item) => item.value === option.value);
    const from = Math.max(0, Math.min(libraryOptions.length - 4, index - 2));
    return libraryOptions.slice(from, from + 4);
  }, [option]);
  const typed = useMemo(() => typedOption(option, picked ? constants : 0), [option, picked, constants]);
  return (
    <>
      <div className="tour-card-head">
        <span className="tour-eyebrow">MATERIAL, FROM THE LIBRARY</span>
        <span className="tour-hint">{libraryOptions.length} cited datasets</span>
      </div>
      <ul className="tour-library" aria-label="Datasets in the materials library">
        {listed.map((item) => (
          <li key={item.value} data-picked={picked && item.value === option.value ? "true" : undefined}>{item.label}</li>
        ))}
        <li className="tour-library-more">and {libraryOptions.length - listed.length} more</li>
      </ul>
      <p className="tour-hint tour-reveal" data-shown={picked ? "true" : undefined}>{option.citation}</p>
      <PropertyRow option={typed} provenance={undefined} />
    </>
  );
});

const LayupCard = memo(function LayupCard({ text, chars, thickness, option, angles, laid, colors, hovered, onHover }: {
  text: string; chars: number; thickness: boolean; option: LibraryOption; angles: number[]; laid: number;
  colors: Map<number, string>; hovered: number | null; onHover: (index: number | null) => void;
}) {
  const shown = useMemo(() => angles.slice(0, laid), [angles, laid]);
  const thicknessText = option.thickness_mm ?? "";
  return (
    <>
      <div className="tour-field-row">
        <TourField label="Layup" value={text.slice(0, chars)} caret={chars < text.length} hint="Bottom face first; s mirrors the stack." />
        <TourField label="Ply thickness (mm)" value={thickness ? thicknessText : ""}
          hint={option.thickness_mm ? "The dataset's cured ply thickness." : "The dataset states no ply thickness."} />
      </div>
      <p className="tour-eyebrow tour-stack-head">PLIES, TOP FACE FIRST</p>
      <div className="tour-stack-slot" style={{ "--tour-rows": angles.length } as CSSProperties}>
        <StackList angles={shown} thickness_mm={thicknessText} colors={colors} hovered={hovered} onHover={onHover} />
      </div>
    </>
  );
});

/** The request as it goes to the engine, read from the request itself; where the site has no calculation service, it says
 * that nothing is sent. */
function RequestLines({ request, thickness_mm, sent }: { request: AnalysisRequest; thickness_mm: string; sent: boolean }) {
  const material = "library_id" in request.material ? `${request.material.library_id} · ${request.material.dataset_id}` : request.material.source_reference;
  const loads = loadNames.filter((name) => request.loads[name] !== 0).map((name) => `${name} = ${request.loads[name]} ${name.startsWith("N") ? "N/m" : "N·m/m"}`);
  return (
    <dl className="tour-request" aria-label="The request to the engine">
      {sent ? <div><dt>POST</dt><dd>/v1/laminates/response</dd></div> : <div><dt>request</dt><dd>not sent: this site has no calculation service</dd></div>}
      <div><dt>material</dt><dd>{material}</dd></div>
      <div><dt>plies</dt><dd>{request.plies.length} × {thickness_mm} mm · {request.plies.map((ply) => signed(ply.angle_deg)).join(" / ")}</dd></div>
      <div><dt>loads</dt><dd>{loads.length ? loads.join(", ") : "none"}</dd></div>
    </dl>
  );
}

/** What stands where the engine's numbers go while there are none: it says so, and keeps the panel's size. */
function NeedsEngine({ apiBaseUrl, entry, what }: { apiBaseUrl: string; entry: EngineEntry | undefined; what: string }) {
  if (apiBaseUrl && entry?.state !== "failed") return <p className="tour-waiting" aria-hidden="true" />;
  return (
    <p className="tour-needs-engine" role="note">
      {entry?.state === "failed" ? `${entry.message} ` : ""}
      {what} are the engine&apos;s numbers, and nothing here stands in for them. The material, the layup and the plies above need no engine.
    </p>
  );
}

const EngineCard = memo(function EngineCard({ stage, apiBaseUrl, entry, request, thickness_mm }: {
  stage: TourView["engine"]; apiBaseUrl: string; entry: EngineEntry | undefined; request: AnalysisRequest | null; thickness_mm: string;
}) {
  const result = entry?.state === "answer" ? entry.result : null;
  const answered = stage >= 2;
  // Busy: the request is on its way in the replay, or the engine has truly not answered yet.
  const busy = Boolean(apiBaseUrl) && (stage === 1 || (answered && !result && entry?.state !== "failed"));
  return (
    <>
      <div className="tour-card-head">
        <span className="tour-eyebrow">THE ENGINE SAYS</span>
        <span className="tour-hint" role="status">
          {answered || !apiBaseUrl || !entry ? (stage >= 1 ? engineLine(apiBaseUrl, entry) : "") : "Sent to the engine."}
        </span>
      </div>
      {request ? (
        <div className="tour-reveal" data-shown={stage >= 1 ? "true" : undefined}>
          <RequestLines request={request} thickness_mm={thickness_mm} sent={Boolean(apiBaseUrl)} />
        </div>
      ) : null}
      <div className="tour-slot tour-slot-specs" data-busy={busy ? "true" : undefined}>
        {answered && result?.summary ? <SpecsList summary={result.summary} />
          : (answered || (stage === 1 && !apiBaseUrl)) && !result ? <NeedsEngine apiBaseUrl={apiBaseUrl} entry={entry} what="The description and the matrices" /> : null}
      </div>
      <div className="tour-slot tour-slot-abd" data-busy={busy || (stage === 2 && Boolean(result)) ? "true" : undefined}>
        {stage >= 3 && result ? <AbdGrid result={result} /> : null}
      </div>
    </>
  );
});

const LoadsCard = memo(function LoadsCard({ chars, loaded, apiBaseUrl, entry }: { chars: number; loaded: boolean; apiBaseUrl: string; entry: EngineEntry | undefined }) {
  const result = entry?.state === "answer" ? entry.result : null;
  return (
    <>
      <div className="tour-card-head">
        <span className="tour-eyebrow">LOADS PER UNIT WIDTH</span>
        <span className="tour-hint" role="status">{loaded ? engineLine(apiBaseUrl, entry) : ""}</span>
      </div>
      <div className="tour-loads">
        {loadNames.map((name) => (
          <TourField key={name} quiet={name !== TOUR_LOAD.name}
            label={<>{name} <small>({name.startsWith("N") ? "N/m" : "N·m/m"})</small></>}
            value={name === TOUR_LOAD.name ? TOUR_LOAD.value.slice(0, chars) || (chars ? "" : "0") : "0"}
            caret={name === TOUR_LOAD.name && chars > 0 && chars < TOUR_LOAD.value.length} />
        ))}
      </div>
      <div className="tour-slot tour-slot-failure" data-busy={loaded && !result && Boolean(apiBaseUrl) && entry?.state !== "failed" ? "true" : undefined}>
        {loaded && result?.first_ply_failure ? <FailurePanel failure={result.first_ply_failure} />
          : loaded && !result ? <NeedsEngine apiBaseUrl={apiBaseUrl} entry={entry} what="The failure check and its factors" /> : null}
      </div>
    </>
  );
});

function HandoverCard({ option, layup, thickness_mm }: { option: LibraryOption; layup: string; thickness_mm: string }) {
  return (
    <>
      <div className="tour-card-head">
        <span className="tour-eyebrow">LAMINATE CALCULATOR / LIVE</span>
        <ArrowDown size={16} aria-hidden="true" />
      </div>
      <dl className="tour-request" aria-label="What the calculator below starts from">
        <div><dt>material</dt><dd>{option.label}</dd></div>
        <div><dt>layup</dt><dd>{layup}</dd></div>
        <div><dt>ply</dt><dd>{thickness_mm} mm</dd></div>
        <div><dt>loads</dt><dd>none yet</dd></div>
      </dl>
    </>
  );
}

/** The tour of the calculator between the hero and the calculator itself (the lead's requests of 2026-11-09 and 2026-11-13):
 * a visitor's scrolling takes them through one real run, from a library material to a first-ply failure, and then leaves them
 * at the live calculator. Each scroll gesture plays one whole step at constant speed (components/home/tour-driver.ts,
 * ADR-0084 amendment 4); after the last step the stage lets go and the page scrolls on. Every engine number it shows is an
 * answer of the real engine to the stack on screen: the unloaded answer is the one the calculator asked for when the page
 * loaded, shared through `EngineAnswersProvider`, and the loaded one is asked for, once, when the visitor reaches that step
 * (ADR-0001). The material's constants are the library record's, as the calculator shows them. */
export function DemoTour({ apiBaseUrl }: { apiBaseUrl: string }) {
  const root = useRef<HTMLDivElement>(null);
  const sceneBox = useRef<HTMLDivElement>(null);
  const loadsStep = useRef<HTMLLIElement>(null);
  const engineStep = useRef<HTMLLIElement>(null);
  const pinned = useMediaQuery(PINNED_QUERY);
  const reducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const answers = useEngineAnswers();
  const run = useMemo(tourRun, []);
  const start = useMemo(() => viewAt(0, run.script, run.angles.length, TOUR_LOAD.value), [run]);
  const whole = useMemo(() => finalView(run.script, run.angles.length, TOUR_LOAD.value), [run]);
  const [scrolled, setScrolled] = useState<TourView | null>(null);
  const [reached, setReached] = useState({ engine: false, loads: false });
  const [hovered, setHovered] = useState<number | null>(null);
  const [viewWanted, setViewWanted] = useState(false);
  const view = pinned ? scrolled ?? start : whole;

  // The 3D view is a second WebGL view on the page (the calculator has its own), so it is not mounted with the page. Pinned,
  // the stage is one gesture away from the hero: the view is mounted once the browser is idle after the load, or at the
  // first scroll. Unpinned, it is mounted when the section comes within a screen of the window.
  useEffect(() => {
    if (viewWanted) return;
    const want = () => setViewWanted(true);
    if (pinned) {
      let idle = 0;
      const timer = window.setTimeout(() => {
        if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(want, { timeout: 1500 });
        else want();
      }, VIEW_AFTER_MS);
      const onScroll = () => { if (window.scrollY > 0) want(); };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
      return () => {
        window.clearTimeout(timer);
        if (idle) window.cancelIdleCallback(idle);
        window.removeEventListener("scroll", onScroll);
      };
    }
    const box = sceneBox.current;
    if (!box || typeof IntersectionObserver === "undefined") {
      want();
      return;
    }
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) want(); }, { rootMargin: "100% 0px" });
    observer.observe(box);
    return () => observer.disconnect();
  }, [pinned, viewWanted]);

  const unloaded = useEngineEntry(run.unloadedJson);
  const loaded = useEngineEntry(run.loadedJson);

  // The clock: tour-driver.ts plays it one step per scroll gesture and reports each frame. What is written here are styles.
  useTourDriver(root, pinned, ({ clock, onStage }) => {
    const element = root.current;
    if (!element) return;
    STEPS.forEach((step, index) => element.style.setProperty(`--tour-rail-${index}`, span(clock, step.start, step.end).toFixed(3)));
    const next = viewAt(clock, run.script, run.angles.length, TOUR_LOAD.value);
    setScrolled((current) => (current && sameView(current, next) ? current : next));
    // A step is reached while at least half of the stage is in the window; past that the visitor is in the calculator.
    const engine = onStage && next.engine >= 1;
    const loads = onStage && next.loaded;
    setReached((current) => (current.engine === engine && current.loads === loads ? current : { engine, loads }));
  });
  useEffect(() => {
    if (pinned) return;
    // Unpinned, a step is reached when most of it is in view.
    setScrolled(null);
    if (typeof IntersectionObserver === "undefined") {
      setReached({ engine: true, loads: true });
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      setReached((current) => {
        const next = { ...current };
        for (const entry of entries) {
          if (entry.target === engineStep.current) next.engine = entry.isIntersecting;
          if (entry.target === loadsStep.current) next.loads = entry.isIntersecting;
        }
        return next;
      });
    }, { threshold: 0.5 });
    if (engineStep.current) observer.observe(engineStep.current);
    if (loadsStep.current) observer.observe(loadsStep.current);
    return () => observer.disconnect();
  }, [pinned]);

  // Asking the engine, exactly as the calculator does (lib/laminate-api.ts), and at most once per stack.
  const flights = useRef(new Set<AbortController>());
  useEffect(() => {
    const open = flights.current;
    return () => open.forEach((controller) => controller.abort("unmount"));
  }, []);
  const ask = useCallback((requestJson: string) => {
    if (!answers || !apiBaseUrl) return;
    const known = answers.read(requestJson);
    if (known?.state === "pending" || known?.state === "answer") return;
    const controller = new AbortController();
    flights.current.add(controller);
    const timeout = window.setTimeout(() => controller.abort("timeout"), TIMEOUT_MS);
    answers.report(requestJson, { state: "pending" });
    requestAnalysis(apiBaseUrl, JSON.parse(requestJson), controller.signal)
      .then((result) => answers.report(requestJson, { state: "answer", result }))
      .catch((error: unknown) => {
        if (controller.signal.reason === "unmount") return;
        answers.report(requestJson, {
          state: "failed",
          message: controller.signal.aborted ? "The calculation timed out."
            : error instanceof CalculationError ? error.message : "Cannot reach the calculation service.",
        });
      })
      .finally(() => {
        window.clearTimeout(timeout);
        flights.current.delete(controller);
      });
  }, [answers, apiBaseUrl]);
  // The loaded case: asked for when the visitor rests on the loads step, and again on a later visit only if it failed.
  useEffect(() => {
    if (!reached.loads || !run.loadedJson) return;
    const json = run.loadedJson;
    const timer = window.setTimeout(() => ask(json), DWELL_MS);
    return () => window.clearTimeout(timer);
  }, [reached.loads, run.loadedJson, ask]);
  // The unloaded case is the calculator's to ask for. The tour asks only if the calculator gave that request up before an
  // answer came (the visitor edited the calculator at once and then came back up here).
  const unloadedDropped = unloaded?.state === "dropped";
  useEffect(() => {
    if (!reached.engine || !unloadedDropped || !run.unloadedJson) return;
    const json = run.unloadedJson;
    const timer = window.setTimeout(() => ask(json), DWELL_MS);
    return () => window.clearTimeout(timer);
  }, [reached.engine, unloadedDropped, run.unloadedJson, ask]);

  const colors = useMemo(() => angleSlots(run.angles), [run]);
  const thickness = Number(run.state.thickness_mm) > 0 ? Number(run.state.thickness_mm) : 1;
  const plies = useMemo(
    () => run.angles.map((angle) => ({ angle_deg: angle, thickness_mm: thickness, color: colors.get(angle) ?? "#5d8f52" })),
    [run, thickness, colors],
  );
  // The first ply to fail, as the engine names it (plies are numbered from 1, bottom first; the view counts from 0).
  const failure = loaded?.state === "answer" ? loaded.result.first_ply_failure : null;
  const first = failure?.evaluated ? failure.criteria[0] : undefined;
  const agreed = Boolean(first && failure?.criteria.every((item) => item.ply === first.ply));
  const marked = view.mark && view.loaded && first ? first.ply - 1 : null;

  const option = run.option;
  if (!option) return null;
  const active = (index: number) => (!pinned || view.step === index ? "true" : undefined);
  const loadText = `${TOUR_LOAD.name} = ${Number(TOUR_LOAD.value) / 1000} kN/m`;
  const steps: { label: string; title: string; text: string; card: ReactNode }[] = [
    {
      label: "01 / MATERIAL",
      title: "Start from a cited material.",
      text: `${option.label.split(" · ")[0]} comes from the materials library. Its elastic constants, density and fiber volume fraction are the record's values, each with its source.`,
      card: <MaterialCard option={option} picked={view.picked} constants={view.constants} />,
    },
    {
      label: "02 / LAYUP",
      title: "Type the stacking.",
      text: `${run.state.layup} is read bottom face first${run.script.text.trim().toLowerCase().endsWith("s") ? ", and the s mirrors it" : ""}: ${run.angles.length} plies, each ${run.state.thickness_mm} mm thick, the dataset's cured ply thickness.`,
      card: (
        <LayupCard text={run.script.text} chars={view.layupChars} thickness={view.thickness} option={option} angles={run.angles}
          laid={Math.round(view.laid)} colors={colors} hovered={hovered} onHover={setHovered} />
      ),
    },
    {
      label: "03 / ENGINE",
      title: "The engine answers.",
      text: "One request carries the stack to the engine. It returns what the laminate is and its A, B and D stiffness matrices, by classical laminate theory. The browser computes none of it.",
      card: <EngineCard stage={view.engine} apiBaseUrl={apiBaseUrl} entry={unloaded} request={run.unloaded} thickness_mm={run.state.thickness_mm} />,
    },
    {
      label: "04 / LOADS",
      title: "Add a load.",
      text: `With ${loadText} on the stack, the engine checks every ply and names the first to fail, with the factor on the load at which it does.`,
      card: <LoadsCard chars={view.loadChars} loaded={view.loaded} apiBaseUrl={apiBaseUrl} entry={loaded} />,
    },
    {
      label: "05 / YOUR TURN",
      title: "Now it is yours.",
      text: "The calculator below starts from this stack. Change the material, the layup or the loads, and the engine answers each edit.",
      card: <HandoverCard option={option} layup={run.state.layup} thickness_mm={run.state.thickness_mm} />,
    },
  ];
  return (
    <div className="demo-tour" id="tour" ref={root} role="region" aria-labelledby="tour-title" data-mode={pinned ? "pinned" : "static"}>
      {/* Without scripts nothing plays the steps: they then lie in the page's flow, as they do for reduced motion. */}
      <noscript><style>{".demo-tour{height:auto!important;background:#080808!important}.demo-tour>.demo-tour-stage{visibility:visible!important}"}</style></noscript>
      <div className="demo-tour-stage">
        <div className="demo-tour-head">
          <p className="demo-tour-label">THE CALCULATOR / STEP BY STEP</p>
          <div className="demo-tour-statement">
            <h2 id="tour-title">One calculation, start to finish.</h2>
            <p>The run the calculator below makes when the page opens, one step at a time.</p>
          </div>
        </div>
        <div className="demo-tour-scene" ref={sceneBox}>
          {viewWanted ? (
            <LaminateScene
              plies={plies} hovered={hovered} onHover={pinned ? ignoreHover : setHovered} reducedMotion={reducedMotion} decor={!pinned}
              laid={pinned ? view.laid : undefined} explode={pinned ? view.explode : 0} marked={marked}
              azimuth={pinned ? view.azimuth : null}
            />
          ) : <div className="demo-tour-view-rest" aria-hidden="true" />}
          <p className="demo-tour-note" role="status">
            {marked !== null && first
              ? `Marked: ply ${first.ply} (${signed(first.angle_deg)}°), the first ply to fail${agreed ? "" : " by the first criterion listed"}.`
              : ""}
          </p>
        </div>
        <ol className="demo-tour-steps">
          {steps.map((step, index) => (
            <li className="demo-tour-step" key={step.label} data-step={STEPS[index].id} data-active={active(index)}
              ref={STEPS[index].id === "loads" ? loadsStep : STEPS[index].id === "engine" ? engineStep : undefined}>
              <div className="demo-tour-text">
                <p className="demo-tour-label">{step.label}</p>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
              <div className="demo-tour-card">{step.card}</div>
            </li>
          ))}
        </ol>
        <ol className="demo-tour-rail" aria-hidden="true">
          {steps.map((step, index) => (
            <li key={step.label} data-active={pinned && view.step === index ? "true" : undefined}
              style={{ "--tour-fill": `var(--tour-rail-${index}, 0)` } as CSSProperties}>{step.label}</li>
          ))}
        </ol>
      </div>
    </div>
  );
}
