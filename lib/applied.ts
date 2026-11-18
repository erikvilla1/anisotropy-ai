/** What is applied to a model, as the page shows it under the model and the assistant says it (ADR-0110): its boundary conditions, its
 * loads, and the model they act on, each from the package's preview. Nothing is computed: the sets, directions and values are the
 * preview's, put in words. */
import { heldWords, loadWords } from "./studio-copy";
import type { Preview } from "./studio-api";

type PreviewLoad = NonNullable<Preview["loads"]>[number];

export type AppliedCondition = { set: string; dofs: number[]; words: string };
export type AppliedLoad = { set: string; control: string; direction: string; value: number; unit: string; words: string };
export type Applied = { conditions: AppliedCondition[]; loads: AppliedLoad[]; model: string[] };

const sameLoad = (a: PreviewLoad, b: PreviewLoad) => a.set === b.set && a.direction === b.direction && a.value === b.value && a.control === b.control;

/** Every boundary condition, one per set with every direction it holds merged, and every load, the first one once even when the preview
 * also lists it among `loads` (audit fea-run-16). */
export function appliedOf(preview: Pick<Preview, "held" | "loaded" | "loads" | "material" | "coupon" | "mesh"> & Partial<Pick<Preview, "plies">>): Applied {
  const conditions = [...new Set(preview.held.map((h) => h.set))].map((set) => {
    const of = preview.held.filter((h) => h.set === set);
    const dofs = [...new Set(of.flatMap((h) => h.dofs))].sort((a, b) => a - b);
    return { set, dofs, words: heldWords(set, dofs, of.flatMap((h) => h.directions)) };
  });
  const all = [...(preview.loaded ? [preview.loaded] : []), ...(preview.loads ?? []).filter((l) => !preview.loaded || !sameLoad(l, preview.loaded))];
  const loads = all.map((l) => ({ set: l.set, control: l.control, direction: l.direction, value: l.value, unit: l.unit, words: loadWords(l) }));
  const plies = preview.plies?.length ?? preview.material.plies;
  const model = [
    preview.material.name,
    preview.coupon.layup ? `${preview.coupon.layup}${plies ? `, ${plies} plies` : ""}` : null,
    `${preview.mesh.element_count} shell elements`,
    "one linear static step",
  ].filter((part): part is string => !!part);
  return { conditions, loads, model };
}
