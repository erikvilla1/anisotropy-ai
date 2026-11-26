"use client";

import { curveLayout } from "@/lib/followed-curve";
import { type Fields } from "@/lib/studio-api";
import { CRITERION_NAMES } from "@/lib/studio-answer";
import { FOLLOWED_CHECK, FOLLOWED_MESH } from "@/lib/studio-copy";
import { printed } from "@/lib/studio-colors";

/** What only a solve with nonlinear geometry has (ADR-0142): that the answer is one, the load against the largest displacement level by
 * level beside the straight line of a linear solve, and the same numbers as a table. Every number is the package's (`summary.followed`).
 * Null for a linear result. */
export function FollowedPanel({ fields }: { fields: Fields }) {
  const followed = fields.summary.followed;
  if (!followed) return null;
  const s = fields.summary, lab = fields.labels;
  const layout = curveLayout(followed, printed);
  const governs = s.verdict?.earliest ?? s.earliest ?? null;
  const index = governs ? followed.index[governs] ?? null : null;
  const linear = followed.linear;
  const where = `node ${followed.curve.label.split(".").pop()}`;
  return (
    <div className="studio-panel studio-followed" data-testid="followed">
      <h3>Nonlinear geometry <span className="studio-badge">{followed.fractions.length} load levels</span></h3>
      <p data-testid="followed-line">
        The plate&rsquo;s shape was followed as the load rose. Largest displacement {printed(s.max_displacement.value)} {lab.length}; a linear solve of the same
        plate gives {printed(Math.abs(linear.largest))} {lab.length}
        {linear.change_percent !== null && linear.change ? `, so following the shape makes it ${printed(linear.change_percent)} % ${linear.change}` : ""}.
      </p>
      {layout ? (
        <figure className="studio-followed-figure">
          <svg viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" data-testid="followed-curve"
            aria-label={`Load against the displacement at ${where}: with nonlinear geometry ${printed(layout.points[layout.points.length - 1].value)} ${layout.unit} at the full load, linear ${printed(layout.points[layout.points.length - 1].linear)} ${layout.unit}`}>
            {layout.yTicks.map((t) => (
              <g key={t.label}>
                <line x1={layout.left} x2={layout.width - layout.right} y1={t.y} y2={t.y} className="studio-followed-grid" />
                <text x={layout.left - 6} y={t.y + 3.5} textAnchor="end" className="studio-followed-tick">{t.label}</text>
              </g>
            ))}
            {layout.xTicks.map((t) => (
              <text key={t.label} x={t.x} y={layout.height - layout.bottom + 15} textAnchor="middle" className="studio-followed-tick">{t.label}</text>
            ))}
            <text x={(layout.left + layout.width - layout.right) / 2} y={layout.height - 4} textAnchor="middle" className="studio-followed-axis">
              Displacement at {where} ({layout.unit})
            </text>
            <line x1={layout.linear.x1} y1={layout.linear.y1} x2={layout.linear.x2} y2={layout.linear.y2} className="studio-followed-linear" />
            <path d={layout.path} className="studio-followed-line" />
            {layout.points.map((p) => (
              <g key={p.percent} data-level={p.percent}>
                <circle cx={p.x} cy={p.y} r={3.5} className="studio-followed-dot" />
                <circle cx={p.x} cy={p.y} r={11} className="studio-followed-hit">
                  <title>{`${p.percent} % of the load: ${printed(p.value)} ${layout.unit}; linear ${printed(p.linear)} ${layout.unit}`}</title>
                </circle>
              </g>
            ))}
          </svg>
          <figcaption className="studio-followed-legend">
            <span><i className="studio-followed-key" aria-hidden="true" /> Nonlinear geometry</span>
            <span><i className="studio-followed-key studio-followed-key-linear" aria-hidden="true" /> Linear{layout.linear.leaves ? ` (reaches ${printed(Math.abs(linear.value))} ${layout.unit} at the full load)` : ""}</span>
            <span className="studio-muted">Vertical: share of the applied load</span>
          </figcaption>
        </figure>
      ) : null}
      <details className="studio-details" data-testid="followed-levels">
        <summary><h4>Every load level</h4></summary>
        <div className="studio-table-scroll">
          <table className="studio-table studio-table-num studio-table-sticky" data-testid="followed-table">
            <thead>
              <tr><th scope="col">Load</th><th scope="col">Displacement ({followed.curve.unit})</th><th scope="col">Linear ({followed.curve.unit})</th>
                <th scope="col">Reaction ({lab.force})</th>{index ? <th scope="col">Failure index, {CRITERION_NAMES[governs ?? ""] ?? governs}</th> : null}</tr>
            </thead>
            <tbody>
              {followed.fractions.map((f, i) => (
                <tr key={f} data-reached={index && index[i] >= 1 ? true : undefined}>
                  <th scope="row">{Math.round(1000 * f) / 10} %</th><td>{printed(Math.abs(followed.curve.values[i]))}</td><td>{printed(Math.abs(followed.curve.linear[i]))}</td>
                  <td>{printed(Math.abs(followed.reaction[i]))}</td>{index ? <td>{printed(index[i])}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="studio-muted" data-testid="followed-note">
        The answer does not scale with the load: doubling the load does not double a stress, and a load at first-ply failure is given only when a ply reaches
        its limit on the way. A pressure follows the surface as it bends; a force keeps its direction. {FOLLOWED_CHECK.replace(/^Nonlinear geometry: o/, "O")}
      </p>
      <p className="studio-muted" data-testid="followed-mesh">{FOLLOWED_MESH}</p>
    </div>
  );
}
