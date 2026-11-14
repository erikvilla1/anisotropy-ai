"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { BEND_DRAWN, demoWing, wingColour, wingExtent } from "@/lib/demo-wing";
import { boxOf, fitInto, roomAbove, roomBeside, type Room } from "./product-demo-fit";
import { clamp01, poseAt, sceneAt } from "./product-demo-timeline";

/** What the page hands the view: the demo's clock, written by the driver's frames, and the view's own request to be drawn again. */
export type DemoSceneHandle = { clock: number; redraw: (() => void) | null; /** How far a visitor has turned the wing by hand, in radians, once the demo has played. */ turn?: { yaw: number; pitch: number }; /** The pointer is down on the stage, turning the wing. */ turning?: boolean; /** How far down the stage the words under the wing begin, in pixels, where a beat's words stand under it. */ under?: number };

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

type Part = {
  id: string; skin: boolean; group: THREE.Group; face: THREE.ShaderMaterial; mesh: THREE.ShaderMaterial; rim: THREE.ShaderMaterial; apart: [number, number, number];
  /** The part's nodes once each, and how far each moves under the load as drawn: what the wing's box on the screen is measured from. */
  places: Float32Array; bends: Float32Array;
};

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
    const own = [...normals.keys()];
    const places = new Float32Array(own.flatMap((node) => at(node)));
    const moves = new Float32Array(own.flatMap((node) => moved(node)));
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
    return { id: part.id, skin, group, face, mesh: net, rim, apart: APART[part.id] ?? [0, 0, 0], places, bends: moves };
  });
  const nodes = built.reduce((sum, part) => sum + part.places.length / 3, 0);
  return { root, parts: built, nodes, turned: new Float32Array(nodes * 3), hasField: Boolean(field), dispose: () => disposables.forEach((item) => item.dispose()) };
}

/** The wing's own axes: x along the chord from nose to tail, y along the span from root to tip, z up (the record's
 * coordinates), all in white, beside the wing. Shown only while the wing is being turned by hand (ADR-0098 amendments 2 and
 * 5). In the view the span lies along the group's x and the chord along its y, so the letters follow the wing, not the
 * screen. */
function buildAxes() {
  const group = new THREE.Group();
  const materials: (THREE.MeshBasicMaterial | THREE.SpriteMaterial)[] = [];
  const disposables: { dispose: () => void }[] = [];
  const shaft = new THREE.CylinderGeometry(0.022, 0.022, 0.8, 12);
  const head = new THREE.ConeGeometry(0.07, 0.22, 16);
  disposables.push(shaft, head);
  const WHITE = "#ffffff";
  const axes: { letter: string; colour: string; along: [number, number, number] }[] = [
    { letter: "X", colour: WHITE, along: [0, 1, 0] }, // the chord
    { letter: "Y", colour: WHITE, along: [1, 0, 0] }, // the span
    { letter: "Z", colour: WHITE, along: [0, 0, 1] }, // up
  ];
  const upright = new THREE.Vector3(0, 1, 0);
  for (const axis of axes) {
    const direction = new THREE.Vector3(...axis.along);
    const material = new THREE.MeshBasicMaterial({ color: axis.colour, transparent: true, opacity: 0, depthTest: false, toneMapped: false });
    const arm = new THREE.Group();
    const stick = new THREE.Mesh(shaft, material);
    stick.position.y = 0.4;
    const tip = new THREE.Mesh(head, material);
    tip.position.y = 0.9;
    arm.add(stick, tip);
    arm.quaternion.setFromUnitVectors(upright, direction);
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 64;
    const context = canvas.getContext("2d")!;
    context.font = "600 44px ui-monospace, SFMono-Regular, Menlo, monospace";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillStyle = axis.colour;
    context.fillText(axis.letter, 32, 34);
    const texture = new THREE.CanvasTexture(canvas);
    const label = new THREE.SpriteMaterial({ map: texture, transparent: true, opacity: 0, depthTest: false, toneMapped: false });
    const letter = new THREE.Sprite(label);
    letter.position.copy(direction).multiplyScalar(1.32);
    letter.scale.setScalar(0.42);
    for (const object of [stick, tip, letter]) object.renderOrder = 10;
    group.add(arm, letter);
    materials.push(material, label);
    disposables.push(material, label, texture);
  }
  group.visible = false;
  return { group, materials, shown: 0, dispose: () => disposables.forEach((item) => item.dispose()) };
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
  const axes = useMemo(buildAxes, []);
  const posed = useMemo(() => new THREE.Euler(), []);
  const spin = useMemo(() => new THREE.Matrix4(), []);
  const turn = useRef<THREE.Group>(null);
  const invalidate = useThree((state) => state.invalidate);
  useEffect(() => {
    handle.redraw = invalidate;
    invalidate();
    return () => { handle.redraw = null; };
  }, [handle, invalidate]);
  useEffect(() => () => {
    model.dispose();
    axes.dispose();
    glow.texture.dispose();
    glow.material.dispose();
    glow.mesh.geometry.dispose();
  }, [model, glow, axes]);

  useFrame((state, delta) => {
    const group = turn.current;
    if (!group) return;
    const clock = handle.clock;
    const pose = poseAt(clock);
    const scene = sceneAt(clock);
    const { width, height } = state.viewport; // the world's size at the model's distance
    const apart = clamp01(pose.explode);
    const field = model.hasField ? scene.field : 0;
    // Every node as the pose turns it, apart and bent as it is drawn, in millimetres about the wing's middle: what the
    // wing's box on the screen is measured from.
    posed.set(-pose.pitch, pose.yaw, 0, "YXZ");
    const turnedBy = spin.makeRotationFromEuler(posed).elements;
    let filled = 0;
    for (const part of model.parts) {
      for (let index = 0; index < part.places.length; index += 3) {
        const along = part.places[index] + part.apart[0] * apart + part.bends[index] * field;
        const fore = part.places[index + 1] + part.apart[1] * apart + part.bends[index + 1] * field;
        const high = part.places[index + 2] + part.apart[2] * apart + part.bends[index + 2] * field;
        model.turned[filled++] = turnedBy[0] * along + turnedBy[4] * fore + turnedBy[8] * high;
        model.turned[filled++] = turnedBy[1] * along + turnedBy[5] * fore + turnedBy[9] * high;
        model.turned[filled++] = turnedBy[2] * along + turnedBy[6] * fore + turnedBy[10] * high;
      }
    }
    // The wing's size and place: it fills the room the beat's words leave, over them or beside them (ADR-0098 amendments 3
    // and 4), whatever the window's shape; between two beats the one room's fit eases into the other's.
    const wide = state.size.width, tall = state.size.height;
    const pixel = width / wide; // world units a pixel of the stage
    const fitted = (room: Room) => fitInto(model.turned, model.nodes, {
      left: (room.left - wide / 2) * pixel, right: (room.right - wide / 2) * pixel, bottom: (tall / 2 - room.bottom) * pixel, top: (tall / 2 - room.top) * pixel,
    }, CAMERA_Z);
    const under = clamp01(pose.under);
    let { unit, x, y } = under < 1 ? fitted(roomBeside(pose.beside, wide, tall)) : { unit: 0, x: 0, y: 0 };
    if (under > 0) {
      const above = fitted(roomAbove(wide, tall, handle.under));
      unit += (above.unit - unit) * under;
      x += (above.x - x) * under;
      y += (above.y - y) * under;
    }
    group.position.set(x, y, 0);
    group.scale.setScalar(unit);
    const hand = handle.turn ?? { yaw: 0, pitch: 0 };
    group.rotation.set(-(pose.pitch + hand.pitch), pose.yaw + hand.yaw, 0, "YXZ");
    group.visible = scene.presence > 0;
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
    // A faint pool of light on the black ground, just under the wing as the pose stands it: most of its width on the
    // screen, and deeper the taller the wing stands.
    const drawn = boxOf(model.turned, model.nodes, unit, x, y, CAMERA_Z);
    glow.mesh.position.set((drawn.left + drawn.right) / 2, drawn.bottom - 0.03 * height, -1);
    glow.mesh.scale.set(0.85 * (drawn.right - drawn.left), 0.09 * height + 0.25 * (drawn.top - drawn.bottom), 1);
    glow.material.opacity = 0.16 * scene.presence;
    // The axes: just beside the wing's left end as the pose stands it, level with its middle, turned as the wing is; they
    // come in while the pointer holds the wing and go when it lets go. The view asks for frames itself while they fade.
    const wanted = handle.turning ? 1 : 0;
    if (axes.shown !== wanted) {
      const step = Math.min(0.05, delta); // the frame before may be long ago: the view draws on demand
      axes.shown = wanted > axes.shown ? Math.min(1, axes.shown + step / 0.18) : Math.max(0, axes.shown - step / 0.26);
      state.invalidate();
    }
    axes.group.visible = axes.shown > 0;
    if (axes.group.visible) {
      const reachOf = Math.min(0.06 * height, 0.05 * width);
      // An arm with its letter reaches 1.5 times `reachOf` from the middle of the axes: they stand that far and a little
      // more to the left of the wing's box, and never off the stage.
      axes.group.position.set(Math.max(-width / 2 + 1.7 * reachOf, drawn.left - 1.9 * reachOf), (drawn.bottom + drawn.top) / 2, 2);
      axes.group.scale.setScalar(reachOf);
      axes.group.rotation.copy(group.rotation);
      for (const material of axes.materials) material.opacity = axes.shown;
    }
  });

  return (
    <>
      <primitive object={glow.mesh} />
      <primitive object={axes.group} />
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
