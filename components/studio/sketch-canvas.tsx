"use client";

import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Sketch } from "@/lib/studio-sketch";
import { HELD, LOADED } from "@/lib/studio-colors";
import { PRESENTATION_MATERIAL, PresentationLighting } from "./scene-lighting";
import { WebGLMissing, webglAvailable } from "./webgl-missing";

const EDGE_COLOR = "#909090";
const BOX_COLOR = "#a0a0a0";
const LIFT = 1e-3;

type P = [number, number, number];

function frame(x0: number, y0: number, x1: number, y1: number, z: number): P[] {
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]];
}

function circle(cx: number, cy: number, r: number, z: number, n = 48): P[] {
  return Array.from({ length: n + 1 }, (_, i) => [cx + r * Math.cos((2 * Math.PI * i) / n), cy + r * Math.sin((2 * Math.PI * i) / n), z] as P);
}

/** The typed rows as a sketch (ADR-0062): a slab the size of the coupon, its tab bands, its hole, the support and nose lines of a
 * bending coupon and a plate's drawn boxes. Not meshed: the package's preview replaces it after the check. */
export function SketchCanvas({ sketch }: { sketch: Sketch }) {
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const { width: w, length: l, thickness: t } = sketch;
  const size = Math.max(w, l, 1);
  const top = t / 2 + LIFT * size;
  const centre = [w / 2, l / 2] as const;
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-canvas" data-testid="sketch-scene" data-mode="presentation">
      <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }} camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}>
        <color attach="background" args={["#0d0d0d"]} />
        <PresentationLighting size={size} centre={centre} floor={-t / 2 - 0.004 * size} />
        <mesh position={[centre[0], centre[1], 0]}>
          <boxGeometry args={[w, l, t]} />
          <meshPhysicalMaterial {...PRESENTATION_MATERIAL} side={THREE.DoubleSide} />
          <Edges color={EDGE_COLOR} />
        </mesh>
        {sketch.tabs !== null ? (
          <>
            <Line points={frame(0, 0, w, sketch.tabs, top)} color={HELD} lineWidth={2} />
            <Line points={frame(0, l - sketch.tabs, w, l, top)} color={HELD} lineWidth={2} />
          </>
        ) : null}
        {sketch.hole !== null ? <Line points={circle(centre[0], centre[1], sketch.hole / 2, top)} color={EDGE_COLOR} lineWidth={2} /> : null}
        {sketch.supports.map((y, i) => <Line key={`s${i}`} points={[[0, y, -top], [w, y, -top]]} color={HELD} lineWidth={3} />)}
        {sketch.noses.map((y, i) => (
          <group key={`n${i}`}>
            <Line points={[[0, y, top], [w, y, top]]} color={LOADED} lineWidth={3} />
            <arrowHelper args={[new THREE.Vector3(0, 0, -1), new THREE.Vector3(centre[0], y, top + 0.18 * size), 0.18 * size, LOADED, 0.054 * size, 0.027 * size]} />
          </group>
        ))}
        {sketch.boxes.map((box, i) => <Line key={`b${i}`} points={frame(box.x0, box.y0, box.x1, box.y1, top)} color={BOX_COLOR} lineWidth={2} />)}
        <OrbitControls makeDefault target={[centre[0], centre[1], 0]} enableDamping={false} />
      </Canvas>
      <p className="studio-scene-key">
        {sketch.tabs !== null ? <span><span className="studio-key-swatch" style={{ borderColor: HELD }} aria-hidden="true" /> the tabs</span> : null}
        {sketch.supports.length ? <span><span className="studio-key-swatch" style={{ borderColor: HELD }} aria-hidden="true" /> the supports</span> : null}
        {sketch.noses.length ? <span><span className="studio-key-swatch" style={{ borderColor: LOADED }} aria-hidden="true" /> the loading nose{sketch.noses.length > 1 ? "s" : ""}</span> : null}
        {sketch.boxes.length ? <span><span className="studio-key-swatch" style={{ borderColor: BOX_COLOR }} aria-hidden="true" /> the drawn boxes</span> : null}
      </p>
    </div>
  );
}
