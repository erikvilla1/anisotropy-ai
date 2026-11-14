/** The example wing the home page's product demo shows (ADR-0098): its parts, the mesh that was solved and the solver's answer,
 * written by scripts/demo-wing.py into lib/demo-wing.json. Nothing here computes a result: the mesh and the numbers are the
 * record's, picked out and worded. The wing is an example made for the demo, not a design of ours or of anyone's. */
import record from "./demo-wing.json";

export type WingPart = { id: string; name: string; layup: string; angles: number[]; first: number; count: number };
export type WingField = { key: string; label: string; unit: string; min: number; max: number; values: number[] };
export type WingSolve = {
  solver: string; recorded: string; nodes: number; elements: number; seconds: number; reaction: number;
  /** The largest rise of any node: with the winglet, the fin's tip. */
  tip_deflection: number;
  /** The largest rise on the tip rib, where the span ends and the winglet begins. */
  tip_rib_deflection: number;
  parts: { id: string; max: number; at: number }[];
  governing: { part: string; value: number; at: number; ply?: number; angle?: number; mode?: string };
};
/** The winglet outboard of the tip rib: seen along the chord (x), the chord line turns up through an arc of `radius` until it
 * leans `cant` degrees from the wing's plane (the bend), then runs straight for `fin` (the fin). The fin's tip has `tip_chord`
 * of chord, its leading edge `sweep` aft of the wing tip's, `rise` above the wing's chord line and `reach` outboard of the tip
 * rib. `stations` has a row for each station outboard of the tip rib: how far out along that line it lies, its leading edge's
 * x, y and z, its chord (which runs along x) and the degrees its section is turned up. `ribs` says how far out the winglet's
 * ribs stand, and `measures` what each number measures, in the record's own words. */
export type Winglet = {
  cant: number; radius: number; fin: number; sweep: number; tip_chord: number; rise: number; reach: number;
  ribs: number[]; stations: number[][]; measures: Record<string, string>;
};
export type DemoWing = {
  what: string;
  built: string;
  units: { length: string; force: string; stress: string };
  /** A straight-edged, tapered and swept half wing with a winglet at its tip. `span` is measured to the tip rib, where the
   * winglet begins; `sweep` is how far aft of the root's leading edge the tip rib's is; `ribs` are the wing's own, by y. */
  wing: { span: number; root_chord: number; tip_chord: number; sweep: number; depth: number; aerofoil: string; spars: number[]; ribs: number[]; library: string; winglet: Winglet };
  parts: WingPart[];
  mesh: { nodes: number[][]; quads: number[][]; part: number[] };
  load?: { total: number; unit: string; how: string };
  field?: WingField;
  /** How far each stored node moves under the load, in node order. */
  displacement?: { unit: string; values: number[][] };
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
  // The wing to its tip rib is its plan; outboard of the tip rib the mesh is the winglet the record states.
  const inboard = mesh.nodes.filter((node) => node[1] <= wing.wing.span);
  const xs = inboard.map((node) => node[0]), ys = inboard.map((node) => node[1]);
  if (Math.abs(Math.max(...xs) - Math.min(...xs) - planExtent(wing)) > 1e-6 || Math.abs(Math.max(...ys) - Math.min(...ys) - wing.wing.span) > 1e-6) problems.push("the mesh is not the wing's plan: its chords and sweep by its span");
  problems.push(...wingletProblems(wing));
  if (Boolean(field) !== Boolean(solve) || Boolean(field) !== Boolean(wing.load) || Boolean(field) !== Boolean(wing.displacement)) problems.push("the analysis is recorded in part: the field, the displacement, the solve and the load go together");
  if (wing.displacement && (wing.displacement.values.length !== mesh.nodes.length || wing.displacement.values.some((row) => row.length !== 3 || row.some((value) => !Number.isFinite(value))))) problems.push("the displacement is not three numbers a node");
  if (wing.displacement && solve && Math.abs(Math.max(...wing.displacement.values.map((row) => row[2])) - solve.tip_deflection) > 0.011) problems.push("the stated tip deflection is not the largest upward displacement stored");
  if (wing.displacement && solve && wing.displacement.values.length === mesh.nodes.length) {
    const onTipRib = wing.displacement.values.filter((_, node) => mesh.nodes[node][1] === wing.wing.span).map((row) => row[2]);
    if (!onTipRib.length || !(Math.abs(Math.max(...onTipRib) - solve.tip_rib_deflection) <= 0.011)) problems.push("the stated deflection of the tip rib is not the largest upward displacement stored on it");
  }
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

/** The colours the parts take, at the lead's word of 2026-11-14 ("make the FEA analysis colors like that"): the rainbow most
 * analysis programs draw, blue at the field's smallest value through cyan, green and yellow to red at its largest. The
 * workspace itself keeps its own scale (lib/studio-colors.ts); this one is the demo's only. */
export const RAINBOW: [number, number, number][] = [[0, 0, 1], [0, 1, 1], [0, 1, 0], [1, 1, 0], [1, 0, 0]];
/** A value's colour on the rainbow, as red, green and blue from 0 to 1. */
export function wingColour(field: WingField, value: number): [number, number, number] {
  const share = field.max > field.min ? Math.min(1, Math.max(0, (value - field.min) / (field.max - field.min))) : 0;
  const place = share * (RAINBOW.length - 1);
  const from = Math.min(RAINBOW.length - 2, Math.floor(place));
  const mix = place - from;
  return [0, 1, 2].map((channel) => RAINBOW[from][channel] + (RAINBOW[from + 1][channel] - RAINBOW[from][channel]) * mix) as [number, number, number];
}
/** The legend's bar: the same rainbow, left to right. */
export const RAINBOW_GRADIENT = `linear-gradient(to right, ${RAINBOW.map((stop) => `rgb(${stop.map((channel) => Math.round(channel * 255)).join(" ")})`).join(", ")})`;

/** How far the wing alone reaches from nose to tail in plan, from the root to the tip rib: the root's chord, or the swept tip
 * rib's trailing edge if that is further aft. */
export const planExtent = (wing: DemoWing): number => Math.max(wing.wing.root_chord, wing.wing.sweep + wing.wing.tip_chord);

/** How far the whole drawn wing reaches from nose to tail in plan, winglet and all: the wing's own reach, or the trailing edge
 * of the winglet's station that lies furthest aft. */
export const wingExtent = (wing: DemoWing): number => Math.max(planExtent(wing), ...wing.wing.winglet.stations.map((station) => station[1] + station[4]));

/** The box the stored mesh fills, as its least and greatest x, y and z: what to centre the drawing on. With the winglet the
 * mesh reaches past `span` along y and far above `depth` along z. */
export function wingBox(wing: DemoWing): { min: [number, number, number]; max: [number, number, number] } {
  const along = (axis: number) => wing.mesh.nodes.map((node) => node[axis]);
  return { min: [0, 1, 2].map((axis) => Math.min(...along(axis))) as [number, number, number], max: [0, 1, 2].map((axis) => Math.max(...along(axis))) as [number, number, number] };
}

/** How many ribs the wing has: its own and the winglet's. */
export const ribCount = (wing: DemoWing): number => wing.wing.ribs.length + wing.wing.winglet.ribs.length;

/** The stored nodes are rounded to 0.001 mm outboard of the tip rib: a stated place is met within twice that. A number that
 * is missing is never near anything. */
const PLACED = 0.002;
const near = (a: number, b: number): boolean => Math.abs(a - b) <= PLACED;

/** What is wrong with the winglet as the record states it, against itself and against the mesh; empty when they agree. */
export function wingletProblems(wing: DemoWing): string[] {
  const problems: string[] = [];
  const { span, sweep, depth, root_chord, winglet } = wing.wing;
  if (!winglet) return ["the record states no winglet"];
  const { cant, radius, fin, rise, reach, stations } = winglet;
  if ([cant, radius, fin, winglet.sweep, winglet.tip_chord, rise, reach].some((value) => !Number.isFinite(value)) || !Array.isArray(stations) || !Array.isArray(winglet.ribs)) return ["the winglet does not state all its numbers"];
  for (const name of ["cant", "radius", "fin", "sweep", "tip_chord", "rise", "reach", "ribs", "stations"]) if (!winglet.measures?.[name]) problems.push(`the winglet does not say what its ${name} measures`);
  if (!stations.length || stations.some((station) => station.length !== 6 || station.some((value) => !Number.isFinite(value)))) return [...problems, "a station of the winglet is not six numbers"];
  // Its stated rise and reach are those of its cant, bend radius and fin length.
  const turn = (cant * Math.PI) / 180;
  if (!near(radius * (1 - Math.cos(turn)) + fin * Math.sin(turn), rise) || !near(radius * Math.sin(turn) + fin * Math.cos(turn), reach)) problems.push("the winglet's rise and reach are not those of its cant, radius and fin");
  // The stations run outwards, turning up round the arc and then standing on the fin's line; the last is the stated tip.
  stations.forEach(([out, , y, z, chord, turned], index) => {
    const before = index ? stations[index - 1] : [0, sweep, span, 0, wing.wing.tip_chord, 0];
    if (!(out > before[0] && turned >= before[5] && turned <= cant && chord > 0)) problems.push(`the winglet's station ${index + 1} does not follow the one before it`);
    // Where the chord line is, that far out: on the arc while the section is still turning, and then up the fin.
    const angle = (turned * Math.PI) / 180, upFin = turned < cant ? 0 : out - radius * turn;
    const onLine = near(y, span + radius * Math.sin(angle) + upFin * Math.cos(turn)) && near(z, radius * (1 - Math.cos(angle)) + upFin * Math.sin(turn));
    if (!onLine || !(upFin >= -PLACED) || (turned < cant && !near(out, radius * angle))) problems.push(`the winglet's station ${index + 1} is not on its arc or its fin`);
  });
  const tip = stations[stations.length - 1];
  const stated = [radius * turn + fin, sweep + winglet.sweep, span + reach, rise, winglet.tip_chord, cant];
  if (stated.some((value, index) => !near(tip[index], value))) problems.push("the winglet's last station is not the tip it states");
  if (!winglet.ribs.length || winglet.ribs.some((rib) => !stations.some((station) => near(station[0], rib)))) problems.push("a rib of the winglet stands on no station");
  // The mesh holds every station: a node on its leading edge and one on its trailing edge, the chord along x between them.
  const outboard = wing.mesh.nodes.filter((node) => node[1] > span);
  const holds = (x: number, y: number, z: number) => outboard.some((node) => near(node[0], x) && near(node[1], y) && near(node[2], z));
  stations.forEach(([, nose, y, z, chord], index) => {
    if (!holds(nose, y, z) || !holds(nose + chord, y, z)) problems.push(`the mesh does not hold the winglet's station ${index + 1}`);
  });
  // And no more than that: the mesh reaches no further aft than the stations, and it ends at the stated tip, within the
  // aerofoil's depth there.
  const deep = (depth / root_chord) * winglet.tip_chord;
  const box = wingBox(wing);
  if (box.min[0] !== 0 || !near(box.max[0], wingExtent(wing))) problems.push("the mesh does not reach from the root's nose to the aftmost trailing edge stated");
  const ends = (value: number, stated: number) => value >= stated - PLACED && value <= stated + deep;
  if (!ends(box.max[1], span + reach) || !ends(box.max[2], rise)) problems.push("the mesh does not end at the winglet's stated tip");
  return problems;
}

/** How many times its size the page draws the wing's deflection, so a bend of a few centimetres on a two-metre wing can be
 * seen. A drawing choice only: the stated deflection is the recorded one. */
export const BEND_DRAWN = 5;

/** A length in metres, to two places: 2.13 m. */
export const metres = (millimetres: number): string => `${(millimetres / 1000).toFixed(2)} m`;
