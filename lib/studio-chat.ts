/**
 * The studio's guided chat (ADR-0055): the order of its questions, the words it reads out of a typed message, and the laminate
 * notation it understands. It only fills the same form rows the full form fills; nothing here judges a value or computes a result:
 * `intake.check_form` does, through the setup check (ADR-0001, ADR-0003). A message that names nothing it can read changes nothing.
 */
import {
  BENDING_TESTS, blankForm, DEFAULT_UNITS, fieldByKey, fields, FOUR_POINT_TEST, labelFor, libraryConstantsIn, libraryOptions, OPEN_HOLE_TEST, PLATE_TEST, PLY_KEYS,
  STANDARDS, standardOf, STRAIN_KEYS, UNIT_SYSTEMS, unitLabels, unitsOf, unitWords, type StudioForm,
} from "./studio-form";

export type ChatStep = "test" | "material" | "shear" | "layup" | "geometry" | "loading" | "name" | "review";
export const STEP_ORDER: ChatStep[] = ["test", "material", "shear", "layup", "geometry", "loading", "name", "review"];

/** What each test is, in an engineer's words, for the first question. */
export const TEST_CHOICES: { test: string; title: string; detail: string }[] = [
  { test: "unnotched tension", title: "Unnotched tension", detail: "a plain strip pulled, as in ASTM D3039" },
  { test: OPEN_HOLE_TEST, title: "Open-hole tension", detail: "a strip with a centre hole pulled, as in ASTM D5766" },
  { test: "unnotched compression", title: "Unnotched compression", detail: "a plain strip pushed" },
  { test: "in-plane shear", title: "In-plane shear", detail: "a ±45 strip pulled, as in ASTM D3518" },
  { test: "three-point bending", title: "Three-point bending", detail: "a beam on two supports, pushed at mid-span" },
  { test: FOUR_POINT_TEST, title: "Four-point bending", detail: "a beam on two supports, pushed by two noses" },
];

/** Layups offered as one click; the notation is the one the chat reads, so a click and the same words typed are the same. */
export const LAYUP_CHOICES: { notation: string; title: string }[] = [
  { notation: "[45/0/-45/90]s", title: "Quasi-isotropic" },
  { notation: "[0/90]2s", title: "Cross-ply" },
  { notation: "[45/-45]2s", title: "±45 (shear)" },
  { notation: "[0]8", title: "Unidirectional, fibres along the load" },
];

/** The library materials offered first; the rest are one menu away. */
export const COMMON_MATERIALS = ["im7-8552", "as4-8552", "t650-5320-1", "x840-z60-pw"];

export const isBending = (form: StudioForm) => BENDING_TESTS.includes(form.test);
const filled = (form: StudioForm, key: string) => (form[key] ?? "").trim() !== "";

/** The plies as typed, bottom first, stopping at the first empty row. */
export function pliesOf(form: StudioForm): string[] {
  const plies: string[] = [];
  for (const key of PLY_KEYS) {
    const value = (form[key] ?? "").trim();
    if (!value) break;
    plies.push(value);
  }
  return plies;
}

/** The layup in the usual bracket notation, from the rows: [45/0/-45/90]s. */
export function layupNotation(form: StudioForm): string {
  const plies = pliesOf(form);
  if (!plies.length) return "";
  return `[${plies.join("/")}]${form.symmetric === "yes" ? "s" : ""}`;
}

/** The library's in-plane shear and transverse moduli in the coupon's units, for the tape estimate of G13 and G23; the numbers are
 * the engine's, written per system into the form definition (the page converts nothing). */
export function libraryConstants(id: string, units: string = DEFAULT_UNITS): { G12: number; E2: number } | null {
  const constants = libraryConstantsIn(id, units);
  return constants ? { G12: constants.G12, E2: constants.E2 } : null;
}

/** The library material's ply thickness in the coupon's units; null when the record gives none or the material is not in the library. */
export function libraryThickness(form: StudioForm): number | null {
  return form.library ? libraryConstantsIn(form.library, unitsOf(form))?.ply_thickness ?? null : null;
}

/** The rows a step needs before the chat moves on; the setup check still judges them all. */
export function missingIn(step: ChatStep, form: StudioForm): string[] {
  const need = (keys: string[]) => keys.filter((key) => !filled(form, key));
  switch (step) {
    case "test": return need(["test", ...((standardOf(form)?.variant_words.length ?? 0) > 0 ? ["specimen"] : [])]);
    case "material": return filled(form, "library") ? [] : need(["own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_source"]);
    case "shear": return need(["G13", "G23"]);
    case "layup": return [...need(["ply_1", "symmetric"]), ...(libraryThickness(form) === null ? need(["ply_thickness"]) : [])];
    case "geometry": {
      const keys = ["length", "width", "size_from"];
      if (isBending(form)) keys.push("span", "overhang", ...(form.test === FOUR_POINT_TEST ? ["load_span"] : []));
      else keys.push("tab_length");
      if (form.test === OPEN_HOLE_TEST) keys.push("hole_diameter");
      keys.push(...(standardOf(form)?.needs ?? []).filter((key) => STRAIN_KEYS.includes(key))); // D3039 counts the gauge length (ADR-0072)
      return need(keys);
    }
    case "loading": return need(["control", "value"]);
    case "name": return need(["filled_by"]);
    case "review": return [];
  }
}

/** The first step with something missing, or the review. */
export function nextStep(form: StudioForm): ChatStep {
  for (const step of STEP_ORDER) if (missingIn(step, form).length) return step;
  return "review";
}

/** The step that asks for a row, so a blocked check item can send the engineer back to it; null when only the full form has it. */
export function stepOfKey(key: string): ChatStep | null {
  if (["test", "standard", "specimen", "units"].includes(key)) return "test";
  if (key === "library" || key.startsWith("own_")) return "material";
  if (["G13", "G23"].includes(key)) return "shear";
  if (PLY_KEYS.includes(key) || ["symmetric", "ply_thickness"].includes(key)) return "layup";
  if (["length", "width", "tab_length", "size_from", "span", "overhang", "load_span", "hole_diameter", ...STRAIN_KEYS].includes(key)) return "geometry";
  if (["control", "value"].includes(key)) return "loading";
  if (key === "filled_by") return "name"; // who runs it; the codes in the coupon's name are derived (ADR-0038 amendment 1), overrides on the form
  if (["criteria", "f12_star", "element_size", "grips", "region", "date", "notes"].includes(key)) return "review";
  return null;
}

/** The label the chat uses for a row, with the unit of the coupon's system: the form's label, shorter where the form's is written for
 * the spreadsheet. */
export function labelOf(key: string, units: string = DEFAULT_UNITS): string {
  const u = unitLabels(units);
  const chat: Record<string, string> = {
    length: `Length, tabs included (${u.length})`, tab_length: `Tab length (${u.length}, 0 for none)`, overhang: `Overhang past each support (${u.length})`,
    load_span: `Loading-nose span (${u.length})`, size_from: "Where the size comes from", ply_thickness: `Cured ply thickness (${u.length})`,
    material_code: "Material code for the coupon's name, e.g. IM7", value: "Amount", own_name: "Material name (no spaces)", own_nu12: "ν12",
    own_source: "Source of these numbers",
  };
  if (chat[key]) return chat[key];
  const field = fieldByKey[key];
  if (!field) return key;
  return labelFor(field, units).replace(/^Own material: /, "");
}

/** The rows whose numbers carry a unit, element size apart (it has a default in every system): what a change of units clears. */
export const DIMENSIONED_KEYS: string[] = fields.filter((f) => f.unit !== null && f.key !== "element_size").map((f) => f.key);
/** The dimensioned rows the engineer has stated: filled, and not at the form's own default (an overhang of 0 is 0 in every system). */
export const statedDimensioned = (form: StudioForm): string[] =>
  DIMENSIONED_KEYS.filter((key) => filled(form, key) && form[key].trim() !== String(fieldByKey[key].default ?? ""));

/** The unit system a message names, by its words; null when it names none. A bare "in" is not read as inches: too common a word. */
export function unitsNamed(text: string): string | null {
  const t = ` ${text.toLowerCase()} `;
  if (/\bin-ksi\b|\bksi\b/.test(t)) return "in-ksi";
  if (/\bin-psi\b|\bpsi\b|\bimperial\b|\bus (customary )?units\b|\binch(es)?\b|\bpounds?\b|\blbf\b|\blbs?\b/.test(t)) return "in-psi";
  if (/\bm-pa\b|\bmet(re|er)s?\b|\bpascals?\b|\bsi units\b/.test(t)) return "m-Pa";
  if (/\bmm-mpa\b|\bmillimet(re|er)s?\b|\bmpa\b|\bmetric\b/.test(t)) return "mm-MPa";
  return null;
}

/** "switch to inches", "use psi", "restate in m-Pa": a request to change the system, which clears the dimensioned rows. */
export const isSwitchRequest = (text: string): boolean => /\b(switch|use|restate|change|work|state)\b/i.test(text) && unitsNamed(text) !== null;

/** The form restated in another system: the Units row set, every filled dimensioned row cleared (a number typed in mm is not a number in
 * inches, and the page converts nothing), the element size back to the system's default. Returns the rows cleared, by key. */
export function switchUnits(form: StudioForm, units: string): { form: StudioForm; cleared: string[] } {
  if (!UNIT_SYSTEMS.includes(units)) return { form, cleared: [] };
  const cleared = statedDimensioned(form);
  const next: StudioForm = { ...form, units, element_size: blankForm(units).element_size };
  for (const key of cleared) next[key] = "";
  return { form: next, cleared };
}

/** The laminate notation: [45/0/-45/90]s, [0/90]2s, [±45]3, [0_2/90]s, [0/45/-45/90]; repeat counts and ± expand, s marks the lower half. */
export function parseLayup(text: string): { plies: number[]; symmetric: boolean } | null {
  const match = /\[([^\]]+)\]\s*(\d*)\s*(s?)(?![a-z0-9])/i.exec(text);
  if (!match) return null;
  const plies: number[] = [];
  for (const raw of match[1].split(/[\/,\s]+/).filter(Boolean)) {
    const token = /^(±|\+-|\+\/-|-\+|∓)?\s*(-?\d+(?:\.\d+)?)(?:_?(\d+)|([₀-₉]+))?$/.exec(raw.trim());
    if (!token) return null;
    const angle = Number(token[2]);
    const count = token[3] ? Number(token[3]) : token[4] ? Number([...token[4]].map((c) => c.charCodeAt(0) - 0x2080).join("")) : 1;
    const group = token[1] ? (token[1] === "-+" || token[1] === "∓" ? [-angle, angle] : [angle, -angle]) : [angle];
    for (let i = 0; i < count; i++) plies.push(...group.map((a) => (Object.is(a, -0) ? 0 : a)));
  }
  const repeat = match[2] ? Number(match[2]) : 1;
  const all = Array.from({ length: repeat }, () => plies).flat();
  if (!all.length || all.length > PLY_KEYS.length) return null;
  return { plies: all, symmetric: match[3].toLowerCase() === "s" };
}

/** The rows a layup fills: every ply row, the ones past the stack cleared. */
export function layupRows(layup: { plies: number[]; symmetric: boolean }): StudioForm {
  const rows: StudioForm = { symmetric: layup.symmetric ? "yes" : "no" };
  PLY_KEYS.forEach((key, i) => { rows[key] = i < layup.plies.length ? String(layup.plies[i]) : ""; });
  return rows;
}

const NUM = String.raw`(\d+(?:\.\d+)?|\.\d+)`;
/** A load keeps a typed minus sign, so the setup check refuses it rather than the chat quietly dropping it (ADR-0003). */
const SIGNED = String.raw`(-?(?:\d+(?:\.\d+)?|\.\d+))`;
const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

/** The words a typed number carries its unit in, per system: a length ("250 mm", "10 in", 10"), and a force with its thousandfold. */
const LENGTH_WORDS: Record<string, string> = { "mm-MPa": "mm", "m-Pa": "m", "in-psi": String.raw`in|inch|inches|"`, "in-ksi": String.raw`in|inch|inches|"` };
const FORCE_WORDS: Record<string, string> = { "mm-MPa": "kn|n", "m-Pa": "kn|n", "in-psi": "kips?|lbf|lbs?", "in-ksi": "kips?|lbf|lbs?" };
const THOUSANDS = /^(kn|kips?)$/;

/** What a typed message states, as form rows, with a few words for each thing understood; the numbers are read in the coupon's units
 * (mm-MPa unless another is given). Unknown words are left alone. */
export function readMessage(text: string, units: string = DEFAULT_UNITS): { rows: StudioForm; understood: string[] } {
  const rows: StudioForm = {};
  const understood: string[] = [];
  const t = ` ${text.toLowerCase()} `;
  const set = (key: string, value: string, words: string) => { rows[key] = value; understood.push(words); };
  const u = unitLabels(units);
  const L = `(?:${LENGTH_WORDS[units] ?? LENGTH_WORDS[DEFAULT_UNITS]})`;
  const F = FORCE_WORDS[units] ?? FORCE_WORDS[DEFAULT_UNITS];

  const test = /open[\s-]?hole|\boht\b|d5766|c1869/.test(t) ? OPEN_HOLE_TEST
    : /four[\s-]?point|4[\s-]?point|\b4pb\b/.test(t) ? FOUR_POINT_TEST
    : /three[\s-]?point|3[\s-]?point|\b3pb\b|d7264|d790/.test(t) ? "three-point bending"
    : /compress|d6641|d3410|d695/.test(t) ? "unnotched compression"
    : /in[\s-]?plane shear|\bshear test|d3518|\biplss?\b/.test(t) ? "in-plane shear"
    : /\bplate\b/.test(t) ? PLATE_TEST
    : /tension|tensile|d3039|\bunt\b/.test(t) ? "unnotched tension" : "";
  if (test) set("test", test, `test: ${test}`);
  // a standard of our list by its short name (d3039, c1869): the row takes the listed designation, or nothing for one we do not check (ADR-0072)
  const code = /\b(?:astm\s*)?([cd]\d{4}m?)\b/i.exec(text)?.[1].toLowerCase();
  const listed = code ? STANDARDS.find((p) => p.aliases.includes(code)) : undefined;
  if (listed) set("standard", listed.designation, `standard: ${listed.designation}`);

  const squashed = squash(text);
  const material = [...libraryOptions].sort((a, b) => b.id.length - a.id.length)
    .find((m) => squashed.includes(squash(m.id)) || squashed.includes(squash(m.name)));
  if (material) set("library", material.id, `material: ${material.name}`);

  const layup = parseLayup(text);
  if (layup) {
    Object.assign(rows, layupRows(layup));
    understood.push(`layup: ${text.match(/\[[^\]]+\]\s*\d*\s*s?/i)?.[0].replace(/\s+/g, "")} (${layup.plies.length * (layup.symmetric ? 2 : 1)} plies)`);
  }

  const size = new RegExp(`${NUM}\\s*${L}?\\s*(?:x|×|by)\\s*${NUM}\\s*${L}`).exec(t);
  if (size) {
    const [a, b] = [Number(size[1]), Number(size[2])];
    set("length", String(Math.max(a, b)), `length ${Math.max(a, b)} ${u.length}`);
    set("width", String(Math.min(a, b)), `width ${Math.min(a, b)} ${u.length}`);
  }
  const single = (pattern: string) => new RegExp(pattern).exec(t)?.slice(1).find(Boolean);
  const tab = /no tabs?|without tabs?|tabless/.test(t) ? "0" : single(`${NUM}\\s*${L}\\s*tabs?|tabs?\\s*(?:of|=|:)?\\s*${NUM}`);
  if (tab !== undefined) set("tab_length", tab, tab === "0" ? "no tabs" : `${tab} ${u.length} tabs`);
  const hole = single(`${NUM}\\s*${L}\\s*(?:diameter\\s*)?hole|hole\\s*(?:diameter\\s*)?(?:of|=|:|ø)?\\s*${NUM}|[øØ]\\s*${NUM}`);
  if (hole) set("hole_diameter", hole, `hole ${hole} ${u.length}`);
  const span = single(`(?:support\\s*)?span\\s*(?:of|=|:)?\\s*${NUM}|${NUM}\\s*${L}\\s*(?:support\\s*)?span`);
  if (span) set("span", span, `span ${span} ${u.length}`);
  const thickness = single(`${NUM}\\s*${L}\\s*(?:per\\s*)?ply|ply\\s*thickness\\s*(?:of|=|:)?\\s*${NUM}`);
  if (thickness) set("ply_thickness", thickness, `ply thickness ${thickness} ${u.length}`);

  const force = new RegExp(`${SIGNED}\\s*(${F})\\b`).exec(t);
  const travel = single(`${SIGNED}\\s*${L}\\s*(?:of\\s*)?(?:displacement|pull(?:ed)?|push(?:ed)?|stroke|travel|deflection|extension)|(?:displacement|pull(?:ed)?|push(?:ed)?|stroke|travel|deflection|extension|displaced?)\\s*(?:of|by|=|:)?\\s*${SIGNED}\\s*${L}`);
  if (travel) { rows.control = "displacement"; set("value", travel, `${travel} ${u.length} displacement`); }
  else if (force) {
    const amount = THOUSANDS.test(force[2]) ? Number((Number(force[1]) * 1000).toPrecision(12)) : Number(force[1]);
    rows.control = "force"; set("value", String(amount), `${amount} ${u.force} force`);
  }
  return { rows, understood };
}

/** A message applied to the form: read in the coupon's system, or in the one it names when nothing dimensioned is stated yet or the
 * message asks to switch (which clears the dimensioned rows, named in `note`); a message in another system while rows are filled
 * changes nothing and says why, so no number is read in the wrong units (ADR-0003). */
export function applyMessage(form: StudioForm, text: string): { rows: StudioForm; understood: string[]; note: string | null } {
  const current = unitsOf(form);
  const named = unitsNamed(text);
  if (named === null || named === current) return { ...readMessage(text, current), note: null };
  const stated = statedDimensioned(form);
  if (stated.length && !isSwitchRequest(text)) {
    return { rows: {}, understood: [], note: `That names ${unitWords(named)}, but this coupon is stated in ${unitWords(current)}. Say “switch to ${unitWords(named)}” `
      + `to restate it (its ${stated.length} dimensioned row${stated.length === 1 ? "" : "s"} would be cleared), or type the values in ${unitWords(current)}.` };
  }
  const switched = switchUnits(form, named);
  const read = readMessage(text, named);
  const rows: StudioForm = { units: named, element_size: switched.form.element_size, ...Object.fromEntries(switched.cleared.map((key) => [key, ""])), ...read.rows };
  const labels = switched.cleared.map((key) => labelOf(key, current).replace(/ \(.*\)$/, ""));
  const note = switched.cleared.length ? `Now stated in ${unitWords(named)}; cleared ${labels.join(", ")}: give them again in ${unitWords(named)}.` : null;
  return { rows, understood: [`units: ${unitWords(named)}`, ...read.understood], note };
}

/** The example sizes, loads and nose travels the chat offers as one click, per system: stated figures, not conversions. */
export const SIZE_CHIPS: Record<string, { words: string; rows: StudioForm }> = {
  "mm-MPa": { words: "250 × 25 mm, 56 mm tabs (the example's size)", rows: { length: "250", width: "25", tab_length: "56", size_from: "the public IM7/8552 example" } },
  "m-Pa": { words: "0.25 × 0.025 m, 0.056 m tabs (the example's size)", rows: { length: "0.25", width: "0.025", tab_length: "0.056", size_from: "the public IM7/8552 example" } },
  "in-psi": { words: "10 × 1 in, 2.2 in tabs (ASTM D3039 proportions)", rows: { length: "10", width: "1", tab_length: "2.2", size_from: "the proportions of ASTM D3039" } },
  "in-ksi": { words: "10 × 1 in, 2.2 in tabs (ASTM D3039 proportions)", rows: { length: "10", width: "1", tab_length: "2.2", size_from: "the proportions of ASTM D3039" } },
};
export const LOAD_CHIPS: Record<string, { words: string; control: string; value: string }[]> = {
  "mm-MPa": [{ words: "Displacement 1 mm", control: "displacement", value: "1" }, { words: "Displacement 0.5 mm", control: "displacement", value: "0.5" },
             { words: "Force 10 kN", control: "force", value: "10000" }],
  "m-Pa": [{ words: "Displacement 0.001 m", control: "displacement", value: "0.001" }, { words: "Displacement 0.0005 m", control: "displacement", value: "0.0005" },
           { words: "Force 10 kN", control: "force", value: "10000" }],
  "in-psi": [{ words: "Displacement 0.04 in", control: "displacement", value: "0.04" }, { words: "Displacement 0.02 in", control: "displacement", value: "0.02" },
             { words: "Force 2000 lbf", control: "force", value: "2000" }],
  "in-ksi": [{ words: "Displacement 0.04 in", control: "displacement", value: "0.04" }, { words: "Displacement 0.02 in", control: "displacement", value: "0.02" },
             { words: "Force 2000 lbf", control: "force", value: "2000" }],
};
export const PUSH_CHIPS: Record<string, string[]> = { "mm-MPa": ["1", "2", "5"], "m-Pa": ["0.001", "0.002", "0.005"], "in-psi": ["0.04", "0.08", "0.2"], "in-ksi": ["0.04", "0.08", "0.2"] };

/** The coupon in a line, for the summary card: only what is stated, in the units it is stated in. */
export function couponLines(form: StudioForm): [string, string][] {
  const material = form.library ? libraryOptions.find((m) => m.id === form.library)?.name ?? form.library : form.own_name;
  const plies = pliesOf(form);
  const count = plies.length * (form.symmetric === "yes" ? 2 : 1);
  const units = unitsOf(form);
  const u = unitLabels(units);
  const size = form.length && form.width ? `${form.length} × ${form.width} ${u.length}` : "";
  const extra = isBending(form)
    ? [form.span && `span ${form.span} ${u.length}`, form.test === FOUR_POINT_TEST && form.load_span && `noses ${form.load_span} ${u.length} apart`].filter(Boolean).join(", ")
    : [form.tab_length && (form.tab_length === "0" ? "no tabs" : `${form.tab_length} ${u.length} tabs`), form.test === OPEN_HOLE_TEST && form.hole_diameter && `Ø${form.hole_diameter} ${u.length} hole`].filter(Boolean).join(", ");
  const load = form.value ? (form.control === "force" ? `${form.value} ${u.force} force` : `${form.value} ${u.length} ${isBending(form) ? "nose travel" : "displacement"}`) : "";
  return [
    ["Units", unitWords(units)],
    ["Test", form.test],
    ["Material", material ?? ""],
    ["Layup", plies.length ? `${layupNotation(form)}, ${count} plies` : ""],
    ["Size", [size, extra].filter(Boolean).join(", ")],
    ["Load", load],
  ];
}
