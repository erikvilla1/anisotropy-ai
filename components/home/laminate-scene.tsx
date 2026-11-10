"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { WebGLMissing, webglAvailable } from "@/components/studio/webgl-missing";
import { createPlyMaterial, type CarbonGrade, type PlyMaterial } from "./carbon-material";
import { Axes, Backdrop, CarbonLighting, Floor, type FloorUniforms } from "./laminate-studio";

export type ScenePly = { angle_deg: number; thickness_mm: number; color: string };
export type LaminateSceneProps = {
  /** Bottom face first (ADR-0004). */
  plies: ScenePly[];
  hovered: number | null;
  onHover: (index: number | null) => void;
  reducedMotion: boolean;
  /** The hero's slow turn; off in the workspace's layup editor, where the stack is a control, not a scene (ADR-0062). */
  decor?: boolean;
  /** How many plies are laid, bottom first: 0 to plies.length, fractional while one is coming down (it drops into place and fades in). Default: all. */
  laid?: number;
  /** 0 to 1: how far the plies stand apart through the thickness, for an exploded view. Default 0. */
  explode?: number;
  /** The index (bottom ply = 0) of a ply to mark, e.g. the first ply to fail: it glows or is outlined and the others dim slightly. Default null. */
  marked?: number | null;
  /** When a number: the camera's turn about the vertical axis in degrees, set by the caller; the view's own auto-turn and drag-to-turn are then off. Default null (today's behaviour).
   * 0 is the view's resting position; a positive turn carries the camera counterclockwise seen from above, so the stack appears to turn clockwise. */
  azimuth?: number | null;
};

const WIDTH = 1.4; // x, along the 0° fiber
const DEPTH = 0.9; // y, across
const STACK_HEIGHT = 0.42; // the drawn thickness of the whole stack: a shape, not a scale
const GAP_SHARE = 0.09; // the seam between two plies, as a share of one ply's pitch
const GAP_MAX = 0.005;
const EXPLODED_HEIGHT = 0.86; // the stack's height when fully exploded, whatever the number of plies, so it stays in the frame
const DROP = 0.3; // how far above its place a ply starts when it is laid
const HOVER_DIM = 0.16; // how far the other plies step back while one is hovered, as a share of what a marked ply does to them
// The axes stand in front of the stack at the level of its bottom face, where all three are in view from the resting position.
const AXES_ORIGIN: [number, number, number] = [-0.16, -0.9, -STACK_HEIGHT / 2];
const CAMERA_POSITION: [number, number, number] = [1.75, -1.95, 1.25];
const CAMERA = { position: CAMERA_POSITION, up: [0, 0, 1] as [number, number, number], fov: 30, near: 0.01, far: 50 };
// Tone mapping that leaves base colours as they are below the highlights, so a ply's line is the colour of its swatch in the list.
const GL = { alpha: false, antialias: true, powerPreference: "high-performance" as const, toneMapping: THREE.NeutralToneMapping };

type Slab = { height: number; z: number };

/** Heights follow the ply thicknesses, scaled so the whole stack is STACK_HEIGHT tall; a thin seam separates the slabs. */
function layoutOf(plies: ScenePly[]): Slab[] {
  const count = plies.length;
  const gap = count > 1 ? Math.min(GAP_MAX, (GAP_SHARE * STACK_HEIGHT) / count) : 0;
  const total = plies.reduce((sum, ply) => sum + Math.max(ply.thickness_mm, 1e-6), 0);
  const usable = STACK_HEIGHT - gap * Math.max(count - 1, 0);
  let z = -STACK_HEIGHT / 2;
  return plies.map((ply) => {
    const height = (Math.max(ply.thickness_mm, 1e-6) / total) * usable;
    const centre = z + height / 2;
    z += height + gap;
    return { height, z: centre };
  });
}

/** A ply that is not laid yet is not drawn, so the pointer must pass through it too. */
function raycastWhenVisible(this: THREE.Mesh, raycaster: THREE.Raycaster, intersects: THREE.Intersection[]) {
  if (this.visible) THREE.Mesh.prototype.raycast.call(this, raycaster, intersects);
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

type StackProps = {
  plies: ScenePly[]; hovered: number | null; onHover: (index: number | null) => void;
  laid: number | undefined; explode: number; marked: number | null;
  /** How much of the carbon look this device is given. */
  grade: CarbonGrade;
  /** No easing and no pulse: the visitor asked for reduced motion, or the view is off screen. */
  still: boolean;
};

/**
 * The plies, the floor under them and the axes beside them. One unit box and one compiled program serve every ply; a ply's angle,
 * colour and height are uniforms set when the layup changes, and what moves while the view runs (how many plies are laid, how far
 * they stand apart, which is hovered or marked) is read from a ref each frame and written to object transforms and uniforms. No
 * geometry or material is rebuilt and no mesh is remounted for any of it.
 */
function Stack({ plies, hovered, onHover, laid, explode, marked, grade, still }: StackProps) {
  const invalidate = useThree((state) => state.invalidate);
  const box = useMemo(() => new THREE.BoxGeometry(1, 1, 1), []);
  useEffect(() => () => box.dispose(), [box]);

  // Materials are kept for the life of the view and only added to, so typing a layup never drops the shared program.
  const pool = useRef<{ grade: CarbonGrade; list: PlyMaterial[] }>({ grade, list: [] });
  const materials = useMemo(() => {
    if (pool.current.grade !== grade) {
      pool.current.list.forEach((material) => material.dispose());
      pool.current = { grade, list: [] };
    }
    while (pool.current.list.length < plies.length) pool.current.list.push(createPlyMaterial(grade));
    return pool.current.list.slice(0, plies.length);
  }, [plies.length, grade]);
  useEffect(() => () => pool.current.list.forEach((material) => material.dispose()), []);

  const layout = useMemo(() => layoutOf(plies), [plies]);
  useEffect(() => {
    plies.forEach((ply, index) => {
      const uniforms = materials[index].userData.ply;
      const angle = THREE.MathUtils.degToRad(ply.angle_deg);
      uniforms.uFibre.value.set(Math.cos(angle), Math.sin(angle));
      uniforms.uTint.value.set(ply.color);
      uniforms.uSize.value.set(WIDTH, DEPTH, layout[index].height);
      uniforms.uState.value.w = 1 + ((index * 0.618034) % 1) * 9;
    });
    invalidate();
  }, [plies, layout, materials, invalidate]);

  const meshes = useRef<(THREE.Mesh | null)[]>([]);
  const group = useRef<THREE.Group>(null);
  // The plies are kept out of the picture until their program is compiled (off the main thread where the browser can), so the page
  // does not stall on it; then the stack fades in as one.
  const entrance = useRef({ phase: "new" as "new" | "compiling" | "in", value: 0 });
  useLayoutEffect(() => {
    if (group.current) group.current.visible = entrance.current.phase === "in";
  }, []);
  const floor = useRef<THREE.Mesh>(null);
  const axes = useRef<THREE.Group>(null);
  const floorUniforms = useMemo<FloorUniforms>(() => ({
    uHalf: { value: new THREE.Vector2(WIDTH / 2, DEPTH / 2) }, uShadow: { value: 1 }, uLift: { value: 0 },
  }), []);
  const live = useRef({ hovered, laid, explode, marked });
  useEffect(() => {
    live.current = { hovered, laid, explode, marked };
    invalidate();
  }, [hovered, laid, explode, marked, invalidate]);

  useFrame((state, delta) => {
    const count = plies.length;
    const now = live.current;
    const laidCount = now.laid === undefined || Number.isNaN(now.laid) ? count : Math.min(count, Math.max(0, now.laid));
    const spread = count > 1 ? (clamp01(now.explode) * (EXPLODED_HEIGHT - STACK_HEIGHT)) / (count - 1) : 0;
    const mark = now.marked !== null && now.marked >= 0 && now.marked < count ? now.marked : null;
    const hover = now.hovered !== null && now.hovered >= 0 && now.hovered < count ? now.hovered : null;
    const ease = still ? 1 : 1 - Math.exp(-14 * Math.min(delta, 0.05));
    const pulse = mark !== null && !still ? 0.84 + 0.16 * Math.sin(state.clock.elapsedTime * 3) : 1;
    const fromAbove = state.camera.position.z >= 0;
    let settling = false;
    const enter = entrance.current;
    if (enter.phase === "new" && group.current && count > 0) {
      enter.phase = "compiling";
      const show = () => {
        if (enter.phase !== "compiling") return;
        enter.phase = "in";
        if (group.current) group.current.visible = true;
        invalidate();
      };
      state.gl.compileAsync(group.current, state.camera, state.scene).then(show, show);
      window.setTimeout(show, 4000);
    }
    if (enter.phase === "in" && enter.value < 1) {
      enter.value = still ? 1 : Math.min(1, enter.value + Math.min(delta, 0.05) / 0.45);
      settling = true;
    }
    const arrived = 1 - (1 - enter.value) ** 3;
    for (let index = 0; index < count; index++) {
      const mesh = meshes.current[index];
      if (!mesh) continue;
      const material = materials[index];
      const progress = clamp01(laidCount - index);
      const fall = (1 - progress) ** 3;
      mesh.visible = progress > 0;
      mesh.position.z = layout[index].z + (index - (count - 1) / 2) * spread + fall * DROP;
      material.opacity = arrived * clamp01(progress / 0.7) ** 2 * (3 - 2 * clamp01(progress / 0.7));
      // Nearest first, so a ply hidden under another is rejected by the depth test before its shader runs; a ply still fading in
      // is drawn after the rest, over them.
      mesh.renderOrder = progress < 1 ? count + 1 : fromAbove ? count - 1 - index : index;
      const values = material.userData.ply.uState.value;
      const hoverTo = hover === index ? 1 : 0;
      const markTo = mark === index ? 1 : 0;
      const dimTo = hoverTo || markTo ? 0 : mark !== null ? 1 : hover !== null ? HOVER_DIM : 0;
      const hoverNow = values.x + (hoverTo - values.x) * ease;
      const markNow = (material.userData.mark as number | undefined) ?? 0;
      const markNext = markNow + (markTo - markNow) * ease;
      const dimNext = values.z + (dimTo - values.z) * ease;
      if (Math.abs(hoverTo - hoverNow) > 0.004 || Math.abs(markTo - markNext) > 0.004 || Math.abs(dimTo - dimNext) > 0.004) settling = true;
      material.userData.mark = markNext;
      values.x = Math.abs(hoverTo - hoverNow) > 0.004 ? hoverNow : hoverTo;
      values.y = (Math.abs(markTo - markNext) > 0.004 ? markNext : markTo) * pulse;
      values.z = Math.abs(dimTo - dimNext) > 0.004 ? dimNext : dimTo;
    }
    // The floor and the axes stay with the bottom ply as the stack opens about its middle; the shadow comes in with the first ply.
    const first = clamp01(laidCount);
    const base = -STACK_HEIGHT / 2 - ((count - 1) / 2) * spread;
    if (floor.current) floor.current.position.z = base - 0.003;
    if (axes.current) axes.current.position.z = base + STACK_HEIGHT / 2;
    floorUniforms.uShadow.value = count > 0 ? arrived * clamp01(first / 0.7) : 0;
    floorUniforms.uLift.value = count > 0 ? (1 - first) ** 3 * DROP : 0;
    if (settling || (!still && mark !== null)) invalidate();
  });

  return (
    <group>
      <group ref={group}>
        {plies.map((_, index) => (
          <mesh
            key={index}
            ref={(mesh) => { meshes.current[index] = mesh; }}
            geometry={box}
            material={materials[index]}
            scale={[WIDTH, DEPTH, layout[index].height]}
            raycast={raycastWhenVisible}
            onPointerOver={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); onHover(index); }}
            onPointerOut={() => onHover(null)}
          />
        ))}
      </group>
      <Floor ref={floor} uniforms={floorUniforms} />
      <group ref={axes}>
        <Axes origin={AXES_ORIGIN} />
      </group>
    </group>
  );
}

const CAMERA_RADIUS = Math.hypot(CAMERA_POSITION[0], CAMERA_POSITION[1]);
const CAMERA_BEARING = Math.atan2(CAMERA_POSITION[1], CAMERA_POSITION[0]);
const CAMERA_DISTANCE = Math.hypot(CAMERA_RADIUS, CAMERA_POSITION[2]);
// What has to stay in the frame: the stack, and the axes with their letters, which stand a little further out than its corners.
const STACK_RADIUS = Math.max(Math.hypot(WIDTH / 2, DEPTH / 2), Math.hypot(AXES_ORIGIN[0] + 0.37, AXES_ORIGIN[1]));

/** How far below the middle of the frame the lowest point comes, as a share of the half height, at zoom 1 and whatever the turn
 * about z: the point nearest the camera of the circle around the bottom face and the axes, for a stack `height` tall. */
function reachBelow(height: number): number {
  const sine = CAMERA_POSITION[2] / CAMERA_DISTANCE;
  const cosine = CAMERA_RADIUS / CAMERA_DISTANCE;
  const down = sine * STACK_RADIUS + cosine * (height / 2);
  const depth = CAMERA_DISTANCE - cosine * STACK_RADIUS + sine * (height / 2);
  return down / (depth * Math.tan(THREE.MathUtils.degToRad(CAMERA.fov / 2)));
}

/** Keeps the stack's full width in view when the canvas is narrower than 4:3, as the home page's view can be when it fills its row
 * (ADR-0077 amendment 10): the camera zooms out by the aspect's shortfall. At 4:3 or wider it changes nothing. An exploded stack
 * is taller than the frame of a 4:3 view, so the camera also zooms out as the stack opens, by just what keeps its bottom ply in. */
function FitWidth({ explode }: { explode: number }) {
  const { camera, size, invalidate } = useThree();
  useEffect(() => {
    const perspective = camera as THREE.PerspectiveCamera;
    const width = Math.min(1, size.width / Math.max(size.height, 1) / (4 / 3));
    const closed = width * reachBelow(STACK_HEIGHT);
    const open = width * reachBelow(STACK_HEIGHT + clamp01(explode) * (EXPLODED_HEIGHT - STACK_HEIGHT));
    const zoom = width * Math.min(1, Math.max(0.94, closed) / open);
    if (perspective.zoom === zoom) return;
    perspective.zoom = zoom;
    perspective.updateProjectionMatrix();
    invalidate();
  }, [camera, size, explode, invalidate]);
  return null;
}

/** The caller's turn of the camera about z, measured from the resting view; the height and the distance stay the resting ones. */
function Turn({ azimuth }: { azimuth: number | null }) {
  const { camera, invalidate } = useThree();
  useEffect(() => {
    if (azimuth === null || Number.isNaN(azimuth)) return;
    const bearing = CAMERA_BEARING + THREE.MathUtils.degToRad(azimuth);
    camera.position.set(CAMERA_RADIUS * Math.cos(bearing), CAMERA_RADIUS * Math.sin(bearing), CAMERA_POSITION[2]);
    camera.up.set(0, 0, 1);
    camera.lookAt(0, 0, 0);
    invalidate();
  }, [azimuth, camera, invalidate]);
  return null;
}

/** Watches the frame time while the view turns by itself: the mean of 20 frames, the first few after any change left out
 * (they carry shader compilation). The caller steps the view down when it is told the mean. */
function FrameBudget({ active, step, onMean }: { active: boolean; step: number; onMean: (seconds: number) => void }) {
  const samples = useRef({ skip: 4, count: 0, total: 0 });
  useEffect(() => { samples.current = { skip: 4, count: 0, total: 0 }; }, [active, step]);
  useFrame((_, delta) => {
    if (!active) return;
    const sample = samples.current;
    if (sample.skip > 0) { sample.skip -= 1; return; }
    sample.count += 1;
    sample.total += Math.min(delta, 2);
    if (sample.count < 20) return;
    const mean = sample.total / sample.count;
    sample.count = 0;
    sample.total = 0;
    onMean(mean);
  });
  return null;
}

/** True where the browser draws WebGL without a graphics processor (SwiftShader, llvmpipe and the like). */
function drawsInSoftware(): boolean {
  try {
    const context = document.createElement("canvas").getContext("webgl2");
    if (!context) return false;
    const info = context.getExtension("WEBGL_debug_renderer_info");
    const name = info ? String(context.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
    context.getExtension("WEBGL_lose_context")?.loseContext();
    return /swiftshader|llvmpipe|software|basic render/i.test(name);
  } catch {
    return false;
  }
}

// How the view steps down when it cannot hold its frame time, in order: a pixel ratio of 1.5, then 1, then the plain look, then no
// turning by itself. A browser that draws in software starts at the plain look. (A phone draws the lite look at 1.5 from the start.)
const STEP_PLAIN = 3;
const STEP_STILL = 4;

/** The next step for a turning view whose frames average `seconds`: under 26 a second (so a display held at 30 keeps its pixels)
 * it gives up pixels, under 15 at a ratio of 1 (or under 6 at any) it gives up the look, and under 8 with the plain look it stops
 * turning. */
function stepDown(step: number, seconds: number): number {
  if (step >= STEP_STILL) return step;
  if (step === STEP_PLAIN) return seconds > 1 / 8 ? STEP_STILL : step;
  if (seconds > 1 / 6) return STEP_PLAIN;
  if (step === STEP_PLAIN - 1) return seconds > 1 / 15 ? STEP_PLAIN : step;
  return seconds > 1 / 26 ? step + 1 : step;
}

export function LaminateSceneCanvas({
  plies, hovered, onHover, reducedMotion, decor = true, laid, explode = 0, marked = null, azimuth = null,
}: LaminateSceneProps) {
  const container = useRef<HTMLDivElement>(null);
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [inView, setInView] = useState(true);
  const [visible, setVisible] = useState(true);
  const [coarse, setCoarse] = useState(false);
  const [dragged, setDragged] = useState(false);
  const [step, setStep] = useState(0);
  useEffect(() => {
    const available = webglAvailable();
    if (available && drawsInSoftware()) setStep(STEP_PLAIN);
    setWebgl(available);
    setCoarse(window.matchMedia("(pointer: coarse)").matches);
    const onVisibility = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);
  useEffect(() => {
    if (!container.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, [webgl]);
  const shown = inView && visible;
  const steered = azimuth !== null;
  const grade: CarbonGrade = step >= STEP_PLAIN ? "plain" : coarse ? "lite" : "full";
  const ratio = step >= 2 ? 1 : coarse || step === 1 ? 1.5 : 2;
  // The view runs every frame only while it turns by itself (until the visitor first drags it); otherwise it draws when something changes.
  const turning = decor && !reducedMotion && shown && !dragged && !steered && step < STEP_STILL;
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading hero-laminate-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="hero-laminate-canvas" data-testid="laminate-scene" ref={container}>
      <Canvas
        frameloop={turning ? "always" : "demand"}
        dpr={[1, ratio]}
        gl={GL}
        camera={CAMERA}
        onPointerMissed={() => onHover(null)}
      >
        <Backdrop />
        <CarbonLighting grade={grade} />
        <Stack
          plies={plies} hovered={hovered} onHover={onHover} laid={laid} explode={explode} marked={marked}
          grade={grade} still={reducedMotion || !shown}
        />
        <FitWidth explode={explode} />
        <Turn azimuth={azimuth} />
        <FrameBudget active={turning} step={step} onMean={(seconds) => setStep((current) => stepDown(current, seconds))} />
        <OrbitControls
          makeDefault
          target={[0, 0, 0]}
          enabled={!steered}
          enableZoom={false}
          enablePan={false}
          enableRotate={!coarse}
          autoRotate={turning}
          autoRotateSpeed={0.7}
          enableDamping={false}
          onStart={() => setDragged(true)}
        />
      </Canvas>
    </div>
  );
}
