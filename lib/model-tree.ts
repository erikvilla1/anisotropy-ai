/**
 * The model tree of the FEA workspace's left side (ADR-0111): one tab per part of an analysis, in the order a finite element program sets
 * a model up, in words no one program owns, so a model built in any of them reads the same here. Each tab holds the rows it edits, the
 * checklist items that judge them and the rows the software chose for it (`built`), shown with their reason in the tab they belong to.
 * The page computes nothing: every value shown is the form's, the setup check's or the preview's.
 */
import { formatNumber } from "./number-format";
import { fieldByLabel, PLY_KEYS, unitLabels, unitsOf, type Checklist, type StudioForm } from "./studio-form";
import { LOAD_KEYS, MESH_KEYS, OWN_MATERIAL_KEYS, SIZE_KEYS, type BuiltLine } from "./tension-screen";
import type { ChatStep } from "./studio-chat";
import type { PanelState } from "./workspace-panels";
import type { PlateLists } from "./studio-plate";
import type { ImportReading } from "./studio-api";

export type TabId = "test" | "geometry" | "material" | "layup" | "step" | "conditions" | "loads" | "mesh" | "run" | "outputs";
export type Tab = { id: TabId; title: string; keys: string[]; items: string[]; built: string[] };

export const MODEL_TREE: readonly Tab[] = [
  { id: "test", title: "Test", keys: ["standard"], items: ["standard", "identity", "units"], built: ["test", "units", "standard"] },
  { id: "geometry", title: "Geometry", keys: SIZE_KEYS, items: ["geometry"], built: ["width", "length", "tab_length", "strain_device", "strain_length"] },
  { id: "material", title: "Material", keys: ["library", ...OWN_MATERIAL_KEYS], items: ["material", "criterion"], built: ["G13", "G23", "criteria"] },
  { id: "layup", title: "Layup", keys: [...PLY_KEYS, "symmetric"], items: ["laminate"], built: [] },
  { id: "step", title: "Analysis step", keys: [], items: [], built: [] },
  // a tension coupon's boundary conditions are its test's: listed and drawn, changed by no row (a blank form's grip row is the Excel form's,
  // and the package chooses clamped grips for the screen, ADR-0090)
  { id: "conditions", title: "Boundary conditions", keys: [], items: ["constraints"], built: ["grips"] },
  { id: "loads", title: "Loads", keys: LOAD_KEYS, items: ["load"], built: ["control", "value"] },
  { id: "mesh", title: "Mesh", keys: MESH_KEYS, items: ["mesh", "probes"], built: ["element_size"] },
  { id: "run", title: "Solve", keys: ["filled_by"], items: ["solver", "document"], built: [] },
  { id: "outputs", title: "Results", keys: [], items: [], built: [] },
];

export function tab(id: TabId): Tab {
  const found = MODEL_TREE.find((t) => t.id === id);
  if (!found) throw new Error(`no tab ${id}`);
  return found;
}

/** The tab that holds what each step of the assistant's conversation asks for: what its suggestions open on the tree. */
export const TAB_OF_STEP: Record<ChatStep, TabId> = {
  test: "test", material: "material", shear: "material", layup: "layup", geometry: "geometry", loading: "loads", name: "run", review: "run",
};

/** A plate's rows on the tree beyond the tension coupon's (ADR-0089 amendment 7): its size with an optional hole and tabs, under Geometry.
 * Its boundary conditions and loads are lists, not rows, under their own tabs. */
export const PLATE_SIZE_KEYS = ["length", "width", "hole_diameter", "tab_length"];

/** The tab that holds a row: where the assistant opens the tree when a message changes it. */
export function tabOfKey(key: string): TabId | null {
  return MODEL_TREE.find((t) => t.keys.includes(key))?.id ?? (PLATE_SIZE_KEYS.includes(key) ? "geometry" : null);
}

/** What a plate still needs before it can be solved, besides the material, the layup and its size: something held, and a load or a held
 * region that moves (ADR-0101 amendment 1). Words for the line above the tree. */
export function plateMissing(lists: PlateLists): string[] {
  const moves = lists.supports.some((s) => s.value.trim());
  return [...(lists.supports.length ? [] : ["a boundary condition"]), ...(lists.loads.length || moves ? [] : ["a load"])];
}

/** A plate's boundary conditions or loads in the tab's one line: how many, on which regions ("2 on Edge-Bottom, Edge-Left"); null for none. */
export function listLine(entries: { region: string }[]): string | null {
  if (!entries.length) return null;
  const regions = [...new Set(entries.map((e) => e.region))];
  return `${entries.length} on ${regions.join(", ")}`;
}

/** Where a failing checklist item is fixed on the tree: the tab holding the first row it names, else the tab its item belongs to. */
export function tabToFix(item: { id: string; rows: string[] }): TabId | null {
  return item.rows.map((label) => tabOfKey(fieldByLabel[label]?.key ?? "")).find((id): id is TabId => id !== null)
    ?? MODEL_TREE.find((t) => t.items.includes(item.id))?.id ?? null;
}

const SEVERITY: Record<Exclude<PanelState, "none">, number> = { pass: 0, pending: 1, warn: 2, fail: 3, missing: 3 };

/** The worst state among the checklist items that judge a tab's rows; `none` with no checklist or for a tab no item judges. */
export function tabState(id: TabId, checklist: Checklist | null): PanelState {
  const items = checklist?.items.filter((item) => tab(id).items.includes(item.id)) ?? [];
  return items.reduce<PanelState>((worst, item) => (worst === "none" || SEVERITY[item.state] > SEVERITY[worst as Exclude<PanelState, "none">] ? item.state : worst), "none");
}

/** The lines of "what the software chose" that belong to a tab, in the order the package chose them. */
export function builtFor(id: TabId, lines: BuiltLine[]): BuiltLine[] {
  const rows = tab(id).built;
  return lines.filter((line) => rows.includes(line.key));
}

const given = (form: StudioForm, key: string): string => (form[key] ?? "").trim();
/** A row's value as the engineer gave it, else the one the software chose (`inUse`, from the latest check), else null. */
const valueOf = (form: StudioForm, inUse: Record<string, string>, key: string): string | null => given(form, key) || inUse[key] || null;

/** The coupon's size in one line, "250 × 25 mm, 56 mm tabs", from the rows given or chosen; null while neither holds them. */
export function sizeLine(form: StudioForm, inUse: Record<string, string>): string | null {
  const [length, width, tabs] = ["length", "width", "tab_length"].map((key) => valueOf(form, inUse, key));
  if (!length || !width) return null;
  const n = (text: string) => formatNumber(Number(text), { zeros: false });
  const mm = unitLabels(unitsOf(form)).length;
  return `${n(length)} × ${n(width)} ${mm}${tabs ? `, ${n(tabs)} ${mm} tabs` : ""}`;
}

/** The loading in one line, "1 mm pull" or "10000 N pull"; null while it is neither given nor chosen. */
export function loadLine(form: StudioForm, inUse: Record<string, string>, chosenControl: string | null): string | null {
  const value = valueOf(form, inUse, "value");
  if (!value) return null;
  const control = given(form, "control") || chosenControl || "displacement";
  const lab = unitLabels(unitsOf(form));
  return `${formatNumber(Number(value), { zeros: false })} ${control === "force" ? lab.force : lab.length} pull`;
}

/** The element size in one line, "2 mm elements", with the count once a model is built. */
export function meshLine(form: StudioForm, inUse: Record<string, string>, elements: number | null): string | null {
  const size = valueOf(form, inUse, "element_size");
  const parts = [size ? `${formatNumber(Number(size), { zeros: false })} ${unitLabels(unitsOf(form)).length} elements` : null, elements ? `${elements} in all` : null].filter(Boolean);
  return parts.length ? parts.join(", ") : null;
}

const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** The tabs of a model brought in as a file (ADR-0105) on the same tree (ADR-0111 amendment 1): read as it stands, so no tab has a row
 * and no badge; each tab's one line is the reader's own report. */
export const IMPORTED_TABS: readonly TabId[] = ["geometry", "material", "layup", "step", "conditions", "loads", "mesh", "run", "outputs"];

/** Each tab's one line for an imported model, from what the reader took from the file: no number is the page's own. */
export function importedLines(reading: ImportReading): Record<"geometry" | "material" | "layup" | "step" | "conditions" | "loads" | "mesh", string> {
  const section = reading.sections[0];
  const loads = [reading.concentrated_loads ? count(reading.concentrated_loads, "force line") : "", reading.pressures ? count(reading.pressures, "pressure line") : "",
    reading.edge_loads ? count(reading.edge_loads, "edge load") : ""].filter(Boolean);
  return {
    geometry: `${count(reading.parts, "part")}, ${count(reading.instances, "instance")}`,
    material: reading.materials.map((m) => m.name).join(", ") || "none",
    layup: reading.layup ? `${reading.layup}${section ? `, ${count(section.plies, "ply", "plies")}` : ""}` : "none stated",
    step: "Static, linear",
    conditions: `${count(reading.boundaries, "boundary line")}${reading.couplings ? `, ${count(reading.couplings, "coupling")}` : ""}`,
    loads: loads.join(", ") || "by moved supports only",
    mesh: `${count(reading.elements, "element")}, ${count(reading.nodes, "node")}`,
  };
}
