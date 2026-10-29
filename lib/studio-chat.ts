/**
 * The studio's guided chat (ADR-0055): the order of its questions, the words it reads out of a typed message, and the laminate
 * notation it understands. It only fills the same form rows the full form fills; nothing here judges a value or computes a result:
 * `intake.check_form` does, through the setup check (ADR-0001, ADR-0003). A message that names nothing it can read changes nothing.
 */
import { BENDING_TESTS, fieldByKey, formDefinition, FOUR_POINT_TEST, libraryOptions, OPEN_HOLE_TEST, PLATE_TEST, PLY_KEYS, type StudioForm } from "./studio-form";

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
  { notation: "[90]8", title: "Unidirectional, fibres along the load" },
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

/** The library's in-plane shear and transverse moduli, for the tape estimate of G13 and G23; the numbers are the library's. */
export function libraryConstants(id: string): { G12: number; E2: number } | null {
  const entry = formDefinition.library.find((row) => String(row.Id) === id);
  const G12 = entry?.["G12 (MPa)"], E2 = entry?.["E2 (MPa)"];
  return typeof G12 === "number" && typeof E2 === "number" ? { G12, E2 } : null;
}

export function libraryThickness(form: StudioForm): number | null {
  return libraryOptions.find((m) => m.id === form.library)?.thickness ?? null;
}

/** The rows a step needs before the chat moves on; the setup check still judges them all. */
export function missingIn(step: ChatStep, form: StudioForm): string[] {
  const need = (keys: string[]) => keys.filter((key) => !filled(form, key));
  switch (step) {
    case "test": return need(["test"]);
    case "material": return filled(form, "library") ? [] : need(["own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_source"]);
    case "shear": return need(["G13", "G23"]);
    case "layup": return [...need(["ply_1", "symmetric"]), ...(libraryThickness(form) === null ? need(["ply_thickness"]) : [])];
    case "geometry": {
      const keys = ["length", "width", "size_from"];
      if (isBending(form)) keys.push("span", "overhang", ...(form.test === FOUR_POINT_TEST ? ["load_span"] : []));
      else keys.push("tab_length");
      if (form.test === OPEN_HOLE_TEST) keys.push("hole_diameter");
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
  if (["test", "standard"].includes(key)) return "test";
  if (key === "library" || key.startsWith("own_")) return "material";
  if (["G13", "G23"].includes(key)) return "shear";
  if (PLY_KEYS.includes(key) || ["symmetric", "ply_thickness"].includes(key)) return "layup";
  if (["length", "width", "tab_length", "size_from", "span", "overhang", "load_span", "hole_diameter"].includes(key)) return "geometry";
  if (["control", "value"].includes(key)) return "loading";
  if (["filled_by", "material_code", "layup_code"].includes(key)) return "name"; // who runs it and the codes in the coupon's name
  if (["criteria", "f12_star", "element_size", "grips", "region", "date", "notes"].includes(key)) return "review";
  return null;
}

/** The label the chat uses for a row: the form's label, shorter where the form's is written for the spreadsheet. */
export const CHAT_LABELS: Record<string, string> = {
  length: "Length, tabs included (mm)", width: "Width (mm)", tab_length: "Tab length (mm, 0 for none)", hole_diameter: "Hole diameter (mm)",
  span: "Support span (mm)", overhang: "Overhang past each support (mm)", load_span: "Loading-nose span (mm)", size_from: "Where the size comes from",
  ply_thickness: "Cured ply thickness (mm)", material_code: "Material code for the coupon's name, e.g. IM7", G13: "G13 (MPa)", G23: "G23 (MPa)", value: "Amount", own_name: "Material name (no spaces)",
  own_E1: "E1 (MPa)", own_E2: "E2 (MPa)", own_G12: "G12 (MPa)", own_nu12: "ν12", own_source: "Source of these numbers",
  own_F1t: "F1t (MPa)", own_F1c: "F1c (MPa)", own_F2t: "F2t (MPa)", own_F2c: "F2c (MPa)", own_F6: "F6 (MPa)", element_size: "Element size (mm)",
};
export const labelOf = (key: string) => CHAT_LABELS[key] ?? fieldByKey[key]?.label ?? key;

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

/** What a typed message states, as form rows, with a few words for each thing understood. Unknown words are left alone. */
export function readMessage(text: string): { rows: StudioForm; understood: string[] } {
  const rows: StudioForm = {};
  const understood: string[] = [];
  const t = ` ${text.toLowerCase()} `;
  const set = (key: string, value: string, words: string) => { rows[key] = value; understood.push(words); };

  const test = /open[\s-]?hole|\boht\b|d5766/.test(t) ? OPEN_HOLE_TEST
    : /four[\s-]?point|4[\s-]?point|\b4pb\b/.test(t) ? FOUR_POINT_TEST
    : /three[\s-]?point|3[\s-]?point|\b3pb\b|d7264|d790/.test(t) ? "three-point bending"
    : /compress|d6641|d3410|d695/.test(t) ? "unnotched compression"
    : /in[\s-]?plane shear|\bshear test|d3518|\biplss?\b/.test(t) ? "in-plane shear"
    : /\bplate\b/.test(t) ? PLATE_TEST
    : /tension|tensile|d3039|\bunt\b/.test(t) ? "unnotched tension" : "";
  if (test) set("test", test, `test: ${test}`);
  const standard = /\b(astm\s*)?(d\d{4})\b/i.exec(text);
  if (standard) set("standard", `ASTM ${standard[2].toUpperCase()}`, `standard: ASTM ${standard[2].toUpperCase()}`);

  const squashed = squash(text);
  const material = [...libraryOptions].sort((a, b) => b.id.length - a.id.length)
    .find((m) => squashed.includes(squash(m.id)) || squashed.includes(squash(m.name)));
  if (material) set("library", material.id, `material: ${material.name}`);

  const layup = parseLayup(text);
  if (layup) {
    Object.assign(rows, layupRows(layup));
    understood.push(`layup: ${text.match(/\[[^\]]+\]\s*\d*\s*s?/i)?.[0].replace(/\s+/g, "")} (${layup.plies.length * (layup.symmetric ? 2 : 1)} plies)`);
  }

  const size = new RegExp(`${NUM}\\s*(?:mm)?\\s*(?:x|×|by)\\s*${NUM}\\s*mm`).exec(t);
  if (size) {
    const [a, b] = [Number(size[1]), Number(size[2])];
    set("length", String(Math.max(a, b)), `length ${Math.max(a, b)} mm`);
    set("width", String(Math.min(a, b)), `width ${Math.min(a, b)} mm`);
  }
  const single = (pattern: string) => new RegExp(pattern).exec(t)?.slice(1).find(Boolean);
  const tab = /no tabs?|without tabs?|tabless/.test(t) ? "0" : single(`${NUM}\\s*mm\\s*tabs?|tabs?\\s*(?:of|=|:)?\\s*${NUM}`);
  if (tab !== undefined) set("tab_length", tab, tab === "0" ? "no tabs" : `${tab} mm tabs`);
  const hole = single(`${NUM}\\s*mm\\s*(?:diameter\\s*)?hole|hole\\s*(?:diameter\\s*)?(?:of|=|:|ø)?\\s*${NUM}|[øØ]\\s*${NUM}`);
  if (hole) set("hole_diameter", hole, `hole ${hole} mm`);
  const span = single(`(?:support\\s*)?span\\s*(?:of|=|:)?\\s*${NUM}|${NUM}\\s*mm\\s*(?:support\\s*)?span`);
  if (span) set("span", span, `span ${span} mm`);
  const thickness = single(`${NUM}\\s*mm\\s*(?:per\\s*)?ply|ply\\s*thickness\\s*(?:of|=|:)?\\s*${NUM}`);
  if (thickness) set("ply_thickness", thickness, `ply thickness ${thickness} mm`);

  const force = new RegExp(`${SIGNED}\\s*(kn|n)\\b`).exec(t);
  const travel = single(`${SIGNED}\\s*mm\\s*(?:of\\s*)?(?:displacement|pull|push|stroke|travel|deflection|extension)|(?:displacement|pull|push|stroke|travel|deflection|extension|displace)\\s*(?:of|by|=|:)?\\s*${SIGNED}\\s*mm`);
  if (travel) { rows.control = "displacement"; set("value", travel, `${travel} mm displacement`); }
  else if (force) {
    const newtons = force[2] === "kn" ? Number((Number(force[1]) * 1000).toPrecision(12)) : Number(force[1]);
    rows.control = "force"; set("value", String(newtons), `${newtons} N force`);
  }
  return { rows, understood };
}

/** The coupon in a line, for the summary card: only what is stated. */
export function couponLines(form: StudioForm): [string, string][] {
  const material = form.library ? libraryOptions.find((m) => m.id === form.library)?.name ?? form.library : form.own_name;
  const plies = pliesOf(form);
  const count = plies.length * (form.symmetric === "yes" ? 2 : 1);
  const size = form.length && form.width ? `${form.length} × ${form.width} mm` : "";
  const extra = isBending(form)
    ? [form.span && `span ${form.span} mm`, form.test === FOUR_POINT_TEST && form.load_span && `noses ${form.load_span} mm apart`].filter(Boolean).join(", ")
    : [form.tab_length && (form.tab_length === "0" ? "no tabs" : `${form.tab_length} mm tabs`), form.test === OPEN_HOLE_TEST && form.hole_diameter && `Ø${form.hole_diameter} mm hole`].filter(Boolean).join(", ");
  const load = form.value ? (form.control === "force" ? `${form.value} N force` : `${form.value} mm ${isBending(form) ? "nose travel" : "displacement"}`) : "";
  return [
    ["Test", form.test],
    ["Material", material ?? ""],
    ["Layup", plies.length ? `${layupNotation(form)}, ${count} plies` : ""],
    ["Size", [size, extra].filter(Boolean).join(", ")],
    ["Load", load],
  ];
}
