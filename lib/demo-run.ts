/** The run the home page's product demo replays (ADR-0094): one answer of the repository's own solver for a public example,
 * recorded by scripts/demo-run.py into lib/demo-run.json. Nothing here computes a result: the numbers are the recorded run's,
 * picked out and worded. */
import record from "./demo-run.json";
import { scaleFor, type Scale } from "./studio-colors";

export type DemoRun = {
  what: string;
  recorded: string;
  solver_version: string;
  rows: string;
  units: { length: string; force: string; stress: string };
  coupon: {
    test: string; standard: string; library: string; layup: string; angles: number[];
    length: number; width: number; tab_length: number; thickness: number; pull: number; pull_unit: string;
  };
  mesh: { nodes: number[][]; quads: number[][]; tabs: number[] };
  field: { key: string; unit: string; min: number; max: number; plies: number[][] };
  summary: {
    nodes: number; elements: number; solve_seconds: number; reaction: number; stress: number;
    first_failure: { ply: number; angle: number; mode: string; place: string; factor: number; fails: boolean; applied: number; applied_unit: string; reaction: number };
  };
};

export const demoRun = record as DemoRun;

/** What is wrong with a recorded run, in words; empty when it is whole and agrees with itself. The unit test reads it. */
export function runProblems(run: DemoRun): string[] {
  const problems: string[] = [];
  const { mesh, field, coupon, summary } = run;
  if (mesh.nodes.length !== summary.nodes) problems.push(`${mesh.nodes.length} nodes stored, ${summary.nodes} counted`);
  if (mesh.quads.length !== summary.elements) problems.push(`${mesh.quads.length} elements stored, ${summary.elements} counted`);
  if (mesh.quads.some((quad) => quad.length !== 4 || quad.some((node) => !Number.isInteger(node) || node < 0 || node >= mesh.nodes.length))) problems.push("an element names a node that is not stored");
  if (mesh.tabs.some((element) => element < 0 || element >= mesh.quads.length)) problems.push("a tab names an element that is not stored");
  if (field.plies.length !== coupon.angles.length) problems.push(`${field.plies.length} plies of the field for ${coupon.angles.length} angles`);
  if (field.plies.some((ply) => ply.length !== mesh.quads.length)) problems.push("a ply's field does not have one value an element");
  const values = field.plies.flat();
  if (values.some((value) => !Number.isFinite(value))) problems.push("the field holds a value that is not a number");
  if (Math.min(...values) !== field.min || Math.max(...values) !== field.max) problems.push("the field's stated range is not its values' range");
  const xs = mesh.nodes.map((node) => node[0]), ys = mesh.nodes.map((node) => node[1]);
  if (Math.abs(Math.max(...xs) - Math.min(...xs) - coupon.width) > 1e-6 || Math.abs(Math.max(...ys) - Math.min(...ys) - coupon.length) > 1e-6) problems.push("the mesh is not the coupon's width by its length");
  const first = summary.first_failure;
  if (first.ply < 1 || first.ply > coupon.angles.length || coupon.angles[first.ply - 1] !== first.angle) problems.push("the first ply to fail is not a ply of the layup");
  if (first.fails !== first.factor <= 1) problems.push("the first failure's factor and its verdict disagree");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(run.recorded) || !run.solver_version) problems.push("the record does not say when it was made or by which version");
  return problems;
}

/** The scale the plies are coloured on: the workspace's own (lib/studio-colors.ts), over the recorded field's range. */
export const demoScale = (run: DemoRun): Scale => scaleFor([], false, [run.field.min, run.field.max]);

/** "ASTM D3039/D3039M-17" as the workspace's standard card names it: "ASTM D3039". */
export const standardName = (run: DemoRun): string => run.coupon.standard.split("/")[0];
/** A force in kilonewtons, to a tenth. */
export const kilonewtons = (newtons: number): string => (newtons / 1000).toFixed(1);
/** An angle as the workspace prints it: 90°, -45°. */
export const degrees = (angle: number): string => `${Number.isInteger(angle) ? angle : angle.toFixed(1)}°`;
