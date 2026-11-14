"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { BEND_DRAWN, demoWing, wingColour, wingExtent } from "@/lib/demo-wing";
import { clamp01, poseAt, sceneAt } from "./product-demo-timeline";

/** What the page hands the view: the demo's clock, written by the driver's frames, and the view's own request to be drawn again. */
export type DemoSceneHandle = { clock: number; redraw: (() => void) | null; /** How far a visitor has turned the wing by hand, in radians, once the demo has played. */ turn?: { yaw: number; pitch: number } };

/** The product demo's centre model (ADR-0098): the example wing, drawn from the very mesh that was solved, one surface a part,
 * on the black stage. Its place and orientation, how far its parts stand apart, the mesh's lines, the analysis's colours and
 * its bend are all read from the demo's clock on each frame (components/home/product-demo-timeline.ts) and written to
 * transforms and uniforms; nothing is computed here but where things are drawn. The wing is drawn in millimetres: its span
 * along the view's x, its chord along y with the leading edge towards the viewer, and its depth along z. Whole, its skins are
 * seen through, so the spars and the ribs show inside it; apart, every part is solid. */

/** How far each part moves when the wing stands fully apart, in millimetres, as [along the span, along the chord, up]: the
 * skins lift off, the spars step out fore and aft, and the ribs stay where they are, in the middle. */
const APART: Record<string, [number, number, number]> = {
  "upper-skin": [0, 0, 190],
  "lower-skin": [0, 0, -190],
  "front-spar": [0, -60, 0],
  "rear-spar": [0, 60, 0],
  ribs: [0, 0, 0],
};
const SKINS = new Set(["upper-skin", "lower-skin"]);
/** How much of a skin is there while the wing is whole: the rest is seen through. */
const SKIN_WHOLE = 0.4;
/** The carbon's tone a part, so the parts can be told apart before the analysis colours them. */
const TONE: Record<string, number> = { "upper-skin": 1, "lower-skin": 0.92, "front-spar": 1.7, "rear-spar": 1.7, ribs: 2.2 };
const CARBON: [number, number, number] = [0.16, 0.165, 0.178];
const CAMERA_Z = 12;
const CAMERA_FOV = 27;
/** The window's shape the poses were set for: on a wider window the wing is sized by the window's height, so it stays in it. */
const POSED_FOR = 1.6;

/** `bend` is how far the node moves under the load, as drawn; `uBend` brings it in with the analysis. A node's normal and its
 * colour are the averages of the faces of its part that meet there, so a curved skin is lit as one surface and the colours
 * run smoothly from face to face, as analysis programs draw an averaged field. */
const PART_VERTEX = /* glsl */ `
  attribute vec3 field;
  attribute vec3 bend;
  uniform float uBend;
  varying vec3 vField;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vField = field;
    vNormal = normalMatrix * normal;
    vec4 view = modelViewMatrix * vec4( position + bend * uBend, 1.0 );
    vView = view.xyz;
    gl_Position = projectionMatrix * view;
  }`;
/** Lit as a part under a studio's lights, with no light in the scene: a key light from the upper right, a soft fill from the
 * left, a highlight where the surface mirrors the key and a sheen where it turns away from the eye. The bare carbon is dark
 * and glossy; the analysis's colours are matt, so a colour means the same wherever it lies. */
const PART_FRAGMENT = /* glsl */ `
  uniform vec3 uCarbon;
  uniform float uOpacity;
  uniform float uField;
  varying vec3 vField;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec3 eye = normalize( -vView );
    vec3 normal = normalize( vNormal );
    if ( dot( normal, eye ) < 0.0 ) normal = -normal;
    vec3 key = normalize( vec3( 0.35, 0.8, 0.55 ) );
    float lit = max( dot( normal, key ), 0.0 );
    float fill = max( dot( normal, normalize( vec3( -0.65, 0.25, 0.5 ) ) ), 0.0 );
    float shine = pow( max( dot( normal, normalize( key + eye ) ), 0.0 ), 42.0 );
    float sheen = pow( 1.0 - max( dot( normal, eye ), 0.0 ), 3.0 );
    vec3 carbon = uCarbon * ( 0.4 + 0.85 * lit + 0.3 * fill ) + vec3( 0.5 ) * shine + vec3( 0.16, 0.18, 0.22 ) * sheen;
    vec3 painted = vField * ( 0.6 + 0.5 * lit + 0.18 * fill ) + vec3( 0.2 ) * shine;
    gl_FragColor = vec4( mix( carbon, painted, uField ), uOpacity );
  }`;
const LINE_VERTEX = /* glsl */ `
  attribute vec3 bend;
  uniform float uBend;
  void main() {
    gl_Position = projectionMatrix * modelViewMatrix * vec4( position + bend * uBend, 1.0 );
  }`;
const LINE_FRAGMENT = /* glsl */ `
  uniform vec3 uColor;
  uniform float uOpacity;
  void main() {
    gl_FragColor = vec4( uColor, uOpacity );
  }`;

type Part = { id: string; skin: boolean; group: THREE.Group; face: THREE.ShaderMaterial; mesh: THREE.ShaderMaterial; rim: THREE.ShaderMaterial; apart: [number, number, number] };

const lineMaterial = (grey: number) => new THREE.ShaderMaterial({
  vertexShader: LINE_VERTEX, fragmentShader: LINE_FRAGMENT,
  uniforms: { uColor: { value: new THREE.Vector3(grey, grey, grey) }, uOpacity: { value: 0 }, uBend: { value: 0 } },
  transparent: true, depthWrite: false, toneMapped: false,
});

/** The wing's parts, built once from the record, centred on the wing's middle in plan. */
function buildModel() {
  const { mesh, parts, wing, field, displacement } = demoWing;
  const middle = { span: wing.span / 2, chord: wingExtent(demoWing) / 2 };
  const at = (node: number): [number, number, number] => [mesh.nodes[node][1] - middle.span, mesh.nodes[node][0] - middle.chord, mesh.nodes[node][2]];
  const moved = (node: number): [number, number, number] => {
    const move = displacement?.values[node];
    return move ? [move[1] * BEND_DRAWN, move[0] * BEND_DRAWN, move[2] * BEND_DRAWN] : [0, 0, 0];
  };
  const disposables: { dispose: () => void }[] = [];
  const root = new THREE.Group();
  const built: Part[] = parts.map((part) => {
    // What meets at each node of this part: the sum of its faces' normals, and the sum and count of their values.
    const normals = new Map<number, THREE.Vector3>();
    const values = new Map<number, { sum: number; count: number }>();
    const corner = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
    const across = [new THREE.Vector3(), new THREE.Vector3()];
    for (let face = part.first; face < part.first + part.count; face++) {
      const quad = mesh.quads[face];
      quad.forEach((node, index) => corner[index].set(...at(node)));
      const normal = new THREE.Vector3().crossVectors(across[0].subVectors(corner[2], corner[0]), across[1].subVectors(corner[3], corner[1]));
      for (const node of quad) {
        const sum = normals.get(node);
        if (sum) sum.add(normal);
        else normals.set(node, normal.clone());
        const value = values.get(node) ?? { sum: 0, count: 0 };
        value.sum += field ? field.values[face] : 0;
        value.count += 1;
        values.set(node, value);
      }
    }
    for (const normal of normals.values()) normal.normalize();
    const positions: number[] = [], bends: number[] = [], colours: number[] = [], facing: number[] = [];
    // Every edge of the part once, with how many of its faces share it: an edge of one face is the part's outline.
    const edges = new Map<string, { a: number; b: number; faces: number }>();
    for (let face = part.first; face < part.first + part.count; face++) {
      const quad = mesh.quads[face];
      for (const index of [0, 1, 2, 0, 2, 3]) {
        const node = quad[index];
        const value = values.get(node)!;
        positions.push(...at(node));
        bends.push(...moved(node));
        colours.push(...(field ? wingColour(field, value.sum / value.count) : CARBON));
        facing.push(...normals.get(node)!.toArray());
      }
      for (let side = 0; side < 4; side++) {
        const a = quad[side], b = quad[(side + 1) % 4];
        const key = a < b ? `${a}-${b}` : `${b}-${a}`;
        const edge = edges.get(key);
        if (edge) edge.faces += 1;
        else edges.set(key, { a, b, faces: 1 });
      }
    }
    const lines = (only: (faces: number) => boolean) => {
      const place: number[] = [], bend: number[] = [];
      for (const edge of edges.values()) {
        if (!only(edge.faces)) continue;
        place.push(...at(edge.a), ...at(edge.b));
        bend.push(...moved(edge.a), ...moved(edge.b));
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(place, 3));
      geometry.setAttribute("bend", new THREE.Float32BufferAttribute(bend, 3));
      disposables.push(geometry);
      return geometry;
    };
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("bend", new THREE.Float32BufferAttribute(bends, 3));
    geometry.setAttribute("field", new THREE.Float32BufferAttribute(colours, 3));
    geometry.setAttribute("normal", new THREE.Float32BufferAttribute(facing, 3));
    const tone = TONE[part.id] ?? 1;
    const skin = SKINS.has(part.id);
    const face = new THREE.ShaderMaterial({
      vertexShader: PART_VERTEX, fragmentShader: PART_FRAGMENT,
      uniforms: {
        uCarbon: { value: new THREE.Vector3(CARBON[0] * tone, CARBON[1] * tone, CARBON[2] * tone) },
        uField: { value: 0 }, uOpacity: { value: 1 }, uBend: { value: 0 },
      },
      transparent: true, side: THREE.DoubleSide, toneMapped: false,
      // A skin that is seen through must not hide what is inside it; the faces sit a little back in depth, so the lines
      // drawn on them never flicker.
      depthWrite: !skin, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    const net = lineMaterial(0.88);
    const rim = lineMaterial(0.92);
    const group = new THREE.Group();
    const surface = new THREE.Mesh(geometry, face);
    surface.renderOrder = skin ? 2 : 1; // the skins after what they cover
    const wires = new THREE.LineSegments(lines((faces) => faces > 1), net);
    const outline = new THREE.LineSegments(lines((faces) => faces === 1), rim);
    wires.renderOrder = outline.renderOrder = 3;
    group.add(surface, wires, outline);
    root.add(group);
    disposables.push(geometry, face, net, rim);
    return { id: part.id, skin, group, face, mesh: net, rim, apart: APART[part.id] ?? [0, 0, 0] };
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
    const span = demoWing.wing.span;
    const chord = wingExtent(demoWing);
    const unit = (pose.size * Math.min(width, POSED_FOR * height)) / span; // world units a millimetre
    const x = (pose.x - 0.5) * width;
    const y = (0.5 - pose.y) * height;
    group.position.set(x, y, 0);
    group.scale.setScalar(unit);
    const hand = handle.turn ?? { yaw: 0, pitch: 0 };
    group.rotation.set(-(pose.pitch + hand.pitch), pose.yaw + hand.yaw, 0, "YXZ");
    group.visible = scene.presence > 0;
    const apart = clamp01(pose.explode);
    const field = model.hasField ? scene.field : 0;
    for (const part of model.parts) {
      part.group.position.set(part.apart[0] * apart, part.apart[1] * apart, part.apart[2] * apart);
      // Whole, a skin is seen through; apart, it is solid.
      const there = part.skin ? Math.min(1, SKIN_WHOLE + (1 - SKIN_WHOLE) * apart + 0.3 * field * (1 - apart)) : 1;
      part.face.uniforms.uField.value = field;
      part.face.uniforms.uOpacity.value = scene.presence * there;
      // The mesh: light lines on the carbon, darker and fainter once the analysis colours the part.
      // The mesh's lines show only while the wing is apart and bare: under the colours, and whole, they would cut it into boxes.
      part.mesh.uniforms.uOpacity.value = scene.presence * scene.mesh * apart * 0.26 * (1 - field);
      part.mesh.uniforms.uColor.value.setScalar(0.88 - 0.8 * field);
      // The outline: always there, so the plan and the aerofoil read at once.
      part.rim.uniforms.uOpacity.value = scene.presence * (0.5 - 0.3 * field);
      for (const material of [part.face, part.mesh, part.rim]) material.uniforms.uBend.value = field;
    }
    // A faint pool of light on the black ground, just under the wing: as wide as the span on the screen, and deeper the
    // further the parts stand apart.
    const reach = ((chord * Math.cos(pose.pitch) + (60 + 380 * apart) * Math.sin(pose.pitch)) * unit) / 2; // half the model's height on the screen
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
