"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { bounds, centroid, deformedHeights, deformedPositions, elementEdges, elementLoop, fieldAttribute, meanHeight, plateMesh, setBox } from "@/lib/studio-geometry";
import { CRITICAL, HELD, LOADED } from "@/lib/studio-colors";
import { applyScale, fieldMaterial, NO_VALUE, type FieldScale } from "./field-material";
import { PRESENTATION_MATERIAL, PresentationLighting } from "./scene-lighting";
import { WebGLMissing, webglAvailable } from "./webgl-missing";

/** A field on the plate (ADR-0063): the package's values, one per node (smooth) or per element (flat), and the scale that colours them. */
export type SceneField = { by: "node" | "element"; values: (number | null)[]; scale: FieldScale };
export type SceneMarker = { nodes: number[]; label: string };
export type SceneProps = {
  nodes: number[][]; quads: number[][]; thickness: number;
  /** With a field the scene is in results mode: unlit, coloured on the graphics card; without one, presentation mode. */
  field?: SceneField | null;
  displacement?: number[][] | null; scale?: number;
  held?: SceneMarker[];
  loaded?: (SceneMarker & { direction: string }) | null;
  loads?: (SceneMarker & { direction: string })[]; // further loads of a plate (ADR-0054), drawn like `loaded`
  highlight?: number | null;
  picked?: number | null;
  wireframe?: boolean;
  onPick?: (element: number | null) => void;
};

const EDGE_COLOR = "#555555";
const LIFT = 1e-3; // frames sit this fraction of the plate's size above the top face so they are not hidden by it

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
  const { nodes, quads, thickness, field = null, displacement = null, scale = 1, held = [], loaded = null, loads = [], highlight = null, picked = null,
    wireframe = true, onPick } = props;
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const xy = useMemo(() => (displacement && scale ? deformedPositions(nodes, displacement, scale) : nodes), [nodes, displacement, scale]);
  const heights = useMemo(() => (displacement && scale ? deformedHeights(displacement, scale) : null), [displacement, scale]);
  const extent = useMemo(() => bounds(nodes), [nodes]);
  const size = Math.max(extent.size[0], extent.size[1], 1);
  const centre = [extent.min[0] + extent.size[0] / 2, extent.min[1] + extent.size[1] / 2] as const;
  const top = thickness / 2 + LIFT * size;
  const mode = field ? "results" : "presentation";
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-canvas" data-testid="studio-scene" data-mode={mode} data-bands={field?.scale.bands ?? ""}>
      <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }}
        camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}
        onPointerMissed={() => onPick?.(null)}>
        <color attach="background" args={["#0d0d0d"]} />
        {field ? null : <PresentationLighting size={size} centre={centre} floor={-thickness / 2 - 0.004 * size} />}
        <Plate nodes={nodes} quads={quads} thickness={thickness} field={field} xy={xy} heights={heights} wireframe={wireframe} onPick={onPick} />
        {held.map((marker, i) => {
          const box = setBox(xy, marker.nodes);
          if (!box) return null;
          return <Line key={`held-${i}`} points={frame(box, top + meanHeight(heights, marker.nodes))} color={HELD} lineWidth={2} />;
        })}
        {[...(loaded ? [loaded] : []), ...loads].map((load, i) => {
          const box = setBox(xy, load.nodes);
          if (!box) return null;
          const at = centroid(xy, load.nodes);
          const lift = top + meanHeight(heights, load.nodes);
          const sign = load.direction.startsWith("-") ? -1 : 1;
          const along = load.direction.endsWith("x") ? [sign, 0, 0] : load.direction.endsWith("y") ? [0, sign, 0] : [0, 0, sign];
          const length = 0.18 * size;
          const origin = along[2] < 0 ? [at[0], at[1], lift + length] : [at[0], at[1], lift]; // a push along -z is drawn arriving onto the plate
          return (
            <group key={`load-${i}`}>
              <Line points={frame(box, lift)} color={LOADED} lineWidth={2} />
              <arrowHelper args={[new THREE.Vector3(...along), new THREE.Vector3(...origin), length, LOADED, 0.3 * length, 0.15 * length]} />
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
      {held.length || loaded ? (
        <p className="studio-scene-key">
          {held.map((marker, i) => <span key={i}><span className="studio-key-swatch" style={{ borderColor: HELD }} aria-hidden="true" /> {marker.label}</span>)}
          {[...(loaded ? [loaded] : []), ...loads].map((load, i) => <span key={`k${i}`}><span className="studio-key-swatch" style={{ borderColor: LOADED }} aria-hidden="true" /> {load.label} (the arrow)</span>)}
          {highlight !== null ? <span><span className="studio-key-swatch" style={{ borderColor: CRITICAL }} aria-hidden="true" /> the critical element</span> : null}
        </p>
      ) : null}
    </div>
  );
}
