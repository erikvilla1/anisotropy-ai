"use client";

import {
  CRITERION_WORDS, inSentence, LIMITS, modelWords, PART_WORDS, shown, sliceWords, unitText, type RegionKind, type RepairReport, type SliceReport,
} from "@/lib/repair";

/** The tables of a repair's answers (ADR-0135), for the repair's page and for its report. Every number is the engine's or the
 * solver's, printed to four figures; the tables pick and label. */

const KINDS: readonly RegionKind[] = ["parent", "patch", "cover", "adhesive"];
/** A value that is zero but for the arithmetic's last digits, beside the largest of its kind, prints as 0: "−1.1 × 10⁻¹⁹" in a column
 * of tens says nothing an engineer can use. */
const settled = (value: number, largest: number): number => (Math.abs(value) < 1e-9 * Math.abs(largest) ? 0 : value);
const largestOf = (values: readonly number[]): number => values.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
const BOND_WORDS: Record<string, string> = {
  ledges: "On the ledges", cut_faces: "Up the cut faces", floor: "On the floor", cover: "Under the cover plies", top_face: "On the laminate's top face",
};

/** What the repair is, as the engine measured it: its sizes, each kind of part's area in the slice and volume in the panel, and the
 * bondline's lengths in the half slice. */
export function SizesTable({ report }: { report: RepairReport }) {
  const u = report.units, s = report.sizes, length = unitText(u.length);
  const rows: [string, string][] = report.kind === "external" ? [
    ["Laminate thickness", `${shown(s.thickness)} ${length}`], ["Patch thickness", `${shown(s.patch_thickness)} ${length}`],
    [report.patch_shape === "strip" ? "Patch length" : "Patch diameter", `${shown(s.patch_diameter)} ${length}`],
    ["Steps reach, from the middle", `${s.cut_radii.map((r) => shown(r)).join(", ")} ${length}`],
  ] : [
    ["Laminate thickness", `${shown(s.thickness)} ${length}`], ["Depth of the cut", `${shown(s.depth)} ${length}${s.through ? ", through every ply" : ""}`],
    ["Plies removed, plies left", `${s.plies_removed}, ${s.plies_left}`], ["Cuts at radius", `${s.cut_radii.map((r) => shown(r)).join(", ")} ${length}`],
    ["Patch diameter", `${shown(s.patch_diameter)} ${length}`], ["Repair diameter, with the cover plies", `${shown(s.repair_diameter)} ${length}`],
  ];
  return (
    <div className="repair-tables">
      <table className="studio-table" data-testid="repair-sizes">
        <tbody>{rows.map(([name, value]) => <tr key={name}><th scope="row">{name}</th><td>{value}</td></tr>)}</tbody>
      </table>
      <table className="studio-table" data-testid="repair-parts">
        <thead><tr><th>Part</th><th>Area in the half slice, {unitText(u.area)}</th><th>Volume in the panel, {unitText(u.volume)}</th></tr></thead>
        <tbody>{KINDS.filter((kind) => report.areas[kind] > 0).map((kind) => (
          <tr key={kind}><th scope="row">{PART_WORDS[kind]}</th><td>{shown(report.areas[kind])}</td><td>{shown(report.volumes[kind], 5)}</td></tr>
        ))}</tbody>
      </table>
      <table className="studio-table" data-testid="repair-bond-lengths">
        <thead><tr><th>Bondline in the half slice</th><th>Length, {length}</th></tr></thead>
        <tbody>{Object.entries(report.bond_lengths).filter(([, value]) => value > 0).map(([name, value]) => (
          <tr key={name}><th scope="row">{BOND_WORDS[name] ?? name}</th><td>{shown(value)}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}

/** The stepped lap the repair makes, worked by hand (ADR-0130): each step from the repair's edge inward, with the patch's force at its
 * two ends and the adhesive's shear stress there once a load is stated. */
export function LapTable({ report }: { report: RepairReport }) {
  const u = report.units, lap = report.lap, answer = lap.answer;
  const length = unitText(u.length), modulus = unitText(u.modulus), force = unitText(u.force), stress = unitText(u.stress);
  const topForce = answer ? largestOf(answer.boundary_forces) : 0, topShear = answer ? largestOf(answer.shear_at_ends.flat()) : 0;
  return (
    <div className="repair-scroll">
      <table className="studio-table" data-testid="repair-lap">
        <thead>
          <tr>
            <th rowSpan={2}>Step, from the repair&apos;s edge inward</th><th rowSpan={2}>Length, {length}</th>
            <th colSpan={2}>Patch over it</th><th colSpan={2}>Laminate under it</th>
            {answer ? <><th colSpan={2}>Force in the patch, {force}</th><th colSpan={2}>Shear in the adhesive, {stress}</th><th rowSpan={2}>λL</th></> : null}
          </tr>
          <tr>
            <th>t, {length}</th><th>E, {modulus}</th><th>t, {length}</th><th>E, {modulus}</th>
            {answer ? <><th>outer end</th><th>inner end</th><th>outer end</th><th>inner end</th></> : null}
          </tr>
        </thead>
        <tbody>{lap.steps.map((step, k) => (
          <tr key={step.name} data-peak={answer && answer.peak_shear.step === k + 1 ? "true" : undefined}>
            <th scope="row">{step.name}</th><td>{shown(step.length)}</td>
            <td>{shown(step.patch_thickness)}</td><td>{shown(step.patch_modulus, 5)}</td><td>{shown(step.laminate_thickness)}</td><td>{shown(step.laminate_modulus, 5)}</td>
            {answer ? <>
              <td>{shown(settled(answer.boundary_forces[k], topForce))}</td><td>{shown(settled(answer.boundary_forces[k + 1], topForce))}</td>
              <td>{shown(settled(answer.shear_at_ends[k][0], topShear))}</td><td>{shown(settled(answer.shear_at_ends[k][1], topShear))}</td><td>{shown(answer.lambda_length[k], 3)}</td>
            </> : null}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

/** The solved slice (ADR-0132) in words and tables: the model and its checks, the bondline's two peaks beside the hand calculation,
 * the patch's force at every boundary of the lap by the slice and by hand, and the plies nearest a strength. */
export function SliceResults({ slice, stale }: { slice: SliceReport; stale: boolean }) {
  const u = slice.units, force = unitText(u.force), stress = unitText(u.stress), length = unitText(u.length);
  const words = sliceWords(slice);
  const checked = slice.plies.filter((p) => p.strength_ratio !== null).sort((a, b) => (a.strength_ratio as number) - (b.strength_ratio as number)).slice(0, 6);
  return (
    <div className="repair-slice-results" data-testid="repair-slice-results" data-stale={stale ? "true" : "false"}>
      {stale ? <p className="studio-alert" role="status" data-testid="repair-slice-stale">This is the slice of the repair as it was when it was solved. The repair has changed since: solve the slice again.</p> : null}
      <p className="studio-muted" data-testid="repair-slice-model">{modelWords(slice)}{slice.model.cut_faces === "bonded" ? " The adhesive on the cut faces is bonded." : ""}</p>
      <ul className="repair-lines" data-testid="repair-slice-lines">
        <li>{words.shear}</li><li>{words.peel}</li><li>{words.limit}</li><li>{words.ply}</li>
        {words.first ? <li><strong>{words.first}</strong></li> : null}
      </ul>
      <p className="studio-hint">Each largest stress is the mean over a square of adhesive {shown(slice.bond.mean_over, 3)} {length} on a side, the bondline&apos;s thickness.</p>
      <div className="repair-scroll">
        <table className="studio-table" data-testid="repair-boundaries">
          <thead><tr><th>Boundary of the lap</th><th>From the middle, {length}</th><th>Patch, {force}</th><th>Laminate, {force}</th><th>Adhesive, {force}</th><th>Patch by hand, {force}</th></tr></thead>
          <tbody>{slice.boundaries.map((b) => (
            <tr key={b.name}><th scope="row">Inner end of {inSentence(b.name)}</th><td>{shown(b.r)}</td><td>{shown(b.patch)}</td><td>{shown(b.laminate)}</td><td>{shown(b.adhesive)}</td><td>{shown(b.hand_patch)}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {slice.bond.cut_faces.length ? (
        <table className="studio-table" data-testid="repair-cut-faces">
          <thead><tr><th>Cut face, bonded</th><th>Stress across it, {stress}</th><th>Shear along it, {stress}</th></tr></thead>
          <tbody>{slice.bond.cut_faces.map((face) => <tr key={face.name}><th scope="row">{face.name}</th><td>{shown(face.normal)}</td><td>{shown(face.shear)}</td></tr>)}</tbody>
        </table>
      ) : null}
      {checked.length ? (
        <div className="repair-scroll">
          <table className="studio-table" data-testid="repair-plies">
            <thead><tr><th>Ply, by {CRITERION_WORDS[slice.criterion] ?? slice.criterion}</th><th>Strength ratio</th><th>Mode</th><th>Where, {length} from the middle</th><th>σ₁, σ₂, τ₁₂ there, {stress}</th></tr></thead>
            <tbody>{checked.map((p) => (
              <tr key={p.name}><th scope="row">{p.name.replace("(-", "(−")}</th><td>{shown(p.strength_ratio, 4)}</td><td>{p.mode}</td><td>{shown(p.r)}</td>
                <td>{(p.stress ?? []).map((v, _, all) => shown(settled(v, largestOf(all)), 4)).join(", ")}</td></tr>
            ))}</tbody>
          </table>
        </div>
      ) : null}
      {checked.length ? <p className="studio-hint">A ply&apos;s strength ratio is the factor on the load of {shown(slice.load)} {force} at which that ply reaches a strength, at its weakest station, with its stresses the mean through its thickness. The six lowest are listed.</p> : null}
    </div>
  );
}

/** What the analysis is not: the same list on the page and in the report. */
export function Limits() {
  return <ul className="repair-lines repair-limits" data-testid="repair-limits">{LIMITS.map((line) => <li key={line}>{line}</li>)}</ul>;
}
