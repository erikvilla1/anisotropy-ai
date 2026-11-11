"use client";

import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import type { Sketch } from "@/lib/studio-sketch";
import { HELD, LOADED } from "@/lib/studio-colors";
import { PRESENTATION_MATERIAL, PresentationLighting } from "./scene-lighting";
import { WebGLMissing, webglAvailable } from "./webgl-missing";

const EDGE_COLOR = "#909090";
const BOX_COLOR = "#a0a0a0";
const TAB_COLOR = "#b9a77a"; // a glass/epoxy tab's colour; a drawing, not a result
const GAUGE_COLOR = "#dedede"; // the neutral grey of #d9e2d3's lightness (ADR-0078)
const LIFT = 1e-3;

type P = [number, number, number];

function frame(x0: number, y0: number, x1: number, y1: number, z: number): P[] {
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]];
}

function circle(cx: number, cy: number, r: number, z: number, n = 48): P[] {
  return Array.from({ length: n + 1 }, (_, i) => [cx + r * Math.cos((2 * Math.PI * i) / n), cy + r * Math.sin((2 * Math.PI * i) / n), z] as P);
}

/** A bonded tab as a prism along the width: its profile in the length-thickness plane is the tab's length at the coupon's face and the
 * length less thickness / tan(bevel) at its outer face, the bevel facing the gauge section (ADR-0072). `y0` is the end of the coupon, `dir`
 * points into the coupon, `z0` is the face it sits on and `up` the side it grows to. */
function TabBlock({ y0, dir, z0, up, length, thickness, bevel, width }: {
  y0: number; dir: 1 | -1; z0: number; up: 1 | -1; length: number; thickness: number; bevel: number; width: number;
}) {
  const run = bevel >= 90 ? 0 : Math.min(length, thickness / Math.tan((bevel * Math.PI) / 180));
  const shape = new THREE.Shape();
  shape.moveTo(y0, z0);
  shape.lineTo(y0 + dir * length, z0);
  shape.lineTo(y0 + dir * (length - run), z0 + up * thickness);
  shape.lineTo(y0, z0 + up * thickness);
  shape.closePath();
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: width, bevelEnabled: false });
  geometry.applyMatrix4(new THREE.Matrix4().set(0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1)); // the shape's (u, v) to (y, z), its depth to x
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color={TAB_COLOR} roughness={0.7} side={THREE.DoubleSide} />
      <Edges color={EDGE_COLOR} />
    </mesh>
  );
}

/** A dog-bone's slab (ADR-0075): its outline, from `outlinePoints`, extruded through the thickness and centred on the mid-plane. */
function DogboneSlab({ outline, thickness }: { outline: [number, number][]; thickness: number }) {
  const geometry = useMemo(() => {
    const shape = new THREE.Shape(outline.map(([x, y]) => new THREE.Vector2(x, y)));
    const extruded = new THREE.ExtrudeGeometry(shape, { depth: thickness, bevelEnabled: false, curveSegments: 1 });
    extruded.translate(0, 0, -thickness / 2);
    return extruded;
  }, [outline, thickness]);
  return (
    <mesh geometry={geometry} name="dogbone">
      <meshPhysicalMaterial {...PRESENTATION_MATERIAL} side={THREE.DoubleSide} />
      <Edges color={EDGE_COLOR} threshold={20} />
    </mesh>
  );
}

/** The typed rows as a sketch (ADR-0062): a slab the size of the coupon or its dog-bone outline (ADR-0075), its tab bands, its hole, the
 * support and nose lines of a bending coupon and a plate's drawn boxes. Not meshed: the package's preview replaces it after the check. */
export function SketchCanvas({ sketch }: { sketch: Sketch }) {
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const { width: w, length: l, thickness: t } = sketch;
  const size = Math.max(w, l, 1);
  const top = t / 2 + LIFT * size;
  const centre = [w / 2, l / 2] as const;
  const across = sketch.dogbone?.narrowWidth ?? w; // the knife edges sit within the narrow section of a dog-bone
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="studio-canvas" data-testid="sketch-scene" data-mode="presentation">
      <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }} camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}>
        <color attach="background" args={["#0d0d0d"]} />
        <PresentationLighting size={size} centre={centre} floor={-t / 2 - 0.004 * size} />
        {sketch.dogbone !== null ? <DogboneSlab outline={sketch.dogbone.outline} thickness={t} /> : (
          <mesh position={[centre[0], centre[1], 0]}>
            <boxGeometry args={[w, l, t]} />
            <meshPhysicalMaterial {...PRESENTATION_MATERIAL} side={THREE.DoubleSide} />
            <Edges color={EDGE_COLOR} />
          </mesh>
        )}
        {sketch.tabs !== null ? (
          <>
            <Line points={frame(0, 0, w, sketch.tabs, top)} color={HELD} lineWidth={2} />
            <Line points={frame(0, l - sketch.tabs, w, l, top)} color={HELD} lineWidth={2} />
          </>
        ) : null}
        {sketch.tabs !== null && sketch.tabThickness !== null && sketch.tabBevel !== null ? (
          <group name="tab-blocks">
            {([[0, 1], [l, -1]] as const).flatMap(([y0, dir]) => ([[t / 2, 1], [-t / 2, -1]] as const).map(([z0, up]) => (
              <TabBlock key={`${y0}-${z0}`} y0={y0} dir={dir} z0={z0} up={up} length={sketch.tabs as number} thickness={sketch.tabThickness as number}
                bevel={sketch.tabBevel as number} width={w} />
            )))}
          </group>
        ) : null}
        {sketch.hole !== null ? <Line points={circle(centre[0], centre[1], sketch.hole / 2, top)} color={EDGE_COLOR} lineWidth={2} /> : null}
        {sketch.strain !== null ? ([-1, 1] as const).map((side) => (
          <Line key={`k${side}`} points={[[centre[0] - 0.2 * across, centre[1] + side * (sketch.strain as { length: number }).length / 2, top],
            [centre[0] + 0.2 * across, centre[1] + side * (sketch.strain as { length: number }).length / 2, top]]} color={GAUGE_COLOR} lineWidth={3} />
        )) : null}
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
        {sketch.tabThickness !== null ? <span><span className="studio-key-swatch" style={{ borderColor: TAB_COLOR }} aria-hidden="true" /> the bonded tabs</span> : null}
        {sketch.strain !== null ? <span><span className="studio-key-swatch" style={{ borderColor: GAUGE_COLOR }} aria-hidden="true" /> the {sketch.strain.device}&apos;s knife edges</span> : null}
      </p>
    </div>
  );
}
