"use client";

import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Grid, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { bounds, deformedHeights, deformedPositions, elementEdges, elementLoop, fieldAttribute, gripOf, meanHeight, onMesh, plateMesh, sampleNodes, setBox } from "@/lib/studio-geometry";
import { HELD, LOADED, overlayColors, type Palette } from "@/lib/studio-colors";
import { applyScale, fieldMaterial, IN_GRIP, NO_VALUE, type FieldScale } from "./field-material";
import { PRESENTATION_MATERIAL, PresentationLighting } from "./scene-lighting";
import { WebGLMissing, webglAvailable } from "./webgl-missing";
import { FitCamera } from "./fit-camera";
import { Slot, useCanvasSlots } from "@/components/workspace/canvas-slots";

/** A field on the plate (ADR-0063): the package's values, one per node (smooth) or per element (flat), and the scale that colours them. */
export type SceneField = { by: "node" | "element"; values: (number | null)[]; scale: FieldScale;
  /** the elements clamped inside a grip, drawn in the grip's grey, not by value (ADR-0063 amendment 4) */ held?: readonly number[] };
/** A region drawn on the model: its nodes, its line in the list under the model, and, for a boundary condition, the directions it holds
 * (1 to 3 the moves along x, y, z, 4 to 6 the turns about them), each marked by a symbol (ADR-0110). */
export type SceneMarker = { nodes: number[]; label: string; dofs?: number[] };
export type SceneLoad = SceneMarker & { direction: string; control?: string };
export type SceneProps = {
  nodes: number[][]; quads: number[][]; thickness: number;
  /** With a field the scene is in results mode: unlit, coloured on the graphics card; without one, presentation mode. */
  field?: SceneField | null;
  displacement?: number[][] | null; scale?: number;
  held?: SceneMarker[];
  loaded?: SceneLoad | null;
  loads?: SceneLoad[]; // further loads of a plate (ADR-0054), drawn like `loaded`
  /** The tab of the model tree open on the left: its boundary conditions or its loads are drawn bolder (ADR-0111). */
  emphasis?: "conditions" | "loads" | null;
  /** What the assistant proposes and the engineer has not applied yet, drawn dashed (ADR-0110). */
  proposed?: { held: SceneMarker[]; loads: SceneLoad[] } | null;
  /** The model the inputs act on, in a few words: material, layup, mesh, step. Shown under the lists. */
  about?: string[];
  highlight?: number | null;
  picked?: number | null;
  wireframe?: boolean;
  onPick?: (element: number | null) => void;
  /** the colour scale of the field shown: on a rainbow the critical element is outlined in white and the mesh lines are near black
   * (ADR-0063 amendment 1) */
  palette?: Palette;
};

const LIFT = 1e-3; // frames sit this fraction of the plate's size above the top face so they are not hidden by it
const SYMBOL_INSET = 0.25; // supports and loads over an area sit this share in from its edges, off the line where the field changes
const EDGE_OPACITY = 0.42; // the mesh lines over a field: black at this opacity, the mockup's, so a colour reads through them (ADR-0063 amendment 3)

const AXES: [number, number, number][] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
const UP = new THREE.Vector3(0, 1, 0); // a cone's own axis, tip at +height/2

/** The direction a load acts in, from the preview's "+x", "-y", "-z". */
function along(direction: string): [number, number, number] {
  const sign = direction.startsWith("-") ? -1 : 1;
  const axis = direction.endsWith("x") ? 0 : direction.endsWith("y") ? 1 : 2;
  return AXES[axis].map((c) => c * sign) as [number, number, number];
}

/** A cone whose tip sits at `tip` and points along `toward`, `back` cone lengths behind the tip. */
function Cone({ tip, toward, height, color, back = 0, opacity = 1 }: { tip: number[]; toward: number[]; height: number; color: string; back?: number; opacity?: number }) {
  const v = new THREE.Vector3(...toward).normalize();
  const centre = new THREE.Vector3(...tip).addScaledVector(v, -height * (back + 0.5));
  const turn = new THREE.Quaternion().setFromUnitVectors(UP, v);
  return (
    <mesh position={centre} quaternion={turn}>
      <coneGeometry args={[height * 0.38, height, 12]} />
      <meshBasicMaterial color={color} transparent={opacity < 1} opacity={opacity} />
    </mesh>
  );
}

/** A boundary condition's symbols at a few of its nodes (ADR-0110): a cone pointing at the node for each held move, a double cone on the
 * far side for each held turn. A move along z is drawn from above, so it is seen from the default view; the in-plane ones lie flat. */
function HeldSymbols({ xy, nodes, dofs, z, height, opacity = 1 }: { xy: number[][]; nodes: number[]; dofs: number[]; z: number; height: number; opacity?: number }) {
  const at = sampleNodes(xy, nodes, 2, 4, SYMBOL_INSET);
  return (
    <group>
      {at.flatMap((n) => dofs.map((dof) => {
        const axis = (dof - 1) % 3;
        const turn = dof > 3;
        const toward = axis === 2 ? [0, 0, -1] : AXES[axis];
        const tip = [xy[n][0], xy[n][1], z];
        return turn ? (
          <group key={`${n}-${dof}`}>
            <Cone tip={tip} toward={toward} height={0.8 * height} color={HELD} back={1.5} opacity={opacity * 0.7} />
            <Cone tip={tip} toward={toward} height={0.8 * height} color={HELD} back={2.4} opacity={opacity * 0.7} />
          </group>
        ) : <Cone key={`${n}-${dof}`} tip={tip} toward={toward} height={height} color={HELD} opacity={opacity} />;
      }))}
    </group>
  );
}

/** A load's arrows at a few of its nodes (ADR-0110): spread over a face for a pressure, along an edge for an edge's force, over a tab for a
 * grip's travel or force. An arrow along -z arrives onto the plate from above; any other leaves its node in the load's direction. */
function LoadArrows({ xy, nodes, direction, z, length, color = LOADED }: { xy: number[][]; nodes: number[]; direction: string; z: number; length: number; color?: string }) {
  const v = along(direction);
  const at = sampleNodes(xy, nodes, 3, 5, SYMBOL_INSET);
  return (
    <group>
      {at.map((n) => {
        const origin = v[2] < 0 ? [xy[n][0], xy[n][1], z + length] : [xy[n][0], xy[n][1], z];
        return <arrowHelper key={n} args={[new THREE.Vector3(...v), new THREE.Vector3(...origin), length, color, 0.3 * length, 0.18 * length]} />;
      })}
    </group>
  );
}

type Grip = NonNullable<ReturnType<typeof gripOf>>;

/** The twelve edges of a box from its two corners, as pairs of points for a segmented line. */
function boxEdges(a: number[], b: number[]): [number, number, number][] {
  const c = (i: number, j: number, k: number): [number, number, number] => [i ? b[0] : a[0], j ? b[1] : a[1], k ? b[2] : a[2]];
  const out: [number, number, number][] = [];
  for (const [p, q] of [[[0, 0, 0], [1, 0, 0]], [[0, 1, 0], [1, 1, 0]], [[0, 0, 1], [1, 0, 1]], [[0, 1, 1], [1, 1, 1]],
    [[0, 0, 0], [0, 1, 0]], [[1, 0, 0], [1, 1, 0]], [[0, 0, 1], [0, 1, 1]], [[1, 0, 1], [1, 1, 1]],
    [[0, 0, 0], [0, 0, 1]], [[1, 0, 0], [1, 0, 1]], [[0, 1, 0], [0, 1, 1]], [[1, 1, 0], [1, 1, 1]]] as const) {
    out.push(c(p[0], p[1], p[2]), c(q[0], q[1], q[2]));
  }
  return out;
}

/** A grip as an engineer draws one (ADR-0063 amendment 4): two jaws, clear enough to see the tab between them, clamping it from above and
 * below. A fixed grip is hatched at its outer end, the ground symbol; a moving grip is drawn in the load's colour and its arrows are the
 * load's. The jaws take the place of a cone per held direction, which over a clamped tab read as a cluster, not as a grip. */
function Jaws({ grip, z, thickness, size, color, fixed, bold }: { grip: Grip; z: number; thickness: number; size: number; color: string; fixed: boolean; bold: boolean }) {
  const m = 0.008 * size, jaw = Math.max(1.2 * thickness, 0.012 * size);
  const lo = [grip.box.min[0] - m, grip.box.min[1] - m], hi = [grip.box.max[0] + m, grip.box.max[1] + m];
  const slabs: [number, number][] = [[z + thickness / 2, z + thickness / 2 + jaw], [z - thickness / 2 - jaw, z - thickness / 2]];
  const across = grip.axis === 1 ? 0 : 1;
  const end = grip.outer > 0 ? hi[grip.axis] : lo[grip.axis];
  const hatch: [number, number, number][] = [];
  if (fixed) {
    // the ground: a line across the outer end of the top jaw and short strokes slanting away from the part
    const zTop = z + thickness / 2 + jaw, at = (u: number, v: number): [number, number, number] => (grip.axis === 1 ? [u, v, zTop] : [v, u, zTop]);
    const reach = 0.022 * size;
    hatch.push(at(lo[across], end), at(hi[across], end));
    const strokes = 7;
    for (let k = 0; k < strokes; k++) {
      const u = lo[across] + ((k + 0.5) / strokes) * (hi[across] - lo[across]);
      hatch.push(at(u, end), at(u - 0.6 * reach, end + grip.outer * reach));
    }
  }
  return (
    <group>
      {slabs.map(([z0, z1], i) => (
        <group key={i}>
          <mesh position={[(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (z0 + z1) / 2]} renderOrder={2}>
            <boxGeometry args={[hi[0] - lo[0], hi[1] - lo[1], z1 - z0]} />
            <meshBasicMaterial color={color} transparent opacity={0.14} depthWrite={false} />
          </mesh>
          <Line segments points={boxEdges([lo[0], lo[1], z0], [hi[0], hi[1], z1])} color={color} lineWidth={bold ? 3 : 1.5} transparent opacity={0.9} />
        </group>
      ))}
      {hatch.length ? <Line segments points={hatch} color={color} lineWidth={bold ? 3 : 2} /> : null}
    </group>
  );
}

/** A moving grip's load: three arrows across its outer end, in the direction it is moved or pulled. */
function GripArrows({ grip, direction, z, thickness, size, color = LOADED }: { grip: Grip; direction: string; z: number; thickness: number; size: number; color?: string }) {
  const v = new THREE.Vector3(...along(direction));
  const m = 0.008 * size, length = 0.075 * size;
  const height = z + thickness / 2 + Math.max(1.2 * thickness, 0.012 * size); // on the top jaw, so the jaw does not hide them
  const across = grip.axis === 1 ? 0 : 1;
  const lo = grip.box.min[across], hi = grip.box.max[across];
  const end = grip.outer > 0 ? grip.box.max[grip.axis] + m : grip.box.min[grip.axis] - m;
  // an arrow along the long axis leaves the outer end; any other leaves the middle of the grip
  const start = Math.abs(v.getComponent(grip.axis)) > 0.5 ? (v.getComponent(grip.axis) * grip.outer > 0 ? end : end - grip.outer * length) : (grip.box.min[grip.axis] + grip.box.max[grip.axis]) / 2;
  return (
    <group>
      {[0.2, 0.5, 0.8].map((f) => {
        const u = lo + f * (hi - lo);
        const origin = grip.axis === 1 ? new THREE.Vector3(u, start, height) : new THREE.Vector3(start, u, height);
        return <arrowHelper key={f} args={[v, origin, length, color, 0.3 * length, 0.16 * length]} />;
      })}
    </group>
  );
}

function frame(box: { min: number[]; max: number[] }, z: number): [number, number, number][] {
  const [x0, y0] = box.min, [x1, y1] = box.max;
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]];
}

/** The plate: one geometry for the run, rebuilt only when the mesh or the deformed shape changes. A field uploads one float per
 * vertex and moves the material's uniforms, so switching fields keeps the geometry (ADR-0063). */
function Plate({ nodes, quads, thickness, field, xy, heights, wireframe, edgeColor, onPick }: {
  nodes: number[][]; quads: number[][]; thickness: number; field?: SceneField | null; xy: number[][]; heights: number[] | null; wireframe: boolean;
  edgeColor: string; onPick?: (element: number | null) => void;
}) {
  const invalidate = useThree((state) => state.invalidate);
  const plate = useMemo(() => plateMesh(nodes, quads, thickness, xy, heights), [nodes, quads, thickness, xy, heights]);
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(plate.positions, 3));
    g.setIndex(plate.triangles);
    g.computeVertexNormals();
    return g;
  }, [plate]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const material = useMemo(() => fieldMaterial(), []);
  useEffect(() => () => material.dispose(), [material]);
  useEffect(() => {
    if (!field) return;
    geometry.setAttribute("value", new THREE.BufferAttribute(fieldAttribute(plate, field.by, field.values, NO_VALUE, field.held, IN_GRIP), 1));
    applyScale(material, field.scale);
    invalidate();
  }, [geometry, plate, material, field, invalidate]);
  const edges = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const points = elementEdges(xy, quads, thickness / 2, heights).flat(2);
    g.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return g;
  }, [xy, quads, thickness, heights]);
  useEffect(() => () => edges.dispose(), [edges]);
  return (
    <group>
      <mesh geometry={geometry} onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation();
        const face = event.faceIndex ?? -1;
        onPick?.(face >= 0 && face < plate.topTriangles ? Math.floor(face / 2) : null);
      }}>
        {field ? <primitive object={material} attach="material" /> : <meshPhysicalMaterial {...PRESENTATION_MATERIAL} side={THREE.DoubleSide} />}
      </mesh>
      {/* the mesh lines see-through, as the mockup draws them: the colours read through them (ADR-0063 amendment 3) */}
      {wireframe ? <lineSegments geometry={edges}><lineBasicMaterial color={edgeColor} transparent opacity={EDGE_OPACITY} depthWrite={false} /></lineSegments> : null}
    </group>
  );
}

/** A spacing of 1, 2 or 5 times a power of ten, about a twentieth of the model: the floor grid's cell. */
function gridStep(size: number): number {
  const raw = size / 20;
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit < 1.5 ? 1 : unit < 3.5 ? 2 : unit < 7.5 ? 5 : 10) * power;
}

/** The floor under the part (ADR-0063 amendment 1): a grid in the plane just below its bottom face, fading with distance from the camera,
 * a cell every twentieth of the model and a heavier line every fifth cell. Drawn, never picked. */
function Floor({ centre, size, z }: { centre: readonly [number, number]; size: number; z: number }) {
  const cell = gridStep(size);
  return (
    <Grid position={[centre[0], centre[1], z]} rotation={[Math.PI / 2, 0, 0]} args={[1, 1]} infiniteGrid fadeDistance={4 * size} fadeStrength={1.6}
      cellSize={cell} sectionSize={5 * cell} cellThickness={0.6} sectionThickness={1} cellColor="#262626" sectionColor="#3a3a3a" raycast={() => null} />
  );
}

const TRIAD: { axis: string; color: string; v: [number, number, number] }[] = [
  { axis: "X", color: "#e0605a", v: [1, 0, 0] }, { axis: "Y", color: "#6cc070", v: [0, 1, 0] }, { axis: "Z", color: "#6a9be8", v: [0, 0, 1] },
];

/** Turns the X Y Z triad in the view's lower left corner with the camera at every frame drawn: each axis's direction as seen. */
function TriadSync({ svg }: { svg: RefObject<SVGSVGElement | null> }) {
  const v = useMemo(() => new THREE.Vector3(), []);
  useFrame(({ camera }) => {
    const root = svg.current;
    if (!root) return;
    TRIAD.forEach((t, i) => {
      v.set(...t.v).transformDirection(camera.matrixWorldInverse);
      const x = 28 * v.x, y = -28 * v.y;
      const line = root.querySelector<SVGLineElement>(`[data-axis="${i}"] line`);
      const label = root.querySelector<SVGTextElement>(`[data-axis="${i}"] text`);
      line?.setAttribute("x2", x.toFixed(2)); line?.setAttribute("y2", y.toFixed(2));
      label?.setAttribute("x", (1.3 * x).toFixed(2)); label?.setAttribute("y", (1.3 * y + 3.5).toFixed(2));
      root.querySelector(`[data-axis="${i}"]`)?.setAttribute("opacity", v.z < -0.2 ? "0.55" : "1");
    });
  });
  return null;
}

type Layer = "mesh" | "conditions" | "loads";
const LAYER_WORDS: Record<Layer, string> = { mesh: "Mesh", conditions: "Boundary conditions", loads: "Loads" };

export function SceneCanvas(props: SceneProps) {
  const { nodes, quads, thickness, field = null, displacement = null, scale = 1, about = [],
    highlight = null, picked = null, wireframe = true, onPick, emphasis = null, palette = "classic" } = props;
  // every region is drawn on this mesh's own nodes: a node number past its end (a region numbered for another mesh) is left out, so a
  // mismatch above the scene draws less and never throws
  const count = nodes.length;
  const held = useMemo(() => (props.held ?? []).map((m) => onMesh(m, count)), [props.held, count]);
  const loaded = useMemo(() => (props.loaded ? onMesh(props.loaded, count) : null), [props.loaded, count]);
  const loads = useMemo(() => (props.loads ?? []).map((l) => onMesh(l, count)), [props.loads, count]);
  const proposed = useMemo(() => (props.proposed ? { held: props.proposed.held.map((m) => onMesh(m, count)), loads: props.proposed.loads.map((l) => onMesh(l, count)) } : null),
    [props.proposed, count]);
  const triad = useRef<SVGSVGElement>(null);
  const canvas = useCanvasSlots(); // in the FEA workspace's layout the model is framed clear of the panels, its tools in the View menu (ADR-0134 amendment 1)
  const overlay = overlayColors(field ? palette : "green"); // before a run the part is grey: the outlines of before
  const [focus, setFocus] = useState<string | null>(null); // the line of the list clicked: its region is drawn bolder
  const [hidden, setHidden] = useState<Layer[]>([]); // the layers switched off over the model
  const [view, setView] = useState<{ view: "home" | "top"; n: number }>({ view: "home", n: 0 });
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const xy = useMemo(() => (displacement && scale ? deformedPositions(nodes, displacement, scale) : nodes), [nodes, displacement, scale]);
  const heights = useMemo(() => (displacement && scale ? deformedHeights(displacement, scale) : null), [displacement, scale]);
  const extent = useMemo(() => bounds(nodes), [nodes]);
  const lowest = useMemo(() => (heights ?? []).reduce((low, h) => (h < low ? h : low), 0), [heights]); // a part bent below its plane
  const size = Math.max(extent.size[0], extent.size[1], 1);
  const centre = [extent.min[0] + extent.size[0] / 2, extent.min[1] + extent.size[1] / 2] as const;
  const top = thickness / 2 + LIFT * size;
  const floor = -thickness / 2 - 0.006 * size + lowest;
  const symbol = Math.min(0.03 * size, 0.15 * Math.max(Math.min(extent.size[0], extent.size[1]), 0.05 * size)); // a boundary condition's cone, kept within a narrow strip
  const arrow = 0.07 * size; // one of a load's arrows
  const allLoads = [...(loaded ? [loaded] : []), ...loads];
  const mode = field ? "results" : "presentation";
  // a model of another size or place is framed again; a finer mesh of the same plate is not
  const placed = [extent.min[0], extent.min[1], extent.size[0], extent.size[1]].map((v) => v.toPrecision(6)).join(",");
  // the box the camera frames: the plate, with room for the supports' cones and the loads' arrows around and above it
  const highest = useMemo(() => (heights ?? []).reduce((high, h) => (h > high ? h : high), 0), [heights]);
  const pad = 0.035 * size;
  const long = extent.size[1] >= extent.size[0] ? 1 : 0, reach = 0.09 * size; // a grip's arrows and hatching stand past the part's ends
  const padOf = (axis: number) => (axis === long && held.some((m) => gripOf(nodes, m.nodes, m.dofs, extent)) ? reach : pad);
  const boxMin = [extent.min[0] - padOf(0), extent.min[1] - padOf(1), -thickness / 2 + lowest] as const;
  const boxMax = [extent.min[0] + extent.size[0] + padOf(0), extent.min[1] + extent.size[1] + padOf(1), thickness / 2 + highest + 0.04 * size] as const;
  // a clamped tab is drawn as its grip; a load on the same nodes is that grip moving (ADR-0063 amendment 4)
  const nodesKey = (nodes: number[]) => [...nodes].sort((a, b) => a - b).join(",");
  const grips = useMemo(() => held.map((marker) => gripOf(xy, marker.nodes, marker.dofs, extent)), [held, xy, extent]);
  const gripFor = (nodes: number[]): Grip | null => {
    const key = nodesKey(nodes);
    const i = held.findIndex((marker) => nodesKey(marker.nodes) === key);
    return i >= 0 ? grips[i] : null;
  };
  const shows = (layer: Layer) => !hidden.includes(layer);
  const toggle = (layer: Layer) => setHidden((h) => (h.includes(layer) ? h.filter((l) => l !== layer) : [...h, layer]));
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-scene-wrap">
      <div className="studio-canvas" data-testid="studio-scene" data-mode={mode} data-bands={field?.scale.bands ?? ""} data-emphasis={emphasis ?? ""}
        data-palette={field ? palette : ""} data-lit={field ? String(Boolean(field.scale.lit)) : ""}
        data-shown={(["mesh", "conditions", "loads"] as Layer[]).filter(shows).join(" ")} data-view={view.view}>
      {/* the view's own buttons (ADR-0111 amendment 2): back to the whole model, straight above it, and each layer shown or hidden; in the FEA
          workspace's layout they are in the card's View menu, with the supports and loads applied (ADR-0134 amendment 1) */}
      <Slot name="look" here>
        <div className="studio-view-tools" role="toolbar" aria-label="View">
          {canvas ? <span>Look from</span> : null}
          <span className="cv-seg">
            <button type="button" aria-pressed={canvas ? view.view === "home" : undefined} onClick={() => setView((v) => ({ view: "home", n: v.n + 1 }))} data-testid="view-fit"
              title="Back to the whole model">{canvas ? "Whole model" : "Fit"}</button>
            <button type="button" aria-pressed={canvas ? view.view === "top" : undefined} onClick={() => setView((v) => ({ view: "top", n: v.n + 1 }))} data-testid="view-top"
              title="Straight above the model">Top</button>
          </span>
          <span className="studio-view-sep" aria-hidden="true" />
          {canvas ? <span>Show</span> : null}
          <span className="cv-seg">
            {(["mesh", "conditions", "loads"] as Layer[]).map((layer) => (
              <button key={layer} type="button" aria-pressed={shows(layer)} onClick={() => toggle(layer)} data-testid={`show-${layer}`}
                title={`${shows(layer) ? "Hide" : "Show"} ${LAYER_WORDS[layer].toLowerCase()}`}>{LAYER_WORDS[layer]}</button>
            ))}
          </span>
        </div>
        {canvas ? <AppliedList held={held} loads={allLoads} proposed={proposed} about={about} critical={highlight !== null} criticalColor={overlay.critical} focus={focus} onFocus={setFocus} /> : null}
      </Slot>
      <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }}
        camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}
        onPointerMissed={() => onPick?.(null)}>
        {/* in the workspace's layout the page's own ground shows through, lighter behind the model (ADR-0134 amendment 1) */}
        {canvas ? null : <color attach="background" args={["#0d0d0d"]} />}
        {field ? null : <PresentationLighting size={size} centre={centre} floor={-thickness / 2 - 0.004 * size} />}
        <Floor centre={centre} size={size} z={floor} />
        <Plate nodes={nodes} quads={quads} thickness={thickness} field={field} xy={xy} heights={heights} wireframe={wireframe && shows("mesh")} edgeColor={overlay.edges} onPick={onPick} />
        {(shows("conditions") ? held : []).map((marker, i) => {
          const box = setBox(xy, marker.nodes);
          if (!box) return null;
          const grip = grips[i];
          if (grip) {
            const key = nodesKey(marker.nodes);
            const moving = allLoads.some((load) => nodesKey(load.nodes) === key);
            const fixed = [1, 2, 3].every((d) => marker.dofs?.includes(d));
            return <Jaws key={`held-${i}`} grip={grip} z={meanHeight(heights, marker.nodes)} thickness={thickness} size={size} color={moving ? LOADED : HELD}
              fixed={fixed && !moving} bold={focus === `held-${i}` || emphasis === "conditions"} />;
          }
          const z = top + meanHeight(heights, marker.nodes);
          return (
            <group key={`held-${i}`}>
              <Line points={frame(box, z)} color={HELD} lineWidth={focus === `held-${i}` ? 5 : emphasis === "conditions" ? 4 : 2} />
              {marker.dofs?.length ? <HeldSymbols xy={xy} nodes={marker.nodes} dofs={marker.dofs} z={z} height={symbol} /> : null}
            </group>
          );
        })}
        {(shows("loads") ? allLoads : []).map((load, i) => {
          const box = setBox(xy, load.nodes);
          if (!box) return null;
          const z = top + meanHeight(heights, load.nodes);
          const grip = gripFor(load.nodes);
          if (grip) return <GripArrows key={`load-${i}`} grip={grip} direction={load.direction} z={meanHeight(heights, load.nodes)} thickness={thickness} size={size} />;
          return (
            <group key={`load-${i}`}>
              {/* a pressure's arrows cover its face, so its frame, which would hide the edges' own, is drawn only when its line is clicked */}
              {load.control !== "pressure" || focus === `load-${i}` || emphasis === "loads"
                ? <Line points={frame(box, z)} color={LOADED} lineWidth={focus === `load-${i}` ? 5 : emphasis === "loads" ? 4 : 2} /> : null}
              <LoadArrows xy={xy} nodes={load.nodes} direction={load.direction} z={z} length={arrow} />
            </group>
          );
        })}
        {proposed?.held.map((marker, i) => {
          const box = setBox(xy, marker.nodes);
          if (!box) return null;
          const z = top + meanHeight(heights, marker.nodes);
          return (
            <group key={`proposed-held-${i}`}>
              <Line points={frame(box, z)} color={HELD} lineWidth={2} dashed dashSize={0.02 * size} gapSize={0.012 * size} />
              {marker.dofs?.length ? <HeldSymbols xy={xy} nodes={marker.nodes} dofs={marker.dofs} z={z} height={symbol} opacity={0.45} /> : null}
            </group>
          );
        })}
        {proposed?.loads.map((load, i) => {
          const box = setBox(xy, load.nodes);
          if (!box) return null;
          const z = top + meanHeight(heights, load.nodes);
          return (
            <group key={`proposed-load-${i}`}>
              {load.control !== "pressure" ? <Line points={frame(box, z)} color={LOADED} lineWidth={2} dashed dashSize={0.02 * size} gapSize={0.012 * size} /> : null}
              <LoadArrows xy={xy} nodes={load.nodes} direction={load.direction} z={z} length={arrow} color={PROPOSED_LOAD} />
            </group>
          );
        })}
        {highlight !== null && highlight >= 0 && highlight < quads.length ? (
          <Line points={[...elementLoop(xy, quads[highlight], top, heights), elementLoop(xy, quads[highlight], top, heights)[0]] as [number, number, number][]} color={overlay.critical} lineWidth={3} />
        ) : null}
        {picked !== null && picked >= 0 && picked < quads.length && picked !== highlight ? (
          <Line points={[...elementLoop(xy, quads[picked], top, heights), elementLoop(xy, quads[picked], top, heights)[0]] as [number, number, number][]} color={overlay.picked} lineWidth={2} />
        ) : null}
        <OrbitControls makeDefault target={[centre[0], centre[1], 0]} enableDamping={false} />
        <FitCamera at={`${placed}|${view.view}|${view.n}`} view={view.view} min={boxMin} max={boxMax} free={canvas?.free ?? null} />
        <TriadSync svg={triad} />
      </Canvas>
      {/* the axes as seen, in the view's lower left corner (ADR-0063 amendment 1) */}
      <svg ref={triad} className="studio-triad" viewBox="-40 -40 80 80" aria-hidden="true" data-testid="view-triad">
        {TRIAD.map((t, i) => (
          <g key={t.axis} data-axis={i}>
            <line x1="0" y1="0" x2="0" y2="0" stroke={t.color} strokeWidth="2.2" strokeLinecap="round" />
            <text x="0" y="0" fill={t.color} fontSize="10" fontWeight="600" textAnchor="middle">{t.axis}</text>
          </g>
        ))}
      </svg>
      </div>
      {canvas ? null : <AppliedList held={held} loads={allLoads} proposed={proposed} about={about} critical={highlight !== null} criticalColor={overlay.critical} focus={focus} onFocus={setFocus} />}
    </div>
  );
}

const PROPOSED_LOAD = "#8a6a2a"; // a proposed load's arrows: the load colour, dimmed until it is applied

/** What is applied to the model, under it (ADR-0110): the boundary conditions and the loads, one line each in the words the assistant uses,
 * then what the assistant proposes and is not applied yet, then the model they act on. A line clicked draws its region bolder. */
function AppliedList({ held, loads, proposed, about, critical, criticalColor, focus, onFocus }: {
  held: SceneMarker[]; loads: SceneLoad[]; proposed: SceneProps["proposed"]; about: string[]; critical: boolean; criticalColor: string; focus: string | null;
  onFocus: (key: string | null) => void;
}) {
  if (!held.length && !loads.length && !proposed?.held.length && !proposed?.loads.length && !about.length && !critical) return null;
  const line = (key: string, color: string, label: string, dashed = false) => (
    <li key={key}>
      <button type="button" className="studio-applied-line" aria-pressed={focus === key} data-key={key} onClick={() => onFocus(focus === key ? null : key)}>
        <span className="studio-key-swatch" style={{ borderColor: color, borderStyle: dashed ? "dashed" : "solid" }} aria-hidden="true" /> {label}
      </button>
    </li>
  );
  return (
    <div className="studio-applied" data-testid="applied">
      {held.length ? (
        <div data-testid="applied-conditions"><h5>Boundary conditions</h5><ul>{held.map((m, i) => line(`held-${i}`, HELD, m.label))}</ul></div>
      ) : null}
      {loads.length ? (
        <div data-testid="applied-loads"><h5>Loads</h5><ul>{loads.map((l, i) => line(`load-${i}`, LOADED, l.label))}</ul></div>
      ) : null}
      {proposed && (proposed.held.length || proposed.loads.length) ? (
        <div data-testid="applied-proposed"><h5>Proposed, not applied yet</h5><ul>
          {proposed.held.map((m, i) => line(`proposed-held-${i}`, HELD, m.label, true))}
          {proposed.loads.map((l, i) => line(`proposed-load-${i}`, LOADED, l.label, true))}
        </ul></div>
      ) : null}
      {about.length || critical ? (
        <p className="studio-applied-about" data-testid="applied-about">
          {about.join(" · ")}
          {critical ? <span>{about.length ? " · " : ""}<span className="studio-key-swatch" style={{ borderColor: criticalColor }} aria-hidden="true" /> the critical element</span> : null}
        </p>
      ) : null}
    </div>
  );
}
