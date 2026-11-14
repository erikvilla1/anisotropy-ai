"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { demoWing, wingScale } from "@/lib/demo-wing";
import { colorAt } from "@/lib/studio-colors";
import { clamp01, poseAt, sceneAt } from "./product-demo-timeline";

/** What the page hands the view: the demo's clock, written by the driver's frames, and the view's own request to be drawn again. */
export type DemoSceneHandle = { clock: number; redraw: (() => void) | null };

/** The product demo's centre model (ADR-0098): the example wing, drawn from the very mesh that was solved, one surface a part,
 * on the black stage. Its place and orientation, how far its parts stand apart, the mesh's lines and the analysis's colours
 * are all read from the demo's clock on each frame (components/home/product-demo-timeline.ts) and written to transforms and
 * uniforms; nothing is computed here but where things are drawn. The wing is drawn in millimetres: its span along the view's
 * x, its chord along y with the leading edge towards the viewer, and its depth along z. */

/** How far each part moves when the wing stands fully apart, in millimetres, as [along the span, along the chord, up]: the
 * skins lift off, the spars step out fore and aft, and the ribs stay where they are, in the middle. */
const APART: Record<string, [number, number, number]> = {
  "upper-skin": [0, 0, 150],
  "lower-skin": [0, 0, -150],
  "front-spar": [0, -70, 0],
  "rear-spar": [0, 70, 0],
  ribs: [0, 0, 0],
};
/** The carbon's tone a part, so the parts can be told apart before the analysis colours them. */
const TONE: Record<string, number> = { "upper-skin": 1, "lower-skin": 0.86, "front-spar": 1.28, "rear-spar": 1.28, ribs: 1.5 };
const CARBON: [number, number, number] = [0.25, 0.256, 0.27];
const CAMERA_Z = 12;
const CAMERA_FOV = 20;

const PART_VERTEX = /* glsl */ `
  attribute vec3 field;
  uniform vec3 uCarbon;
  uniform float uField;
  varying vec3 vColor;
  varying vec3 vView;
  void main() {
    vColor = mix( uCarbon, field, uField );
    vec4 view = modelViewMatrix * vec4( position, 1.0 );
    vView = view.xyz;
    gl_Position = projectionMatrix * view;
  }`;
/** Each face is lit by where it faces, read from the surface itself, so the aerofoil's curve and the parts' edges show without
 * a light in the scene; the analysis's colours are lit less, so a colour means the same on every face. */
const PART_FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  uniform float uField;
  varying vec3 vColor;
  varying vec3 vView;
  void main() {
    vec3 normal = normalize( cross( dFdx( vView ), dFdy( vView ) ) );
    float facing = abs( dot( normal, normalize( vec3( 0.25, 0.55, 0.8 ) ) ) );
    float lit = mix( 0.45 + 0.75 * facing, 0.8 + 0.25 * facing, uField );
    gl_FragColor = vec4( vColor * lit, uOpacity );
  }`;

type Part = { id: string; group: THREE.Group; skin: THREE.ShaderMaterial; mesh: THREE.LineBasicMaterial; apart: [number, number, number] };

/** The wing's parts, built once from the record, centred on the wing's middle. */
function buildModel() {
  const { mesh, parts, wing, field } = demoWing;
  const scale = field ? wingScale(field) : null;
  const middle = { span: wing.span / 2, chord: wing.chord / 2 };
  const at = (node: number): [number, number, number] => [mesh.nodes[node][1] - middle.span, mesh.nodes[node][0] - middle.chord, mesh.nodes[node][2]];
  const disposables: { dispose: () => void }[] = [];
  const root = new THREE.Group();
  const built: Part[] = parts.map((part) => {
    const positions: number[] = [];
    const colours: number[] = [];
    const lines: number[] = [];
    const seen = new Set<string>();
    for (let face = part.first; face < part.first + part.count; face++) {
      const quad = mesh.quads[face];
      const colour = scale && field ? colorAt(scale, field.values[face]) : CARBON;
      for (const corner of [0, 1, 2, 0, 2, 3]) {
        positions.push(...at(quad[corner]));
        colours.push(...colour);
      }
      for (let side = 0; side < 4; side++) {
        const a = quad[side], b = quad[(side + 1) % 4];
        const key = a < b ? `${a}-${b}` : `${b}-${a}`;
        if (seen.has(key)) continue;
        seen.add(key);
        lines.push(...at(a), ...at(b));
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("field", new THREE.Float32BufferAttribute(colours, 3));
    const tone = TONE[part.id] ?? 1;
    const skin = new THREE.ShaderMaterial({
      vertexShader: PART_VERTEX, fragmentShader: PART_FRAGMENT,
      uniforms: { uCarbon: { value: new THREE.Vector3(CARBON[0] * tone, CARBON[1] * tone, CARBON[2] * tone) }, uField: { value: 0 }, uOpacity: { value: 1 } },
      transparent: true, side: THREE.DoubleSide, toneMapped: false,
      // The faces sit a little back in depth, so the mesh's lines drawn on them never flicker.
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    const lineGeometry = new THREE.BufferGeometry();
    lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    const wire = new THREE.LineBasicMaterial({ color: new THREE.Color(0.86, 0.88, 0.9), transparent: true, opacity: 0, toneMapped: false });
    const group = new THREE.Group();
    group.add(new THREE.Mesh(geometry, skin), new THREE.LineSegments(lineGeometry, wire));
    root.add(group);
    disposables.push(geometry, lineGeometry, skin, wire);
    return { id: part.id, group, skin, mesh: wire, apart: APART[part.id] ?? [0, 0, 0] };
  });
  return { root, parts: built, hasField: Boolean(field), dispose: () => disposables.forEach((item) => item.dispose()) };
}

function glowTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const context = canvas.getContext("2d")!;
  const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(255,255,255,0.5)");
  gradient.addColorStop(0.6, "rgba(255,255,255,0.16)");
  gradient.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function Wing({ handle }: { handle: DemoSceneHandle }) {
  const model = useMemo(buildModel, []);
  const glow = useMemo(() => {
    const texture = glowTexture();
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false });
    return { mesh: new THREE.Mesh(new THREE.PlaneGeometry(1, 1), material), material, texture };
  }, []);
  const turn = useRef<THREE.Group>(null);
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    handle.redraw = invalidate;
    invalidate();
    return () => { handle.redraw = null; };
  }, [handle, invalidate]);
  useEffect(() => () => {
    model.dispose();
    glow.texture.dispose();
    glow.material.dispose();
    glow.mesh.geometry.dispose();
  }, [model, glow]);

  useFrame((state) => {
    const group = turn.current;
    if (!group) return;
    const clock = handle.clock;
    const pose = poseAt(clock);
    const scene = sceneAt(clock);
    const { width, height } = state.viewport; // the world's size at the model's distance
    const { span, chord } = demoWing.wing;
    const unit = (pose.size * width) / span; // world units a millimetre
    const x = (pose.x - 0.5) * width;
    const y = (0.5 - pose.y) * height;
    group.position.set(x, y, 0);
    group.scale.setScalar(unit);
    group.rotation.set(-pose.pitch, pose.yaw, 0, "YXZ");
    group.visible = scene.presence > 0;
    const apart = clamp01(pose.explode);
    const field = model.hasField ? scene.field : 0;
    for (const part of model.parts) {
      part.group.position.set(part.apart[0] * apart, part.apart[1] * apart, part.apart[2] * apart);
      part.skin.uniforms.uField.value = field;
      part.skin.uniforms.uOpacity.value = scene.presence;
      // The mesh: light lines on the carbon, darker and fainter once the analysis colours the part.
      part.mesh.opacity = scene.presence * scene.mesh * (0.34 - 0.2 * field);
      part.mesh.color.setScalar(0.88 - 0.8 * field);
    }
    // A faint pool of light on the black ground, just under the wing: as wide as the span on the screen, and deeper the
    // further the parts stand apart.
    const reach = ((chord * Math.cos(pose.pitch) + (40 + 300 * apart) * Math.sin(pose.pitch)) * unit) / 2; // half the model's height on the screen
    glow.mesh.position.set(x, y - reach - 0.03 * height, -1);
    glow.mesh.scale.set(span * unit * Math.cos(pose.yaw) * 1.15, 0.09 * height + 0.5 * reach, 1);
    glow.material.opacity = 0.16 * scene.presence;
  });

  return (
    <>
      <primitive object={glow.mesh} />
      <group ref={turn}>
        <primitive object={model.root} />
      </group>
    </>
  );
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/** The view fills its box and has no ground of its own: the black stage shows through. A browser without WebGL draws nothing
 * here; the words and the cards still tell the analysis. */
export function ProductDemoSceneCanvas({ handle }: { handle: DemoSceneHandle }) {
  const available = useMemo(() => (typeof document === "undefined" ? false : webglAvailable()), []);
  if (!available) return null;
  return (
    <Canvas
      frameloop="demand" dpr={[1, 2]} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, CAMERA_Z], fov: CAMERA_FOV, near: 4, far: 30 }}
      style={{ pointerEvents: "none" }} aria-hidden="true"
    >
      <Wing handle={handle} />
    </Canvas>
  );
}
