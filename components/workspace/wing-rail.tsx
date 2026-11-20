"use client";

import { useEffect, useRef, useState } from "react";
import {
  AERO_FIELDS, AILERON_FIELDS, ENVELOPE_FIELDS, EXAMPLE_WING, GEOMETRY_FIELDS, GUST_FACTOR_FIELDS, GUST_SPEED_FIELDS, OWN_MATERIAL_FIELDS, OWN_MATERIAL_KEYS,
  feProgress, readNumber, readNumbers, shown, SPEED_FIELDS, unitLabel, unitsOf, unitText, valueAt, WING_CORES, WING_MATERIALS, wingFileName, wingToml,
  type WingDescription, type WingField, type WingShape, type WingValue,
} from "@/lib/wing";
import { shapeWing, StudioError } from "@/lib/studio-api";
import { useWing } from "./wing-context";
import { StepPanel } from "./panels/step-panel";

const CRITERIA = [
  { id: "max_stress", label: "Maximum stress" }, { id: "max_strain", label: "Maximum strain" },
  { id: "tsai_hill", label: "Tsai-Hill" }, { id: "tsai_wu", label: "Tsai-Wu" },
];

function idOf(path: string): string { return `wing-${path.replace(/\./g, "-")}`; }

function textOf(value: WingValue | undefined): string {
  if (value === undefined) return "";
  if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
  return String(value);
}

/** One value of the description: typed as text, written to the description as soon as it reads as a number (or a list of them);
 * emptied, an optional value leaves the description. The text stays as typed while it does not read, with a note under it. */
function WingNumber({ field }: { field: WingField }) {
  const { wing, revision, setValue } = useWing();
  const value = valueAt(wing, field.path);
  const [text, setText] = useState(textOf(value));
  const [bad, setBad] = useState("");
  const shownRevision = useRef(revision);
  useEffect(() => { // a replaced description (a file, the example) shows its own values
    if (shownRevision.current === revision) return;
    shownRevision.current = revision;
    setText(textOf(valueAt(wing, field.path))); setBad("");
  }, [revision, wing, field.path]);
  const id = idOf(field.path);
  const unit = unitLabel(wing, field.unit);
  function typed(next: string) {
    setText(next);
    if (!next.trim()) {
      setBad(field.optional ? "" : "Needs a value.");
      if (field.optional) setValue(field.path, undefined);
      return;
    }
    const read = field.list ? readNumbers(next) : readNumber(next);
    if (read === null) { setBad(field.list ? "Numbers separated by commas." : "Not a number."); return; }
    setBad("");
    setValue(field.path, read);
  }
  return (
    <div className="studio-field wing-field">
      <label htmlFor={id}>{field.label}{field.optional ? <small> optional</small> : null}</label>
      <span className="wing-input">
        <input id={id} type="text" inputMode={field.list ? "text" : "decimal"} autoComplete="off" value={text} onChange={(e) => typed(e.target.value)}
          aria-invalid={bad ? true : undefined} data-testid={id} />
        {unit ? <span className="wing-unit">{unit}</span> : null}
      </span>
      {bad ? <span className="studio-hint wing-bad" role="alert">{bad}</span> : field.hint ? <span className="studio-hint">{field.hint}</span> : null}
    </div>
  );
}

/** Fields two to a row: a value, its unit and its hint stay together in one cell. */
function Fields({ fields }: { fields: readonly WingField[] }) {
  return <div className="wing-grid">{fields.map((f) => <WingNumber key={f.path} field={f} />)}</div>;
}

/** A plain text value, such as the wing's title or a typed material's name. */
function WingText({ path, label }: { path: string; label: string }) {
  const { wing, setValue } = useWing();
  const id = idOf(path);
  return (
    <div className="studio-field wing-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" autoComplete="off" value={textOf(valueAt(wing, path))} onChange={(e) => setValue(path, e.target.value)} data-testid={id} />
    </div>
  );
}

function WingChoice({ path, label, options, hint }: { path: string; label: string; options: { id: string; label: string }[]; hint?: string }) {
  const { wing, setValue } = useWing();
  const id = idOf(path);
  return (
    <div className="studio-field wing-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={textOf(valueAt(wing, path))} onChange={(e) => setValue(path, e.target.value)} data-testid={id}>
        {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      {hint ? <span className="studio-hint">{hint}</span> : null}
    </div>
  );
}

/** The wing as a whole: where it comes from, its name, and its file. */
/** Hands the browser a file to save, made from text. */
function download(text: string, name: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function WingFilePanel() {
  const { wing, replace, openFile } = useWing();
  const [note, setNote] = useState("");
  const input = useRef<HTMLInputElement>(null);
  async function opened(file: File | undefined) {
    if (!file) return;
    setNote(`Reading ${file.name}…`);
    const refused = await openFile(await file.text());
    setNote(refused ? `${file.name} was not opened: ${refused}` : `${file.name} opened.`);
    if (input.current) input.current.value = "";
  }
  function save() { download(wingToml(wing), wingFileName(wing), "application/toml"); }
  const units = unitsOf(wing);
  return (
    <StepPanel id="wing" step={1} title="Wing" note={units === "US" ? "in · lb" : "m · N"}>
      <WingText path="title" label="Name" />
      <p className="studio-hint">Values are in {units === "US" ? "inches, pounds and feet of altitude" : "metres, newtons and millimetres for thicknesses"}, as the wing file states them. Speeds are in {textOf(valueAt(wing, "envelope.speed_unit"))}.</p>
      <div className="studio-buttons">
        <button type="button" className="studio-button" onClick={() => { replace(EXAMPLE_WING); setNote("The example wing."); }} data-testid="wing-example">Start from the example</button>
        <button type="button" className="studio-button" onClick={() => input.current?.click()} data-testid="wing-open">Open a wing file</button>
        <button type="button" className="studio-button" onClick={save} data-testid="wing-save">Save the wing file</button>
        <input ref={input} type="file" accept=".toml,text/plain" hidden onChange={(e) => void opened(e.target.files?.[0])} data-testid="wing-file" />
      </div>
      {note ? <p className="studio-status" role="status" data-testid="wing-file-note">{note}</p> : null}
    </StepPanel>
  );
}

function AirfoilField() {
  const { wing, setValue } = useWing();
  const airfoil = valueAt(wing, "geometry.airfoil");
  const points = typeof airfoil === "object" && !Array.isArray(airfoil) ? airfoil : null;
  const [text, setText] = useState(typeof airfoil === "string" ? airfoil : "");
  const { revision } = useWing();
  const shownRevision = useRef(revision);
  useEffect(() => { // a replaced description shows its own airfoil
    if (shownRevision.current === revision) return;
    shownRevision.current = revision;
    setText(typeof airfoil === "string" ? airfoil : "");
  }, [revision, airfoil]);
  if (points) {
    const upper = Array.isArray(points.upper) ? points.upper.length : 0;
    const lower = Array.isArray(points.lower) ? points.lower.length : 0;
    return (
      <div className="studio-field wing-field">
        <span className="wing-label">Airfoil</span>
        <span data-testid="wing-airfoil">{String(points.name)}: {upper} points on the upper surface, {lower} on the lower, from the wing file.</span>
        <button type="button" className="studio-text-button" onClick={() => { setValue("geometry.airfoil", "naca-2412"); setText("naca-2412"); }}>Use a NACA four-digit airfoil instead</button>
      </div>
    );
  }
  return (
    <div className="studio-field wing-field">
      <label htmlFor="wing-airfoil">Airfoil</label>
      <input id="wing-airfoil" type="text" autoComplete="off" value={text} data-testid="wing-airfoil"
        onChange={(e) => { setText(e.target.value); setValue("geometry.airfoil", e.target.value.trim()); }} />
      <span className="studio-hint">A NACA four-digit airfoil, such as naca-2412. Other airfoils come in a wing file as points.</span>
    </div>
  );
}

function MaterialPanel() {
  const { wing, replace } = useWing();
  const library = valueAt(wing, "material.library");
  const own = library === undefined;
  function pick(id: string) {
    const material: WingDescription = id ? { library: id } : Object.fromEntries(OWN_MATERIAL_KEYS.map((k) => [k, k === "name" ? "My material" : 0])) as WingDescription;
    replace({ ...wing, material });
  }
  return (
    <StepPanel id="wing-material" step={3} title="Material" open={false} note={own ? String(valueAt(wing, "material.name") ?? "typed") : WING_MATERIALS.find((m) => m.id === library)?.name ?? String(library)}>
      <div className="studio-field wing-field">
        <label htmlFor="wing-material-library">Ply material</label>
        <select id="wing-material-library" value={own ? "" : String(library)} onChange={(e) => pick(e.target.value)} data-testid="wing-material-library">
          {WING_MATERIALS.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          <option value="">My own values</option>
        </select>
        <span className="studio-hint">A library material brings its ply thickness, density and strengths with their sources.</span>
      </div>
      {own ? <><WingText path="material.name" label="Material name" /><Fields fields={OWN_MATERIAL_FIELDS} /></> : null}
    </StepPanel>
  );
}

/** A layup: the half stack and, for a sandwich, the core between its halves. */
function LayupFields({ member, title }: { member: "skin" | "spar" | "rib"; title: string }) {
  const { wing, setValue, replace } = useWing();
  const core = valueAt(wing, `${member}.core`);
  const density = valueAt(wing, `${member}.core_density`);
  const thickness = valueAt(wing, `${member}.core_thickness`);
  const choice = typeof core === "string" ? core : density !== undefined ? "own" : "";
  function pickCore(id: string) {
    const table = { ...(valueAt(wing, member) as WingDescription) };
    for (const key of ["core", "core_density", "core_modulus", "core_shear_modulus", "core_shear_strength"]) delete table[key];
    if (id === "") delete table.core_thickness;
    else {
      if (table.core_thickness === undefined) table.core_thickness = unitsOf(wing) === "US" ? 0.25 : 6;
      if (id === "own") table.core_density = 0;
      else table.core = id;
    }
    replace({ ...wing, [member]: table });
  }
  return (
    <fieldset className="wing-fieldset" data-testid={`wing-${member}`}>
      <legend>{title}</legend>
      <WingNumber field={{ path: `${member}.half_stack`, label: "Half stack", hint: "Degrees from the span, outside ply first; the other half mirrors it", list: true, unit: "deg" }} />
      <div className="studio-field wing-field">
        <label htmlFor={idOf(`${member}.core-choice`)}>Core</label>
        <select id={idOf(`${member}.core-choice`)} value={choice} onChange={(e) => pickCore(e.target.value)}>
          <option value="">None: plies only</option>
          {WING_CORES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          <option value="own">My own core density</option>
        </select>
      </div>
      {choice ? <WingNumber field={{ path: `${member}.core_thickness`, label: "Core thickness", unit: "thickness" }} /> : null}
      {choice === "own" ? <WingNumber field={{ path: `${member}.core_density`, label: "Core density", unit: "density", hint: "Its weight only; the hand calculation leaves the core's own stiffness out" }} /> : null}
      {thickness !== undefined && !choice ? <button type="button" className="studio-text-button" onClick={() => setValue(`${member}.core_thickness`, undefined)}>Remove the core thickness</button> : null}
    </fieldset>
  );
}

function LoadsPanel() {
  const { wing, replace } = useWing();
  const gust = valueAt(wing, "envelope.gust");
  const gustKind = gust === undefined ? "" : valueAt(wing, "envelope.gust.cruise_gust_speed") !== undefined || valueAt(wing, "envelope.gust.dive_gust_speed") !== undefined ? "speeds" : "factors";
  const aileron = valueAt(wing, "envelope.aileron");
  const envelope = valueAt(wing, "envelope") as WingDescription;
  function setEnvelope(next: WingDescription) { replace({ ...wing, envelope: next }); }
  function pickGust(kind: string) {
    const next = { ...envelope };
    delete next.gust;
    const blank = (fields: readonly WingField[]) => Object.fromEntries(fields.map((f) => [f.path.split(".").pop() as string, 0]));
    if (kind === "speeds") next.gust = blank(GUST_SPEED_FIELDS);
    if (kind === "factors") next.gust = blank(GUST_FACTOR_FIELDS);
    setEnvelope(next);
  }
  function toggleAileron() {
    const next = { ...envelope };
    if (aileron !== undefined) delete next.aileron;
    else next.aileron = Object.fromEntries(AILERON_FIELDS.map((f) => [f.path.split(".").pop() as string, 0]));
    setEnvelope(next);
  }
  return (
    <StepPanel id="wing-loads" step={6} title="Loads" note="17 flight cases at each altitude">
      <p className="studio-hint">Level flight, the four maneuver corners, gusts and rolls, from these values. A case whose speed or gust is missing is left out and listed with what it needs.</p>
      <Fields fields={ENVELOPE_FIELDS} />
      <WingChoice path="envelope.criterion" label="Failure criterion" options={CRITERIA} />
      <WingChoice path="envelope.airspeed" label="Speeds are" options={[{ id: "equivalent", label: "Equivalent airspeeds" }, { id: "true", label: "True airspeeds" }]} />
      <fieldset className="wing-fieldset"><legend>Speeds</legend><Fields fields={SPEED_FIELDS} /></fieldset>
      <fieldset className="wing-fieldset" data-testid="wing-gust">
        <legend>Gusts</legend>
        <div className="studio-field wing-field">
          <label htmlFor="wing-gust-kind">Given as</label>
          <select id="wing-gust-kind" value={gustKind} onChange={(e) => pickGust(e.target.value)}>
            <option value="">No gust cases</option>
            <option value="speeds">Gust speeds (the formula finds the load factors)</option>
            <option value="factors">Load factors</option>
          </select>
        </div>
        {gustKind === "speeds" ? <Fields fields={GUST_SPEED_FIELDS} /> : gustKind === "factors" ? <Fields fields={GUST_FACTOR_FIELDS} /> : null}
      </fieldset>
      <fieldset className="wing-fieldset" data-testid="wing-aileron">
        <legend>Aileron</legend>
        {aileron !== undefined ? <Fields fields={AILERON_FIELDS} /> : <p className="studio-hint">Without one the roll cases and aileron reversal are left out.</p>}
        <button type="button" className="studio-text-button" onClick={toggleAileron} data-testid="wing-aileron-toggle">{aileron !== undefined ? "Remove the aileron" : "+ Add an aileron"}</button>
      </fieldset>
    </StepPanel>
  );
}

/** The left column of the wing workspace (ADR-0118): the description's tables as the steps of an FEA setup, in the general words of
 * the model tree (ADR-0111). Every change is worked at once; the Solve step says how the last calculation went. */
/** The wing's finite element check (ADR-0117, ADR-0119): started on request, in the background like a coupon run, from the description as
 * it stands; its stage shows here and its answer in the centre. Opening the panel starts a machine on the hosted tier, so the check does
 * not wait for one. */
function FeCheckPanel() {
  const { feCheck, feCheckStale, feProblem, startFeCheck, wakeChecks, problem, apiBaseUrl } = useWing();
  const [starting, setStarting] = useState(false);
  const running = feCheck !== null && (feCheck.state === "queued" || feCheck.state === "running");
  const done = feCheck?.state === "done" && feCheck.report !== null;
  async function start() {
    setStarting(true);
    try { await startFeCheck(); } finally { setStarting(false); }
  }
  const status = feProblem || (feCheck ? feProgress(feCheck) + (done && feCheckStale ? " The wing has changed since; check it again to see the change." : "") : "");
  return (
    <StepPanel id="wing-fe" step={9} title="Finite element check" open={false}
      state={done && !feCheckStale ? "pass" : "none"} word="checked" onToggle={(open) => { if (open) wakeChecks(); }}>
      <p className="studio-hint">Solves the wing&apos;s finite element model under every flight case that runs and for its first vibration modes, and sets it
        beside the hand calculation. The skins count between the spars, as the hand calculation counts them. It runs in the background; keep working meanwhile.</p>
      <div className="studio-buttons">
        <button type="button" className="studio-button" onClick={() => void start()} disabled={starting || running || Boolean(problem) || !apiBaseUrl}
          data-testid="wing-fe-start">{done || feCheck?.state === "stopped" || feCheck?.state === "refused" ? "Check again" : "Check with the finite element model"}</button>
      </div>
      {status ? <p className={feProblem || feCheck?.state === "refused" || feCheck?.state === "stopped" ? "studio-alert" : "studio-status"}
        role={feProblem ? "alert" : "status"} data-testid="wing-fe-status">{status}</p> : null}
    </StepPanel>
  );
}

/** The wing's shape for a CAD program (ADR-0116, ADR-0118): built on request, from the description as it stands, by the engine's
 * reading and the fea package's shape builder; the page saves the STEP file and lists each part's thickness, which a STEP file
 * cannot hold. */
function ShapePanel() {
  const { apiBaseUrl, wing } = useWing();
  const [building, setBuilding] = useState(false);
  const [note, setNote] = useState("");
  const [shape, setShape] = useState<WingShape | null>(null);
  async function build() {
    setBuilding(true); setNote("Building the shape…"); setShape(null);
    try {
      const found = await shapeWing(apiBaseUrl, { wing });
      const name = wingFileName(wing, "step");
      download(found.step, name, "application/step");
      setShape(found);
      setNote(`${name} saved: ${found.parts.parts.length} parts, in millimetres.`);
    } catch (error) {
      setNote(error instanceof StudioError ? error.message : "The shape could not be built.");
    } finally {
      setBuilding(false);
    }
  }
  const table = shape?.parts;
  return (
    <StepPanel id="wing-shape" step={10} title="Shape for CAD" note="STEP" open={false}>
      <p className="studio-hint">The skins, spar webs and ribs as surfaces at their mid-thickness, every part named, in millimetres. Any CAD program that reads STEP files opens it.</p>
      <div className="studio-buttons">
        <button type="button" className="studio-button" onClick={() => void build()} disabled={building || !apiBaseUrl} data-testid="wing-step">Download STEP</button>
      </div>
      {note ? <p className="studio-status" role="status" data-testid="wing-step-note">{note}</p> : null}
      {table ? (
        <>
          <p className="studio-hint">A STEP file holds no thickness. In the CAD program, thicken each part on both sides of its surface, half on each side, to the whole thickness below.</p>
          <table className="studio-table" data-testid="wing-parts">
            <thead><tr><th>Part</th><th>Thickness, {unitText(table.units.thickness)}</th><th>Mass, {unitText(table.units.mass)}</th></tr></thead>
            <tbody>{table.parts.map((p) => <tr key={p.name}><td>{p.name}</td><td>{p.thickness === null ? "not given" : shown(p.thickness, 4)}</td><td>{shown(p.mass, 3)}</td></tr>)}</tbody>
            {table.mass !== null ? <tfoot><tr><td>Whole wing, one side</td><td /><td>{shown(table.mass, 3)}</td></tr></tfoot> : null}
          </table>
          <p className="studio-hint">The skins here run round the whole airfoil, so this mass is more than the hand calculation&apos;s, which counts the box between the spars.</p>
        </>
      ) : null}
    </StepPanel>
  );
}

export function WingRail() {
  const { wing, answer, stale, working, problem } = useWing();
  const status = problem ? "" : working || stale ? "Working the wing…"
    : answer ? `Worked ${answer.report.cases.length} case${answer.report.cases.length === 1 ? "" : "s"} in ${Math.max(answer.report.seconds, 0.001).toFixed(3)} s.` : "";
  const ribs = valueAt(wing, "geometry.rib_spacing") !== undefined;
  return (
    <div className="studio-form ws-rail-panels" data-testid="wing-rail">
      <WingFilePanel />
      <StepPanel id="wing-geometry" step={2} title="Geometry" note={`${textOf(valueAt(wing, "geometry.half_span"))} × ${textOf(valueAt(wing, "geometry.chord"))} ${unitLabel(wing, "length")}`}>
        <AirfoilField />
        <Fields fields={GEOMETRY_FIELDS} />
      </StepPanel>
      <MaterialPanel />
      <StepPanel id="wing-layup" step={4} title="Layup">
        <LayupFields member="skin" title="Skins" />
        <LayupFields member="spar" title="Spar webs" />
        {ribs ? <LayupFields member="rib" title="Ribs" /> : null}
      </StepPanel>
      <StepPanel id="wing-aero" step={5} title="Aerodynamics" open={false} note={`moment coefficient ${textOf(valueAt(wing, "aerodynamics.pitching_moment_coefficient"))}`}><Fields fields={AERO_FIELDS} /></StepPanel>
      <LoadsPanel />
      <StepPanel id="wing-supports" step={7} title="Boundary conditions" note="Root fixed" open={false}>
        <p className="studio-hint">The wing is a cantilever clamped at the root. The hand calculation works it as a beam with a thin-walled box section between the spars.</p>
      </StepPanel>
      <StepPanel id="wing-solve" step={8} title="Solve" note="Hand calculation" state={answer && !stale && !problem ? "pass" : "none"} word="solved">
        <p className="studio-hint">Worked again on every change, in a fraction of a second.</p>
        {problem ? <p className="studio-alert" role="alert" data-testid="wing-problem">{problem}</p> : null}
        <p className="studio-status" role="status" data-testid="wing-status">{status}</p>
      </StepPanel>
      <FeCheckPanel />
      <ShapePanel />
    </div>
  );
}
