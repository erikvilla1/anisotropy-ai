"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { bounds, centroid, deformedPositions, elementEdges, elementLoop, plateMesh, setBox, vertexColors } from "@/lib/studio-geometry";
import { CRITICAL, HELD, LOADED } from "@/lib/studio-colors";
import { WebGLMissing, webglAvailable } from "./webgl-missing";

export type SceneColors = { by: "node" | "element"; rgb: number[] };
export type SceneMarker = { nodes: number[]; label: string };
export type SceneProps = {
  nodes: number[][]; quads: number[][]; thickness: number;
  colors?: SceneColors | null;
  displacement?: number[][] | null; scale?: number;
  held?: SceneMarker[];
  loaded?: (SceneMarker & { direction: string }) | null;
  highlight?: number | null;
  picked?: number | null;
  wireframe?: boolean;
  onPick?: (element: number | null) => void;
};

const BASE_COLOR = "#5d8f52";
const EDGE_COLOR = "#50574f";
const LIFT = 1e-3; // frames sit this fraction of the plate's size above the top face so they are not hidden by it

function frame(box: { min: number[]; max: number[] }, z: number): [number, number, number][] {
  const [x0, y0] = box.min, [x1, y1] = box.max;
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]];
}

function Plate({ nodes, quads, thickness, colors, xy, wireframe, onPick }: {
  nodes: number[][]; quads: number[][]; thickness: number; colors?: SceneColors | null; xy: number[][]; wireframe: boolean;
  onPick?: (element: number | null) => void;
}) {
  const plate = useMemo(() => plateMesh(nodes, quads, thickness, xy), [nodes, quads, thickness, xy]);
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(plate.positions, 3));
    g.setIndex(plate.triangles);
    if (colors) g.setAttribute("color", new THREE.Float32BufferAttribute(vertexColors(plate, colors.by, colors.rgb), 3));
    g.computeVertexNormals();
    return g;
  }, [plate, colors]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const edges = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const points = elementEdges(xy, quads, thickness / 2).flat(2);
    g.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return g;
  }, [xy, quads, thickness]);
  useEffect(() => () => edges.dispose(), [edges]);
  return (
    <group>
      <mesh geometry={geometry} onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation();
        const face = event.faceIndex ?? -1;
        onPick?.(face >= 0 && face < plate.topTriangles ? Math.floor(face / 2) : null);
      }}>
        <meshStandardMaterial vertexColors={Boolean(colors)} color={colors ? "#ffffff" : BASE_COLOR} side={THREE.DoubleSide} metalness={0} roughness={0.85} />
      </mesh>
      {wireframe ? <lineSegments geometry={edges}><lineBasicMaterial color={EDGE_COLOR} /></lineSegments> : null}
    </group>
  );
}

export function SceneCanvas(props: SceneProps) {
  const { nodes, quads, thickness, colors = null, displacement = null, scale = 1, held = [], loaded = null, highlight = null, picked = null,
    wireframe = true, onPick } = props;
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const xy = useMemo(() => (displacement && scale ? deformedPositions(nodes, displacement, scale) : nodes), [nodes, displacement, scale]);
  const extent = useMemo(() => bounds(nodes), [nodes]);
  const size = Math.max(extent.size[0], extent.size[1], 1);
  const centre = [extent.min[0] + extent.size[0] / 2, extent.min[1] + extent.size[1] / 2] as const;
  const top = thickness / 2 + LIFT * size;
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-canvas" data-testid="studio-scene">
      <Canvas frameloop="demand" dpr={[1, 2]} camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}
        onPointerMissed={() => onPick?.(null)}>
        <color attach="background" args={["#0c0e0d"]} />
        <ambientLight intensity={0.85} />
        <directionalLight position={[size, -size, 2 * size]} intensity={1.1} />
        <directionalLight position={[-size, size, -size]} intensity={0.3} />
        <Plate nodes={nodes} quads={quads} thickness={thickness} colors={colors} xy={xy} wireframe={wireframe} onPick={onPick} />
        {held.map((marker, i) => {
          const box = setBox(xy, marker.nodes);
          if (!box) return null;
          return <Line key={`held-${i}`} points={frame(box, top)} color={HELD} lineWidth={2} />;
        })}
        {loaded && setBox(xy, loaded.nodes) ? (() => {
          const box = setBox(xy, loaded.nodes)!;
          const at = centroid(xy, loaded.nodes);
          const sign = loaded.direction.startsWith("-") ? -1 : 1;
          const along = loaded.direction.endsWith("x") ? [sign, 0, 0] : [0, sign, 0];
          const length = 0.18 * size;
          return (
            <group>
              <Line points={frame(box, top)} color={LOADED} lineWidth={2} />
              <arrowHelper args={[new THREE.Vector3(...along), new THREE.Vector3(at[0], at[1], top), length, LOADED, 0.3 * length, 0.15 * length]} />
            </group>
          );
        })() : null}
        {highlight !== null && highlight >= 0 && highlight < quads.length ? (
          <Line points={[...elementLoop(xy, quads[highlight], top), elementLoop(xy, quads[highlight], top)[0]] as [number, number, number][]} color={CRITICAL} lineWidth={3} />
        ) : null}
        {picked !== null && picked >= 0 && picked < quads.length && picked !== highlight ? (
          <Line points={[...elementLoop(xy, quads[picked], top), elementLoop(xy, quads[picked], top)[0]] as [number, number, number][]} color="#eef0e9" lineWidth={2} />
        ) : null}
        <OrbitControls makeDefault target={[centre[0], centre[1], 0]} enableDamping={false} />
      </Canvas>
      {held.length || loaded ? (
        <p className="studio-scene-key">
          {held.map((marker, i) => <span key={i}><span className="studio-key-swatch" style={{ borderColor: HELD }} aria-hidden="true" /> {marker.label}</span>)}
          {loaded ? <span><span className="studio-key-swatch" style={{ borderColor: LOADED }} aria-hidden="true" /> {loaded.label} (the arrow)</span> : null}
          {highlight !== null ? <span><span className="studio-key-swatch" style={{ borderColor: CRITICAL }} aria-hidden="true" /> the critical element</span> : null}
        </p>
      ) : null}
    </div>
  );
}
