"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { bounds, deformedHeights, deformedPositions, elementEdges, elementLoop, fieldAttribute, meanHeight, plateMesh, sampleNodes, setBox } from "@/lib/studio-geometry";
import { CRITICAL, HELD, LOADED } from "@/lib/studio-colors";
import { applyScale, fieldMaterial, NO_VALUE, type FieldScale } from "./field-material";
import { PRESENTATION_MATERIAL, PresentationLighting } from "./scene-lighting";
import { WebGLMissing, webglAvailable } from "./webgl-missing";

/** A field on the plate (ADR-0063): the package's values, one per node (smooth) or per element (flat), and the scale that colours them. */
export type SceneField = { by: "node" | "element"; values: (number | null)[]; scale: FieldScale };
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
};

const EDGE_COLOR = "#555555";
const LIFT = 1e-3; // frames sit this fraction of the plate's size above the top face so they are not hidden by it

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
  const at = sampleNodes(xy, nodes, 2, 4);
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
  const at = sampleNodes(xy, nodes, 3, 5);
  return (
    <group>
      {at.map((n) => {
        const origin = v[2] < 0 ? [xy[n][0], xy[n][1], z + length] : [xy[n][0], xy[n][1], z];
        return <arrowHelper key={n} args={[new THREE.Vector3(...v), new THREE.Vector3(...origin), length, color, 0.3 * length, 0.18 * length]} />;
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
function Plate({ nodes, quads, thickness, field, xy, heights, wireframe, onPick }: {
  nodes: number[][]; quads: number[][]; thickness: number; field?: SceneField | null; xy: number[][]; heights: number[] | null; wireframe: boolean;
  onPick?: (element: number | null) => void;
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
    geometry.setAttribute("value", new THREE.BufferAttribute(fieldAttribute(plate, field.by, field.values, NO_VALUE), 1));
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
      {wireframe ? <lineSegments geometry={edges}><lineBasicMaterial color={EDGE_COLOR} /></lineSegments> : null}
    </group>
  );
}

export function SceneCanvas(props: SceneProps) {
  const { nodes, quads, thickness, field = null, displacement = null, scale = 1, held = [], loaded = null, loads = [], proposed = null, about = [],
    highlight = null, picked = null, wireframe = true, onPick, emphasis = null } = props;
  const [focus, setFocus] = useState<string | null>(null); // the line of the list clicked: its region is drawn bolder
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const xy = useMemo(() => (displacement && scale ? deformedPositions(nodes, displacement, scale) : nodes), [nodes, displacement, scale]);
  const heights = useMemo(() => (displacement && scale ? deformedHeights(displacement, scale) : null), [displacement, scale]);
  const extent = useMemo(() => bounds(nodes), [nodes]);
  const size = Math.max(extent.size[0], extent.size[1], 1);
  const centre = [extent.min[0] + extent.size[0] / 2, extent.min[1] + extent.size[1] / 2] as const;
  const top = thickness / 2 + LIFT * size;
  const symbol = Math.min(0.03 * size, 0.15 * Math.max(Math.min(extent.size[0], extent.size[1]), 0.05 * size)); // a boundary condition's cone, kept within a narrow strip
  const arrow = 0.07 * size; // one of a load's arrows
  const allLoads = [...(loaded ? [loaded] : []), ...loads];
  const mode = field ? "results" : "presentation";
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-scene-wrap">
      <div className="studio-canvas" data-testid="studio-scene" data-mode={mode} data-bands={field?.scale.bands ?? ""} data-emphasis={emphasis ?? ""}>
      <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }}
        camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}
        onPointerMissed={() => onPick?.(null)}>
        <color attach="background" args={["#0d0d0d"]} />
        {field ? null : <PresentationLighting size={size} centre={centre} floor={-thickness / 2 - 0.004 * size} />}
        <Plate nodes={nodes} quads={quads} thickness={thickness} field={field} xy={xy} heights={heights} wireframe={wireframe} onPick={onPick} />
        {held.map((marker, i) => {
          const box = setBox(xy, marker.nodes);
          if (!box) return null;
          const z = top + meanHeight(heights, marker.nodes);
          return (
            <group key={`held-${i}`}>
              <Line points={frame(box, z)} color={HELD} lineWidth={focus === `held-${i}` ? 5 : emphasis === "conditions" ? 4 : 2} />
              {marker.dofs?.length ? <HeldSymbols xy={xy} nodes={marker.nodes} dofs={marker.dofs} z={z} height={symbol} /> : null}
            </group>
          );
        })}
        {allLoads.map((load, i) => {
          const box = setBox(xy, load.nodes);
          if (!box) return null;
          const z = top + meanHeight(heights, load.nodes);
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
          <Line points={[...elementLoop(xy, quads[highlight], top, heights), elementLoop(xy, quads[highlight], top, heights)[0]] as [number, number, number][]} color={CRITICAL} lineWidth={3} />
        ) : null}
        {picked !== null && picked >= 0 && picked < quads.length && picked !== highlight ? (
          <Line points={[...elementLoop(xy, quads[picked], top, heights), elementLoop(xy, quads[picked], top, heights)[0]] as [number, number, number][]} color="#efefef" lineWidth={2} />
        ) : null}
        <OrbitControls makeDefault target={[centre[0], centre[1], 0]} enableDamping={false} />
      </Canvas>
      </div>
      <AppliedList held={held} loads={allLoads} proposed={proposed} about={about} critical={highlight !== null} focus={focus} onFocus={setFocus} />
    </div>
  );
}

const PROPOSED_LOAD = "#8a6a2a"; // a proposed load's arrows: the load colour, dimmed until it is applied

/** What is applied to the model, under it (ADR-0110): the boundary conditions and the loads, one line each in the words the assistant uses,
 * then what the assistant proposes and is not applied yet, then the model they act on. A line clicked draws its region bolder. */
function AppliedList({ held, loads, proposed, about, critical, focus, onFocus }: {
  held: SceneMarker[]; loads: SceneLoad[]; proposed: SceneProps["proposed"]; about: string[]; critical: boolean; focus: string | null; onFocus: (key: string | null) => void;
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
          {critical ? <span>{about.length ? " · " : ""}<span className="studio-key-swatch" style={{ borderColor: CRITICAL }} aria-hidden="true" /> the critical element</span> : null}
        </p>
      ) : null}
    </div>
  );
}
