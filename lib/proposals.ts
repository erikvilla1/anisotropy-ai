/**
 * The model proposes, the engineer confirms (ADR-0088): the rows each chat offers a message to fill, what the model may see of the problem,
 * and the proposals the engineer ticked turned into the rows or the draft. The API's source guard has already kept only values the
 * engineer's own words write; nothing here converts a unit or computes a value (ADR-0001, ADR-0002), and a value enters only once ticked.
 */
import { CONDITIONS, conditionOf } from "./conditions";
import { enabledWords, isRowEnabled } from "./enabled-tests";
import {
  blankOwn, CONSTANT_NAMES, hasCondition, isReportUnits, LOAD_NAMES, REPORT_SYSTEMS, systemUnit, type ConstantName, type Kind, type LaminateDraft,
  type LoadName, type Quantity,
} from "./laminate-chat";
import { expandLayup } from "./layup";
import { layupNotation, layupRows, parseLayup, pliesOf, TEST_CHOICES } from "./studio-chat";
import { fieldByKey, fields, libraryOptions, unitLabels, unitsOf, type StudioForm } from "./studio-form";
import type { OfferedRow, PlateOffer, Proposal, ProposalAnswer, ProposalRequest, UnreadPart } from "./studio-api";
import { DOF_WORDS, ownRegions, type PlateLists, type PlateLoad } from "./studio-plate";

/** Rows the model never sees: who filled the form in, notes, sources and names, the team's own model and data (R-11). */
const HIDDEN = new Set(["filled_by", "date", "notes", "size_from", "team_model", "test_data", "material_code", "layup_code", "tab_material", "own_name",
  "own_source"]);
const hidden = (key: string) => HIDDEN.has(key) || key.startsWith("name_") || key.startsWith("mesh_") || /^ply_\d+$/.test(key);

/** Why nothing was proposed for a part of the message, in the page's words (ADR-0088 amendment 1). The model names the reason and
 * quotes the engineer; it phrases nothing here. */
const UNREAD_WORDS: Record<UnreadPart["reason"], string> = {
  not_offered: "not something you can set here yet",
  no_value: "names no value to enter; state the value itself, for example a layup as [0/90]2s",
  refers_back: "each message is read on its own, so say the whole change",
};
export type UnreadLine = { quote: string; words: string };
export const unreadLines = (parts: UnreadPart[]): UnreadLine[] => parts.map((p) => ({ quote: p.quote, words: UNREAD_WORDS[p.reason] }));

// ----------------------------------------------------------------------------------------------- the coupon

/** The choice rows a coupon message may set, with the form's words as the choices. Units stay with the chat's own switch (ADR-0061). */
const COUPON_CHOICES = ["test", "standard", "specimen", "material_kind", "symmetric", "criteria", "strain_device", "grips", "region"];
/** Number rows the panels hold but a message is not offered: the mesh's own controls and the tab's bevel angle, a pure number in degrees. */
const COUPON_NUMBERS_LEFT = new Set(["value", "hole_ring", "hole_growth", "tab_bevel"]);
const testTitle = (word: string) => TEST_CHOICES.find((c) => c.test === word)?.title ?? word;

/** The rows a coupon message is offered: its choices, its numbers each in the unit of the coupon's system, the layup as a notation, and the
 * loading as a displacement or a force (each sets the loading type with the value). With `all` false (ADR-0089) the choices are the
 * enabled tests, standards and material kinds only, and the hidden tests' own rows are not offered: the API's guard then drops any
 * proposal outside them. */
export function couponOffer(form: StudioForm, all = true): Pick<ProposalRequest, "rows" | "form"> {
  const labels = unitLabels(unitsOf(form));
  const rows: OfferedRow[] = [];
  for (const key of COUPON_CHOICES) {
    const field = fieldByKey[key];
    if (!isRowEnabled(key, all)) continue;
    if (!field) continue;
    const words = enabledWords(key, field.words, all);
    if (!words.length) continue;
    rows.push({ key, label: field.label, kind: "choice", choices: words.map((w) => ({ value: w, label: key === "test" ? testTitle(w) : w })) });
  }
  rows.push({ key: "library", label: "Library material", kind: "choice", choices: libraryOptions.map((m) => ({ value: m.id, label: m.name })) });
  rows.push({ key: "layup", label: "Layup, in laminate notation, bottom ply first", kind: "notation" });
  // each stated ply's angle, so "change ply 3 to 30 degrees" has a row to fill (ADR-0121 amendment 5); a symmetric layup's mirror follows
  const mirror = form.symmetric === "yes" ? ", its mirror with it" : "";
  pliesOf(form).forEach((_, i) => rows.push({ key: `ply_${i + 1}`, label: `Ply ${i + 1} angle, counted from the bottom${mirror}`, kind: "angle" }));
  for (const field of fields) {
    if (field.kind !== "number" || COUPON_NUMBERS_LEFT.has(field.key) || hidden(field.key) || !isRowEnabled(field.key, all)) continue;
    if (field.unit === "length" || field.unit === "stress") rows.push({ key: field.key, label: field.labels?.[unitsOf(form)] ?? field.label, kind: "number", unit: labels[field.unit] });
    else if (field.unit === null) rows.push({ key: field.key, label: field.label, kind: "number" });
  }
  rows.push({ key: "displacement", label: `Displacement applied, the grip's or the nose's travel (${labels.length})`, kind: "number", unit: labels.length });
  rows.push({ key: "force", label: `Force applied (${labels.force})`, kind: "number", unit: labels.force });
  const view: Record<string, string> = {};
  for (const [key, value] of Object.entries(form)) if (value.trim() && !hidden(key)) view[key] = value;
  const layup = layupNotation(form);
  if (layup) view.layup = layup;
  return { rows, form: view };
}

/** The rows the ticked proposals fill: a layup into the ply rows, a displacement or a force into the loading; and what could not be read. */
export function couponRowsFrom(accepted: Proposal[]): { rows: StudioForm; notes: string[] } {
  const rows: StudioForm = {};
  const notes: string[] = [];
  for (const p of accepted) {
    if (p.key === "layup") {
      const layup = parseLayup(p.value);
      if (layup) Object.assign(rows, layupRows(layup));
      else notes.push(`Layup ${p.value}: not laminate notation the page reads; type it as [45/0/-45/90]s.`);
    } else if (p.key === "displacement" || p.key === "force") {
      rows.control = p.key;
      rows.value = p.value;
    } else rows[p.key] = p.value;
  }
  return { rows, notes };
}

// ----------------------------------------------------------------------------------------------- the plate

/** What a plate offers a message besides its rows (ADR-0101): its own regions, those of the clicked element (`here`), the units a force
 * and a pressure are stated in, and which regions are already held and loaded. A box the engineer drew and named is not offered. */
export function plateOffer(form: StudioForm, lists: PlateLists, here: string[]): PlateOffer {
  const labels = unitLabels(unitsOf(form));
  const regions = ownRegions(form);
  const own = (names: string[]) => [...new Set(names)].filter((name) => regions.some((r) => r.name === name));
  return { regions, here: own(here), force_unit: labels.force, stress_unit: labels.stress,
    held: own(lists.supports.map((s) => s.region)), loaded: own(lists.loads.map((l) => l.region)) };
}

/** One line of the card per support and load kept (the card's own shape): what it does in the plate's words, and the words it came from. */
export type PlateLine = { id: string; label: string; value: string; unit: string; note?: string; quote: string };
export function plateLines(answer: Pick<ProposalAnswer, "supports" | "loads">): PlateLine[] {
  const dof = (d: number) => DOF_WORDS[d] ?? `direction ${d}`;
  const written = (value: string, unit: string | null, taken: string, takenUnit: string) =>
    (unit && (unit !== takenUnit || value.replace(/^[-+]/, "") !== taken.replace(/^-/, "")) ? `written ${value} ${unit}` : null);
  return [
    ...answer.supports.map((s, i) => ({ id: `support:${i}`, label: `Hold ${s.region}`, value: s.dofs.map(dof).join(", "), unit: "", quote: s.quote })),
    ...answer.loads.map((l, i) => {
      const notes = [written(l.written_value, l.written_unit, l.value, l.unit),
        l.kind === "pressure" ? "positive presses down on the plate" : l.sense === "tension" ? "tension: pulling outward from the edge"
          : l.sense === "compression" ? "compression: pushing in at the edge" : null].filter((n): n is string => n !== null);
      return { id: `load:${i}`, label: l.kind === "pressure" ? `Pressure on ${l.region}` : `Force on ${l.region}`, value: l.value,
        unit: l.kind === "pressure" ? l.unit : `${l.unit} along ${dof(l.dof ?? 3)}`, quote: l.quote, ...(notes.length ? { note: notes.join("; ") } : {}) };
    }),
  ];
}

/** The plate's lists with the ticked supports and loads added, each as a row of the Boundary conditions and loads panel. */
export function plateWith(lists: PlateLists, answer: Pick<ProposalAnswer, "supports" | "loads">, ticked: Set<string>): PlateLists {
  const supports = answer.supports.filter((_, i) => ticked.has(`support:${i}`)).map((s) => ({ region: s.region, dofs: [...s.dofs], value: "" }));
  const loads = answer.loads.filter((_, i) => ticked.has(`load:${i}`)).map((l): PlateLoad => (l.kind === "pressure"
    ? { region: l.region, kind: "pressure", pressure: l.value } : { region: l.region, kind: "force", dof: l.dof ?? 3, total: l.value }));
  return { ...lists, supports: [...lists.supports, ...supports], loads: [...lists.loads, ...loads] };
}

// ----------------------------------------------------------------------------------------------- the laminate

const PRESSURE: Record<ConstantName, boolean> = { E1: true, E2: true, G12: true, nu12: false, F1t: true, F1c: true, F2t: true, F2c: true, F6: true };
const KIND_OF_KEY: Record<string, Kind> = {
  E1: "modulus", E2: "modulus", G12: "modulus", F1t: "stress", F1c: "stress", F2t: "stress", F2c: "stress", F6: "stress", ply_thickness: "length",
  Nx: "N", Ny: "N", Nxy: "N", Mx: "M", My: "M", Mxy: "M", delta_T: "delta_T", alpha1: "alpha", alpha2: "alpha",
};
const DIMENSION_OF_KIND: Record<Kind, string> = {
  modulus: "pressure", stress: "pressure", length: "length", N: "force_per_length", M: "moment_per_length", delta_T: "temperature_change", alpha: "expansion",
};

/** The rows a laminate message is offered, every number with the dimension of its units (each value keeps the unit written; the API's
 * engine converts, ADR-0060), the conditions that are off, and the problem so far with no name or source. */
export function laminateOffer(draft: LaminateDraft): Pick<ProposalRequest, "rows" | "conditions" | "form"> {
  const number = (key: string, label: string): OfferedRow => (KIND_OF_KEY[key]
    ? { key, label, kind: "number", dimension: DIMENSION_OF_KIND[KIND_OF_KEY[key]] } : { key, label, kind: "number" });
  const rows: OfferedRow[] = [
    { key: "system", label: "Units the problem is stated in", kind: "choice", choices: REPORT_SYSTEMS.map((s) => ({ value: s.id, label: `${s.title}: ${s.detail}` })) },
    { key: "library", label: "Library material", kind: "choice", choices: libraryOptions.map((m) => ({ value: m.id, label: m.name })) },
    ...CONSTANT_NAMES.map((name) => number(name, PRESSURE[name] ? `${name}, a material constant` : "nu12, the major Poisson's ratio")),
    { key: "layup", label: "Layup, in laminate notation, bottom ply first", kind: "notation" },
    number("ply_thickness", "Ply thickness"),
    ...LOAD_NAMES.map((name) => number(name, `${name}, a ${name.startsWith("N") ? "force" : "moment"} per unit width`)),
    number("f12_star", "Tsai-Wu interaction f12*"),
    number("delta_T", "Temperature change, uniform (a cooling is negative)"),
    number("alpha1", "alpha1, thermal expansion along the fibres"),
    number("alpha2", "alpha2, thermal expansion across the fibres"),
  ];
  const conditions = CONDITIONS.filter((c) => c.product === "laminate" && !hasCondition(draft, c.id)).map((c) => ({ id: c.id, title: c.title, detail: c.detail }));
  const form: Record<string, string> = {};
  const q = (x: Quantity | null | undefined) => (x && x.value.trim() ? `${x.value} ${x.unit}`.trim() : "");
  if (draft.system) form.system = draft.system;
  if (draft.material && "library" in draft.material) form.library = draft.material.library;
  if (draft.material && "own" in draft.material) {
    for (const name of CONSTANT_NAMES) {
      const value = draft.material.own[name];
      const written = typeof value === "string" ? value.trim() : q(value);
      if (written) form[name] = written;
    }
  }
  if (draft.layup) form.layup = draft.layup.notation;
  if (q(draft.thickness)) form.ply_thickness = q(draft.thickness);
  for (const name of LOAD_NAMES) if (draft.loads && q(draft.loads[name])) form[name] = q(draft.loads[name]);
  if (draft.f12_star.trim()) form.f12_star = draft.f12_star.trim();
  if (q(draft.delta_T)) form.delta_T = q(draft.delta_T);
  if (draft.alphas) { if (q(draft.alphas.alpha1)) form.alpha1 = q(draft.alphas.alpha1); if (q(draft.alphas.alpha2)) form.alpha2 = q(draft.alphas.alpha2); }
  if (draft.conditions?.length) form.conditions = draft.conditions.join(", ");
  return { rows, conditions, form };
}

/** Whether a laminate row's number carries a unit (a pure number such as nu12 does not). */
export const laminateUnitNeeded = (key: string): boolean => key in KIND_OF_KEY;

/** The unit a laminate proposal takes: the one written, or with none written the system's for its kind; null with neither (pick the units first). */
export function laminateUnit(p: Proposal, system: string): string | null {
  if (p.unit) return p.unit;
  const kind = KIND_OF_KEY[p.key];
  if (!kind) return null;
  return isReportUnits(system) ? systemUnit(system, kind) : null;
}

/** The draft with the ticked proposals and conditions in it, each value with its unit as `laminateUnit` gives it, and what could not go in.
 * A temperature change or an expansion turns the temperature condition on with it, as the chat's own reading does (ADR-0087). */
export function laminateDraftFrom(draft: LaminateDraft, accepted: Proposal[], conditionIds: string[]): { next: LaminateDraft; notes: string[] } {
  const next: LaminateDraft = { ...draft };
  const notes: string[] = [];
  const of = (key: string) => accepted.find((p) => p.key === key);
  const system = of("system")?.value;
  if (system && isReportUnits(system)) next.system = system;
  const quantity = (p: Proposal): Quantity | null => {
    const unit = laminateUnit(p, next.system);
    if (unit === null) { notes.push(`${p.label}: no unit written; pick the units the problem is stated in first.`); return null; }
    return { value: p.value, unit };
  };
  const library = of("library");
  if (library) next.material = { library: library.value };
  const constants = CONSTANT_NAMES.filter((name) => of(name));
  if (constants.length) {
    const own = next.material && "own" in next.material ? { ...next.material.own } : blankOwn();
    let put = 0;
    for (const name of constants) {
      const p = of(name)!;
      if (name === "nu12") { own.nu12 = p.value; put += 1; }
      else { const value = quantity(p); if (value) { own[name] = value; put += 1; } }
    }
    if (put) next.material = { own }; // a typed material replaces a library one only once a constant goes in
  }
  const layup = of("layup");
  if (layup) {
    const expanded = expandLayup(layup.value);
    if (expanded.layup) next.layup = { notation: layup.value.replace(/\s+/g, ""), angles: expanded.layup.angles, symmetric: expanded.layup.symmetric };
    else notes.push(`Layup ${layup.value}: ${expanded.error}`);
  }
  const thickness = of("ply_thickness");
  if (thickness) { const value = quantity(thickness); if (value) next.thickness = value; }
  const loads = LOAD_NAMES.filter((name) => of(name));
  if (loads.length) {
    const merged: Partial<Record<LoadName, Quantity>> = { ...(next.loads ?? {}) };
    for (const name of loads) { const value = quantity(of(name)!); if (value) merged[name] = value; }
    const blank = (name: LoadName): Quantity => ({ value: "", unit: isReportUnits(next.system) ? systemUnit(next.system, name.startsWith("N") ? "N" : "M") : "" });
    next.loads = Object.fromEntries(LOAD_NAMES.map((name) => [name, merged[name] ?? blank(name)])) as Record<LoadName, Quantity>;
  }
  const f12 = of("f12_star");
  if (f12) next.f12_star = f12.value;
  const conditions = new Set([...(next.conditions ?? []), ...conditionIds.filter((id) => conditionOf(id)?.product === "laminate")]);
  const deltaT = of("delta_T");
  if (deltaT) { const value = quantity(deltaT); if (value) { next.delta_T = value; conditions.add("temperature"); } }
  const alphas = (["alpha1", "alpha2"] as const).map((name) => { const p = of(name); return p ? quantity(p) : null; });
  if (alphas[0] || alphas[1]) {
    const blank = { value: "", unit: "1e-6/degC" };
    next.alphas = { alpha1: alphas[0] ?? next.alphas?.alpha1 ?? blank, alpha2: alphas[1] ?? next.alphas?.alpha2 ?? blank };
    conditions.add("temperature");
  }
  if (conditions.size) next.conditions = [...conditions];
  return { next, notes };
}
