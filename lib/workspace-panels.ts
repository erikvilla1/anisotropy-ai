/** The step panels of the coupon FEA workspace (ADR-0062, part 3): each edits named rows of the one values file (ADR-0046 amendment 3) and
 * shows the checklist items that judge them (the `ITEM_OF_KEY` table of `fea/src/anisotropy_fea/checks.py`, by panel). Every row of the
 * form belongs to exactly one panel; `tests/workspace-panels.test.ts` holds that against the definition. */
import type { ChatStep } from "./studio-chat";
import { fieldByKey, fields, PLY_KEYS, sectionsFor, type Checklist, type StudioForm } from "./studio-form";

export type PanelId = "project" | "geometry" | "layup" | "loads" | "mesh" | "validate" | "run" | "outputs" | "advanced";
export type Panel = { id: PanelId; title: string; keys: string[]; items: string[] };

export const PANELS: readonly Panel[] = [
  { id: "project", title: "Project", keys: ["units", "test", "standard", "size_from", "notes"], items: ["identity", "units"] },
  { id: "geometry", title: "Geometry", keys: ["length", "width", "tab_length", "hole_diameter", "span", "overhang", "load_span"], items: ["geometry"] },
  {
    id: "layup", title: "Layup and material", items: ["laminate", "material", "criterion"],
    keys: [...PLY_KEYS, "symmetric", "ply_thickness", "library", "own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t", "own_F1c", "own_F2t", "own_F2c",
      "own_F6", "own_source", "G13", "G23", "criteria", "f12_star"],
  },
  { id: "loads", title: "Loads and supports", keys: ["control", "value", "grips", "region"], items: ["constraints", "load"] },
  { id: "mesh", title: "Mesh", keys: ["element_size", "mesh_nx", "mesh_partitions", "mesh_seeds", "hole_circumferential", "hole_radial", "hole_ring", "hole_growth"], items: ["mesh", "probes"] },
  { id: "validate", title: "Validate", keys: [], items: [] },
  { id: "run", title: "Run", keys: [], items: ["solver", "document"] },
  { id: "outputs", title: "Outputs", keys: [], items: [] },
  {
    id: "advanced", title: "Advanced: every other row", items: [],
    keys: ["filled_by", "date", "material_code", "layup_code", "team_model", "test_data", "name_part", "name_instance", "name_material", "name_layup", "name_section"],
  },
];

/** The material rows of the layup panel, after the plies: what the panel renders below its ply editor. */
export const MATERIAL_KEYS = PANELS[2].keys.filter((key) => !PLY_KEYS.includes(key) && !["symmetric", "ply_thickness"].includes(key));

export function panel(id: PanelId): Panel {
  const found = PANELS.find((p) => p.id === id);
  if (!found) throw new Error(`no panel ${id}`);
  return found;
}

export function panelOfKey(key: string): PanelId | null {
  return PANELS.find((p) => p.keys.includes(key))?.id ?? null;
}

export function panelOfItem(itemId: string): PanelId | null {
  return PANELS.find((p) => p.items.includes(itemId))?.id ?? null;
}

/** The panel that holds what each step of the assistant's conversation asks for (ADR-0062, part 5): what its suggestions open. */
export const PANEL_OF_STEP: Record<ChatStep, PanelId> = {
  test: "project", material: "layup", shear: "layup", layup: "layup", geometry: "geometry", loading: "loads", name: "run", review: "validate",
};
export const panelOfStep = (step: ChatStep): PanelId => PANEL_OF_STEP[step];

/** The panel's rows the test shows, in the definition's order (a bending coupon has no tab length; a plate no grips). */
export function visibleKeys(form: StudioForm, id: PanelId): string[] {
  const visible = new Set(sectionsFor(form).flatMap((section) => section.fields.map((field) => field.key)));
  const wanted = new Set(panel(id).keys);
  return fields.map((field) => field.key).filter((key) => wanted.has(key) && visible.has(key) && fieldByKey[key]);
}

export type PanelState = "pass" | "warn" | "fail" | "missing" | "pending" | "none";
const SEVERITY: Record<Exclude<PanelState, "none">, number> = { pass: 0, pending: 1, warn: 2, fail: 3, missing: 3 };

/** The worst state among the panel's checklist items; `none` without a checklist or for a panel no item judges. */
export function panelState(id: PanelId, checklist: Checklist | null): PanelState {
  if (!checklist) return "none";
  const items = checklist.items.filter((item) => panel(id).items.includes(item.id));
  if (!items.length) return "none";
  return items.map((item) => item.state).reduce<PanelState>((worst, state) => (worst === "none" || SEVERITY[state] > SEVERITY[worst as Exclude<PanelState, "none">] ? state : worst), "none");
}
