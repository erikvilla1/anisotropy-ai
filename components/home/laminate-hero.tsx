"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Layers3 } from "lucide-react";
import { LaminateScene } from "./scene";
import { AbdGrid, FailurePanel, PropertyRow, SpecsList, StackList } from "./laminate-panels";
import {
  buildAnalysisRequest, CalculationError, loadNames, requestAnalysis, type AnalysisResult, type FieldErrors, type LoadName,
} from "@/lib/laminate-api";
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
  const lastSent = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const sequence = useRef(0);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(media.matches);
    const onChange = () => setReducedMotion(media.matches);
    media.addEventListener("change", onChange);
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
  // The result is fresh when the engine answered these very inputs; otherwise it is the last answer, shown dimmed while the next one is on its way.
  const fresh = result !== null && requestJson !== null && JSON.stringify(result.inputs) === requestJson;
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
      const timeout = window.setTimeout(() => mine.abort("timeout"), TIMEOUT_MS);
      try {
        const answer = await requestAnalysis(apiBaseUrl, JSON.parse(requestJson), mine.signal);
        if (seq === sequence.current) setResult(answer);
      } catch (error) {
        if (mine.signal.reason === "superseded" || mine.signal.reason === "unmount" || seq !== sequence.current) return;
        setResult(null);
        lastSent.current = null;
        setMessage(mine.signal.aborted
          ? "The calculation timed out. Edit the layup to try again."
          : error instanceof CalculationError ? error.message : "Cannot reach the calculation service. The view still draws your stack.");
      } finally {
        window.clearTimeout(timeout);
        if (seq === sequence.current) setPending(false);
      }
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [apiBaseUrl, requestJson]);

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
  return (
    <section className="hero-laminate" id="laminate" aria-labelledby="laminate-title">
      <div className="hero-laminate-inner">
        <div className="hero-laminate-head">
          <p className="hero-laminate-label">LAMINATE CALCULATOR / LIVE</p>
          <div className="hero-laminate-statement">
            <h2 id="laminate-title">Your layup, calculated.</h2>
            <p>
              Pick a material from the library, type the stacking, and the engine returns what your laminate is and how
              stiff it is as you type. Add loads to see the first ply to fail.
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
              <span className="calc-hint">{option ? option.citation : "Choose a cited dataset."}</span>
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
            <p className="hero-stack-head" aria-hidden="true">Plies, top face first</p>
            <StackList angles={angles} thickness_mm={state.thickness_mm} colors={colors} hovered={hovered} onHover={setHovered} />
            <div className="hero-laminate-caption">
              <p className="hero-laminate-hover" role="status" data-testid="hover-label">
                {hoveredPly !== null
                  ? `Ply ${hovered! + 1} of ${angles.length} · ${hoveredPly > 0 ? `+${hoveredPly}` : hoveredPly}° · ${state.thickness_mm} mm`
                  : "Hover a ply to read its angle. Drag to turn the stack."}
              </p>
              <div className="hero-laminate-legend">
                <span><i style={{ background: "#d4d4d4" }} /> x, along the 0° fiber</span>
                <span><i style={{ background: "#acacac" }} /> y, across</span>
                <span><i style={{ background: "#efefef" }} /> z, through the thickness (not to scale)</span>
              </div>
            </div>
          </div>
          <div className={`hero-laminate-results ${fresh ? "" : "is-stale"}`} aria-busy={pending} aria-live="polite">
            <div className="hero-results-side">
              <div className="hero-results-head">
                <span className="eyebrow">THE ENGINE SAYS</span>
                <span className="calc-hint" title={result?.run_id ?? undefined}>
                  {!apiBaseUrl ? "Calculations are unavailable on this site." : pending ? "Calculating…" : result && fresh ? `Engine ${result.engine_version}${result.run_id ? ` · run ${result.run_id.slice(0, 8)}` : ""}` : inputError ? "" : "Waiting for the engine."}
                </span>
              </div>
              {inputError ? <p className="calc-alert" role="alert">{inputError}</p> : message ? <p className="calc-alert" role="alert">{message}</p> : null}
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
                  <p>{apiBaseUrl ? "The description, the matrices and the failure check appear here." : "Without a calculation service the view still draws your stack; the numbers need the engine."}</p>
                </div>
              ) : null}
            </div>
            {result && !inputError ? (
              <div className="hero-results-end">
                <Link className="button primary hero-check" href="/calculator" onClick={handOff}>
                  Want to check the math? <ArrowUpRight size={16} />
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
