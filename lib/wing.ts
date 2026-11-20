/** The wing workspace (ADR-0118): one wing description, the same one a wing file holds (ADR-0115), edited on the page and worked by
 * the engine's hand calculation on every change. Nothing here computes a result: the description is sent as it stands, the engine
 * reads it by its own rules and refuses what is wrong by name, and the page shows its numbers. What this file does is keep the
 * description (read a value, change one), say what each field is in the description's own units, write the description out as a
 * wing file, and word the engine's answer. */
import choices from "./wing-choices.json";

/** A wing description: the object a wing file's TOML reads as. Its tables and keys are the engine's (engine/src/anisotropy_engine/wing/wing_file.py). */
export type WingValue = string | number | boolean | WingValue[] | WingDescription;
export type WingDescription = { [key: string]: WingValue };

export const EXAMPLE_WING: WingDescription = choices.example as unknown as WingDescription;
export const WING_MATERIALS: readonly { id: string; name: string }[] = choices.materials;
export const WING_CORES: readonly { id: string; name: string }[] = choices.cores;

export type WingUnits = "SI" | "US";
export type UnitKind = "length" | "thickness" | "force" | "modulus" | "stress" | "density" | "altitude" | "moment" | "running_load"
  | "stiffness" | "mass" | "deflection";
/** The engine's labels for each kind in each system (wing_file.WING_UNITS); the page shows them, the engine converts. */
export const UNIT_LABELS: Record<WingUnits, Record<UnitKind, string>> = {
  SI: { length: "m", thickness: "mm", force: "N", modulus: "GPa", stress: "MPa", density: "kg/m³", altitude: "m", moment: "N·m",
        running_load: "N/m", stiffness: "N·m²", mass: "kg", deflection: "mm" },
  US: { length: "in", thickness: "in", force: "lb", modulus: "Msi", stress: "ksi", density: "lb/in³", altitude: "ft", moment: "lb·in",
        running_load: "lb/in", stiffness: "lb·in²", mass: "lb", deflection: "in" },
};
export const SPEED_UNITS = ["m/s", "km/h", "kt", "mph", "ft/s"] as const;

export function unitsOf(wing: WingDescription): WingUnits {
  return wing.units === "US" ? "US" : "SI";
}

// ----------------------------------------------------------------------------------------------- reading and changing values

const isTable = (value: WingValue | undefined): value is WingDescription => typeof value === "object" && value !== null && !Array.isArray(value);

/** The value at a dotted path ("envelope.speeds.cruise"), or undefined when a table or the key is not there. */
export function valueAt(wing: WingDescription, path: string): WingValue | undefined {
  let here: WingValue | undefined = wing;
  for (const key of path.split(".")) {
    if (!isTable(here)) return undefined;
    here = here[key];
  }
  return here;
}

/** A new description with the value at `path` set, the tables on the way made as needed; `undefined` removes the key, and a table
 * left empty by that goes too, so an emptied optional table (a gust, an aileron) leaves the file as if never written. */
export function withValue(wing: WingDescription, path: string, value: WingValue | undefined): WingDescription {
  const [key, ...rest] = path.split(".");
  const out: WingDescription = { ...wing };
  if (rest.length === 0) {
    if (value === undefined) delete out[key];
    else out[key] = value;
    return out;
  }
  const inner = withValue(isTable(wing[key]) ? wing[key] : {}, rest.join("."), value);
  if (Object.keys(inner).length === 0) delete out[key];
  else out[key] = inner;
  return out;
}

/** Numbers typed as a list ("0, 45, -45, 0" or "[0/45/-45/0]"), or null when one of them is not a number. */
export function readNumbers(text: string): number[] | null {
  const parts = text.replace(/[[\]]/g, " ").split(/[\s,/;]+/).filter(Boolean);
  if (!parts.length) return null;
  const numbers = parts.map((p) => Number(p.replace("−", "-")));
  return numbers.every(Number.isFinite) ? numbers : null;
}

/** A typed number, or null when the text is not one. A comma for the decimal point is read as one. */
export function readNumber(text: string): number | null {
  const cleaned = text.trim().replace("−", "-").replace(/^(-?\d+),(\d+)$/, "$1.$2");
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) ? value : null;
}

// ----------------------------------------------------------------------------------------------- the wing file

/** A key TOML takes bare, or the key quoted. */
function tomlKey(key: string): string {
  return /^[A-Za-z0-9_-]+$/.test(key) ? key : JSON.stringify(key);
}

function tomlValue(value: WingValue): string {
  if (typeof value === "string") return JSON.stringify(value); // a JSON string is a TOML basic string: the same escapes
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("A wing file holds finite numbers only");
    return String(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) return `[${value.map(tomlValue).join(", ")}]`;
  throw new Error("A table inside a list cannot be written");
}

/** The description as a wing file (TOML): the plain keys of each table first, then its tables, in the order they were written, so
 * the file reads as the engine's example does. The engine reads it back as the same description. */
export function wingToml(wing: WingDescription): string {
  const lines: string[] = [];
  const write = (table: WingDescription, path: string[]) => {
    const plain = Object.entries(table).filter(([, v]) => !isTable(v));
    const tables = Object.entries(table).filter(([, v]) => isTable(v)) as [string, WingDescription][];
    if (path.length && (plain.length || !tables.length)) {
      if (lines.length) lines.push("");
      lines.push(`[${path.map(tomlKey).join(".")}]`);
    }
    for (const [key, value] of plain) lines.push(`${tomlKey(key)} = ${tomlValue(value)}`);
    for (const [key, value] of tables) write(value, [...path, key]);
  };
  write(wing, []);
  return lines.join("\n") + "\n";
}

/** The file name a wing is saved under: its title in lower case with hyphens, or "wing". */
export function wingFileName(wing: WingDescription, extension = "toml"): string {
  const title = typeof wing.title === "string" ? wing.title : "";
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  return `${slug || "wing"}.${extension}`;
}

// ----------------------------------------------------------------------------------------------- the fields of each tab

/** A field of the setup: where its value sits in the description, what it is, and its unit kind (null for a pure number). A
 * `list` field holds numbers typed as a list; an `optional` one may be left empty, which removes it from the description. */
export type WingField = {
  path: string; label: string; hint?: string; unit?: UnitKind | "speed" | "area" | "per_rad" | "chord" | "deg"; optional?: boolean; list?: boolean;
};

export const GEOMETRY_FIELDS: readonly WingField[] = [
  { path: "geometry.half_span", label: "Half span", hint: "Root to tip of one side", unit: "length" },
  { path: "geometry.chord", label: "Chord", hint: "The same from root to tip", unit: "length" },
  { path: "geometry.front_spar", label: "Front spar", hint: "As a share of the chord: 0.25 is a quarter of the way back", unit: "chord" },
  { path: "geometry.rear_spar", label: "Rear spar", hint: "As a share of the chord", unit: "chord" },
  { path: "geometry.rib_spacing", label: "Rib spacing", hint: "Ribs at the root, every spacing outboard, and at the tip. Empty: no ribs", unit: "length", optional: true },
];

export const AERO_FIELDS: readonly WingField[] = [
  { path: "aerodynamics.aerodynamic_center", label: "Aerodynamic center", hint: "As a share of the chord", unit: "chord" },
  { path: "aerodynamics.pitching_moment_coefficient", label: "Pitching moment coefficient", hint: "About the aerodynamic center, nose up positive" },
  { path: "aerodynamics.lift_curve_slope", label: "Lift curve slope", hint: "The section's, per radian. Divergence and aileron reversal need it", unit: "per_rad", optional: true },
];

export const ENVELOPE_FIELDS: readonly WingField[] = [
  { path: "envelope.gross_weight", label: "Gross weight", hint: "The whole airplane", unit: "force" },
  { path: "envelope.positive_load_factor", label: "Positive load factor" },
  { path: "envelope.negative_load_factor", label: "Negative load factor" },
  { path: "envelope.altitudes", label: "Altitudes", hint: "Every case runs at each, for example 0, 3000", unit: "altitude", list: true },
  { path: "envelope.ultimate_factor", label: "Ultimate factor", hint: "Margins are at this times the limit load" },
  { path: "envelope.proof_factor", label: "Proof factor", hint: "Empty: no proof margins", optional: true },
  { path: "envelope.f12_star", label: "Tsai-Wu f₁₂*", hint: "Only for Tsai-Wu, between −1 and 1", optional: true },
];

export const SPEED_FIELDS: readonly WingField[] = [
  { path: "envelope.speeds.stall_flaps", label: "Stall, flaps extended", unit: "speed", optional: true },
  { path: "envelope.speeds.stall_clean", label: "Stall, flaps stowed", unit: "speed", optional: true },
  { path: "envelope.speeds.positive_maneuver", label: "Positive maneuver corner", unit: "speed", optional: true },
  { path: "envelope.speeds.negative_maneuver", label: "Negative maneuver corner", unit: "speed", optional: true },
  { path: "envelope.speeds.cruise", label: "Cruise", unit: "speed", optional: true },
  { path: "envelope.speeds.dive", label: "Dive", unit: "speed", optional: true },
  { path: "envelope.speeds.flutter", label: "Flutter clearance", unit: "speed", optional: true },
];

export const GUST_SPEED_FIELDS: readonly WingField[] = [
  { path: "envelope.gust.cruise_gust_speed", label: "Gust speed at cruise", unit: "speed" },
  { path: "envelope.gust.dive_gust_speed", label: "Gust speed at dive", unit: "speed" },
  { path: "envelope.gust.lift_curve_slope_per_rad", label: "Airplane lift curve slope", unit: "per_rad" },
  { path: "envelope.gust.wing_area", label: "Wing area", hint: "Both sides", unit: "area" },
];

export const GUST_FACTOR_FIELDS: readonly WingField[] = [
  { path: "envelope.gust.cruise_positive", label: "Load factor, cruise gust up" },
  { path: "envelope.gust.cruise_negative", label: "Load factor, cruise gust down" },
  { path: "envelope.gust.dive_positive", label: "Load factor, dive gust up" },
  { path: "envelope.gust.dive_negative", label: "Load factor, dive gust down" },
];

export const AILERON_FIELDS: readonly WingField[] = [
  { path: "envelope.aileron.span_start", label: "Inboard end", hint: "From the root", unit: "length" },
  { path: "envelope.aileron.span_end", label: "Outboard end", unit: "length" },
  { path: "envelope.aileron.down_delta_cl", label: "Δc_l, aileron down" },
  { path: "envelope.aileron.down_delta_cm", label: "Δc_m, aileron down" },
  { path: "envelope.aileron.up_delta_cl", label: "Δc_l, aileron up" },
  { path: "envelope.aileron.up_delta_cm", label: "Δc_m, aileron up" },
  { path: "envelope.aileron.roll_pull_up_fraction", label: "Roll pull-up", hint: "Share of the positive load factor the rolling pull-up flies at" },
];

export const OWN_MATERIAL_FIELDS: readonly WingField[] = [
  { path: "material.E1", label: "E₁", unit: "modulus" }, { path: "material.E2", label: "E₂", unit: "modulus" },
  { path: "material.G12", label: "G₁₂", unit: "modulus" }, { path: "material.nu12", label: "ν₁₂" },
  { path: "material.F1t", label: "F1t", unit: "stress" }, { path: "material.F1c", label: "F1c", unit: "stress" },
  { path: "material.F2t", label: "F2t", unit: "stress" }, { path: "material.F2c", label: "F2c", unit: "stress" },
  { path: "material.F6", label: "F6", unit: "stress" },
  { path: "material.ply_thickness", label: "Ply thickness", unit: "thickness" }, { path: "material.density", label: "Density", unit: "density" },
];

/** A typed material's fields with a blank for each, to fill in. */
export const OWN_MATERIAL_KEYS = ["name", ...OWN_MATERIAL_FIELDS.map((f) => f.path.split(".")[1])];

/** A field's unit as the page prints it, in the description's units and speed unit. */
export function unitLabel(wing: WingDescription, unit: WingField["unit"]): string {
  if (!unit) return "";
  const units = unitsOf(wing);
  if (unit === "speed") return String(valueAt(wing, "envelope.speed_unit") ?? "");
  if (unit === "area") return units === "US" ? "in²" : "m²";
  if (unit === "per_rad") return "per rad";
  if (unit === "chord") return "of the chord";
  if (unit === "deg") return "°";
  return UNIT_LABELS[units][unit];
}

/** A wing in the list of projects (ADR-0120): its size in a few words, as the description states it ("2 m half span, 0.45 m chord"). */
export function wingAbout(wing: WingDescription): string {
  const length = UNIT_LABELS[unitsOf(wing)].length;
  const part = (path: string, words: string) => {
    const value = valueAt(wing, path);
    return typeof value === "number" && Number.isFinite(value) ? `${shown(value)} ${length} ${words}` : null;
  };
  return [part("geometry.half_span", "half span"), part("geometry.chord", "chord")].filter(Boolean).join(", ") || "–";
}

/** A wing's material by its name: the library's, or the one typed in. */
export function wingMaterial(wing: WingDescription): string {
  const library = valueAt(wing, "material.library"), own = valueAt(wing, "material.name");
  if (typeof library === "string") return WING_MATERIALS.find((m) => m.id === library)?.name ?? library;
  return typeof own === "string" && own.trim() ? own : "–";
}

// ----------------------------------------------------------------------------------------------- the engine's answer

export type WingCheckName = "skin plies" | "spar plies" | "skin buckling" | "web buckling";
export const CHECK_NAMES: readonly WingCheckName[] = ["skin plies", "spar plies", "skin buckling", "web buckling"];
export const CHECK_WORDS: Record<WingCheckName, string> = {
  "skin plies": "Skin strength", "spar plies": "Spar web strength", "skin buckling": "Skin buckling", "web buckling": "Web buckling",
};

export type WingCheck = {
  strength_ratio: number | null; margin_ultimate: number | null; margin_proof: number | null; station: number | null; member: string | null;
  ply_angle: number | null; mode: string | null; point: [number, number] | null;
};
export type WingCase = {
  number: number; label: string; group: string; altitude: number; speed: number; load_factor: number; aileron: string | null;
  dynamic_pressure: number; root_shear: number; root_moment: number; root_torque: number; tip_deflection: number; tip_twist: number;
  checks: Record<WingCheckName, WingCheck>;
};
export type WingReport = {
  units: Record<string, string>; wing: string; passes: boolean; seconds: number;
  design: {
    mass: number; mass_skins: number; mass_spars: number; mass_core: number; bending_stiffness: number; torsion_stiffness: number;
    first_bending_frequency: number; skin_modulus: number; spar_modulus: number; skin_thickness: number; spar_thickness: number;
    skin_buckling_load: number; skin_widths: number[]; spar_heights: number[]; shear_center: number; shear_shares: number[];
    centroid: number[]; enclosed_area: number;
  };
  governing: { case: number; label: string; altitude: number; check: WingCheckName; margin_ultimate: number | null } | null;
  cases: WingCase[];
  aeroelastic: {
    divergence_speed: number | null; reversal_speed: number | null; dive_speed: number | null; divergence_over_dive: number | null;
    reversal_over_dive: number | null; divergence_never: boolean; reversal_never: boolean; needs: string[];
  } | null;
  not_run: { number: number; label: string; altitude: number; needs: string }[];
};
export type WingWall = { name: string; x: number[]; z: number[] };
export type WingViews = {
  half_span: number; chord: number;
  airfoil: { name: string; x: number[]; upper: number[]; lower: number[] };
  walls: WingWall[]; spars: number[]; spar_heights: number[]; shear_center: number; centroid: number[]; ribs: number[]; stations: number[];
  cases: {
    number: number; altitude: number; margins: Record<WingCheckName, (number | null)[]>; deflection: (number | null)[]; twist: (number | null)[];
    root: { name: string; load: (number | null)[]; shear_flow: (number | null)[] }[];
  }[];
};
export type WingAnswer = { run_id: string | null; engine_version: string; wing: WingDescription; report: WingReport; views: WingViews };
/** A part of the wing's shape for a CAD program (ADR-0116): the thickness to thicken its surface to, in the file's units. */
export type WingShapePart = { name: string; layup: string; thickness: number | null; area: number; mass: number | null };
/** The wing's STEP file and its part table (ADR-0118), as the API sends them. */
export type WingShape = {
  run_id: string | null;
  step: string;
  parts: { wing: string; units: { thickness: string; area: string; mass: string; step: string }; parts: WingShapePart[]; mass: number | null };
};

/** A margin as the page prints it: a sign and three decimals, or a dash for a check nothing loads. */
export function marginText(margin: number | null | undefined): string {
  if (margin === null || margin === undefined || !Number.isFinite(margin)) return "–";
  return `${margin >= 0 ? "+" : "−"}${Math.abs(margin).toFixed(3)}`;
}

/** A value to a few significant digits, as the page prints a result; the engine's number in full stays in the answer. */
export function shown(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "–";
  if (value !== 0 && (Math.abs(value) >= 1e6 || Math.abs(value) < 1e-3)) {
    const [mantissa, exponent] = value.toExponential(digits - 1).split("e");
    return `${mantissa} × 10${superscript(Number(exponent))}`;
  }
  return Number(value.toPrecision(digits)).toLocaleString("en-US", { maximumFractionDigits: 6 }).replace("-", "−");
}

function superscript(n: number): string {
  const digits = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  return `${n < 0 ? "⁻" : ""}${String(Math.abs(n)).split("").map((d) => digits[Number(d)]).join("")}`;
}

/** An engine unit label as the page prints it: "N*m^2" as "N·m²". */
export const unitText = (label: string): string => label.replace(/\*/g, "·").replace("^2", "²").replace("^3", "³");

/** Where a check governs, in words: the part, the station and, for a ply check, the ply, how it fails and the point on the section. */
export function whereWords(check: WingCheck, units: Record<string, string>): string {
  const parts: string[] = [];
  if (check.member) parts.push(check.member);
  if (check.station !== null) parts.push(check.station === 0 ? "at the root" : `${shown(check.station, 3)} ${unitText(units.length)} from the root`);
  if (check.ply_angle !== null) parts.push(`${check.ply_angle}° ply`);
  if (check.mode) parts.push(check.mode.replace(/_/g, " "));
  if (check.point) parts.push(`${shown(check.point[0], 3)} ${unitText(units.length)} from the leading edge`);
  return parts.join(", ");
}

/** The answer in one line and its facts, worded from the engine's report: what governs, where, and in which case. */
export function answerWords(report: WingReport): { verdict: string; detail: string; facts: string[] } {
  const ran = report.cases.length;
  const waiting = report.not_run.length;
  if (!report.governing || !ran) {
    return { verdict: "No case could run yet", detail: "Every case still needs a value. The list under the results says which.", facts: [] };
  }
  const g = report.governing;
  const governing = report.cases.find((c) => c.number === g.case && c.altitude === g.altitude);
  const check = governing?.checks[g.check];
  const failing = report.cases.filter((c) => CHECK_NAMES.some((n) => (c.checks[n].margin_ultimate ?? 0) < 0)).length;
  const verdict = report.passes ? `Passes the ${ran} case${ran === 1 ? "" : "s"} run` : `Fails ${failing} of the ${ran} case${ran === 1 ? "" : "s"} run`;
  const detail = `Lowest margin ${marginText(g.margin_ultimate)}: ${CHECK_WORDS[g.check].toLowerCase()}${check ? `, ${whereWords(check, report.units)}` : ""}, case ${g.case} (${g.label}).`;
  const facts = [`${ran} case${ran === 1 ? "" : "s"} run`];
  if (waiting) facts.push(`${waiting} waiting for inputs`);
  return { verdict, detail, facts };
}

// ------------------------------------------------------------------------------- the finite element check (ADR-0119)

/** One value by the hand calculation and by the finite element model. */
export type HandAndModel = { hand: number | null; fe: number | null };
/** Where a lowest margin is: the case, the check and, for the model's, the part, the point and the ply. */
export type FeWhere = {
  case: number; label: string; altitude: number; check: string; margin_ultimate: number | null;
  part?: string | null; station?: number | null; chord?: number | null; ply_angle?: number | null; mode?: string | null;
};
/** The check's report as the API sends it, in the wing file's units: the model's numbers beside the hand calculation's. */
export type WingFeReport = {
  wing: string;
  units: Record<string, string>;
  model: { elements: number; nodes: number; element_size: number; skins: string; equations: number | null };
  seconds: { build: number; static: number; modes: number; total: number };
  root_zone: number;
  lowest: FeWhere; lowest_hand: FeWhere; lowest_root: FeWhere;
  cases: { number: number; label: string; altitude: number; tip_deflection: HandAndModel; tip_twist: HandAndModel; skin: HandAndModel;
    spar: HandAndModel; rib: number | null; core: number | null; root: HandAndModel }[];
  not_run: number;
  modes: { number: number; frequency: number; kind: string; part: string }[];
  beam: { shear_center: HandAndModel; torsion_stiffness: HandAndModel; first_bending_frequency: HandAndModel; mass_per_length: number; center_of_mass: number };
  divergence_speed: HandAndModel | null;
  flutter: null | { required: number | null; airspeed: string; bending_frequency: number; torsion_frequency: number;
    altitudes: { altitude: number; speed: number | null; frequency: number | null; times_required: number | null }[] };
  buckling: { case: number; label: string; altitude: number; part: string; station: number; factor: number; margin_ultimate: number | null;
    hand_skin: number | null; hand_web: number | null }[];
};
export type FeCheckState = "queued" | "running" | "done" | "stopped" | "refused";
/** The check as it stands, as the API sends it. */
export type WingFeCheck = {
  job_id: string; state: FeCheckState; wing: string | null; started_at: string; finished_at: string | null; stage: string | null;
  stages_done: string[]; stages: string[]; message: string | null; run_id: string | null; report: WingFeReport | null;
};

/** The check's steps in words, by the tool's names for them. */
export const FE_STAGES: Record<string, string> = { build: "Building the model", solve: "Solving the flight loads", modes: "Vibration modes and flutter" };
/** The model's checks in words. */
export const FE_CHECK_WORDS: Record<string, string> = {
  "skin plies": "skin strength", "spar plies": "spar web strength", "rib plies": "rib strength", "core shear": "core shear",
};
/** What a stop says when the service sends no words of its own. */
export const FE_STOPPED = "The check could not be finished. Start it again; if it keeps failing, contact us.";

/** Where the check stands, in one line. */
export function feProgress(check: WingFeCheck): string {
  if (check.state === "queued") return "Waiting to start…";
  if (check.state === "running") {
    const at = check.stage ? check.stages.indexOf(check.stage) : -1;
    return check.stage && at >= 0 ? `${FE_STAGES[check.stage] ?? "Working"} (${at + 1} of ${check.stages.length})…` : "Starting…";
  }
  if (check.state === "done" && check.report) return `Checked in ${Math.max(1, Math.round(check.report.seconds.total))} s.`;
  return check.message ?? FE_STOPPED;
}

/** Where one of the model's lowest margins is, in words: the part, the point, the ply and how it fails. */
export function feWhereWords(where: FeWhere, units: Record<string, string>): string {
  const parts: string[] = [];
  if (where.part) parts.push(where.part.toLowerCase());
  if (where.station !== null && where.station !== undefined) parts.push(`${shown(where.station, 3)} ${unitText(units.length)} from the root`);
  if (where.chord !== null && where.chord !== undefined) parts.push(`${shown(where.chord, 3)} ${unitText(units.length)} from the leading edge`);
  if (where.ply_angle !== null && where.ply_angle !== undefined) parts.push(`${where.ply_angle}° ply`);
  if (where.mode && where.mode !== where.check) parts.push(where.mode.replace(/_/g, " "));
  return parts.join(", ");
}

/** The check in a few lines, from its report: the lowest margin by the model and by the hand calculation, where the model's is, and
 * what the model says at the root itself, where its clamp raises the stresses. Every number is the report's. */
export function feWords(report: WingFeReport): { headline: string; where: string; root: string } {
  const fe = report.lowest, hand = report.lowest_hand, root = report.lowest_root;
  const length = unitText(report.units.length);
  return {
    headline: `Lowest margin ${marginText(fe.margin_ultimate)} by the finite element model, ${marginText(hand.margin_ultimate)} by the hand calculation.`,
    where: `The model's: ${FE_CHECK_WORDS[fe.check] ?? fe.check}, ${feWhereWords(fe, report.units)}, case ${fe.case} (${fe.label}). `
      + `Both are read from ${shown(report.root_zone, 3)} ${length} out, one web height from the root.`,
    root: `The model holds the root fully clamped, which raises the stresses within about one web height of it; a real root gives a little. `
      + `At the root itself the model's lowest is ${marginText(root.margin_ultimate)} (${FE_CHECK_WORDS[root.check] ?? root.check}, ${(root.part ?? "").toLowerCase()}, case ${root.case}).`,
  };
}

/** The hand calculation's and the model's values side by side, as a cell prints them: a narrow cell breaks after the dot. */
export function handAndModel(pair: HandAndModel, print: (value: number | null) => string): string {
  return `${print(pair.hand)}\u00a0· ${print(pair.fe)}`;
}
