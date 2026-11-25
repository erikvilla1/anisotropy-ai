import { appliedOf } from "@/lib/applied";
import { heldWords } from "@/lib/studio-copy";
import type { ProposedInputs } from "./project-context";
import type { Preview } from "@/lib/studio-api";
import type { SceneLoad, SceneMarker } from "./scene-canvas";

/** The preview's words for each direction (`fea/src/anisotropy_fea/preview.py`, `DOF_WORDS`), so a proposed line reads as the applied lines beside it. */
const PREVIEW_WORDS: Record<number, string> = { 1: "x", 2: "y", 3: "z", 4: "rotation about x", 5: "rotation about y", 6: "rotation about z" };

type Mesh = { quads: number[][]; node_sets: Record<string, number[]>; element_sets: Record<string, number[]> };

/** Whether two meshes are one: as many elements, the first and the last on the same corner nodes. Results solved for a setup changed
 * since (a coupon carried over to boundary conditions of the engineer's own, another element size) are another mesh. */
function sameElements(a: number[][], b: number[][]): boolean {
  return a.length === b.length && String(a[0]) === String(b[0]) && String(a[a.length - 1]) === String(b[b.length - 1]);
}

/** The nodes a region covers: a node set, or the corner nodes of an element set (a pressure on an area region). `mesh` is the one drawn,
 * the results' when they are shown; the preview's mesh is the fall-back, but only while it is the mesh drawn: the preview numbers its own
 * nodes, so a region the drawn mesh does not have covers none of it. (A coupon's results stayed on the page while its setup became a
 * plate with a face under pressure: the plate's node numbers, past the end of the coupon's mesh, blanked the page.) */
export function nodesOf(preview: Pick<Preview, "mesh">, set: string, mesh: Partial<Mesh> = {}): number[] {
  const own = !mesh.quads || sameElements(mesh.quads, preview.mesh.quads); // the preview's numbering holds on the mesh drawn
  const nodeSet = mesh.node_sets?.[set] ?? (own ? preview.mesh.node_sets[set] : undefined);
  if (nodeSet) return nodeSet;
  const drawn = mesh.element_sets?.[set];
  if (!drawn && !own) return [];
  const quads = drawn ? mesh.quads ?? preview.mesh.quads : preview.mesh.quads;
  const elements = drawn ?? preview.mesh.element_sets[set];
  if (!elements) return [];
  return [...new Set(elements.flatMap((e) => quads[e] ?? []))];
}

/** What the model draws and lists of a preview (ADR-0110): every boundary condition with the directions it holds, every load, and the
 * model they act on. The same for the preview and for the results, so a load is never drawn before a run and lost after it. */
export function sceneInputs(preview: Preview, mesh: Partial<Mesh> = {}): { held: SceneMarker[]; loads: SceneLoad[]; about: string[] } {
  const applied = appliedOf(preview);
  return {
    held: applied.conditions.map((c) => ({ nodes: nodesOf(preview, c.set, mesh), label: c.words, dofs: c.dofs })),
    loads: applied.loads.map((l) => ({ nodes: nodesOf(preview, l.set, mesh), label: l.words, direction: l.direction, control: l.control })),
    about: applied.model,
  };
}

/** What a proposal card holds for a plate (ADR-0101), as the model draws it dashed before it is applied (ADR-0110): each boundary condition
 * with its directions, each load with its direction. A pressure positive presses down on the plate, so it is drawn along -z. */
export function proposedInputs(preview: Pick<Preview, "mesh">, proposed: ProposedInputs | null, mesh: Partial<Mesh> = {}): { held: SceneMarker[]; loads: SceneLoad[] } | null {
  if (!proposed || (!proposed.supports.length && !proposed.loads.length)) return null;
  const axis = (dof: number | null) => ["x", "y", "z"][((dof ?? 3) - 1) % 3];
  return {
    held: proposed.supports.map((s) => ({ nodes: nodesOf(preview, s.region, mesh), dofs: s.dofs,
      label: heldWords(s.region, s.dofs, s.dofs.map((d) => PREVIEW_WORDS[d] ?? String(d))) })),
    loads: proposed.loads.map((l) => {
      const value = Number(l.value);
      const direction = l.kind === "pressure" ? (value > 0 ? "-z" : "+z") : `${value < 0 ? "-" : "+"}${axis(l.dof)}`;
      // said as the applied lines beside it say a load (`loadWords`): the amount, then the way it acts
      const label = l.kind === "pressure" ? `${l.region}: pressure ${l.value} ${l.unit} along ${direction}` : `${l.region}: force ${Math.abs(value)} ${l.unit} along ${direction}`;
      return { nodes: nodesOf(preview, l.region, mesh), direction, control: l.kind, label };
    }),
  };
}
