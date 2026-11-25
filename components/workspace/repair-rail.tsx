"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ADHESIVE_FIELDS, bondNeedsWords, bondWords, COVER_FIELDS, DAMAGE_FIELDS, EXAMPLE_REPAIR, EXTERNAL_PATCH_FIELDS, EXTERNAL_REPAIR, FLUSH_PATCH_FIELD, kindOf, layupText, materialMode,
  needsWords, PANEL_FIELDS, PART_WORDS, REPAIR_KINDS, REPAIR_MATERIALS, REPAIR_UNIT_LABELS, REPAIR_UNIT_WORDS, repairFileName, repairToml, shown,
  STRENGTH_FIELDS, TYPED_MATERIAL_FIELDS, unitsOf, unitText, valueAt, withKind, withLaminateMaterial, withLibraryMaterial, withTypedMaterial,
  type RegionKind, type RepairField, type RepairKind, type RepairShape, type RepairUnitKind, type RepairValue,
} from "@/lib/repair";
import { shapeRepair, StudioError } from "@/lib/studio-api";
import { readNumber, readNumbers } from "@/lib/wing";
import { REPAIR_HREF } from "@/lib/workspaces";
import { StepPanel } from "./panels/step-panel";
import { useRepair } from "./repair-context";

function idOf(path: string): string { return `repair-${path.replace(/[._]/g, "-")}`; }

function textOf(value: RepairValue | undefined): string {
  if (value === undefined) return "";
  if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
  return String(value);
}

/** One value of the description: typed as text, written to the description as soon as it reads as a number (a whole one for a count,
 * a list of them for ply angles); emptied, an optional value leaves the description. The text stays as typed while it does not read,
 * with a note under it. */
function RepairNumber({ field }: { field: RepairField }) {
  const { repair, revision, setValue } = useRepair();
  const [text, setText] = useState(textOf(valueAt(repair, field.path)));
  const [bad, setBad] = useState("");
  const shownRevision = useRef(revision);
  useEffect(() => { // a replaced description (a file, an example, the other kind) shows its own values
    if (shownRevision.current === revision) return;
    shownRevision.current = revision;
    setText(textOf(valueAt(repair, field.path))); setBad("");
  }, [revision, repair, field.path]);
  const id = idOf(field.path);
  const unit = field.unit === "deg" ? "°" : field.unit ? REPAIR_UNIT_LABELS[unitsOf(repair)][field.unit] : "";
  function typed(next: string) {
    setText(next);
    if (!next.trim()) {
      setBad(field.optional ? "" : "Needs a value.");
      if (field.optional) setValue(field.path, undefined);
      return;
    }
    const read = field.list ? readNumbers(next) : readNumber(next);
    if (read === null) { setBad(field.list ? "Angles separated by commas." : "Not a number."); return; }
    if (field.whole && !(Number.isInteger(read) && (read as number) >= 1)) { setBad("A whole number, 1 or more."); return; }
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

function Fields({ fields }: { fields: readonly RepairField[] }) {
  return <div className="wing-grid">{fields.map((f) => <RepairNumber key={f.path} field={f} />)}</div>;
}

function RepairText({ path, label }: { path: string; label: string }) {
  const { repair, setValue } = useRepair();
  const id = idOf(path);
  return (
    <div className="studio-field wing-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="text" autoComplete="off" value={textOf(valueAt(repair, path))} onChange={(e) => setValue(path, e.target.value)} data-testid={id} />
    </div>
  );
}

/** Hands the browser a file to save, made from text. */
function download(text: string, name: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The repair as a whole: its name, its kind, and its file. */
function RepairFilePanel() {
  const { repair, replace, openFile } = useRepair();
  const [note, setNote] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const kind = kindOf(repair);
  async function opened(file: File | undefined) {
    if (!file) return;
    setNote(`Reading ${file.name}…`);
    const refused = await openFile(await file.text());
    setNote(refused ? `${file.name} was not opened: ${refused}` : `${file.name} opened.`);
    if (input.current) input.current.value = "";
  }
  return (
    <StepPanel id="repair" step={1} title="Repair" note={kind === "external" ? "On top" : "Flush"}>
      <RepairText path="title" label="Name" />
      <div className="studio-field wing-field">
        <label htmlFor="repair-kind">Kind of repair</label>
        <select id="repair-kind" value={kind} onChange={(e) => { replace(withKind(repair, e.target.value as RepairKind)); setNote(""); }} data-testid="repair-kind">
          {REPAIR_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
        </select>
        <span className="studio-hint">{REPAIR_KINDS.find((k) => k.id === kind)?.detail}</span>
      </div>
      <p className="studio-hint">Values are in {REPAIR_UNIT_WORDS[unitsOf(repair)]}, as the repair file states them. Angles are in degrees from the load.</p>
      <div className="studio-buttons repair-buttons">
        <button type="button" className="studio-button" onClick={() => { replace(EXAMPLE_REPAIR); setNote("The flush example."); }} data-testid="repair-example">Flush example</button>
        <button type="button" className="studio-button" onClick={() => { replace(EXTERNAL_REPAIR); setNote("The example bonded on top."); }} data-testid="repair-example-external">On-top example</button>
        <button type="button" className="studio-button" onClick={() => input.current?.click()} data-testid="repair-open">Open a repair file</button>
        <button type="button" className="studio-button" onClick={() => download(repairToml(repair), repairFileName(repair), "application/toml")} data-testid="repair-save">Save the repair file</button>
        <input ref={input} type="file" accept=".toml,text/plain" hidden onChange={(e) => void opened(e.target.files?.[0])} data-testid="repair-file" />
      </div>
      {note ? <p className="studio-status" role="status" data-testid="repair-file-note">{note}</p> : null}
    </StepPanel>
  );
}

/** A table's ply material: one of the library's, typed in full, or (a patch) the laminate's own; and what the solve of the slice
 * needs of it through the thickness. */
function MaterialFields({ table }: { table: "parent" | "patch" }) {
  const { repair, replace } = useRepair();
  const mode = materialMode(repair, table);
  const library = valueAt(repair, `${table}.library`);
  const units = REPAIR_UNIT_LABELS[unitsOf(repair)];
  const picked = mode === "library" ? String(library) : mode === "typed" ? "typed" : "laminate";
  function pick(id: string) {
    replace(id === "laminate" ? withLaminateMaterial(repair) : id === "typed" ? withTypedMaterial(repair, table) : withLibraryMaterial(repair, table, id));
  }
  const material = REPAIR_MATERIALS.find((m) => m.id === library);
  const field = (key: string, label: string, unit?: RepairUnitKind, optional = false): RepairField => ({ path: `${table}.${key}`, label, unit, optional });
  return (
    <>
      <div className="studio-field wing-field">
        <label htmlFor={`repair-${table}-material`}>Ply material</label>
        <select id={`repair-${table}-material`} value={picked} onChange={(e) => pick(e.target.value)} data-testid={`repair-${table}-material`}>
          {table === "patch" ? <option value="laminate">The laminate&apos;s material</option> : null}
          {REPAIR_MATERIALS.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          <option value="typed">My own values</option>
        </select>
        <span className="studio-hint">{mode === "library"
          ? `A library material brings its stiffness, its cured ply thickness and${material?.strengths === false ? " no ply strengths: its plies are not checked" : " its ply strengths"}.`
          : mode === "typed" ? `Every value in ${units.modulus} and ${units.length}, as the repair file states them.` : "The patch is made of the laminate's own ply."}</span>
      </div>
      {mode === "typed" ? (
        <>
          <RepairText path={`${table}.name`} label="Material name" />
          <Fields fields={TYPED_MATERIAL_FIELDS.filter((f) => !f.text).map((f) => field(f.key, f.label, f.unit))} />
          <fieldset className="wing-fieldset">
            <legend>Ply strengths, {units.stress}</legend>
            <p className="studio-hint">All five or none. With them the solve of the slice checks which ply reaches a strength first.</p>
            <div className="wing-grid">{STRENGTH_FIELDS.map((f) => <RepairNumber key={f.key} field={field(f.key, f.label, "stress", true)} />)}</div>
          </fieldset>
        </>
      ) : null}
      {mode !== "laminate" ? (
        <RepairNumber field={{ path: `${table}.nu23`, label: "ν23, across the fibres", optional: true,
          hint: "For the solve of the slice. A unidirectional ply's constants through the thickness follow from it; a fabric states all five in its repair file." }} />
      ) : null}
    </>
  );
}

function PatchShape() {
  const { repair, setValue } = useRepair();
  return (
    <div className="studio-field wing-field">
      <label htmlFor="repair-patch-shape">Shape</label>
      <select id="repair-patch-shape" value={textOf(valueAt(repair, "patch.shape")) || "round"} data-testid="repair-patch-shape" onChange={(e) => setValue("patch.shape", e.target.value)}>
        <option value="round">Round</option>
        <option value="strip">A strip across the panel&apos;s width</option>
      </select>
    </div>
  );
}

function CoverFields() {
  const { repair, replace } = useRepair();
  const has = valueAt(repair, "cover") !== undefined;
  const length = valueAt(repair, "steps.length");
  if (!has) {
    return (
      <>
        <p className="studio-hint">No cover plies: the patch ends level with the laminate at the widest cut.</p>
        <button type="button" className="studio-button" data-testid="repair-cover-add"
          onClick={() => replace({ ...repair, cover: { layup: [45], overlap: typeof length === "number" ? length : 10 } })}>Add a cover ply</button>
      </>
    );
  }
  return (
    <>
      <Fields fields={COVER_FIELDS} />
      <button type="button" className="studio-text-button" data-testid="repair-cover-remove"
        onClick={() => { const { cover: _cover, ...rest } = repair; replace(rest); }}>Remove the cover plies</button>
    </>
  );
}

/** The solve of the slice (ADR-0132): what it still needs, the one choice it has, and the button; and under it the bond followed
 * until it lets go (ADR-0140): what that still needs, and its button. */
function SolvePanel() {
  const { repair, answer, stale, working, problem, solve, solveStale, solving, solveProblem, cutFaces, setCutFaces, solveSlice, apiBaseUrl,
    bond, bondStale, following, bondProblem, bondNeeds, followBond } = useRepair();
  const canFollow = answer !== null && !stale && !problem && bondNeeds !== null && bondNeeds.length === 0;
  const needs = answer && !stale ? answer.needs : [];
  const ready = answer !== null && !stale && !problem && needs.length === 0;
  const hand = problem ? "" : working || stale ? "Working the repair…" : answer?.report.lap.answer ? "Worked by hand." : answer ? "Described; no load is stated." : "";
  return (
    <StepPanel id="repair-solve" step={kindOf(repair) === "external" ? 7 : 8} title="Solve" note={solve && !solveStale ? "By hand and as a slice" : "By hand"}
      state={solve && !solveStale ? "pass" : answer && !stale && !problem ? "pass" : "none"} word="solved">
      <p className="studio-hint">The hand calculation is worked again on every change. The slice through the repair&apos;s middle is solved when you ask, in a few seconds.</p>
      {problem ? <p className="studio-alert" role="alert" data-testid="repair-problem">{problem}</p> : null}
      <p className="studio-status" role="status" data-testid="repair-status">{hand}</p>
      {kindOf(repair) === "flush" ? (
        <div className="studio-field wing-field">
          <label htmlFor="repair-cut-faces">Adhesive on the cut faces</label>
          <select id="repair-cut-faces" value={cutFaces} onChange={(e) => setCutFaces(e.target.value as "open" | "bonded")} data-testid="repair-cut-faces">
            <option value="open">Carries nothing</option>
            <option value="bonded">Bonded</option>
          </select>
          <span className="studio-hint">The upright faces of the cut are hard to bond well. Left carrying nothing, the ledges take all the load.</span>
        </div>
      ) : null}
      {needs.length ? <p className="studio-hint" data-testid="repair-needs">{needsWords(needs)}</p> : null}
      <div className="studio-buttons">
        <button type="button" className="studio-button studio-button-primary" disabled={!ready || solving || !apiBaseUrl} onClick={() => void solveSlice()} data-testid="repair-solve-button">
          {solving ? "Solving the slice…" : solve ? "Solve the slice again" : "Solve the slice"}
        </button>
      </div>
      {solveProblem ? <p className="studio-alert" role="alert" data-testid="repair-solve-problem">{solveProblem}</p> : null}
      {solve ? <p className="studio-status" role="status" data-testid="repair-solve-status">{solveStale ? "The slice was solved for the repair as it was; it has changed since." : solve.headline}</p> : null}
      {bondNeeds !== null ? (
        <>
          <p className="studio-hint">Past the adhesive&apos;s elastic limit, the bond can be followed as it softens and parts, until it lets go: about ten seconds. It needs the bond&apos;s two strengths and two fracture energies, on the Adhesive step, and no load.</p>
          {bondNeeds.length && !stale ? <p className="studio-hint" data-testid="repair-bond-needs">{bondNeedsWords(bondNeeds)}</p> : null}
          <div className="studio-buttons">
            <button type="button" className="studio-button" disabled={!canFollow || following || !apiBaseUrl} onClick={() => void followBond()} data-testid="repair-bond-button">
              {following ? "Following the bond…" : bond ? "Follow the bond again" : "Follow the bond until it lets go"}
            </button>
          </div>
          {bondProblem ? <p className="studio-alert" role="alert" data-testid="repair-bond-problem">{bondProblem}</p> : null}
          {bond ? <p className="studio-status" role="status" data-testid="repair-bond-status">{bondStale ? "The bond was followed for the repair as it was; it has changed since."
            : `${bondWords(bond.report).headline}. ${bondWords(bond.report).short}`}</p> : null}
        </>
      ) : null}
    </StepPanel>
  );
}

const SOLID_KINDS: readonly RegionKind[] = ["parent", "patch", "cover", "adhesive"];

/** The report and the solids for a CAD program: the report opens as a page laid out for paper; the STEP file is built on request,
 * from the description as it stands, by the fea package's shape builder. */
function OutputPanel() {
  const { apiBaseUrl, repair, answer, stale, problem } = useRepair();
  const [building, setBuilding] = useState(false);
  const [note, setNote] = useState("");
  const [shape, setShape] = useState<RepairShape | null>(null);
  async function build() {
    setBuilding(true); setNote("Building the solids…"); setShape(null);
    try {
      const found = await shapeRepair(apiBaseUrl, repair);
      const name = repairFileName(repair, "step");
      download(found.step, name, "application/step");
      setShape(found);
      setNote(`${name} saved: ${found.parts.parts.length} solids, in millimetres.`);
    } catch (error) {
      setNote(error instanceof StudioError ? error.message : "The solids could not be built.");
    } finally {
      setBuilding(false);
    }
  }
  const ready = answer !== null && !stale && !problem;
  return (
    <StepPanel id="repair-report" step={kindOf(repair) === "external" ? 8 : 9} title="Report and shape" note="PDF · STEP" open={false}>
      <p className="studio-hint">The report lays this repair out for paper: what it is, its slice, the hand calculation, the solved slice when there is one, and what the analysis is not. Print it or save it as a PDF from there.</p>
      <div className="studio-buttons">
        {ready ? <Link className="studio-button" href={`${REPAIR_HREF}/report`} target="_blank" rel="noopener" data-testid="repair-report-link">Open the report</Link>
          : <button type="button" className="studio-button" disabled data-testid="repair-report-link">Open the report</button>}
        <button type="button" className="studio-button" onClick={() => void build()} disabled={!ready || building || !apiBaseUrl} data-testid="repair-step">Download STEP</button>
      </div>
      <p className="studio-hint">The STEP file holds every ply and the adhesive as a named solid, in millimetres. Any CAD program that reads STEP files opens it.</p>
      {note ? <p className="studio-status" role="status" data-testid="repair-step-note">{note}</p> : null}
      {shape ? (
        <table className="studio-table" data-testid="repair-solids">
          <thead><tr><th>Solids</th><th>Count</th><th>Volume, {unitText(shape.parts.units.volume)}</th></tr></thead>
          <tbody>{SOLID_KINDS.filter((kind) => shape.parts.volumes[kind] > 0).map((kind) => (
            <tr key={kind}><th scope="row">{PART_WORDS[kind]}</th><td>{shape.parts.parts.filter((p) => p.kind === kind).length}</td><td>{shown(shape.parts.volumes[kind], 5)}</td></tr>
          ))}</tbody>
        </table>
      ) : null}
    </StepPanel>
  );
}

/** The model tree of the repair's page (ADR-0135): the repair file's tables as steps, in the order a repair is described. */
export function RepairRail() {
  const { repair } = useRepair();
  const kind = kindOf(repair);
  const units = REPAIR_UNIT_LABELS[unitsOf(repair)];
  const patchMode = materialMode(repair, "patch");
  const next = kind === "external" ? 5 : 6; // the adhesive's step: a patch bonded on top has no cover plies
  return (
    <div className="studio-form ws-rail-panels" data-testid="repair-rail">
      <RepairFilePanel />
      <StepPanel id="repair-laminate" step={2} title="Laminate" note={layupText(valueAt(repair, "parent.layup"))}>
        <MaterialFields table="parent" />
        <RepairNumber field={{ path: "parent.layup", label: "Plies", unit: "deg", list: true, hint: "From the bottom face up. The repair is made from the top face." }} />
      </StepPanel>
      <StepPanel id="repair-damage" step={3} title={kind === "external" ? "Hole and steps" : "Damage and steps"}
        note={`${textOf(valueAt(repair, "steps.count"))} × ${textOf(valueAt(repair, "steps.length"))} ${units.length}`}>
        <Fields fields={DAMAGE_FIELDS[kind]} />
      </StepPanel>
      <StepPanel id="repair-patch" step={4} title="Patch" open={kind === "external"}
        note={kind === "external" ? layupText(valueAt(repair, "patch.layup")) : valueAt(repair, "patch.layup") !== undefined ? layupText(valueAt(repair, "patch.layup")) : "The plies removed"}>
        {kind === "external" ? (
          <>
            <Fields fields={EXTERNAL_PATCH_FIELDS} />
            <PatchShape />
          </>
        ) : <RepairNumber field={FLUSH_PATCH_FIELD} />}
        <MaterialFields table="patch" />
        {kind === "flush" && patchMode !== "laminate" ? <p className="studio-hint">A flush patch&apos;s plies must be as thick as the laminate&apos;s: each group fills the step cut for it.</p> : null}
      </StepPanel>
      {kind === "flush" ? (
        <StepPanel id="repair-cover" step={5} title="Cover plies" open={false} note={valueAt(repair, "cover.layup") !== undefined ? layupText(valueAt(repair, "cover.layup")) : "None"}>
          <CoverFields />
        </StepPanel>
      ) : null}
      <StepPanel id="repair-adhesive" step={next} title="Adhesive" open={false} note={`${textOf(valueAt(repair, "adhesive.thickness"))} ${units.length}`}>
        <Fields fields={ADHESIVE_FIELDS} />
      </StepPanel>
      <StepPanel id="repair-loads" step={next + 1} title="Panel and load" note={valueAt(repair, "applied.load") !== undefined ? `${textOf(valueAt(repair, "applied.load"))} ${units.load}` : "No load"}>
        <Fields fields={PANEL_FIELDS} />
        <p className="studio-hint">The load is tension along the panel&apos;s length, per unit of its width, far from the repair.</p>
      </StepPanel>
      <SolvePanel />
      <OutputPanel />
    </div>
  );
}
