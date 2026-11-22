/** The repair's page (ADR-0135): one stepped patch repair, the same table a repair file holds (ADR-0131), edited on the page, worked by
 * the engine's hand calculation on every change (ADR-0130) and, on request, solved as a slice in CalculiX (ADR-0132). Nothing here
 * computes a result: the description is sent as it stands, the engine reads it by its own rules and refuses what is wrong by name, and
 * the page shows its numbers. What this file does is keep the description (its fields, its two kinds, its materials), write it out as a
 * repair file, and word the engine's and the solver's answers. */
import choices from "./repair-choices.json";
import { shown, unitText, valueAt, wingToml, withValue, type WingDescription, type WingValue } from "./wing";

/** A repair's description: the object a repair file's TOML reads as. Its tables and keys are the engine's
 * (engine/src/anisotropy_engine/repair/repair_file.py). */
export type RepairDescription = WingDescription;
export type RepairValue = WingValue;

/** The flush example: a stepped cut filled level, with a cover ply (engine/examples/example-patch-repair.toml). */
export const EXAMPLE_REPAIR: RepairDescription = choices.example as unknown as RepairDescription;
/** The example of a patch bonded on top over a hole (engine/examples/example-external-patch-repair.toml). */
export const EXTERNAL_REPAIR: RepairDescription = choices.external as unknown as RepairDescription;
/** The library's ply materials a repair can name; `strengths` says whether the plies of that material can be checked. */
export const REPAIR_MATERIALS: readonly { id: string; name: string; strengths: boolean }[] = choices.materials;

export type RepairKind = "flush" | "external";
export const REPAIR_KINDS: readonly { id: RepairKind; label: string; detail: string }[] = [
  { id: "flush", label: "Flush, in a stepped cut", detail: "The damage is cut out in steps and the cut is filled level with patch plies." },
  { id: "external", label: "Bonded on top, over a hole", detail: "A stepped patch is made flat and bonded on the laminate's top face." },
];
export const kindOf = (repair: RepairDescription): RepairKind => (repair.kind === "external" ? "external" : "flush");

// ----------------------------------------------------------------------------------------------- units

export type RepairUnits = "mm-MPa" | "SI" | "US" | "psi";
export type RepairUnitKind = "length" | "modulus" | "stress" | "load";
/** The engine's labels for each kind in each system (engine units.py); the page shows them, the engine converts. */
export const REPAIR_UNIT_LABELS: Record<RepairUnits, Record<RepairUnitKind, string>> = {
  "mm-MPa": { length: "mm", modulus: "MPa", stress: "MPa", load: "N/mm" },
  SI: { length: "mm", modulus: "GPa", stress: "MPa", load: "N/m" },
  US: { length: "in", modulus: "Msi", stress: "ksi", load: "lb/in" },
  psi: { length: "in", modulus: "psi", stress: "psi", load: "lb/in" },
};
export const REPAIR_UNIT_WORDS: Record<RepairUnits, string> = {
  "mm-MPa": "mm, MPa, N/mm", SI: "mm, GPa and MPa, N/m", US: "in, Msi and ksi, lb/in", psi: "in, psi, lb/in",
};
export function unitsOf(repair: RepairDescription): RepairUnits {
  return repair.units === "SI" || repair.units === "US" || repair.units === "psi" ? repair.units : "mm-MPa";
}

// ----------------------------------------------------------------------------------------------- the fields of each step

/** A field of the setup: where its value sits in the description, what it is and its unit kind. A `list` field holds ply angles typed
 * as a list; an `optional` one may be left empty, which removes it from the description; a `whole` one is a count. */
export type RepairField = {
  path: string; label: string; hint?: string; unit?: RepairUnitKind | "deg"; optional?: boolean; list?: boolean; whole?: boolean;
};

export const DAMAGE_FIELDS: Record<RepairKind, readonly RepairField[]> = {
  flush: [
    { path: "damage.diameter", label: "Deepest cut, diameter", unit: "length", hint: "The cut round the damage at the bottom of the steps." },
    { path: "steps.count", label: "Steps", whole: true, hint: "Each step is one cut, wider than the one below." },
    { path: "steps.length", label: "Step length", unit: "length", hint: "How much wider each cut is all round: the ledge the patch bonds to." },
    { path: "steps.plies", label: "Plies in each step", whole: true, optional: true, hint: "1 unless said." },
  ],
  external: [
    { path: "damage.diameter", label: "Hole diameter", unit: "length" },
    { path: "steps.count", label: "Steps", whole: true, hint: "The patch thins toward its edge in this many steps." },
    { path: "steps.length", label: "Step length", unit: "length", hint: "The ledge of each step, at the patch's edge." },
    { path: "steps.plies", label: "Patch plies in each step", whole: true, optional: true, hint: "1 unless said." },
  ],
};
export const EXTERNAL_PATCH_FIELDS: readonly RepairField[] = [
  { path: "patch.layup", label: "Patch plies", unit: "deg", list: true, hint: "From the ply on the laminate upward: steps × plies in each step of them." },
  { path: "patch.overlap", label: "Overlap past the hole", unit: "length", hint: "How far the whole patch, its shortest plies, reaches past the hole's edge." },
];
export const FLUSH_PATCH_FIELD: RepairField = {
  path: "patch.layup", label: "Patch plies", unit: "deg", list: true, optional: true,
  hint: "Deepest ply first, one for each ply removed. Left empty, the patch repeats the angles of the plies removed.",
};
export const COVER_FIELDS: readonly RepairField[] = [
  { path: "cover.layup", label: "Cover plies", unit: "deg", list: true, hint: "Lowest first: the plies laid over the filled cut." },
  { path: "cover.overlap", label: "Overlap past the widest cut", unit: "length" },
];
export const ADHESIVE_FIELDS: readonly RepairField[] = [
  { path: "adhesive.shear_modulus", label: "Shear modulus", unit: "stress" },
  { path: "adhesive.thickness", label: "Bondline thickness", unit: "length" },
  { path: "adhesive.shear_strength", label: "Shear strength", unit: "stress", optional: true, hint: "The stress at the adhesive's elastic limit. Without it no elastic limit load is given." },
  { path: "adhesive.poisson", label: "Poisson's ratio", optional: true, hint: "For the solve of the slice." },
  { path: "adhesive.peel_strength", label: "Peel strength", unit: "stress", optional: true, hint: "For the solve of the slice: with it the peel stress is judged, without it only reported." },
];
export const PANEL_FIELDS: readonly RepairField[] = [
  { path: "panel.length", label: "Panel length", unit: "length", hint: "Along the load." },
  { path: "panel.width", label: "Panel width", unit: "length" },
  { path: "applied.load", label: "Load per unit width", unit: "load", optional: true, hint: "Tension positive. Without it the repair is described and drawn, not worked." },
];
/** A ply material typed in full: every one of these, in the file's units. */
export const TYPED_MATERIAL_FIELDS: readonly { key: string; label: string; unit?: RepairUnitKind; text?: boolean }[] = [
  { key: "name", label: "Name", text: true }, { key: "E1", label: "E1, along the fibres", unit: "modulus" }, { key: "E2", label: "E2, across them", unit: "modulus" },
  { key: "G12", label: "G12", unit: "modulus" }, { key: "nu12", label: "ν12" }, { key: "ply_thickness", label: "Cured ply thickness", unit: "length" },
];
/** The ply strengths a typed material may state, all five or none: with them the solve checks which ply fails first. */
export const STRENGTH_FIELDS: readonly { key: string; label: string }[] = [
  { key: "F1t", label: "F1t" }, { key: "F1c", label: "F1c" }, { key: "F2t", label: "F2t" }, { key: "F2c", label: "F2c" }, { key: "F6", label: "F6" },
];
const TYPED_KEYS = [...TYPED_MATERIAL_FIELDS.map((f) => f.key), ...STRENGTH_FIELDS.map((f) => f.key)];
const LIBRARY_KEYS = ["library", "dataset"];

const isTable = (value: RepairValue | undefined): value is RepairDescription => typeof value === "object" && value !== null && !Array.isArray(value);
const tableOf = (repair: RepairDescription, name: string): RepairDescription => (isTable(repair[name]) ? (repair[name] as RepairDescription) : {});

/** How a table names its ply material: by the library, typed in full, or (the patch only) not at all, which is the laminate's. */
export function materialMode(repair: RepairDescription, table: "parent" | "patch"): "library" | "typed" | "laminate" {
  const stated = tableOf(repair, table);
  if (typeof stated.library === "string") return "library";
  return TYPED_KEYS.some((key) => key in stated) || table === "parent" ? "typed" : "laminate";
}

/** The description with a table's material named by the library: its typed constants leave the file, the rest of the table stays. */
export function withLibraryMaterial(repair: RepairDescription, table: "parent" | "patch", id: string): RepairDescription {
  const kept = Object.fromEntries(Object.entries(tableOf(repair, table)).filter(([key]) => !TYPED_KEYS.includes(key) && !LIBRARY_KEYS.includes(key)));
  return { ...repair, [table]: { library: id, ...kept } };
}

/** The description with a table's material to be typed in full: the library's name leaves the file and the constants wait to be typed,
 * so the engine says which are missing until they are. Nothing is guessed. */
export function withTypedMaterial(repair: RepairDescription, table: "parent" | "patch"): RepairDescription {
  const kept = Object.fromEntries(Object.entries(tableOf(repair, table)).filter(([key]) => !LIBRARY_KEYS.includes(key)));
  return { ...repair, [table]: { name: "", ...kept } };
}

/** The description with the patch of the laminate's own material: the patch's table keeps what is not a material's. */
export function withLaminateMaterial(repair: RepairDescription): RepairDescription {
  const kept = Object.fromEntries(Object.entries(tableOf(repair, "patch")).filter(([key]) => !TYPED_KEYS.includes(key) && !LIBRARY_KEYS.includes(key)
    && !["E3", "G13", "G23", "nu13", "nu23"].includes(key)));
  const out: RepairDescription = { ...repair, patch: kept };
  if (Object.keys(kept).length === 0) delete out.patch;
  return out;
}

/** The description as the other kind of repair. The laminate, the damage, the steps, the adhesive, the panel and the load stay; what
 * belongs to one kind alone is taken from that kind's example, since the two kinds state their patch differently: a patch bonded on
 * top lists its plies and its overlap and has no cover plies; a flush one needs neither. */
export function withKind(repair: RepairDescription, kind: RepairKind): RepairDescription {
  if (kindOf(repair) === kind) return repair;
  const { patch: _patch, cover: _cover, kind: _kind, ...rest } = repair;
  if (kind === "flush") return rest;
  const steps = tableOf(repair, "steps");
  const count = typeof steps.count === "number" ? steps.count : 1;
  const per = typeof steps.plies === "number" ? steps.plies : 1;
  const example = tableOf(EXTERNAL_REPAIR, "patch");
  const layup = Array.isArray(example.layup) && example.layup.length === count * per ? example.layup : Array.from({ length: Math.max(1, count * per) }, () => 0);
  // `kind` goes with the first keys, before the tables, so the saved file reads as the engine's example does
  const plain = Object.fromEntries(Object.entries(rest).filter(([, value]) => !isTable(value)));
  const tables = Object.fromEntries(Object.entries(rest).filter(([, value]) => isTable(value)));
  const out: RepairDescription = {};
  for (const [key, value] of Object.entries({ ...plain, kind: "external", ...tables })) {
    out[key] = value as RepairValue;
    if (key === "steps") out.patch = { layup, overlap: typeof steps.length === "number" ? steps.length : (example.overlap as number), shape: "round" };
  }
  if (!("patch" in out)) out.patch = { layup, overlap: example.overlap as number, shape: "round" };
  return out;
}

/** The repair as a repair file (TOML), which the engine reads back as the same description. */
export const repairToml = (repair: RepairDescription): string => wingToml(repair);

/** The file name a repair is saved under: its title in lower case with hyphens, or "repair". */
export function repairFileName(repair: RepairDescription, extension = "toml"): string {
  const title = typeof repair.title === "string" ? repair.title : "";
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  return `${slug || "repair"}.${extension}`;
}

/** Whether two descriptions are the same repair, value for value. */
export const sameRepair = (a: RepairDescription | null, b: RepairDescription | null): boolean => a !== null && b !== null && JSON.stringify(a) === JSON.stringify(b);

/** A layup as it is read aloud: "[45/0/−45/90]". */
export function layupText(angles: RepairValue | undefined): string {
  return Array.isArray(angles) ? `[${angles.map((a) => String(a).replace("-", "−")).join("/")}]` : "";
}

/** A stated value as the page prints it: a list of ply angles as a layup, a number as typed, a word as it is. */
function statedText(value: RepairValue | undefined, unit: string): string {
  if (value === undefined) return "";
  if (Array.isArray(value)) return `${layupText(value)}, ${value.length} ${value.length === 1 ? "ply" : "plies"}`;
  return `${String(value).replace(/^-/, "−")}${unit ? ` ${unit}` : ""}`;
}

/** A table's ply material as rows: the library's name, or the constants typed. */
function materialRows(repair: RepairDescription, table: "parent" | "patch", units: Record<RepairUnitKind, string>): [string, string][] {
  const stated = tableOf(repair, table);
  const mode = materialMode(repair, table);
  if (mode === "laminate") return [["Ply material", "The laminate's"]];
  const through = ["E3", "G13", "G23", "nu13", "nu23"].filter((key) => key in stated)
    .map((key): [string, string] => [key.replace("nu", "ν"), statedText(stated[key], key.startsWith("nu") ? "" : units.modulus)]);
  if (mode === "library") {
    const found = REPAIR_MATERIALS.find((m) => m.id === stated.library);
    return [["Ply material", found?.name ?? String(stated.library)], ...through];
  }
  const typed = TYPED_MATERIAL_FIELDS.filter((f) => f.key in stated).map((f): [string, string] => [f.label, statedText(stated[f.key], f.unit ? units[f.unit] : "")]);
  const strengths = STRENGTH_FIELDS.filter((f) => f.key in stated).map((f): [string, string] => [f.label, statedText(stated[f.key], units.stress)]);
  return [...typed, ...through, ...strengths];
}

/** What the description states, grouped as the page's steps are, for the report: every value as it was typed, with its unit. A value
 * left out is not listed, so the report says only what the file says. */
export function statedGroups(repair: RepairDescription): { title: string; rows: [string, string][] }[] {
  const kind = kindOf(repair), units = REPAIR_UNIT_LABELS[unitsOf(repair)];
  const rows = (fields: readonly RepairField[]): [string, string][] => fields.filter((f) => valueAt(repair, f.path) !== undefined)
    .map((f) => [f.label, statedText(valueAt(repair, f.path), f.unit && f.unit !== "deg" ? units[f.unit] : "")]);
  const kindWords = REPAIR_KINDS.find((k) => k.id === kind);
  const groups: { title: string; rows: [string, string][] }[] = [
    { title: "Repair", rows: [["Kind", kindWords ? kindWords.label : kind], ["Units", REPAIR_UNIT_WORDS[unitsOf(repair)]]] },
    { title: "Laminate", rows: [...materialRows(repair, "parent", units), ["Plies, bottom ply first", statedText(valueAt(repair, "parent.layup"), "")]] },
    { title: kind === "external" ? "Hole and steps" : "Damage and steps", rows: rows(DAMAGE_FIELDS[kind]) },
    { title: "Patch", rows: [...materialRows(repair, "patch", units), ...rows(kind === "external" ? EXTERNAL_PATCH_FIELDS : [FLUSH_PATCH_FIELD]),
      ...(kind === "external" && typeof valueAt(repair, "patch.shape") === "string" ? [["Shape", String(valueAt(repair, "patch.shape"))] as [string, string]] : [])] },
    ...(kind === "flush" && valueAt(repair, "cover.layup") !== undefined ? [{ title: "Cover plies", rows: rows(COVER_FIELDS) }] : []),
    { title: "Adhesive", rows: rows(ADHESIVE_FIELDS) },
    { title: "Panel and load", rows: rows(PANEL_FIELDS) },
  ];
  return groups.filter((g) => g.rows.length > 0);
}

// ----------------------------------------------------------------------------------------------- the engine's answer

export type RegionKind = "parent" | "patch" | "cover" | "adhesive";
/** One rectangle of the half slice (ADR-0131): `r` from the repair's middle, `z` from the laminate's bottom face, in the file's length. */
export type RepairRegion = { kind: RegionKind; name: string; r0: number; r1: number; z0: number; z1: number; angle: number | null; step: number | null };
export type LapStep = { name: string; length: number; patch_thickness: number; patch_modulus: number; laminate_thickness: number; laminate_modulus: number };
export type LapAnswer = {
  units: { force: string; stress: string; length: string };
  lambda_length: number[]; shared_forces: number[]; boundary_forces: number[]; shear_at_ends: [number, number][];
  peak_shear: { value: number; step: number; end: "start" | "end" };
  adherend_stresses: [number, number][]; elastic_limit_load?: number;
};
export type RepairReport = {
  units: { length: string; area: string; volume: string; modulus: string; force: string; stress: string };
  kind: RepairKind; patch_shape: "round" | "strip";
  sizes: { thickness: number; patch_thickness: number; depth: number; through: boolean; plies_removed: number; plies_left: number; cut_radii: number[];
    patch_diameter: number; repair_diameter: number };
  patch_layup: number[]; regions: RepairRegion[];
  areas: Record<RegionKind, number>; volumes: Record<RegionKind, number>; bond_lengths: Record<string, number>;
  lap: { ends_at_the_middle: boolean; steps: LapStep[]; load?: number; answer?: LapAnswer };
};
export type RepairViews = {
  half_length: number; outer: number; boundaries: { name: string; r: number }[];
  lap?: { r: number[]; shear: number[]; patch_force: number[] };
};
export type SolveNeed = { path: string; words: string };
export type RepairAnswer = { run_id: string | null; engine_version: string; repair: RepairDescription; report: RepairReport; views: RepairViews; needs: SolveNeed[] };

export type SlicePeak = { value: number; r: number; part: string };
export type SlicePly = { name: string; kind: RegionKind; angle: number; strength_ratio: number | null; mode: string | null; r: number | null; stress: number[] | null };
/** The solved slice (ADR-0132), as `slice_report` gives it in the file's units. */
export type SliceReport = {
  units: { length: string; stress: string; force: string }; load: number;
  model: { solver: string; element: string; elements: number; nodes: number; equations: number | null; seconds: number; element_size: number; fine_size: number;
    hold: string; cut_faces: "open" | "bonded" };
  checks: { equilibrium: number; far_field: number };
  bond: { peak_shear: SlicePeak; peak_peel: SlicePeak; mean_over: number;
    lines: { name: string; step: number | null; r: number[]; shear: number[]; peel: number[] }[];
    cut_faces: { name: string; step: number | null; normal: number; shear: number }[] };
  forces: { r: number[]; patch: number[]; laminate: number[]; adhesive: number[] };
  boundaries: { name: string; r: number; patch: number; laminate: number; adhesive: number; hand_patch: number }[];
  hand: { peak_shear: number; elastic_limit_load: number | null };
  elastic_limit_load: number | null; peel_limit_load: number | null; criterion: string;
  plies: SlicePly[]; first_ply: (SlicePly & { load: number }) | null; first: { what: "adhesive" | "peel" | "ply"; load: number } | null;
};
export type RepairSolve = { run_id: string | null; headline: string; report: SliceReport };
export type RepairShape = { run_id: string | null; step: string;
  parts: { title: string; units: { length: string; volume: string }; parts: { name: string; kind: RegionKind; angle: number | null; volume: number }[]; volumes: Record<RegionKind, number> } };

// ----------------------------------------------------------------------------------------------- words

export const PART_WORDS: Record<RegionKind, string> = { parent: "Laminate", patch: "Patch", cover: "Cover plies", adhesive: "Adhesive" };
/** What reaches its limit first as the load grows, in the solver tool's own words (anisotropy_fea.repair_model.FIRST_WORDS). */
export const FIRST_WORDS: Record<"adhesive" | "peel" | "ply", string> = {
  adhesive: "the adhesive reaches its elastic limit in shear", peel: "the bondline's peel stress reaches the peel strength", ply: "a ply reaches a strength",
};
export const CRITERION_WORDS: Record<string, string> = { max_stress: "maximum stress", tsai_hill: "Tsai-Hill" };
/** The sentence that stands beside every limit load of the adhesive (ADR-0130): it is not a strength. */
export const NOT_THE_STRENGTH = "Not the repair's strength: the adhesive yields before it fails.";

const lowerFirst = (text: string): string => (text ? text[0].toLowerCase() + text.slice(1) : text);
/** A name of the engine's inside a sentence: "Ledge of step 2" as "the ledge of step 2", "The whole patch" as "the whole patch",
 * "Adhesive on the floor" as "the adhesive on the floor"; a ply's name ("Laminate ply 6 (−45°)") keeps no article. */
export function inSentence(name: string): string {
  const text = name.replace(/\((-)/, "(−");
  if (/^The /.test(text)) return lowerFirst(text);
  return /^(Laminate|Patch|Cover) ply /.test(text) ? lowerFirst(text) : `the ${lowerFirst(text)}`;
}

/** A line of words closed as a sentence: the solver tool's headline ends without a full stop. */
export const sentence = (text: string): string => (/[.!?]$/.test(text.trim()) ? text.trim() : `${text.trim()}.`);

/** Where the hand calculation's largest shear stress is: an end of a step of the lap, the outer one toward the repair's edge. */
export function peakPlace(report: RepairReport): string {
  const answer = report.lap.answer;
  if (!answer) return "";
  const step = report.lap.steps[answer.peak_shear.step - 1];
  return `at the ${answer.peak_shear.end === "start" ? "outer" : "inner"} end of ${step ? inSentence(step.name) : "the lap"}`;
}

/** The hand calculation's answer in the page's short form: a heading, one sentence and a line of facts. No strength, no verdict
 * (ADR-0135): the largest shear stress in the adhesive under the stated load, and the load at its elastic limit. */
export function answerWords(report: RepairReport): { headline: string; detail: string; facts: string[] } {
  const u = report.units, sizes = report.sizes, lap = report.lap;
  const length = unitText(u.length);
  const what = report.kind === "external"
    ? `${report.patch_layup.length}-ply ${report.patch_shape === "strip" ? "strip" : "round"} patch on top, ${shown(sizes.patch_diameter)} ${length} ${report.patch_shape === "strip" ? "long" : "across"}`
    : `${sizes.plies_removed} ${sizes.plies_removed === 1 ? "ply" : "plies"} cut in ${sizes.cut_radii.length} ${sizes.cut_radii.length === 1 ? "step" : "steps"}${sizes.through ? ", through every ply" : ""}, ${shown(sizes.repair_diameter)} ${length} across`;
  const facts = [what, `laminate ${shown(sizes.thickness)} ${length} thick`];
  const answer = lap.answer;
  if (!answer || lap.load === undefined) {
    return { headline: "No load stated yet", detail: "The repair is described and drawn. State a load per unit width, under Panel and load, to work the bondline.", facts };
  }
  const stress = unitText(u.stress), force = unitText(u.force);
  const limit = answer.elastic_limit_load === undefined
    ? "The adhesive states no shear strength, so no elastic limit load is given."
    : `The adhesive reaches its elastic limit in shear at ${shown(answer.elastic_limit_load)} ${force}. ${NOT_THE_STRENGTH}`;
  return {
    headline: `Largest bondline shear ${shown(Math.abs(answer.peak_shear.value))} ${stress} under ${shown(lap.load)} ${force}`,
    detail: `By hand, ${peakPlace(report)}. ${limit}`,
    facts,
  };
}

/** What a solve of the slice still needs, as one sentence, or empty when it can be solved. */
export function needsWords(needs: readonly SolveNeed[]): string {
  if (!needs.length) return "";
  return `The solve of the slice still needs ${needs.map((n) => n.words).join("; ")}.`;
}

/** The model of a solved slice in one line: what was solved and how its two checks came out. The page names no tool (ADR-0091), so the
 * solver's own name, which the report holds as `model.solver`, is not said. */
export function modelWords(report: SliceReport): string {
  const m = report.model, length = unitText(report.units.length);
  return `Solved as ${m.elements.toLocaleString("en-US")} eight-node plane elements held flat${m.equations ? `, ${m.equations.toLocaleString("en-US")} equations` : ""}, `
    + `elements ${shown(m.fine_size, 3)} to ${shown(m.element_size, 3)} ${length} long, in ${shown(m.seconds, 2)} s. `
    + `The forces along the load add up to the load within ${report.checks.equilibrium.toExponential(1)} of it; far from the repair the strain is the laminate theory's within ${report.checks.far_field.toExponential(1)}.`;
}

/** The solved slice beside the hand calculation, as the lines the page lists: the bondline's two peaks, each a mean over a square of
 * adhesive (ADR-0132), the three limit loads there are, and what comes first. */
export function sliceWords(report: SliceReport): { shear: string; peel: string; limit: string; ply: string; first: string } {
  const u = report.units, stress = unitText(u.stress), force = unitText(u.force), length = unitText(u.length);
  const bond = report.bond;
  const where = (peak: SlicePeak) => `${shown(peak.r)} ${length} from the middle (${inSentence(peak.part)})`;
  return {
    shear: `Largest shear ${shown(Math.abs(bond.peak_shear.value))} ${stress}, ${where(bond.peak_shear)}; by hand ${shown(report.hand.peak_shear)} ${stress}.`,
    peel: `Largest peel ${shown(bond.peak_peel.value)} ${stress}, ${where(bond.peak_peel)}`
      + (report.peel_limit_load !== null ? `; it reaches the peel strength at ${shown(report.peel_limit_load)} ${force}.` : "; not judged: the adhesive states no peel strength."),
    limit: report.elastic_limit_load === null ? "The adhesive states no shear strength, so no elastic limit load is given."
      : `The adhesive reaches its elastic limit in shear at ${shown(report.elastic_limit_load)} ${force}; by hand ${shown(report.hand.elastic_limit_load)} ${force}. ${NOT_THE_STRENGTH}`,
    ply: report.first_ply === null ? "No ply is checked: the materials state no strengths."
      : `First ply by ${CRITERION_WORDS[report.criterion] ?? report.criterion}: ${inSentence(report.first_ply.name)}, ${report.first_ply.mode ?? ""}, at ${shown(report.first_ply.load)} ${force}`
        + (report.first_ply.r !== null ? `, ${shown(report.first_ply.r)} ${length} from the middle.` : "."),
    first: report.first === null ? "" : `First, ${FIRST_WORDS[report.first.what]}, at ${shown(report.first.load)} ${force}.`,
  };
}

/** What the analysis is not, said on the page and in the report (ADR-0130, ADR-0132): the same list wherever a number is read. */
export const LIMITS: readonly string[] = [
  "The hand calculation treats the patch and the laminate as bars joined by an adhesive in shear. It leaves out the peel stress, bending, and shear through the plies' thickness.",
  "The solved slice is one plane through the repair's middle, along the load, held flat. It does not hold the panel beside the repair, which carries load round it, and a panel free to bend would add bending.",
  "Both are elastic. The load at the adhesive's elastic limit is where the adhesive starts to yield, not where the repair fails.",
  "Largest bondline stresses in the slice are means over a square of adhesive as long as the bondline is thick: at a corner the stress itself grows with the mesh.",
  "Cure stresses, moisture, temperature, fatigue and the quality of the bond are not in either.",
];

export { shown, unitText, valueAt, withValue };
