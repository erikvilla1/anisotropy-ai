/**
 * A plate's supports, loads and regions in the studio (ADR-0054): the lists the engineer builds by clicking regions on the model or by typing,
 * kept as the values object the API checks (`intake.plate_lists`). The region names are the package's: the four edges, the hole's ring when
 * there is a hole, the whole face, the tabs when there are tabs, and the boxes the engineer draws. Nothing here judges a value beyond its
 * shape: `intake.check_form` and the spec refuse by name, through the setup check.
 */
import { formDefinition, type StudioForm } from "./studio-form";

export type PlateSupport = { region: string; dofs: number[]; value: string };
export type PlateForce = { region: string; kind: "force"; dof: number; total: string };
export type PlatePressure = { region: string; kind: "pressure"; pressure: string };
export type PlateLoad = PlateForce | PlatePressure;
export type PlateRegion = { name: string; x0: string; x1: string; y0: string; y1: string };
export type PlateLists = { supports: PlateSupport[]; loads: PlateLoad[]; regions: PlateRegion[] };

export const PLATE_TEST = formDefinition.plate?.test ?? "plate";
export const DOF_WORDS: Record<number, string> = Object.fromEntries(Object.entries(formDefinition.plate?.dofs ?? {}).map(([k, v]) => [Number(k), v]));
export const EDGES: string[] = formDefinition.plate?.edges ?? ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right"];
export const AREAS: string[] = formDefinition.plate?.areas ?? ["Face"];
const NUMBER = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i;

export function emptyPlate(): PlateLists {
  return { supports: [], loads: [], regions: [] };
}

/** The regions a plate's supports and loads may name, from what the form states and the boxes drawn: edges first, then areas. */
export function regionOptions(form: StudioForm, lists: PlateLists): { name: string; kind: "edge" | "area" }[] {
  const hole = (form.hole_diameter ?? "").trim() !== "";
  const tabs = Number(form.tab_length) > 0;
  const edges = [...EDGES, ...(hole ? formDefinition.plate?.with_hole ?? ["Hole"] : [])];
  const areas = [...AREAS, ...(tabs ? formDefinition.plate?.with_tabs ?? ["Tab-Bottom", "Tab-Top"] : []), ...lists.regions.map((r) => r.name).filter(Boolean)];
  return [...edges.map((name) => ({ name, kind: "edge" as const })), ...areas.map((name) => ({ name, kind: "area" as const }))];
}

const parse = (text: string): number | string => (NUMBER.test(text.trim()) ? Number(text) : text.trim());

/** The lists as the API takes them: numbers parsed, blank values left out so the check names the row. */
export function plateValues(lists: PlateLists): Record<string, unknown[]> {
  const supports = lists.supports.map((s) => ({ region: s.region, dofs: s.dofs, ...(s.value.trim() ? { value: parse(s.value) } : {}) }));
  const loads = lists.loads.map((l) => l.kind === "pressure" ? { region: l.region, pressure: parse(l.pressure) } : { region: l.region, dof: l.dof, total: parse(l.total) });
  const regions = lists.regions.map((r) => ({ name: r.name.trim(), x0: parse(r.x0), x1: parse(r.x1), y0: parse(r.y0), y1: parse(r.y1) }));
  return { supports, loads, regions };
}

/** The lists read back from a coupon's values (`GET /v1/coupons/{name}/values`), as text rows. */
export function plateFromValues(values: Record<string, unknown>): PlateLists {
  const text = (v: unknown) => (v === null || v === undefined ? "" : String(v));
  const supports = Array.isArray(values.supports) ? (values.supports as Record<string, unknown>[]).map((s) => ({
    region: text(s.region), dofs: Array.isArray(s.dofs) ? (s.dofs as number[]).map(Number) : [], value: s.value ? text(s.value) : "" })) : [];
  const loads = Array.isArray(values.loads) ? (values.loads as Record<string, unknown>[]).map((l): PlateLoad => "pressure" in l
    ? { region: text(l.region), kind: "pressure", pressure: text(l.pressure) }
    : { region: text(l.region), kind: "force", dof: Number(l.dof ?? 3), total: text(l.total) }) : [];
  const regions = Array.isArray(values.regions) ? (values.regions as Record<string, unknown>[]).map((r) => ({
    name: text(r.name), x0: text(r.x0), x1: text(r.x1), y0: text(r.y0), y1: text(r.y1) })) : [];
  return { supports, loads, regions };
}

/** The named regions an element touches, from the preview's sets: the areas that hold it, then the edges it has nodes on. */
export function regionsOfElement(element: number, quads: number[][], nodeSets: Record<string, number[]>, elementSets: Record<string, number[]>,
  options: { name: string; kind: "edge" | "area" }[]): { name: string; kind: "edge" | "area" }[] {
  const corners = new Set(quads[element] ?? []);
  const out: { name: string; kind: "edge" | "area" }[] = [];
  for (const option of options) {
    if (option.kind === "area") {
      const members = elementSets[option.name];
      const nodes = nodeSets[option.name];
      // the region holds the element, or (a box too small for a centroid) one of its corner nodes
      if (option.name === "Face" || (members && members.includes(element)) || (nodes && [...corners].some((n) => nodes.includes(n)))) out.push(option);
    } else {
      const members = nodeSets[option.name];
      if (members && [...corners].filter((n) => members.includes(n)).length >= 2) out.push(option);
    }
  }
  return out;
}

/** The lists with one support added for a region: both in-plane directions and z, the usual start of a fixed edge. */
export function withSupport(lists: PlateLists, region: string): PlateLists {
  return { ...lists, supports: [...lists.supports, { region, dofs: [1, 2, 3], value: "" }] };
}

/** The lists with one load added for a region: a pressure on an area, a force along z on an edge, its value left for the engineer. */
export function withLoad(lists: PlateLists, region: string, kind: "edge" | "area"): PlateLists {
  const load: PlateLoad = kind === "area" ? { region, kind: "pressure", pressure: "" } : { region, kind: "force", dof: 3, total: "" };
  return { ...lists, loads: [...lists.loads, load] };
}

/** One sentence per entry, for the panel's summary and the tests. */
export function plateWords(lists: PlateLists): string[] {
  const dof = (d: number) => DOF_WORDS[d] ?? `dof ${d}`;
  return [
    ...lists.supports.map((s) => `${s.region} holds ${s.dofs.map(dof).join(", ")}${s.value.trim() ? ` at ${s.value.trim()}` : ""}`),
    ...lists.loads.map((l) => l.kind === "pressure" ? `${l.region} under a pressure of ${l.pressure.trim() || "?"} MPa` : `${l.region} loaded by ${l.total.trim() || "?"} N along ${dof(l.dof)}`),
    ...lists.regions.map((r) => `box ${r.name.trim() || "?"}: x ${r.x0}..${r.x1}, y ${r.y0}..${r.y1} mm`),
  ];
}
