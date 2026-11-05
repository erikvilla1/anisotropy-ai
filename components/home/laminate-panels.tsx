"use client";

import type { ReactNode } from "react";
import { Matrix } from "@/components/abd-matrix";
import type { AnalysisResult, FirstPlyFailure, LaminateSummary, MaterialProvenance } from "@/lib/laminate-api";
import type { LibraryOption } from "@/lib/material-library-options";

/** Display conversions only: the engine's SI values shown in the units engineers read (ADR-0002). */
const gpa = (pa: number) => trim(pa / 1e9);
const mm = (m: number) => trim(m * 1e3);
const trim = (value: number, digits = 4) => String(Number(value.toPrecision(digits)));

/** The material's recorded properties: the engine's cited values once a response has arrived, the record's display values
 * before that, "not provided" where the record states none. */
export function PropertyRow({ option, provenance }: { option: LibraryOption | undefined; provenance: MaterialProvenance | null | undefined }) {
  const role = (name: string) => provenance?.values.find((v) => v.role === name);
  const alpha = (name: "alpha1" | "alpha2", fallback: string | null) => {
    const cited = role(name);
    return cited ? trim(cited.value * 1e6) : fallback;
  };
  const rows: { key: string; label: ReactNode; value: string | null; unit: string }[] = [
    { key: "E1", label: "E₁", value: provenance ? gpa(provenance.E1_pa) : option?.E1_GPa ?? null, unit: "GPa" },
    { key: "E2", label: "E₂", value: provenance ? gpa(provenance.E2_pa) : option?.E2_GPa ?? null, unit: "GPa" },
    { key: "G12", label: "G₁₂", value: provenance ? gpa(provenance.G12_pa) : option?.G12_GPa ?? null, unit: "GPa" },
    { key: "nu12", label: "ν₁₂", value: provenance ? trim(provenance.nu12) : option?.nu12 ?? null, unit: "" },
    { key: "alpha1", label: "α₁", value: alpha("alpha1", option?.alpha1_per_K ?? null), unit: "10⁻⁶/K" },
    { key: "alpha2", label: "α₂", value: alpha("alpha2", option?.alpha2_per_K ?? null), unit: "10⁻⁶/K" },
    { key: "rho", label: "ρ", value: provenance ? (provenance.density_kg_per_m3 == null ? null : trim(provenance.density_kg_per_m3)) : option?.density_kg_per_m3 ?? null, unit: "kg/m³" },
    { key: "Vf", label: <>V<sub>f</sub></>, value: provenance ? (provenance.fiber_volume_fraction == null ? null : trim(provenance.fiber_volume_fraction * 100, 3)) : option?.Vf_percent ?? null, unit: "%" },
  ];
  return (
    <dl className="hero-properties" aria-label="Material properties" data-testid="property-row">
      {rows.map((row) => (
        <div key={row.key}>
          <dt>{row.label}</dt>
          <dd>{row.value === null ? <span className="hero-not-provided">not provided</span> : <>{row.value}{row.unit ? <small> {row.unit}</small> : null}</>}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The plies as a list, top face first, each with its colour, angle and thickness; hovering a row lights the slab. */
export function StackList({ angles, thickness_mm, colors, hovered, onHover }: {
  angles: number[]; thickness_mm: string; colors: Map<number, string>; hovered: number | null; onHover: (index: number | null) => void;
}) {
  const rows = angles.map((angle, index) => ({ angle, index })).reverse();
  return (
    <ol className="hero-stack" aria-label="Stacking sequence, top face first" data-testid="stack-list">
      {rows.map(({ angle, index }) => (
        <li
          key={index}
          data-testid="stack-row"
          className={hovered === index ? "is-hovered" : ""}
          onMouseEnter={() => onHover(index)}
          onMouseLeave={() => onHover(null)}
        >
          <span className="hero-stack-swatch" style={{ background: colors.get(angle) }} aria-hidden="true" />
          <span className="hero-stack-index">{index + 1}</span>
          <span className="hero-stack-angle">{angle > 0 ? `+${angle}` : String(angle)}°</span>
          <span className="hero-stack-thickness">{thickness_mm} mm</span>
        </li>
      ))}
    </ol>
  );
}

const kindLabel: Record<LaminateSummary["kind"], string> = {
  unidirectional: "Unidirectional",
  "cross-ply": "Cross-ply",
  "angle-ply": "Angle-ply",
  "quasi-isotropic": "Quasi-isotropic",
  general: "General (anisotropic)",
};

/** What the stack is, as the engine says it (ADR-0059). */
export function SpecsList({ summary }: { summary: LaminateSummary }) {
  const couplings = [
    summary.coupling.extension_shear ? "extension–shear" : null,
    summary.coupling.extension_bending ? "extension–bending" : null,
    summary.coupling.bending_twisting ? "bending–twisting" : null,
  ].filter((c): c is string => c !== null);
  const items: { label: string; value: string; note?: string }[] = [
    { label: "Plies", value: String(summary.ply_count) },
    { label: "Total thickness", value: `${mm(summary.total_thickness_m)} mm` },
    { label: "Stacking", value: [summary.symmetric ? "symmetric" : summary.antisymmetric ? "antisymmetric" : "unsymmetric", summary.balanced ? "balanced" : "unbalanced"].join(", ") },
    { label: "Laminate type", value: kindLabel[summary.kind] },
    { label: "Coupling", value: couplings.length ? couplings.join(", ") : "none at the engine's tolerance" },
    summary.areal_mass_kg_per_m2 === null
      ? { label: "Areal mass", value: "not computed", note: summary.areal_mass_missing ?? undefined }
      : { label: "Areal mass", value: `${trim(summary.areal_mass_kg_per_m2, 4)} kg/m²` },
  ];
  return (
    <dl className="hero-specs" aria-label="Laminate description" data-testid="specs">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}{item.note ? <small>{item.note}</small> : null}</dd>
        </div>
      ))}
    </dl>
  );
}

const criterionLabel: Record<string, string> = { max_stress: "Maximum stress", max_strain: "Maximum strain", tsai_hill: "Tsai-Hill", tsai_wu: "Tsai-Wu" };

/** First-ply failure, shown only when loads were entered; the engine says what it computed and why not the rest. */
export function FailurePanel({ failure }: { failure: FirstPlyFailure }) {
  return (
    <div className="hero-failure" data-testid="failure-panel">
      <h3>First-ply failure <span>under your loads</span></h3>
      {failure.evaluated ? (
        <table>
          <thead><tr><th scope="col">Criterion</th><th scope="col">R</th><th scope="col">Ply</th><th scope="col">Face</th><th scope="col">Mode</th></tr></thead>
          <tbody>
            {failure.criteria.map((item) => (
              <tr key={item.criterion}>
                <th scope="row">{criterionLabel[item.criterion] ?? item.criterion}</th>
                <td>{item.strength_ratio === null ? "unbounded" : trim(item.strength_ratio, 3)}</td>
                <td>{item.ply} ({item.angle_deg > 0 ? `+${item.angle_deg}` : item.angle_deg}°)</td>
                <td>{item.face}</td>
                <td>{item.mode}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="hero-failure-reason">Not evaluated: {failure.reason}.</p>
      )}
      {failure.not_computed.length ? (
        <p className="hero-failure-note">
          Not computed: {failure.not_computed.map((item) => `${criterionLabel[item.criterion] ?? item.criterion} (${item.reason})`).join("; ")}.
        </p>
      ) : null}
      <p className="hero-failure-note">R is the factor on every load at which the first ply fails; every load scales together, nothing held fixed.</p>
    </div>
  );
}

/** The A, B and D matrices in the 2 × 2 arrangement of the ABD matrix. */
export function AbdGrid({ result }: { result: AnalysisResult }) {
  return (
    <div className="hero-abd" data-testid="abd-grid">
      <Matrix title="A" unit="N/m" meaning="Stretching stiffness" values={result.A_N_per_m} compact />
      <Matrix title="B" unit="N" meaning="Stretching–bending coupling" values={result.B_N} compact />
      <p className="hero-abd-note">
        The ABD matrix is <span>[A B; B D]</span>: B appears twice, once above and once mirrored here. Values in scientific notation, three figures; the full page prints six.
      </p>
      <Matrix title="D" unit="N·m" meaning="Bending stiffness" values={result.D_N_m} compact />
    </div>
  );
}
