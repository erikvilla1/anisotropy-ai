"use client";

import { forwardRef, memo, useEffect, useMemo } from "react";
import { Environment, Lightformer, Line } from "@react-three/drei";
import * as THREE from "three";
import type { CarbonGrade } from "./carbon-material";

/**
 * The room the laminate view is photographed in: light panels rendered once into an environment map (the approach of
 * `components/studio/scene-lighting.tsx`, ADR-0063, with panels placed for dark carbon), a backdrop, a floor that carries a soft
 * contact shadow, and the axes. Nothing is downloaded. The scene is z-up: the plies lie in x and y, the thickness runs along z.
 */

const Z_UP: [number, number, number] = [0, 0, 1];
// The upright panels around the stack: bearing about z in degrees, intensity, width. Uneven on purpose, with dark between them, so
// what the faces mirror changes as the view turns.
const PANELS: [number, number, number][] = [[20, 2.4, 1.5], [75, 1.1, 2.4], [132, 2.8, 1.3], [190, 0.9, 2.6], [248, 2.2, 1.4], [305, 1.3, 2.2]];

/** Soft boxes around and above the stack, so the resin coat and the fibres' stretched reflection have something to reflect from
 * every side as the view turns, a dim floor for the cut edges (which mirror what is below them), and one key light for form.
 * Memoized, and it must stay so: drei's Environment renders its panels into the map again whenever it is handed new children,
 * which without the memo would be on every render of the view (every hover, every step of a scroll-driven prop). */
export const CarbonLighting = memo(function CarbonLighting({ grade }: { grade: CarbonGrade }) {
  // Without an environment map (a browser drawing in software), three lamps stand in for the panels.
  if (grade === "plain") {
    return (
      <>
        <hemisphereLight position={Z_UP} args={["#ffffff", "#4a4a4a", 1.5]} />
        <directionalLight position={[3.6, -1.3, 3.4]} intensity={0.9} />
        <directionalLight position={[-3.2, 3.4, 2.2]} intensity={0.34} />
        <directionalLight position={[-2.6, -3.6, 2.8]} intensity={0.3} />
      </>
    );
  }
  return (
    <>
      <Environment resolution={grade === "lite" ? 128 : 256} frames={1}>
        <Lightformer form="circle" intensity={0.9} color="#ffffff" position={[0.6, -1.2, 7]} scale={6} />
        {PANELS.map(([bearing, intensity, width], index) => {
          const angle = THREE.MathUtils.degToRad(bearing);
          return (
            <Lightformer key={index} form="rect" up={Z_UP} intensity={intensity} color="#ffffff"
              position={[7 * Math.cos(angle), 7 * Math.sin(angle), 2.5]} scale={[width, 4.4]} />
          );
        })}
        <Lightformer form="circle" intensity={0.42} color="#a6a6a6" position={[0, 0, -7]} scale={9} />
      </Environment>
      <hemisphereLight position={Z_UP} args={["#ffffff", "#4a4a4a", 1.1]} />
      <directionalLight position={[3.6, -1.3, 3.4]} intensity={0.8} />
    </>
  );
});

const BACKDROP_VERTEX = /* glsl */ `
  void main() {
    gl_Position = vec4( position.xy, 1.0, 1.0 );
  }`;
// Pure black, as the page around the view is (ADR-0077 amendment 25). The only light on the ground is the floor's faint pool
// under the stack. Until that amendment this was a dark grey, lighter behind the stack.
const BACKDROP_FRAGMENT = /* glsl */ `
  void main() {
    gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
  }`;

/** The view's ground colour, drawn in WebGL behind everything else (the card's own CSS background is never seen through it). */
export const Backdrop = memo(function Backdrop() {
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: BACKDROP_VERTEX, fragmentShader: BACKDROP_FRAGMENT, depthTest: false, depthWrite: false, toneMapped: false,
  }), []);
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh frustumCulled={false} renderOrder={-1000} material={material}>
      <planeGeometry args={[2, 2]} />
    </mesh>
  );
});

const FLOOR_VERTEX = /* glsl */ `
  varying vec2 vPoint;
  void main() {
    vPoint = position.xy;
    gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
  }`;
// The floor under the stack: a faint pool of light, and the stack's contact shadow, which for a box standing on a plane is the
// blurred outline of its footprint, so it is written as that instead of being rendered from the scene every frame.
const FLOOR_FRAGMENT = /* glsl */ `
  uniform vec2 uHalf;
  uniform float uShadow;
  uniform float uLift;
  varying vec2 vPoint;
  float hash( vec2 p ) {
    vec3 p3 = fract( vec3( p.xyx ) * 0.1031 );
    p3 += dot( p3, p3.yzx + 33.33 );
    return fract( ( p3.x + p3.y ) * p3.z );
  }
  float box( vec2 p, vec2 b ) {
    vec2 d = abs( p ) - b;
    return length( max( d, 0.0 ) ) + min( max( d.x, d.y ), 0.0 );
  }
  void main() {
    float d = box( vPoint, uHalf );
    float core = 1.0 - smoothstep( -0.05, 0.075 + 0.7 * uLift, d );
    float wide = 1.0 - smoothstep( -0.1, 0.62 + uLift, d );
    float shadow = uShadow * ( 0.82 * core + 0.4 * wide * wide ) / ( 1.0 + 2.5 * uLift );
    float r = length( vPoint );
    float fade = 1.0 - smoothstep( 1.5, 2.7, r );
    float pool = 0.06 * exp( - r * r / 1.7 );
    vec3 light = vec3( pool * ( 1.0 - shadow ) * fade );
    light += ( hash( gl_FragCoord.xy ) - 0.5 ) / 255.0 * fade;
    gl_FragColor = vec4( max( light, 0.0 ), shadow * fade );
  }`;

export type FloorUniforms = { uHalf: { value: THREE.Vector2 }; uShadow: { value: number }; uLift: { value: number } };

/** The floor. Its uniforms are the caller's, so the shadow can fade in with the first ply and soften as that ply is lifted. */
export const Floor = forwardRef<THREE.Mesh, { uniforms: FloorUniforms }>(function Floor({ uniforms }, ref) {
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: FLOOR_VERTEX, fragmentShader: FLOOR_FRAGMENT, uniforms, transparent: true, depthWrite: false, toneMapped: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
  }), [uniforms]);
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh ref={ref} material={material} renderOrder={-1}>
      <planeGeometry args={[6, 6]} />
    </mesh>
  );
});

function labelTexture(letter: string, color: string): THREE.CanvasTexture {
  const size = 96;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (context) {
    context.font = `500 ${Math.round(size * 0.62)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = color;
    context.fillText(letter, size / 2, size / 2);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** The colours of the three axes: the greys of the legend beside the view on the home page. */
export const AXIS_COLORS = { x: "#d4d4d4", y: "#acacac", z: "#efefef" } as const;

const AXIS_LENGTH = 0.3;
const AXES: { name: "x" | "y" | "z"; direction: [number, number, number]; rotation: [number, number, number] }[] = [
  { name: "x", direction: [1, 0, 0], rotation: [0, 0, -Math.PI / 2] },
  { name: "y", direction: [0, 1, 0], rotation: [0, 0, 0] },
  { name: "z", direction: [0, 0, 1], rotation: [Math.PI / 2, 0, 0] },
];

/** The laminate's axes: x along the 0° fibre, y across, z through the thickness. Thin lines with a small head and a letter
 * each, in colours that are not tone mapped, so they are the legend's greys exactly. */
export const Axes = memo(function Axes({ origin }: { origin: [number, number, number] }) {
  const labels = useMemo(() => AXES.map((axis) => labelTexture(axis.name, AXIS_COLORS[axis.name])), []);
  useEffect(() => () => labels.forEach((texture) => texture.dispose()), [labels]);
  return (
    <group position={origin}>
      <mesh>
        <sphereGeometry args={[0.0065, 16, 12]} />
        <meshBasicMaterial color="#8c8c8c" toneMapped={false} />
      </mesh>
      {AXES.map((axis, i) => {
        const tip = axis.direction.map((value) => value * AXIS_LENGTH) as [number, number, number];
        const label = axis.direction.map((value) => value * (AXIS_LENGTH + 0.07)) as [number, number, number];
        return (
          <group key={axis.name}>
            <Line points={[[0, 0, 0], tip]} color={AXIS_COLORS[axis.name]} lineWidth={1.1} toneMapped={false} />
            <mesh position={tip} rotation={axis.rotation}>
              <coneGeometry args={[0.0095, 0.042, 24]} />
              <meshBasicMaterial color={AXIS_COLORS[axis.name]} toneMapped={false} />
            </mesh>
            <sprite position={label} scale={0.07}>
              <spriteMaterial map={labels[i]} transparent depthWrite={false} toneMapped={false} />
            </sprite>
          </group>
        );
      })}
    </group>
  );
});
