/**
 * The chat's laminate problems (ADR-0060; ADR-0055 amendment 2): the hand-calculation kind, a stack under loads per unit width
 * with no coupon around it. The chat asks for the units the problem is stated in, the material, the layup and the loads, reads
 * typed values with fixed patterns, and sends every value with the unit it was typed in. Nothing here converts a unit or computes
 * a laminate quantity: the API converts with the engine's table and the engine solves (ADR-0001, ADR-0002).
 */
import unitTable from "../engine/src/anisotropy_engine/data/units.json";
import { expandLayup } from "./layup";
import { libraryOptions } from "./studio-form";

export type Dimension = "pressure" | "length" | "force_per_length" | "moment_per_length";
export type ReportUnits = "SI" | "mm-MPa" | "US" | "psi";
export type Kind = "modulus" | "stress" | "length" | "N" | "M";
export const LOAD_NAMES = ["Nx", "Ny", "Nxy", "Mx", "My", "Mxy"] as const;
export type LoadName = (typeof LOAD_NAMES)[number];
export const CONSTANT_NAMES = ["E1", "E2", "G12", "nu12", "F1t", "F1c", "F2t", "F2c", "F6"] as const;
export type ConstantName = (typeof CONSTANT_NAMES)[number];
export const STRENGTH_NAMES: ConstantName[] = ["F1t", "F1c", "F2t", "F2c", "F6"];

/** The unit names the engine's table lists, by dimension (engine/src/anisotropy_engine/data/units.json, held equal to the table). */
export const UNIT_NAMES = unitTable.units as Record<Dimension, string[]>;
export const KIND_DIMENSION = unitTable.kinds as Record<Kind, Dimension>;
const SYSTEM_UNITS = unitTable.systems as Record<ReportUnits, Record<string, string>>;
export const REPORT_SYSTEMS: { id: ReportUnits; title: string; detail: string }[] = [
  { id: "SI", title: "SI", detail: "GPa, MPa, mm, N/m" },
  { id: "mm-MPa", title: "mm, N and MPa", detail: "MPa, mm, N/mm, N·mm/mm; the units the coupon decks use" },
  { id: "US", title: "US customary", detail: "Msi, ksi, in, lb/in" },
  { id: "psi", title: "psi and inches", detail: "psi, in, lb/in" },
];
export const SYSTEM_IDS = REPORT_SYSTEMS.map((s) => s.id);
export const isReportUnits = (value: string): value is ReportUnits => (SYSTEM_IDS as string[]).includes(value);

/** The unit a reporting system uses for a kind, from the engine's table. */
export function systemUnit(system: ReportUnits, kind: Kind | "kappa" | "A" | "B" | "D" | "areal_mass"): string {
  return SYSTEM_UNITS[system][kind];
}
export const dimensionOf = (kind: Kind): Dimension => KIND_DIMENSION[kind];
export const unitsOf = (kind: Kind): string[] => UNIT_NAMES[dimensionOf(kind)];
/** A unit name as the page prints it: the engine writes N*m/m, the page N·m/m. */
export const printedUnit = (unit: string) => unit.replace(/\*/g, "·").replace("^2", "²").replace("10^6 ", "10⁶ ").replace("10^3 ", "10³ ");

const squashUnit = (text: string) => text.toLowerCase().replace(/[·×]/g, "*").replace(/\s+/g, "").replace(/lbf/g, "lb").replace(/-/g, "/");
const UNIT_SYNONYMS: Record<string, string> = { "n/mm": "N/mm", "nmm/mm": "N*mm/mm", "nm/m": "N*m/m", "knm/m": "kN*m/m", "lbin/in": "lb*in/in", "kipin/in": "kip*in/in", "inch": "in", "inches": "in" };

/** The canonical name of a typed unit of one dimension, or null: `gpa` is GPa, `N·mm/mm` is N*mm/mm, `lbf/in` is lb/in. */
export function unitNamed(dimension: Dimension, typed: string): string | null {
  const wanted = squashUnit(typed);
  const alias = UNIT_SYNONYMS[wanted.replace(/\*/g, "")];
  for (const name of UNIT_NAMES[dimension]) {
    if (squashUnit(name) === wanted || name === alias) return name;
  }
  return null;
}

export type Quantity = { value: string; unit: string };
export type OwnConstants = { name: string; source: string } & Record<ConstantName, Quantity | string>;
export type Material = { library: string } | { own: OwnConstants };
export type LaminateDraft = {
  system: ReportUnits | "";
  material: Material | null;
  layup: { notation: string; angles: number[]; symmetric: boolean } | null;
  thickness: Quantity | null;
  loads: Record<LoadName, Quantity> | null;
  f12_star: string;
  /** Maximum strain with limits derived from the strengths (strength over modulus, linear to failure, ADR-0021): a stated choice. */
  strain_limits: boolean;
};
export type LaminateStep = "units" | "material" | "layup" | "loads" | "review";
export const STEP_ORDER: LaminateStep[] = ["units", "material", "layup", "loads", "review"];

export function blankDraft(): LaminateDraft {
  return { system: "", material: null, layup: null, thickness: null, loads: null, f12_star: "", strain_limits: false };
}

export const libraryThicknessOf = (id: string): number | null => libraryOptions.find((m) => m.id === id)?.thickness ?? null;
export const libraryNameOf = (id: string): string => libraryOptions.find((m) => m.id === id)?.name ?? id;

/** The rows a step still needs; the API and the engine judge the values themselves. */
export function missingIn(step: LaminateStep, draft: LaminateDraft): string[] {
  switch (step) {
    case "units": return draft.system ? [] : ["units"];
    case "material": {
      if (!draft.material) return ["material"];
      if ("library" in draft.material) return [];
      const own = draft.material.own;
      return (["E1", "E2", "G12", "nu12"] as ConstantName[]).filter((k) => !filledConstant(own[k]));
    }
    case "layup": {
      if (!draft.layup) return ["layup"];
      const fromLibrary = draft.material && "library" in draft.material && libraryThicknessOf(draft.material.library) !== null;
      return fromLibrary || (draft.thickness && draft.thickness.value.trim()) ? [] : ["ply thickness"];
    }
    case "loads": return draft.loads && LOAD_NAMES.every((n) => draft.loads![n].value.trim() !== "") ? [] : ["loads"];
    case "review": return [];
  }
}
const filledConstant = (q: Quantity | string | undefined) => (typeof q === "string" ? q.trim() !== "" : !!q && q.value.trim() !== "");

export function nextStep(draft: LaminateDraft): LaminateStep {
  for (const step of STEP_ORDER) if (missingIn(step, draft).length) return step;
  return "review";
}

// ----------------------------------------------------------------------------------------------- reading typed messages

const SIGNED = String.raw`([-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?)`;
const UNIT = String.raw`([A-Za-z][A-Za-z0-9*·×^/]*(?:/[A-Za-z0-9^]+)?)?`;

/** Which system a message names: "SI", "US", "psi" or the millimetre system; null when none. */
export function readSystem(text: string): ReportUnits | null {
  const t = ` ${text.toLowerCase()} `;
  if (/\bmm[\s,-]*(n|mpa)\b|\bmpa[\s,-]*mm\b|millimet|\bmm system\b/.test(t)) return "mm-MPa";
  if (/\bpsi\b/.test(t) && !/\bksi\b|\bmsi\b/.test(t)) return "psi";
  if (/\bus\b|customary|imperial|\binch(es)?\b|\bksi\b|\bmsi\b/.test(t)) return "US";
  if (/\bsi\b|metric/.test(t)) return "SI";
  return null;
}

/** The dimension a typed unit belongs to, if it is a unit at all. */
function dimensionNamed(typed: string): Dimension | null {
  return (Object.keys(UNIT_NAMES) as Dimension[]).find((d) => unitNamed(d, typed) !== null) ?? null;
}

/** A number followed by a unit of the kind, or by no unit: then the system's unit for that kind. Null when the word after the
 * number is a unit of another dimension (a length where a modulus belongs); a word that is no unit at all is the next word. */
function quantityFrom(value: string, typedUnit: string | undefined, kind: Kind, system: ReportUnits): Quantity | null {
  const unit = typedUnit ? unitNamed(dimensionOf(kind), typedUnit) : null;
  if (unit) return { value, unit };
  if (typedUnit && dimensionNamed(typedUnit) !== null) return null;
  return { value, unit: systemUnit(system, kind) };
}

const CONSTANT_PATTERNS: Record<ConstantName, string> = {
  E1: String.raw`e[_\s]?1\b|e₁`, E2: String.raw`e[_\s]?2\b|e₂`, G12: String.raw`g[_\s]?12\b|g₁₂`, nu12: String.raw`(?:nu|ν|v|poisson'?s?(?:\s*ratio)?)[_\s]?(?:12|₁₂)?\b`,
  F1t: String.raw`f[_\s]?1t\b|x[_\s]?t\b`, F1c: String.raw`f[_\s]?1c\b|x[_\s]?c\b`, F2t: String.raw`f[_\s]?2t\b|y[_\s]?t\b`, F2c: String.raw`f[_\s]?2c\b|y[_\s]?c\b`, F6: String.raw`f[_\s]?6\b|f[_\s]?12\b`,
};
const KIND_OF_CONSTANT: Record<ConstantName, Kind | null> = { E1: "modulus", E2: "modulus", G12: "modulus", nu12: null, F1t: "stress", F1c: "stress", F2t: "stress", F2c: "stress", F6: "stress" };

/** The material constants a message states, each with its typed unit or the system's: "E1 147 GPa, E2 10300 MPa, nu12 0.27, F1t 2280 MPa". */
export function readConstants(text: string, system: ReportUnits): { constants: Partial<Record<ConstantName, Quantity | string>>; understood: string[]; refused: string[] } {
  const constants: Partial<Record<ConstantName, Quantity | string>> = {};
  const understood: string[] = [];
  const refused: string[] = [];
  for (const name of CONSTANT_NAMES) {
    const match = new RegExp(String.raw`(?:^|[\s,;(])(?:${CONSTANT_PATTERNS[name]})\s*(?:=|:|of|is)?\s*${SIGNED}\s*${UNIT}`, "i").exec(text);
    if (!match) continue;
    const kind = KIND_OF_CONSTANT[name];
    if (kind === null) { constants[name] = match[1]; understood.push(`${name} ${match[1]}`); continue; }
    const quantity = quantityFrom(match[1], match[2], kind, system);
    if (!quantity) { refused.push(`${name}: ${match[2]} is not a ${kind} unit`); continue; }
    constants[name] = quantity;
    understood.push(`${name} ${quantity.value} ${printedUnit(quantity.unit)}`);
  }
  return { constants, understood, refused };
}

const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

/** A library material named in a message, by id or name, the longest id first so "as4-8552" is not "as4-3501". */
export function readLibraryMaterial(text: string): string | null {
  const squashed = squash(text);
  return [...libraryOptions].sort((a, b) => b.id.length - a.id.length).find((m) => squashed.includes(squash(m.id)) || squashed.includes(squash(m.name)))?.id ?? null;
}

/** A layup in laminate notation and a ply thickness, "[0/45/-45/90]s, 0.125 mm plies" or "ply thickness 0.0049 in". */
export function readLayupLine(text: string, system: ReportUnits): { layup: LaminateDraft["layup"] | null; thickness: Quantity | null; understood: string[]; refused: string[] } {
  const understood: string[] = [];
  const refused: string[] = [];
  let layup: LaminateDraft["layup"] | null = null;
  const notation = text.match(/\[[^\]]+\]\s*\d*\s*s?/i)?.[0].replace(/\s+/g, "");
  if (notation) {
    const expanded = expandLayup(notation);
    if (expanded.layup) {
      layup = { notation, angles: expanded.layup.angles, symmetric: expanded.layup.symmetric };
      understood.push(`layup ${notation} (${expanded.layup.angles.length} plies)`);
    } else refused.push(expanded.error);
  }
  let thickness: Quantity | null = null;
  const t = text.replace(/\[[^\]]*\]\s*\d*\s*s?/i, " ");
  const match = new RegExp(String.raw`${SIGNED}\s*${UNIT}\s*(?:per\s*|thick\s*)?(?:ply|plies)\b|(?:ply|cured)\s*thickness\s*(?:of|=|:)?\s*${SIGNED}\s*${UNIT}|(?:plies|ply)\s*(?:of|=|:)?\s*${SIGNED}\s*${UNIT}`, "i").exec(t);
  if (match) {
    const value = match[1] ?? match[3] ?? match[5];
    const unit = match[1] !== undefined ? match[2] : match[3] !== undefined ? match[4] : match[6];
    const quantity = quantityFrom(value, unit, "length", system);
    if (quantity) { thickness = quantity; understood.push(`ply thickness ${quantity.value} ${printedUnit(quantity.unit)}`); }
    else refused.push(`ply thickness: ${unit} is not a length unit`);
  }
  return { layup, thickness, understood, refused };
}

/** The loads a message states, each with its typed unit or the system's: "Nx = 100 N/mm, Ny 50, everything else zero". */
export function readLoads(text: string, system: ReportUnits): { loads: Partial<Record<LoadName, Quantity>>; othersZero: boolean; understood: string[]; refused: string[] } {
  const loads: Partial<Record<LoadName, Quantity>> = {};
  const understood: string[] = [];
  const refused: string[] = [];
  for (const name of LOAD_NAMES) {
    const sub = name.slice(1).split("").join("[_\\s]?");
    const match = new RegExp(String.raw`(?:^|[\s,;(])${name[0]}[_\s]?${sub}\b\s*(?:=|:|of|is)?\s*${SIGNED}\s*${UNIT}`, "i").exec(text);
    if (!match) continue;
    const kind: Kind = name.startsWith("N") ? "N" : "M";
    const quantity = quantityFrom(match[1], match[2], kind, system);
    if (!quantity) { refused.push(`${name}: ${match[2]} is not a ${kind === "N" ? "force per width" : "moment per width"} unit`); continue; }
    loads[name] = quantity;
    understood.push(`${name} ${quantity.value} ${printedUnit(quantity.unit)}`);
  }
  const othersZero = /(everything|all|the rest|rest|others?|other loads|else)\s+(else\s+)?(is\s+|are\s+)?(zero|0)\b|\bonly\b/i.test(text) && Object.keys(loads).length > 0;
  if (othersZero) understood.push("the other loads are zero");
  return { loads, othersZero, understood, refused };
}

/** Six loads from the ones stated, the rest zero in the system's units, for a click or an "everything else zero". */
export function loadsWithZeros(given: Partial<Record<LoadName, Quantity>>, system: ReportUnits): Record<LoadName, Quantity> {
  return Object.fromEntries(LOAD_NAMES.map((name) => [name, given[name] ?? { value: "0", unit: systemUnit(system, name.startsWith("N") ? "N" : "M") }])) as Record<LoadName, Quantity>;
}

// ----------------------------------------------------------------------------------------------- the problem the API takes

export type QuantityJson = { value: number; unit: string };
export type LaminateProblem = {
  title?: string;
  material: ({ library: string } | { name: string; E1: QuantityJson; E2: QuantityJson; G12: QuantityJson; nu12: number; source?: string }
    & Partial<Record<"F1t" | "F1c" | "F2t" | "F2c" | "F6", QuantityJson>>) & { strain_limits?: "from-strengths" };
  layup: number[];
  layup_notation?: string;
  ply_thickness?: QuantityJson;
  loads: Record<LoadName, QuantityJson>;
  f12_star?: number;
  report_units: ReportUnits;
};

const NUMBER = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i;

/** The problem as the API takes it, every value a number with the unit it was typed in; or what is wrong, by row. The browser
 * converts nothing (ADR-0002) and fills nothing in (ADR-0003). */
export function buildProblem(draft: LaminateDraft, reportUnits?: ReportUnits): { problem: LaminateProblem; errors?: never } | { problem?: never; errors: string[] } {
  const errors: string[] = [];
  const number = (text: string, row: string): number => {
    const value = text.trim();
    if (!value) { errors.push(`${row}: required`); return NaN; }
    if (!NUMBER.test(value) || !Number.isFinite(Number(value))) { errors.push(`${row}: ${JSON.stringify(value)} is not a number`); return NaN; }
    return Number(value);
  };
  const quantity = (q: Quantity | string | undefined, row: string): QuantityJson => {
    if (!q || typeof q === "string") { errors.push(`${row}: required`); return { value: NaN, unit: "" }; }
    if (!q.unit) errors.push(`${row}: pick a unit`);
    return { value: number(q.value, row), unit: q.unit };
  };
  if (!draft.system) errors.push("units: pick the system the problem is stated in");
  const system = reportUnits ?? (draft.system || "SI");
  let material: LaminateProblem["material"];
  const limits = draft.strain_limits ? { strain_limits: "from-strengths" as const } : {};
  if (!draft.material) { errors.push("material: required"); material = { library: "" }; }
  else if ("library" in draft.material) material = { library: draft.material.library, ...limits };
  else {
    const own = draft.material.own;
    const strengths = STRENGTH_NAMES.filter((k) => filledConstant(own[k]));
    if (strengths.length && strengths.length !== 5) errors.push(`strengths: give all five (F1t, F1c, F2t, F2c, F6) or none; ${strengths.join(", ")} given`);
    if (draft.strain_limits && strengths.length !== 5) errors.push("strain limits: maximum strain needs all five strengths to derive its limits from");
    material = {
      name: own.name.trim() || "typed in the chat", E1: quantity(own.E1, "E1"), E2: quantity(own.E2, "E2"), G12: quantity(own.G12, "G12"),
      nu12: number(typeof own.nu12 === "string" ? own.nu12 : own.nu12?.value ?? "", "nu12"),
      ...(own.source.trim() ? { source: own.source.trim() } : {}),
      ...(strengths.length === 5 ? Object.fromEntries(STRENGTH_NAMES.map((k) => [k, quantity(own[k], k)])) : {}),
      ...limits,
    };
  }
  if (!draft.layup) errors.push("layup: required");
  const loads = draft.loads;
  if (!loads) errors.push("loads: required");
  const problem: LaminateProblem = {
    material, layup: draft.layup?.angles ?? [], ...(draft.layup ? { layup_notation: draft.layup.notation } : {}),
    ...(draft.thickness && draft.thickness.value.trim() ? { ply_thickness: quantity(draft.thickness, "ply thickness") } : {}),
    loads: Object.fromEntries(LOAD_NAMES.map((name) => [name, loads ? quantity(loads[name], name) : { value: NaN, unit: "" }])) as Record<LoadName, QuantityJson>,
    ...(draft.f12_star.trim() ? { f12_star: number(draft.f12_star, "f12*") } : {}),
    report_units: system,
  };
  if (draft.layup) problem.title = `${draft.layup.notation} under ${LOAD_NAMES.filter((n) => loads && Number(loads[n].value) !== 0).map((n) => `${n} = ${loads![n].value} ${printedUnit(loads![n].unit)}`).join(", ") || "no load"}`;
  return errors.length ? { errors } : { problem };
}

/** The problem in a line each, for the card beside the chat: only what is stated. */
export function problemLines(draft: LaminateDraft): [string, string][] {
  const material = !draft.material ? "" : "library" in draft.material ? libraryNameOf(draft.material.library)
    : [draft.material.own.name.trim() || "own constants", ...(["E1", "E2", "G12"] as ConstantName[]).map((k) => {
      const q = draft.material && "own" in draft.material ? draft.material.own[k] : undefined;
      return q && typeof q !== "string" && q.value ? `${k} ${q.value} ${printedUnit(q.unit)}` : "";
    }).filter(Boolean)].join(", ");
  const recorded = draft.material && "library" in draft.material ? libraryThicknessOf(draft.material.library) : null;
  const thickness = draft.thickness?.value ? `${draft.thickness.value} ${printedUnit(draft.thickness.unit)} plies`
    : recorded !== null ? `${Number(recorded.toPrecision(4))} mm plies (library)` : "";
  const loads = draft.loads ? LOAD_NAMES.filter((n) => draft.loads![n].value.trim() && Number(draft.loads![n].value) !== 0).map((n) => `${n} = ${draft.loads![n].value} ${printedUnit(draft.loads![n].unit)}`).join(", ") || "no load" : "";
  return [
    ["Units", draft.system ? REPORT_SYSTEMS.find((s) => s.id === draft.system)?.title ?? draft.system : ""],
    ["Material", material],
    ["Layup", draft.layup ? `${draft.layup.notation}, ${draft.layup.angles.length} plies${thickness ? `, ${thickness}` : ""}` : ""],
    ["Loads", loads],
  ];
}
