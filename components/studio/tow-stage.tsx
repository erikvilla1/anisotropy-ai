"use client";

import type { TowResult, TowStats } from "@/lib/studio-api";
import { printed } from "@/lib/studio-colors";
import { useProject } from "./project-context";

/** The strand as typed: the free length between the tabs (or the grips of an untabbed specimen) drawn as the one dimension, the tabs or the
 * jaws at the ends, the extensometer's two knife edges at the centre and the pull at both ends. Drawn from the typed rows, not to scale
 * across the strand; it computes nothing. */
export function StrandSketch({ gauge, tabs }: { gauge: string; tabs: string }) {
  const untabbed = !tabs || tabs === "none";
  const where = untabbed ? "between the grips" : "between the tabs";
  const label = gauge.trim() ? `${gauge.trim()} mm ${where}` : `gauge length ${where}`;
  return (
    <svg className="ws-strand" viewBox="0 0 640 150" role="img" aria-label={`The tow: ${label}${untabbed ? ", gripped directly" : `, ${tabs} tabs`}`} data-testid="strand-sketch">
      <defs>
        <marker id="ws-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" className="ws-strand-arrowhead" />
        </marker>
      </defs>
      <line x1="40" y1="70" x2="600" y2="70" className="ws-strand-line" />
      {[[52, 128], [512, 588]].map(([a, b]) => (
        <g key={a}>
          <rect x={a} y={untabbed ? 52 : 58} width={b - a} height={untabbed ? 36 : 24} rx="3" className={untabbed ? "ws-strand-jaw" : "ws-strand-tab"} />
        </g>
      ))}
      <line x1="300" y1="56" x2="300" y2="84" className="ws-strand-knife" />
      <line x1="340" y1="56" x2="340" y2="84" className="ws-strand-knife" />
      <text x="320" y="48" textAnchor="middle" className="ws-strand-note">extensometer</text>
      <line x1="40" y1="70" x2="8" y2="70" className="ws-strand-pull" markerEnd="url(#ws-arrow)" />
      <line x1="600" y1="70" x2="632" y2="70" className="ws-strand-pull" markerEnd="url(#ws-arrow)" />
      <line x1="128" y1="112" x2="512" y2="112" className="ws-strand-dim" markerStart="url(#ws-arrow)" markerEnd="url(#ws-arrow)" />
      <line x1="128" y1="96" x2="128" y2="120" className="ws-strand-ext" />
      <line x1="512" y1="96" x2="512" y2="120" className="ws-strand-ext" />
      <text x="320" y="136" textAnchor="middle" className="ws-strand-label">{label}</text>
      <text x="90" y="44" textAnchor="middle" className="ws-strand-note">{untabbed ? "grip" : `${tabs} tab`}</text>
    </svg>
  );
}

function Stat({ title, unit, stats, testid }: { title: string; unit: string; stats: TowStats | null; testid: string }) {
  return (
    <div className="ws-tow-stat" data-testid={testid}>
      <span className="ws-tow-stat-title">{title}</span>
      {stats ? (
        <>
          <strong>{printed(stats.mean)} {unit}</strong>
          <span className="studio-muted">s<sub>n−1</sub> {printed(stats.sd)} {unit}, CV {printed(stats.cv)} %, n = {stats.n}</span>
        </>
      ) : <span className="studio-muted">fewer than two valid specimens: no statistics</span>}
    </div>
  );
}

/** The record's result as the engine computed it and the fea package wrote it, in the standard's report units (ADR-0073): the fibre, each
 * specimen, the statistics, the planning loads and the report items the record gives. The page prints the numbers; it computes none. */
export function TowResults({ result }: { result: TowResult }) {
  const u = result.units;
  const f = result.fibre_properties;
  const s = result.strains;
  const p = result.planning;
  const planned = [p.preload_force, p.force_lower, p.force_upper, p.failure_force].some((v) => v !== null);
  return (
    <div className="studio-panel ws-tow-results" data-testid="tow-results">
      <h3>{result.fibre}{result.lot ? `, ${result.lot}` : ""} <span className="studio-badge">{result.designation ? `reduced by ${result.designation}` : "reduced by D4018's equations, no standard named"}</span></h3>
      <div className="ws-tow-stats">
        <Stat title="Tensile strength (Eq 4)" unit={u.strength} stats={result.strength} testid="tow-strength" />
        <Stat title={`Chord modulus, ${printed(s.chord[0])} to ${printed(s.chord[1])} microstrain (Eq 5)`} unit={u.modulus} stats={result.modulus} testid="tow-modulus" />
      </div>
      <p className="studio-muted">{result.counts.valid} valid of {result.counts.specimens} specimens; {result.counts.strength} give a strength and {result.counts.modulus} a modulus. A rejected specimen is listed with its values, never counted (§11.3.12).</p>

      <h4>The fibre</h4>
      <table className="studio-table" data-testid="tow-fibre">
        <tbody>
          <tr><th>Mass per unit length</th><td>{printed(f.mul)} {u.mul} ({f.mul_from}){f.bundles > 1 ? `; ${f.bundles} bundles: ${printed(f.specimen_mul)} ${u.mul} per specimen` : ""}</td></tr>
          <tr><th>Fibre density</th><td>{printed(f.density)} {u.density} ({f.density_from})</td></tr>
          <tr><th>Fibre area, MUL / density</th><td>{printed(f.area)} {u.area}</td></tr>
          <tr><th>Resin content</th><td>{f.resin_content === null ? "not given" : `${printed(f.resin_content)} % by weight (${f.resin_content_from})`}</td></tr>
          <tr><th>Typical strain at failure</th><td>{printed(s.failure)} microstrain: chord {printed(s.chord_table[0])} to {printed(s.chord_table[1])} (Table 2), preload at most {printed(s.preload)} (Table 1)</td></tr>
          {s.chord_from === "given" ? <tr><th>Chord strains used</th><td>{printed(s.chord[0])} to {printed(s.chord[1])} microstrain, as given</td></tr> : null}
        </tbody>
      </table>

      <h4>Each specimen</h4>
      <div className="ws-table-scroll">
        <table className="studio-table ws-tow-specimens" data-testid="tow-specimen-table">
          <thead>
            <tr><th>Specimen</th><th>P ({u.force})</th><th>Strength ({u.strength})</th><th>P<sub>l</sub> ({u.force})</th><th>P<sub>u</sub> ({u.force})</th><th>Modulus ({u.modulus})</th><th>Failure</th><th>Status</th></tr>
          </thead>
          <tbody>
            {result.specimens.map((sp) => (
              <tr key={sp.id} data-status={sp.status}>
                <td>{sp.id}</td><td>{printed(sp.max_force)}</td><td>{printed(sp.strength)}</td><td>{printed(sp.force_lower)}</td><td>{printed(sp.force_upper)}</td>
                <td>{printed(sp.modulus)}</td><td>{sp.failure_code ? <span title={sp.failure_words ?? ""}>{sp.failure_code}</span> : "–"}</td>
                <td>{sp.status}{sp.note ? `: ${sp.note}` : ""}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><th>Mean</th><td></td><td>{printed(result.strength?.mean)}</td><td></td><td></td><td>{printed(result.modulus?.mean)}</td><td></td><td></td></tr>
            <tr><th>s<sub>n−1</sub></th><td></td><td>{printed(result.strength?.sd)}</td><td></td><td></td><td>{printed(result.modulus?.sd)}</td><td></td><td></td></tr>
            <tr><th>CV (%)</th><td></td><td>{printed(result.strength?.cv)}</td><td></td><td></td><td>{printed(result.modulus?.cv)}</td><td></td><td></td></tr>
          </tfoot>
        </table>
      </div>

      <h4>Planning loads</h4>
      {planned ? (
        <table className="studio-table" data-testid="tow-planning">
          <tbody>
            <tr><th>Largest preload ({printed(s.preload)} microstrain)</th><td>{printed(p.preload_force)} {u.force}</td></tr>
            <tr><th>At the chord&apos;s lower strain</th><td>{printed(p.force_lower)} {u.force}</td></tr>
            <tr><th>At the chord&apos;s upper strain</th><td>{printed(p.force_upper)} {u.force}</td></tr>
            <tr><th>At the datasheet strength</th><td>{printed(p.failure_force)} {u.force}</td></tr>
          </tbody>
        </table>
      ) : null}
      <p className="studio-muted">{planned ? `From the ${p.from.join(" and ")} and the fibre's area, linear to failure (§11.3.6).` : "Give the datasheet modulus and strength under The tensile test for the preload and the forces to expect."}</p>

      {result.conformance ? <p className={`ws-standard-summary ${result.conformance.deviations || result.conformance.advisories ? "ws-standard-warn" : ""}`} data-testid="tow-conformance">{result.conformance.words}</p> : null}
      <h4>What the report holds (§13.1.3)</h4>
      <ul className="ws-tow-report" data-testid="tow-report">
        {result.report.map((item) => <li key={item.clause} data-shown={item.shown ? "yes" : "no"}><span aria-hidden="true">{item.shown ? "✓" : "○"}</span> {item.clause} {item.item}{item.shown ? "" : ": not in this record"}</li>)}
      </ul>
      <p className="studio-hint">{result.note}</p>
    </div>
  );
}

/** The centre of the workspace for a fibre tow record (ADR-0073): the strand as typed, then the result once calculated. */
export function TowStage() {
  const { form, specimens, towAnswer } = useProject();
  const result = towAnswer?.result ?? null;
  return (
    <section className="studio-output" data-testid="tow-stage">
      <div className="studio-panel" data-testid="tow-sketch">
        <h3>The tow <span className="studio-badge">sketch of the typed rows</span></h3>
        <StrandSketch gauge={form.tow_gauge_length ?? ""} tabs={form.tow_tabs ?? ""} />
        <p className="studio-muted">A resin-impregnated, consolidated fibre tow pulled to failure, {specimens.length} specimen{specimens.length === 1 ? "" : "s"} listed. ASTM D4018 asks
          for 150 mm ± 5 mm between the tabs or grips; drawn from the rows as typed, not to scale across the strand.</p>
      </div>
      {result ? <TowResults result={result} /> : (
        <div className="studio-empty" data-testid="tow-empty">
          <h3>No result yet</h3>
          <p>Give the fibre&apos;s mass per unit length and density, the test&apos;s gauge length and the typical strain at failure, list the specimens with their
            forces, and select Calculate. Each specimen&apos;s strength and modulus, their mean, deviation and coefficient of variation, and the planning loads appear here.</p>
        </div>
      )}
    </section>
  );
}
