"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { demoRun, demoScale } from "@/lib/demo-run";
import { angleSlots, colorAt, hexToRgb } from "@/lib/studio-colors";
import { clamp01, poseAt, sceneAt, type LayupScript } from "./product-demo-timeline";

/** What the page hands the view: the demo's clock, written by the driver's frames, and the view's own request to be drawn again. */
export type DemoSceneHandle = { clock: number; redraw: (() => void) | null };

/** The product demo's centre model (ADR-0095): the recorded run's coupon, one slab a ply, on the black box. Its place and
 * orientation, how far its plies stand apart, the mesh and the stress field's colours are all read from the demo's clock on
 * each frame (components/home/product-demo-timeline.ts) and written to transforms and uniforms; nothing is computed here but
 * where things are drawn. The coupon is drawn in millimetres, its thickness enlarged so the plies can be told apart. */

const PLY_THICK = 2.2; // mm as drawn: the real ply is 0.18 mm
const PLY_GAP = 15; // mm between plies when they stand fully apart
const PLY_DROP = 30; // mm above its place a ply starts when it is laid
const CARBON: [number, number, number] = [0.15, 0.154, 0.163]; // a dark grey that still reads on the black ground
const CAMERA_Z = 12;
const CAMERA_FOV = 20;

const SKIN_VERTEX = /* glsl */ `
  attribute vec3 carbon;
  attribute vec3 field;
  uniform float uField;
  varying vec3 vColor;
  void main() {
    vColor = mix( carbon, field, uField );
    gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
  }`;
const SKIN_FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vColor;
  void main() {
    gl_FragColor = vec4( vColor, uOpacity );
  }`;

type Ply = { group: THREE.Group; skin: THREE.ShaderMaterial; slab: THREE.MeshBasicMaterial; rim: THREE.LineBasicMaterial; mesh: THREE.LineBasicMaterial };

/** The coupon's parts, built once from the recorded run. Its length lies along x and its width along y, centred; z is through
 * the thickness, the bottom ply lowest. */
function buildModel() {
  const { mesh, field, coupon } = demoRun;
  const scale = demoScale(demoRun);
  const slots = angleSlots(coupon.angles);
  const half = { x: coupon.length / 2, y: coupon.width / 2 };
  const at = (node: number): [number, number] => [mesh.nodes[node][1] - half.x, mesh.nodes[node][0] - half.y];
  // The faces: two triangles an element, each vertex carrying the carbon's tone and the element's colour on the field's scale.
  const positions: number[] = [];
  for (const quad of mesh.quads) for (const corner of [0, 1, 2, 0, 2, 3]) positions.push(...at(quad[corner]), 0);
  // The mesh's lines, each edge once.
  const seen = new Set<string>();
  const lines: number[] = [];
  for (const quad of mesh.quads) {
    for (let side = 0; side < 4; side++) {
      const a = quad[side], b = quad[(side + 1) % 4];
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key)) continue;
      seen.add(key);
      lines.push(...at(a), 0, ...at(b), 0);
    }
  }
  const lineGeometry = new THREE.BufferGeometry();
  lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
  const rimGeometry = new THREE.BufferGeometry();
  rimGeometry.setAttribute("position", new THREE.Float32BufferAttribute([
    -half.x, -half.y, 0, half.x, -half.y, 0, half.x, -half.y, 0, half.x, half.y, 0, half.x, half.y, 0, -half.x, half.y, 0, -half.x, half.y, 0, -half.x, -half.y, 0,
  ], 3));
  const slabGeometry = new THREE.BoxGeometry(coupon.length, coupon.width, PLY_THICK);

  const root = new THREE.Group();
  const plies: Ply[] = coupon.angles.map((angle, index) => {
    const group = new THREE.Group();
    const carbon: number[] = [];
    const colours: number[] = [];
    // A ply's fibres run at its angle: a faint stripe of tone along them tells the plies apart before the field colours them.
    const tone = 1 + 0.22 * Math.cos(THREE.MathUtils.degToRad(angle) * 2);
    for (const value of field.plies[index]) {
      const colour = colorAt(scale, value);
      for (let vertex = 0; vertex < 6; vertex++) {
        carbon.push(CARBON[0] * tone, CARBON[1] * tone, CARBON[2] * tone);
        colours.push(...colour);
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("carbon", new THREE.Float32BufferAttribute(carbon, 3));
    geometry.setAttribute("field", new THREE.Float32BufferAttribute(colours, 3));
    const skin = new THREE.ShaderMaterial({
      vertexShader: SKIN_VERTEX, fragmentShader: SKIN_FRAGMENT, uniforms: { uField: { value: 0 }, uOpacity: { value: 1 } },
      transparent: true, side: THREE.DoubleSide, toneMapped: false,
    });
    const face = new THREE.Mesh(geometry, skin);
    face.position.z = PLY_THICK / 2 + 0.12;
    // The slab is pushed back in depth a little, so its top never shows through the face that lies on it.
    const slab = new THREE.MeshBasicMaterial({
      color: new THREE.Color(0.085, 0.088, 0.094), transparent: true, toneMapped: false, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2,
    });
    const rim = new THREE.LineBasicMaterial({ color: new THREE.Color(...hexToRgb(slots.get(angle) ?? "#888888")), transparent: true, toneMapped: false });
    const edge = new THREE.LineSegments(rimGeometry, rim);
    edge.position.z = PLY_THICK / 2 + 0.3;
    const wire = new THREE.LineBasicMaterial({ color: new THREE.Color(0.86, 0.88, 0.9), transparent: true, opacity: 0, toneMapped: false });
    const net = new THREE.LineSegments(lineGeometry, wire);
    net.position.z = PLY_THICK / 2 + 0.22;
    group.add(new THREE.Mesh(slabGeometry, slab), face, net, edge);
    root.add(group);
    return { group, skin, slab, rim, mesh: wire };
  });
  return { root, plies, dispose: () => { lineGeometry.dispose(); rimGeometry.dispose(); slabGeometry.dispose(); } };
}

function shadowTexture(): THREE.CanvasTexture {
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

function Coupon({ handle, script }: { handle: DemoSceneHandle; script: LayupScript }) {
  const model = useMemo(buildModel, []);
  const shadow = useMemo(() => {
    const texture = shadowTexture();
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
    shadow.texture.dispose();
    shadow.material.dispose();
  }, [model, shadow]);

  useFrame((state) => {
    const group = turn.current;
    if (!group) return;
    const clock = handle.clock;
    const pose = poseAt(clock);
    const scene = sceneAt(clock, script);
    const { width, height } = state.viewport; // the world's size at the model's distance
    const unit = (pose.size * width) / demoRun.coupon.length; // world units a millimetre
    const x = (pose.x - 0.5) * width;
    const y = (0.5 - pose.y) * height;
    group.position.set(x, y, 0);
    group.scale.setScalar(unit);
    group.rotation.set(-pose.pitch, pose.yaw, 0, "YXZ");
    const count = model.plies.length;
    const step = PLY_THICK + clamp01(pose.explode) * PLY_GAP;
    model.plies.forEach((ply, index) => {
      const laid = clamp01(scene.laid - index);
      const eased = laid * laid * (3 - 2 * laid);
      ply.group.visible = laid > 0 && scene.presence > 0;
      ply.group.position.z = (index - (count - 1) / 2) * step + (1 - eased) * PLY_DROP;
      const opacity = eased * scene.presence;
      ply.skin.uniforms.uField.value = scene.field;
      ply.skin.uniforms.uOpacity.value = opacity;
      ply.slab.opacity = opacity;
      ply.rim.opacity = opacity * (1 - 0.75 * scene.field);
      // The mesh: light lines on the carbon, darker and fainter once the field colours the ply.
      ply.mesh.opacity = opacity * scene.mesh * (0.5 - 0.3 * scene.field);
      ply.mesh.color.setScalar(0.88 - 0.8 * scene.field);
    });
    // A faint pool of light on the black ground, just under the model (a shadow, when the ground was white): as wide as the coupon is long on the screen, and deeper the
    // further the plies stand apart.
    const laidShare = clamp01(scene.laid / count);
    const stack = ((count - 1) * step + PLY_THICK) * unit; // the stack's height in the world
    const reach = (demoRun.coupon.width * Math.cos(pose.pitch) + stack * Math.sin(pose.pitch)) / 2; // half its height on the screen
    const long = demoRun.coupon.length * unit * Math.cos(pose.yaw);
    shadow.mesh.position.set(x, y - reach - 0.03 * height, -1);
    shadow.mesh.scale.set(long * 1.15, 0.09 * height + 0.5 * reach, 1);
    shadow.material.opacity = 0.16 * scene.presence * laidShare;
  });

  return (
    <>
      <primitive object={shadow.mesh} />
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

/** The view fills its box and has no ground of its own: the black box shows through. A browser without WebGL draws nothing here;
 * the words and the cards still tell the run. */
export function ProductDemoSceneCanvas({ handle, script }: { handle: DemoSceneHandle; script: LayupScript }) {
  const available = useMemo(() => (typeof document === "undefined" ? false : webglAvailable()), []);
  if (!available) return null;
  return (
    <Canvas
      frameloop="demand" dpr={[1, 2]} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, CAMERA_Z], fov: CAMERA_FOV, near: 4, far: 30 }}
      style={{ pointerEvents: "none" }} aria-hidden="true"
    >
      <Coupon handle={handle} script={script} />
    </Canvas>
  );
}
