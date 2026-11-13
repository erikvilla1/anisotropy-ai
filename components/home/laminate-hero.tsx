"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, Layers3 } from "lucide-react";
import { LaminateScene } from "./scene";
import { AbdGrid, FailurePanel, PropertyRow, SpecsList, StackList, summaryLine, trim } from "./laminate-panels";
import { useEngineAnswers } from "./engine-answers";
import {
  buildAnalysisRequest, CalculationError, loadNames, requestAnalysis, shownCitation, type AnalysisResult, type FieldErrors, type LoadName,
} from "@/lib/laminate-api";
import { ANALYSIS_UNAVAILABLE } from "@/lib/studio-copy";
import { calculatorHandoffKey, defaultHeroState, heroForm, loadsEntered, zeroLoads, type HeroState } from "@/lib/home-calculator";
import { expandLayup } from "@/lib/layup";
import { findLibraryOption, libraryOptions } from "@/lib/material-library-options";
import { angleSlots } from "@/lib/studio-colors";

const DEBOUNCE_MS = 450;
const TIMEOUT_MS = 20_000;

function firstError(errors: FieldErrors): string {
  const [key, text] = Object.entries(errors)[0] ?? ["", ""];
  if (key.startsWith("plies.")) return `Ply thickness: ${text}`;
  if (key.startsWith("loads.")) return `${key.slice(6)}: ${text}`;
  return text;
}

/** The laminate calculator on the home page (audit of 2026-10-31, item 4): a 3D view of the stack that updates as the user
 * types, the library material's properties, the stacking, the engine's description of the stack, the A, B and D matrices,
 * and first-ply failure once loads are given. The browser draws the typed stack and computes nothing else: every number
 * comes from `POST /v1/laminates/response` (ADR-0001, ADR-0059), one request per settled edit, recorded as the actor
 * `calculator` (ADR-0026). */
export function LaminateHero({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [state, setState] = useState<HeroState>(defaultHeroState);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [hovered, setHovered] = useState<number | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  // A touch screen cannot hover or drag the view (components/home/laminate-scene.tsx), so the caption says what it can do.
  const [coarse, setCoarse] = useState(false);
  // Bumped by Retry, to send the same request again; Retry shows only for a failure that sending it again may change.
  const [attempt, setAttempt] = useState(0);
  const [retryable, setRetryable] = useState(false);
  const lastSent = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  // The page's shared answers (components/home/engine-answers.tsx): the tour above shows the answer asked for here.
  const shared = useEngineAnswers();

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener("change", onChange);
    setCoarse(window.matchMedia("(pointer: coarse)").matches);
    return () => media.removeEventListener("change", onChange);
  }, []);
  useEffect(() => () => controller.current?.abort("unmount"), []);

  const parsed = useMemo(() => expandLayup(state.layup), [state.layup]);
  const angles = useMemo(() => parsed.layup?.angles ?? [], [parsed]);
  const option = findLibraryOption(state.library);
  const form = useMemo(() => (parsed.layup ? heroForm(state, parsed.layup.angles) : null), [state, parsed]);
  const built = useMemo(() => (form ? buildAnalysisRequest(form) : null), [form]);
  const requestJson = built?.request ? JSON.stringify(built.request) : null;
  const inputError = parsed.error ?? (built?.errors ? firstError(built.errors) : null);
  const colors = useMemo(() => angleSlots(angles), [angles]);
  const thickness = Number(state.thickness_mm) > 0 ? Number(state.thickness_mm) : 1;
  const plies = useMemo(() => angles.map((angle) => ({ angle_deg: angle, thickness_mm: thickness, color: colors.get(angle) ?? "#5d8f52" })), [angles, thickness, colors]);
  // The result is fresh when the engine answered these very inputs; otherwise it is the last answer, shown dimmed while the next one
  // is on its way. Only an older answer on the screen is dimmed: an error is never faded.
  const fresh = result !== null && requestJson !== null && JSON.stringify(result.inputs) === requestJson;
  const stale = result !== null && !fresh;
  const showLoads = loadsEntered(state.loads);

  useEffect(() => {
    if (!apiBaseUrl || !requestJson || requestJson === lastSent.current) return;
    const timer = window.setTimeout(async () => {
      if (requestJson === lastSent.current) return;
      controller.current?.abort("superseded");
      const mine = new AbortController();
      controller.current = mine;
      const seq = ++sequence.current;
      lastSent.current = requestJson;
      setPending(true);
      setMessage("");
      shared?.report(requestJson, { state: "pending" });
      const timeout = window.setTimeout(() => mine.abort("timeout"), TIMEOUT_MS);
      try {
        const answer = await requestAnalysis(apiBaseUrl, JSON.parse(requestJson), mine.signal);
        shared?.report(requestJson, { state: "answer", result: answer });
        if (seq === sequence.current) setResult(answer);
      } catch (error) {
        if (mine.signal.reason === "superseded" || mine.signal.reason === "unmount" || seq !== sequence.current) {
          shared?.report(requestJson, { state: "dropped" });
          return;
        }
        setResult(null);
        lastSent.current = null;
        const text = mine.signal.aborted
          ? "The calculation timed out."
          : error instanceof CalculationError ? error.message : ANALYSIS_UNAVAILABLE;
        setMessage(text);
        // A timeout or an outage (lib/laminate-api.ts says ANALYSIS_UNAVAILABLE for no answer and for the service's own failure)
        // may go another way; an answer that turns the request down stands until the inputs change.
        setRetryable(mine.signal.aborted || !(error instanceof CalculationError) || error.message === ANALYSIS_UNAVAILABLE);
        shared?.report(requestJson, { state: "failed", message: text });
      } finally {
        window.clearTimeout(timeout);
        if (seq === sequence.current) setPending(false);
      }
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [apiBaseUrl, requestJson, shared, attempt]);

  function update(next: Partial<HeroState>) {
    setState((current) => ({ ...current, ...next }));
  }
  function updateLoad(name: LoadName, value: string) {
    setState((current) => ({ ...current, loads: { ...(current.loads ?? zeroLoads()), [name]: value } }));
  }
  function handOff() {
    if (!form) return;
    try { sessionStorage.setItem(calculatorHandoffKey, JSON.stringify({ form })); } catch { /* storage blocked: the full page opens on its example */ }
  }

  const hoveredPly = hovered !== null && hovered < angles.length ? angles[hovered] : null;
  const plyThickness = Number(state.thickness_mm) > 0 ? trim(Number(state.thickness_mm)) : state.thickness_mm;
  // The results' state in a few words; nothing while an input or the request has failed, which the alert says.
  const head = !apiBaseUrl ? "Calculations are unavailable on this site."
    : pending ? "Calculating…"
    : inputError || message ? ""
    : result && fresh ? `Up to date: ${result.summary ? summaryLine(result.summary) : "the stack below"}`
    : "Results appear as you type.";
  return (
    <section className="hero-laminate" id="laminate" aria-labelledby="laminate-title">
      <div className="hero-laminate-inner">
        <div className="hero-laminate-head">
          <p className="hero-laminate-label">LAMINATE CALCULATOR / LIVE</p>
          <div className="hero-laminate-statement">
            <h2 id="laminate-title">Your layup, calculated.</h2>
            <p>
              Pick a material, type the layup and see the laminate&apos;s stiffness as you type. Add loads to find the first ply
              to fail.
            </p>
          </div>
        </div>
        <div className="hero-laminate-grid">
          <div className="hero-laminate-view">
            <LaminateScene plies={plies} hovered={hovered} onHover={setHovered} reducedMotion={reducedMotion} />
          </div>
          <form className="hero-laminate-inputs" onSubmit={(event) => event.preventDefault()} aria-label="Laminate inputs">
            <div className="hero-field">
              <label htmlFor="hero-material">Material, from the library</label>
              <select id="hero-material" value={state.library} onChange={(event) => {
                const next = findLibraryOption(event.target.value);
                update({ library: event.target.value, thickness_mm: next?.thickness_mm ?? state.thickness_mm });
              }}>
                {libraryOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
              <span className="calc-hint">{option ? shownCitation(option.citation) : "Choose a cited dataset."}</span>
            </div>
            <PropertyRow option={option} provenance={fresh ? result?.material_provenance : undefined} />
            <div className="hero-field-row">
              <div className="hero-field">
                <label htmlFor="hero-layup">Layup</label>
                <input id="hero-layup" type="text" value={state.layup} spellCheck={false} autoComplete="off"
                  onChange={(event) => update({ layup: event.target.value })} aria-invalid={Boolean(parsed.error)} aria-describedby="hero-layup-hint" />
                <span id="hero-layup-hint" className={parsed.error ? "calc-field-error" : "calc-hint"}>
                  {parsed.error ?? "Bottom face first; s mirrors the stack; [±45]2 repeats."}
                </span>
              </div>
              <div className="hero-field">
                <label htmlFor="hero-thickness">Ply thickness (mm)</label>
                <input id="hero-thickness" type="text" inputMode="decimal" value={state.thickness_mm}
                  onChange={(event) => update({ thickness_mm: event.target.value })} aria-invalid={Boolean(built?.errors && Object.keys(built.errors).some((k) => k.startsWith("plies.")))} />
                <span className="calc-hint">{option?.thickness_mm ? "The dataset's cured ply thickness." : "The dataset states no ply thickness."}</span>
              </div>
            </div>
            <details className="hero-loads" open={state.loads !== null} onToggle={(event) => {
              const open = (event.target as HTMLDetailsElement).open;
              if (open && state.loads === null) update({ loads: zeroLoads() });
              if (!open && state.loads !== null) update({ loads: null });
            }}>
              <summary>Add loads per unit width</summary>
              <div className="hero-loads-grid">
                {loadNames.map((name) => (
                  <div className="hero-field" key={name}>
                    <label htmlFor={`hero-load-${name}`}>{name} ({name.startsWith("N") ? "N/m" : "N·m/m"})</label>
                    <input id={`hero-load-${name}`} type="text" inputMode="decimal" value={state.loads?.[name] ?? "0"}
                      onChange={(event) => updateLoad(name, event.target.value)} />
                  </div>
                ))}
              </div>
              <span className="calc-hint">First-ply failure is evaluated only when a load is given; every load scales together.</span>
            </details>
          </form>
          <div className="hero-laminate-stack">
            <p className="hero-stack-head" aria-hidden="true">Plies, top face first <span>(mm)</span></p>
            <StackList angles={angles} thickness_mm={state.thickness_mm} colors={colors} hovered={hovered} onHover={setHovered} focusable />
            <div className="hero-laminate-caption">
              <p className="hero-laminate-hover" role="status" data-testid="hover-label">
                {hoveredPly !== null
                  ? `Ply ${hovered! + 1} of ${angles.length} · ${hoveredPly > 0 ? `+${hoveredPly}` : hoveredPly}° · ${plyThickness} mm`
                  : coarse ? "The list gives each ply's angle." : "Drag to turn the stack; each ply's angle is listed."}
              </p>
              <div className="hero-laminate-legend">
                <span><i style={{ background: "#d4d4d4" }} /> x, along the 0° fiber</span>
                <span><i style={{ background: "#acacac" }} /> y, across</span>
                <span><i style={{ background: "#efefef" }} /> z, through the thickness (not to scale)</span>
              </div>
            </div>
          </div>
          <div className={`hero-laminate-results ${stale ? "is-stale" : ""}`} aria-busy={pending}>
            <div className="hero-results-side">
              <div className="hero-results-head">
                <span className="eyebrow">RESULTS</span>
                {/* The version and the run that answered stay in data attributes, for support, not on the screen. */}
                <span className="calc-hint" role="status" data-engine-version={result && fresh ? result.engine_version : undefined}
                  data-run-id={result && fresh ? result.run_id ?? undefined : undefined}>
                  {head}
                </span>
              </div>
              {inputError ? <p className="calc-alert" role="alert">{inputError}</p> : message ? (
                <div className="hero-retry">
                  <p className="calc-alert" role="alert">{message}</p>
                  {retryable ? <button type="button" className="calc-text-button" onClick={() => setAttempt((n) => n + 1)}>Retry</button> : null}
                </div>
              ) : null}
              {result && !inputError && result.summary ? <SpecsList summary={result.summary} /> : null}
            </div>
            <div className="hero-results-main">
              {result && !inputError ? (
                <>
                  {showLoads && result.first_ply_failure ? <FailurePanel failure={result.first_ply_failure} /> : null}
                  <AbdGrid result={result} />
                </>
              ) : !inputError ? (
                <div className="calc-empty hero-empty">
                  <Layers3 size={30} strokeWidth={1} />
                  <p>{apiBaseUrl ? "The description, the matrices and the failure check appear here." : "Without a calculation service the view still draws your stack; the numbers need the service."}</p>
                </div>
              ) : null}
            </div>
            {result && !inputError ? (
              <div className="hero-results-end">
                <Link className="button primary hero-check" href="/calculator" onClick={handOff}>
                  Want to check the math? <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <p className="calc-scope">
                  Flat laminate, one material, linear elastic classical laminate theory. The full page shows the strains, the curvatures and every cited value.
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
