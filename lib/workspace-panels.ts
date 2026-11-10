/** The step panels of the coupon FEA workspace (ADR-0062, part 3): each edits named rows of the one values file (ADR-0046 amendment 3) and
 * shows the checklist items that judge them (the `ITEM_OF_KEY` table of `fea/src/anisotropy_fea/checks.py`, by panel). Every row of the
 * form belongs to exactly one panel; `tests/workspace-panels.test.ts` holds that against the definition. */
import type { ChatStep } from "./studio-chat";
import {
  DOGBONE_KEYS, fieldByKey, fields, ISOTROPIC_KEYS, NO_STANDARD, PLY_KEYS, sectionsFor, standardOf, standardsFor, type Checklist, type JudgedRequirement,
  type StandardProfile, type StandardRequirement, type StudioForm,
} from "./studio-form";

export type PanelId = "test" | "project" | "geometry" | "layup" | "loads" | "mesh" | "validate" | "run" | "outputs" | "advanced";
export type Panel = { id: PanelId; title: string; keys: string[]; items: string[] };

export const PANELS: readonly Panel[] = [
  // the first step asks what test this is and under which standard (ADR-0062 amendment 1): every later step depends on the answer
  { id: "test", title: "Test and standard", keys: ["test", "standard", "specimen"], items: ["standard"] },
  { id: "project", title: "Project", keys: ["units", "notes"], items: ["identity", "units"] },
  {
    id: "geometry", title: "Geometry", items: ["geometry"],
    keys: ["size_from", "length", "width", "tab_length", "hole_diameter", "span", "overhang", "load_span", "tab_thickness", "tab_bevel", "tab_material", "strain_device",
      "strain_length", ...DOGBONE_KEYS],
  },
  {
    // what the coupon is made of first (ADR-0075): plies of a composite, or one isotropic material such as a plastic, stated by its thickness, E and nu
    id: "layup", title: "Layup and material", items: ["laminate", "material", "criterion"],
    keys: ["material_kind", ...ISOTROPIC_KEYS, ...PLY_KEYS, "symmetric", "ply_thickness", "library", "own_name", "own_E1", "own_E2", "own_G12", "own_nu12", "own_F1t",
      "own_F1c", "own_F2t", "own_F2c", "own_F6", "own_source", "G13", "G23", "criteria", "f12_star"],
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

export function panel(id: PanelId): Panel {
  const found = PANELS.find((p) => p.id === id);
  if (!found) throw new Error(`no panel ${id}`);
  return found;
}

/** The material rows of the layup panel, after the plies: what the panel renders below its ply editor. The Material kind row sits above the
 * editor, since it decides whether there are plies at all (ADR-0075). */
export const MATERIAL_KEYS = panel("layup").keys.filter((key) => !PLY_KEYS.includes(key) && !["material_kind", "symmetric", "ply_thickness"].includes(key));

export function panelOfKey(key: string): PanelId | null {
  return PANELS.find((p) => p.keys.includes(key))?.id ?? null;
}

export function panelOfItem(itemId: string): PanelId | null {
  return PANELS.find((p) => p.items.includes(itemId))?.id ?? null;
}

/** The panel that holds what each step of the assistant's conversation asks for (ADR-0062, part 5): what its suggestions open. */
export const PANEL_OF_STEP: Record<ChatStep, PanelId> = {
  test: "test", material: "layup", shear: "layup", layup: "layup", geometry: "geometry", loading: "loads", name: "run", review: "validate",
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

/** The step panels in the order the rail numbers them, the first being the test and its standard; Validate, Run, Outputs and Advanced follow
 * unnumbered as the panels that act on the rows rather than state them. */
export const STEPS: PanelId[] = ["test", "project", "geometry", "layup", "loads", "mesh"];
export const stepNumber = (id: PanelId): number | null => (STEPS.includes(id) ? STEPS.indexOf(id) + 1 : null);
/** The steps whose rows depend on the test (a bending coupon has supports, a plate regions): they wait for the first step's answer. */
export const NEEDS_TEST: PanelId[] = ["geometry", "layup", "loads", "mesh"];

/** What the rail's head says the engineer is setting up (ADR-0062 amendment 1): the test, and the standard it follows or that it follows
 * none; null before a test is picked. Words only: the page judges nothing. */
export function setupLine(form: StudioForm): { test: string; standard: StandardProfile | null; offered: StandardProfile[]; specimen: string } | null {
  if (!form.test) return null;
  return { test: form.test, standard: standardOf(form), offered: standardsFor(form.test), specimen: form.specimen ?? "" };
}

/** The requirements of the coupon's standard that name a row of this step (ADR-0062 amendment 1, on ADR-0072's profiles): what the step
 * shows as "what the standard asks here". A requirement naming rows of two steps shows on both; the laboratory's clauses name no row and stay
 * on the standard's card. After a check, each comes with the check's verdict from the Test standard item; before one, as the profile states it. */
export function stepRequirements(form: StudioForm, id: PanelId, checklist: Checklist | null): (StandardRequirement | JudgedRequirement)[] {
  const profile = standardOf(form);
  if (!profile || id === "test" || form.standard === NO_STANDARD) return [];
  const keys = new Set(panel(id).keys);
  const judged = new Map((checklist?.items.find((item) => item.id === "standard")?.requirements ?? []).map((r) => [r.id, r]));
  return profile.requirements
    .filter((r) => r.level !== "lab" && r.rows.some((key) => keys.has(key)))
    .map((r) => judged.get(r.id) ?? r);
}
