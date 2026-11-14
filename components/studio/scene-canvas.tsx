"use client";

import { useEffect, useId, useMemo, useRef, useState, type RefObject } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { bounds, centroid, deformedHeights, deformedPositions, elementEdges, elementLoop, fieldAttribute, fitDistance, meanHeight, plateMesh, setBox } from "@/lib/studio-geometry";
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
  /** What the view shows, in words: its text alternative (WCAG 1.1.1, audit fea-run-47); the key below it describes it further. */
  label?: string;
  /** Changed by "Fit view": the camera fits the model again. */
  fit?: number;
};

const EDGE_COLOR = "#555555";
const LIFT = 1e-3; // frames sit this fraction of the plate's size above the top face so they are not hidden by it
/** The view the camera starts from: this direction from the coupon's centre, z up. */
const VIEW = [0.9, -1.1, 0.9];
const ARROW = 0.18; // a load's arrow, as a fraction of the plate's size

function frame(box: { min: number[]; max: number[] }, z: number): [number, number, number][] {
  const [x0, y0] = box.min, [x1, y1] = box.max;
  return [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [x0, y0, z]];
}

/** The unit vector of a load's direction ("y", "-x", "-z"). */
const alongOf = (direction: string): [number, number, number] => {
  const sign = direction.startsWith("-") ? -1 : 1;
  return direction.endsWith("x") ? [sign, 0, 0] : direction.endsWith("y") ? [0, sign, 0] : [0, 0, sign];
};

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

/** The orbit controls as drei registers them (three-stdlib's): what the keyboard and the fit move. */
type Orbit = {
  target: THREE.Vector3; update(): void; getAzimuthalAngle(): number; setAzimuthalAngle(angle: number): void; getPolarAngle(): number; setPolarAngle(angle: number): void;
  dollyIn(scale?: number): void; dollyOut(scale?: number): void;
};

/** The camera fitted to the model at the canvas's own shape (audit fea-run-45): on the first frame, when the canvas is resized and when "Fit
 * view" asks; the engineer's own turning is left alone in between. */
function FitCamera({ points, target, fit }: { points: number[][]; target: [number, number, number]; fit: number }) {
  const camera = useThree((state) => state.camera) as THREE.PerspectiveCamera;
  const size = useThree((state) => state.size);
  const controls = useThree((state) => state.controls) as unknown as Orbit | null;
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    const distance = fitDistance(points, target, VIEW, [0, 0, 1], camera.fov, size.width / Math.max(size.height, 1));
    const view = new THREE.Vector3(...VIEW).normalize().multiplyScalar(distance);
    camera.position.set(target[0] + view.x, target[1] + view.y, target[2] + view.z);
    camera.near = distance / 1000;
    camera.far = distance * 40;
    camera.updateProjectionMatrix();
    if (controls) { controls.target.set(...target); controls.update(); } else camera.lookAt(...target);
    invalidate();
  }, [camera, controls, invalidate, points, target, fit, size.width, size.height]);
  return null;
}

/** The view turned and zoomed from the keyboard once it has the focus (WCAG 2.1.1, audit fea-run-47): the arrow keys turn it, + and − zoom. */
function KeyboardOrbit({ element }: { element: RefObject<HTMLDivElement | null> }) {
  const controls = useThree((state) => state.controls) as unknown as Orbit | null;
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    const host = element.current;
    if (!host || !controls) return;
    const step = Math.PI / 24;
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.key === "ArrowLeft") controls.setAzimuthalAngle(controls.getAzimuthalAngle() - step);
      else if (event.key === "ArrowRight") controls.setAzimuthalAngle(controls.getAzimuthalAngle() + step);
      else if (event.key === "ArrowUp") controls.setPolarAngle(controls.getPolarAngle() - step);
      else if (event.key === "ArrowDown") controls.setPolarAngle(controls.getPolarAngle() + step);
      else if (event.key === "+" || event.key === "=") controls.dollyIn(0.9);
      else if (event.key === "-" || event.key === "_") controls.dollyOut(0.9);
      else return;
      event.preventDefault(); // the page does not scroll under the keys that turn the view
      controls.update();
      invalidate();
    };
    host.addEventListener("keydown", onKey);
    return () => host.removeEventListener("keydown", onKey);
  }, [element, controls, invalidate]);
  return null;
}

export function SceneCanvas(props: SceneProps) {
  const { nodes, quads, thickness, field = null, displacement = null, scale = 1, held = [], loaded = null, loads = [], highlight = null, picked = null,
    wireframe = true, onPick, label, fit = 0 } = props;
  const [webgl, setWebgl] = useState<boolean | null>(null);
  useEffect(() => { setWebgl(webglAvailable()); }, []);
  const wrapper = useRef<HTMLDivElement>(null);
  const keyId = useId();
  const xy = useMemo(() => (displacement && scale ? deformedPositions(nodes, displacement, scale) : nodes), [nodes, displacement, scale]);
  const heights = useMemo(() => (displacement && scale ? deformedHeights(displacement, scale) : null), [displacement, scale]);
  const extent = useMemo(() => bounds(nodes), [nodes]);
  // the coupon's box in numbers: a new answer for the same coupon (a live preview, a re-read) brings new arrays but the same box, and neither
  // the target nor the fit change with it, so the engineer's turning is kept (review P16)
  const extentKey = `${extent.min.join()}|${extent.max.join()}`;
  const size = Math.max(extent.size[0], extent.size[1], 1);
  const centre = useMemo<[number, number, number]>(() => [extent.min[0] + extent.size[0] / 2, extent.min[1] + extent.size[1] / 2, 0], [extentKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const top = thickness / 2 + LIFT * size;
  const mode = field ? "results" : "presentation";
  const arrows = [...(loaded ? [loaded] : []), ...loads];
  // what the camera fits: the plate's box and the tips of the load arrows, keyed by the box and the loads' directions so a re-render does not refit
  const arrowKey = arrows.map((a) => `${a.direction}:${a.nodes.length}:${a.nodes[0] ?? ""}`).join("|");
  const fitted = useMemo(() => {
    const points: number[][] = [];
    for (const x of [extent.min[0], extent.max[0]]) for (const y of [extent.min[1], extent.max[1]]) for (const z of [-thickness / 2, thickness / 2]) points.push([x, y, z]);
    for (const a of arrows) {
      const at = centroid(nodes, a.nodes), along = alongOf(a.direction);
      points.push([at[0] + along[0] * ARROW * size, at[1] + along[1] * ARROW * size, top + Math.abs(along[2]) * ARROW * size]);
    }
    return points;
  }, [`${extentKey}|${thickness}|${arrowKey}`]); // eslint-disable-line react-hooks/exhaustive-deps
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading" role="status">Loading the 3D view…</div>;
  const outline = (element: number) => [...elementLoop(xy, quads[element], top, heights), elementLoop(xy, quads[element], top, heights)[0]] as [number, number, number][];
  const critical = highlight !== null && highlight >= 0 && highlight < quads.length ? highlight : null;
  return (
    <>
      <div className="studio-canvas" data-testid="studio-scene" data-mode={mode} data-bands={field?.scale.bands ?? ""} ref={wrapper} tabIndex={0} role="img"
        aria-label={label ?? "3D view of the coupon"} aria-describedby={held.length || arrows.length || critical !== null ? keyId : undefined}>
        <Canvas frameloop="demand" dpr={[1, 2]} gl={{ toneMapping: THREE.ACESFilmicToneMapping }}
          camera={{ position: [centre[0] + 0.9 * size, centre[1] - 1.1 * size, 0.9 * size], up: [0, 0, 1], fov: 32, near: size / 1000, far: size * 40 }}
          onPointerMissed={() => onPick?.(null)}>
          <color attach="background" args={["#0d0d0d"]} />
          {field ? null : <PresentationLighting size={size} centre={[centre[0], centre[1]]} floor={-thickness / 2 - 0.004 * size} />}
          <Plate nodes={nodes} quads={quads} thickness={thickness} field={field} xy={xy} heights={heights} wireframe={wireframe} onPick={onPick} />
          {held.map((marker, i) => {
            const box = setBox(xy, marker.nodes);
            if (!box) return null;
            return <Line key={`held-${i}`} points={frame(box, top + meanHeight(heights, marker.nodes))} color={HELD} lineWidth={2} />;
          })}
          {arrows.map((load, i) => {
            const box = setBox(xy, load.nodes);
            if (!box) return null;
            const at = centroid(xy, load.nodes);
            const lift = top + meanHeight(heights, load.nodes);
            const along = alongOf(load.direction);
            const length = ARROW * size;
            const origin = along[2] < 0 ? [at[0], at[1], lift + length] : [at[0], at[1], lift]; // a push along -z is drawn arriving onto the plate
            return (
              <group key={`load-${i}`}>
                <Line points={frame(box, lift)} color={LOADED} lineWidth={2} />
                <arrowHelper args={[new THREE.Vector3(...along), new THREE.Vector3(...origin), length, LOADED, 0.3 * length, 0.15 * length]} />
              </group>
            );
          })}
          {critical !== null ? (
            // the critical element: a dark band under the status colour, wider than any other outline, so it reads on every colour of the
            // ramp and is not told by colour alone (WCAG 1.4.1, 1.4.11, audit uiux-fea-run-3); the view's text alternative names it
            <>
              <Line points={outline(critical)} color="#0d0d0d" lineWidth={7} />
              <Line points={outline(critical).map(([x, y, z]) => [x, y, z + LIFT * size] as [number, number, number])} color={CRITICAL} lineWidth={3} />
            </>
          ) : null}
          {picked !== null && picked >= 0 && picked < quads.length && picked !== critical ? (
            <Line points={outline(picked)} color="#efefef" lineWidth={2} />
          ) : null}
          <OrbitControls makeDefault target={centre} enableDamping={false} />
          <FitCamera points={fitted} target={centre} fit={fit} />
          <KeyboardOrbit element={wrapper} />
        </Canvas>
      </div>
      {held.length || arrows.length || critical !== null ? (
        <p className="studio-scene-key" id={keyId}>
          {held.map((marker, i) => <span key={i}><span className="studio-key-swatch" style={{ borderColor: HELD }} aria-hidden="true" /> {marker.label}</span>)}
          {arrows.map((load, i) => <span key={`k${i}`}><span className="studio-key-swatch" style={{ borderColor: LOADED }} aria-hidden="true" /> {load.label} (the arrow)</span>)}
          {critical !== null ? <span><span className="studio-key-swatch studio-key-critical" style={{ borderColor: CRITICAL }} aria-hidden="true" /> the critical element, outlined in a wide dark band</span> : null}
        </p>
      ) : null}
    </>
  );
}
