"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { WebGLMissing, webglAvailable } from "@/components/studio/webgl-missing";

export type ScenePly = { angle_deg: number; thickness_mm: number; color: string };
export type LaminateSceneProps = {
  /** Bottom face first (ADR-0004). */
  plies: ScenePly[];
  hovered: number | null;
  onHover: (index: number | null) => void;
  reducedMotion: boolean;
  /** The hero's dust and slow turn; off in the workspace's layup editor, where the stack is a control, not a scene (ADR-0062). */
  decor?: boolean;
};

const WIDTH = 1.4; // x, along the 0° fiber
const DEPTH = 0.9; // y, across
const STACK_HEIGHT = 0.42; // the drawn thickness of the whole stack: a shape, not a scale
const GAP = 0.006;
const DUST_DESKTOP = 300;
const DUST_PHONE = 120;

// Each ply is a slab whose top and bottom faces carry stripes along its fiber direction: the stripe value is constant along
// the fiber (x cos θ + y sin θ) and steps across it. Side faces are the plain colour, darker; a hovered ply brightens.
const vertexShader = /* glsl */ `
  varying vec3 vNormal;
  varying vec3 vLocal;
  void main() {
    vNormal = normal;
    vLocal = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;
const fragmentShader = /* glsl */ `
  uniform vec3 uColor;
  uniform float uAngle;
  uniform float uHighlight;
  varying vec3 vNormal;
  varying vec3 vLocal;
  void main() {
    float flat_face = step(0.5, abs(vNormal.z));
    float across = -vLocal.x * sin(uAngle) + vLocal.y * cos(uAngle);
    float stripe = step(0.7, fract(across * 16.0));
    vec3 face = mix(uColor, uColor * 0.5, stripe);
    vec3 side = uColor * 0.58;
    vec3 color = mix(side, face, flat_face);
    color = mix(color, vec3(1.0), uHighlight * 0.28);
    gl_FragColor = vec4(color, 1.0);
  }`;

function PlySlab({ ply, index, z, height, highlighted, onHover }: {
  ply: ScenePly; index: number; z: number; height: number; highlighted: boolean; onHover: (index: number | null) => void;
}) {
  const invalidate = useThree((state) => state.invalidate);
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader, fragmentShader,
    uniforms: { uColor: { value: new THREE.Color(ply.color) }, uAngle: { value: THREE.MathUtils.degToRad(ply.angle_deg) }, uHighlight: { value: 0 } },
  }), [ply.color, ply.angle_deg]);
  useEffect(() => () => material.dispose(), [material]);
  useEffect(() => {
    material.uniforms.uHighlight.value = highlighted ? 1 : 0;
    invalidate();
  }, [material, highlighted, invalidate]);
  return (
    <mesh
      position={[0, 0, z]}
      material={material}
      onPointerOver={(event: ThreeEvent<PointerEvent>) => { event.stopPropagation(); onHover(index); }}
      onPointerOut={() => onHover(null)}
    >
      <boxGeometry args={[WIDTH, DEPTH, height]} />
      <Edges color={highlighted ? "#eef0e9" : "#232a21"} />
    </mesh>
  );
}

function Stack({ plies, hovered, onHover }: { plies: ScenePly[]; hovered: number | null; onHover: (index: number | null) => void }) {
  // Heights follow the ply thicknesses, scaled so the whole stack is STACK_HEIGHT tall; a gap separates the slabs.
  const slabs = useMemo(() => {
    const total = plies.reduce((sum, ply) => sum + Math.max(ply.thickness_mm, 1e-6), 0);
    const usable = STACK_HEIGHT - GAP * Math.max(plies.length - 1, 0);
    let z = -STACK_HEIGHT / 2;
    return plies.map((ply) => {
      const height = (Math.max(ply.thickness_mm, 1e-6) / total) * usable;
      const centre = z + height / 2;
      z += height + GAP;
      return { height, z: centre };
    });
  }, [plies]);
  return (
    <group>
      {plies.map((ply, index) => (
        <PlySlab key={index} ply={ply} index={index} z={slabs[index].z} height={slabs[index].height} highlighted={hovered === index} onHover={onHover} />
      ))}
    </group>
  );
}

function Axes() {
  const origin: [number, number, number] = [-WIDTH / 2 - 0.12, -DEPTH / 2 - 0.12, -STACK_HEIGHT / 2];
  const length = 0.34;
  const axes: { to: [number, number, number]; color: string }[] = [
    { to: [origin[0] + length, origin[1], origin[2]], color: "#c1deb5" },
    { to: [origin[0], origin[1] + length, origin[2]], color: "#8fbb80" },
    { to: [origin[0], origin[1], origin[2] + length], color: "#eef0e9" },
  ];
  return (
    <group>
      {axes.map((axis, i) => (
        <Line key={i} points={[origin, axis.to]} color={axis.color} lineWidth={1.5} />
      ))}
      {axes.map((axis, i) => {
        const direction = new THREE.Vector3(...axis.to).sub(new THREE.Vector3(...origin)).normalize();
        return <arrowHelper key={`h${i}`} args={[direction, new THREE.Vector3(...axis.to), 0.001, axis.color, 0.05, 0.03]} />;
      })}
    </group>
  );
}

function Dust({ count, active }: { count: number; active: boolean }) {
  const points = useRef<THREE.Points>(null);
  const seeds = useMemo(() => {
    const base = new Float32Array(count * 3);
    const phase = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      base[3 * i] = (Math.random() - 0.5) * 2.6;
      base[3 * i + 1] = (Math.random() - 0.5) * 2.0;
      base[3 * i + 2] = (Math.random() - 0.5) * 1.4;
      phase[i] = Math.random() * Math.PI * 2;
    }
    return { base, phase };
  }, [count]);
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(seeds.base.slice(), 3));
    return g;
  }, [seeds]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useFrame((state) => {
    if (!active || !points.current) return;
    const t = state.clock.elapsedTime;
    const attribute = geometry.getAttribute("position") as THREE.BufferAttribute;
    const array = attribute.array as Float32Array;
    for (let i = 0; i < count; i++) {
      const p = seeds.phase[i];
      array[3 * i] = seeds.base[3 * i] + 0.03 * Math.cos(0.25 * t + p);
      array[3 * i + 2] = seeds.base[3 * i + 2] + 0.04 * Math.sin(0.35 * t + p);
    }
    attribute.needsUpdate = true;
  });
  return (
    <points ref={points} geometry={geometry}>
      <pointsMaterial color="#c1deb5" size={0.012} sizeAttenuation transparent opacity={0.55} depthWrite={false} />
    </points>
  );
}

export function LaminateSceneCanvas({ plies, hovered, onHover, reducedMotion, decor = true }: LaminateSceneProps) {
  const container = useRef<HTMLDivElement>(null);
  const [webgl, setWebgl] = useState<boolean | null>(null);
  const [inView, setInView] = useState(true);
  const [visible, setVisible] = useState(true);
  const [coarse, setCoarse] = useState(false);
  const [autoRotate, setAutoRotate] = useState(decor);
  useEffect(() => {
    setWebgl(webglAvailable());
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
  const motion = decor && !reducedMotion && inView && visible;
  const active = motion && (autoRotate || true);
  const dust = coarse ? DUST_PHONE : DUST_DESKTOP;
  if (webgl === false) return <WebGLMissing />;
  if (webgl === null) return <div className="studio-scene-loading hero-laminate-loading" role="status">Loading the 3D view…</div>;
  return (
    <div className="hero-laminate-canvas" data-testid="laminate-scene" ref={container}>
      <Canvas
        frameloop={active ? "always" : "demand"}
        dpr={[1, 1.5]}
        gl={{ alpha: true, antialias: true }}
        camera={{ position: [1.75, -1.95, 1.25], up: [0, 0, 1], fov: 30, near: 0.01, far: 50 }}
        onPointerMissed={() => onHover(null)}
      >
        <ambientLight intensity={0.9} />
        <directionalLight position={[2, -2, 3]} intensity={1.0} />
        <Stack plies={plies} hovered={hovered} onHover={onHover} />
        <Axes />
        {reducedMotion || !decor ? null : <Dust count={dust} active={motion} />}
        <OrbitControls
          makeDefault
          target={[0, 0, 0]}
          enableZoom={false}
          enablePan={false}
          enableRotate={!coarse}
          autoRotate={autoRotate && motion}
          autoRotateSpeed={0.7}
          enableDamping={false}
          onStart={() => setAutoRotate(false)}
        />
      </Canvas>
    </div>
  );
}
