/** The example wing the home page's product demo shows (ADR-0098): its parts, the mesh that was solved and the solver's answer,
 * written by scripts/demo-wing.py into lib/demo-wing.json. Nothing here computes a result: the mesh and the numbers are the
 * record's, picked out and worded. The wing is an example made for the demo, not a design of ours or of anyone's. */
import record from "./demo-wing.json";
import { scaleFor, type Scale } from "./studio-colors";

export type WingPart = { id: string; name: string; layup: string; angles: number[]; first: number; count: number };
export type WingField = { key: string; label: string; unit: string; min: number; max: number; values: number[] };
export type WingSolve = {
  solver: string; recorded: string; nodes: number; elements: number; seconds: number; reaction: number; tip_deflection: number;
  parts: { id: string; max: number; at: number }[];
  governing: { part: string; value: number; at: number; ply?: number; angle?: number; mode?: string };
};
export type DemoWing = {
  what: string;
  built: string;
  units: { length: string; force: string; stress: string };
  wing: { span: number; chord: number; depth: number; aerofoil: string; spars: number[]; ribs: number[]; library: string };
  parts: WingPart[];
  mesh: { nodes: number[][]; quads: number[][]; part: number[] };
  load?: { total: number; unit: string; how: string };
  field?: WingField;
  solve?: WingSolve;
};

export const demoWing = record as unknown as DemoWing;

/** What is wrong with the record, in words; empty when it is whole and agrees with itself. The unit test reads it. */
export function wingProblems(wing: DemoWing): string[] {
  const problems: string[] = [];
  const { mesh, parts, field, solve } = wing;
  if (mesh.part.length !== mesh.quads.length) problems.push(`${mesh.part.length} part marks for ${mesh.quads.length} faces`);
  if (mesh.quads.some((quad) => quad.length !== 4 || new Set(quad).size !== 4 || quad.some((node) => !Number.isInteger(node) || node < 0 || node >= mesh.nodes.length))) problems.push("a face names a node that is not stored, or one twice");
  if (mesh.nodes.some((node) => node.length !== 3 || node.some((value) => !Number.isFinite(value)))) problems.push("a node is not three numbers");
  const used = new Set(mesh.quads.flat());
  if (used.size !== mesh.nodes.length) problems.push(`${mesh.nodes.length - used.size} nodes belong to no face`);
  let next = 0;
  parts.forEach((part, index) => {
    if (part.first !== next) problems.push(`${part.name} does not start where the part before it ends`);
    for (let face = part.first; face < part.first + part.count; face++) if (mesh.part[face] !== index) { problems.push(`a face of ${part.name} is marked for another part`); break; }
    if (!part.angles.length) problems.push(`${part.name} has no plies`);
    next = part.first + part.count;
  });
  if (next !== mesh.quads.length) problems.push("the parts do not cover the mesh");
  const xs = mesh.nodes.map((node) => node[0]), ys = mesh.nodes.map((node) => node[1]);
  if (Math.abs(Math.max(...xs) - Math.min(...xs) - wing.wing.chord) > 1e-6 || Math.abs(Math.max(...ys) - Math.min(...ys) - wing.wing.span) > 1e-6) problems.push("the mesh is not the wing's chord by its span");
  if (Boolean(field) !== Boolean(solve) || Boolean(field) !== Boolean(wing.load)) problems.push("the analysis is recorded in part: the field, the solve and the load go together");
  if (field && solve) {
    if (field.values.length !== mesh.quads.length) problems.push(`${field.values.length} values for ${mesh.quads.length} faces`);
    if (field.values.some((value) => !Number.isFinite(value))) problems.push("the field holds a value that is not a number");
    if (Math.min(...field.values) !== field.min || Math.max(...field.values) !== field.max) problems.push("the field's stated range is not its values' range");
    for (const entry of solve.parts) {
      const part = parts.find((candidate) => candidate.id === entry.id);
      if (!part) { problems.push(`the solve names a part that is not stored: ${entry.id}`); continue; }
      const largest = Math.max(...field.values.slice(part.first, part.first + part.count));
      if (Math.abs(largest - entry.max) > 1e-9 * Math.max(1, Math.abs(largest))) problems.push(`${part.name}'s stated largest value is not its faces' largest`);
    }
    if (solve.parts.length !== parts.length) problems.push("the solve does not speak of every part");
    if (!parts.some((part) => part.id === solve.governing.part)) problems.push("the governing part is not a part of the wing");
    if (Math.abs(solve.governing.value - field.max) > 1e-9 * Math.max(1, Math.abs(field.max))) problems.push("the governing value is not the field's largest");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(solve.recorded) || !solve.solver) problems.push("the solve does not say when it was made or by what");
    if (wing.load && Math.abs(solve.reaction - wing.load.total) > 0.01 * wing.load.total) problems.push(`the root holds ${solve.reaction} ${wing.load.unit} against ${wing.load.total} applied`);
  }
  return problems;
}

/** The scale the parts are coloured on: the workspace's own (lib/studio-colors.ts), over the recorded field's range. */
export const wingScale = (field: WingField): Scale => scaleFor([], false, [field.min, field.max]);

/** A length in metres, to two places: 2.13 m. */
export const metres = (millimetres: number): string => `${(millimetres / 1000).toFixed(2)} m`;
