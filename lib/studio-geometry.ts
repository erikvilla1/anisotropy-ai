/**
 * The shapes the studio draws (ADR-0051): a plate from the mesh's nodes and quads, extruded by the laminate's thickness, its
 * deformed positions, and where a node set sits. Plain arrays and no three.js import, so `tsx --test` runs the checks. Every
 * number drawn comes from the fea package's preview or fields; a scale factor is a display choice, named as such.
 */

export type Vec2 = number[];

/** Two triangles per quad, keeping the quad's orientation (counterclockwise seen from +z). */
export function quadsToTriangles(quads: number[][]): number[] {
  const out: number[] = [];
  for (const [a, b, c, d] of quads) out.push(a, b, c, a, c, d);
  return out;
}

/** The element a picked triangle of the top face belongs to. */
export function elementOfTriangle(triangleIndex: number): number {
  return Math.floor(triangleIndex / 2);
}

/** The edges that belong to one quad only: the plate's outline, each as [a, b] in the quad's order. */
export function boundaryEdges(quads: number[][]): [number, number][] {
  const seen = new Map<string, [number, number]>();
  const counts = new Map<string, number>();
  for (const quad of quads) {
    for (let k = 0; k < 4; k++) {
      const a = quad[k], b = quad[(k + 1) % 4];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
      if (!seen.has(key)) seen.set(key, [a, b]);
    }
  }
  return [...counts.entries()].filter(([, n]) => n === 1).map(([key]) => seen.get(key)!);
}

export type PlateMesh = {
  positions: number[]; // x, y, z per vertex
  triangles: number[]; // vertex indices, three per triangle: the top face first (two per element), then the bottom, then the walls
  vertexNode: number[]; // the mesh node each vertex stands on
  vertexElement: number[]; // the element each vertex belongs to (a wall takes the element that owns its edge)
  topTriangles: number; // the first triangles: picking one of them picks an element
  elementCount: number;
};

/** The quad that owns each boundary edge, in the same order as `boundaryEdges`. */
export function boundaryOwners(quads: number[][]): number[] {
  const owner = new Map<string, number>();
  const counts = new Map<string, number>();
  quads.forEach((quad, e) => {
    for (let k = 0; k < 4; k++) {
      const a = quad[k], b = quad[(k + 1) % 4];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
      if (!owner.has(key)) owner.set(key, e);
    }
  });
  return [...counts.entries()].filter(([, n]) => n === 1).map(([key]) => owner.get(key)!);
}

/**
 * The plate as a closed surface with its own four vertices per element face, so an element can be painted flat with one colour
 * or smoothly with its nodes' colours: the top face at +thickness/2 (two triangles per element, counterclockwise seen from +z),
 * the bottom face at -thickness/2 (reversed) and a wall on every boundary edge. `xy` gives the (deformed) node positions when
 * they differ from `nodes`.
 */
export function plateMesh(nodes: number[][], quads: number[][], thickness: number, xy?: number[][], heights?: number[] | null): PlateMesh {
  const points = xy ?? nodes;
  const positions: number[] = [], triangles: number[] = [], vertexNode: number[] = [], vertexElement: number[] = [];
  const z = thickness / 2;
  const add = (node: number, element: number, height: number) => {
    positions.push(points[node][0], points[node][1], height + (heights ? heights[node] : 0));
    vertexNode.push(node);
    vertexElement.push(element);
    return vertexNode.length - 1;
  };
  quads.forEach((quad, e) => {
    const [a, b, c, d] = quad.map((node) => add(node, e, z));
    triangles.push(a, b, c, a, c, d);
  });
  const topTriangles = triangles.length / 3;
  quads.forEach((quad, e) => {
    const [a, b, c, d] = quad.map((node) => add(node, e, -z));
    triangles.push(a, c, b, a, d, c);
  });
  const edges = boundaryEdges(quads), owners = boundaryOwners(quads);
  edges.forEach(([a, b], k) => {
    const e = owners[k];
    const [at, bt, bb, ab] = [add(a, e, z), add(b, e, z), add(b, e, -z), add(a, e, -z)];
    triangles.push(at, bb, bt, at, ab, bb);
  });
  return { positions, triangles, vertexNode, vertexElement, topTriangles, elementCount: quads.length };
}

/** Red, green, blue per vertex from one colour per node (smooth) or one per element (flat), each as flat RGB triples. */
export function vertexColors(mesh: PlateMesh, by: "node" | "element", colors: number[]): number[] {
  const out: number[] = [];
  const source = by === "node" ? mesh.vertexNode : mesh.vertexElement;
  for (const index of source) out.push(colors[3 * index], colors[3 * index + 1], colors[3 * index + 2]);
  return out;
}

/** The outline of one element on the top face, as a closed loop of x, y, z, for the critical element's frame; `heights` lifts each node (a deflection). */
export function elementLoop(nodes: number[][], quad: number[], height: number, heights?: number[] | null): number[][] {
  return quad.map((node) => [nodes[node][0], nodes[node][1], height + (heights ? heights[node] : 0)]);
}

/** Every element edge once, on the top face: the wireframe. Returns pairs of points. */
export function elementEdges(nodes: number[][], quads: number[][], height: number, heights?: number[] | null): number[][][] {
  const seen = new Set<string>();
  const out: number[][][] = [];
  const lift = (node: number) => height + (heights ? heights[node] : 0);
  for (const quad of quads) {
    for (let k = 0; k < 4; k++) {
      const a = quad[k], b = quad[(k + 1) % 4];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push([[nodes[a][0], nodes[a][1], lift(a)], [nodes[b][0], nodes[b][1], lift(b)]]);
    }
  }
  return out;
}

/** Node coordinates moved by their in-plane displacement times a display scale. */
export function deformedPositions(nodes: number[][], displacement: number[][], scale: number): number[][] {
  return nodes.map(([x, y], i) => [x + scale * displacement[i][0], y + scale * displacement[i][1]]);
}

/** The deflection of every node times a display scale, when the package wrote a third component (a shell solve, ADR-0053); else null. */
export function deformedHeights(displacement: number[][], scale: number): number[] | null {
  if (!displacement.length || displacement[0].length < 3) return null;
  return displacement.map((u) => scale * u[2]);
}

/** The mean lift of a node set, so a frame drawn on the deformed plate sits on it. */
export function meanHeight(heights: number[] | null, indices: number[]): number {
  if (!heights || !indices.length) return 0;
  return indices.reduce((sum, i) => sum + (heights[i] ?? 0), 0) / indices.length;
}

/** A display scale that makes the largest displacement about a tenth of the plate's longest side, rounded to one significant digit. */
export function suggestedScale(nodes: number[][], magnitude: number[]): number {
  const largest = Math.max(...magnitude, 0);
  if (largest <= 0) return 1;
  const xs = nodes.map((p) => p[0]), ys = nodes.map((p) => p[1]);
  const size = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const raw = 0.1 * size / largest;
  const power = 10 ** Math.floor(Math.log10(raw));
  return Math.max(1, Math.round(raw / power) * power);
}

export function centroid(nodes: number[][], indices: number[]): Vec2 {
  if (!indices.length) return [0, 0];
  let x = 0, y = 0;
  for (const i of indices) { x += nodes[i][0]; y += nodes[i][1]; }
  return [x / indices.length, y / indices.length];
}

export function bounds(nodes: number[][]): { min: Vec2; max: Vec2; size: Vec2 } {
  const xs = nodes.map((p) => p[0]), ys = nodes.map((p) => p[1]);
  const min = [Math.min(...xs), Math.min(...ys)], max = [Math.max(...xs), Math.max(...ys)];
  return { min, max, size: [max[0] - min[0], max[1] - min[1]] };
}

/** The outline of a node set as the bounding box of its nodes: how a held or loaded tab is framed. */
export function setBox(nodes: number[][], indices: number[]): { min: Vec2; max: Vec2 } | null {
  if (!indices.length) return null;
  const { min, max } = bounds(indices.map((i) => nodes[i]));
  return { min, max };
}

/** One value per node from one value per element: the mean over the elements sharing the node, for a smooth display only. The fea
 * package writes these averages for every field it reports; this helper exists for the checks of the page's own drawing code. */
export function nodeMeans(quads: number[][], nodeCount: number, elementValues: number[]): (number | null)[] {
  const totals = new Array<number>(nodeCount).fill(0), counts = new Array<number>(nodeCount).fill(0);
  quads.forEach((quad, e) => { for (const i of quad) { totals[i] += elementValues[e]; counts[i] += 1; } });
  return totals.map((t, i) => (counts[i] ? t / counts[i] : null));
}
