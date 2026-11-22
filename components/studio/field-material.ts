import * as THREE from "three";
import { hexToRgb } from "@/lib/studio-colors";

/**
 * The results material (ADR-0063): the graphics card colours every fragment from one float per vertex, the package's value there,
 * and the scale's ends and ramp. Unlit, so no light skews a colour: a colour on the plate is the legend's colour for that value.
 * Bands cut the ramp into equal steps of the legend, each step one flat colour and no line between them (ADR-0063 amendment 3: a
 * dark line at every step stacked into a black band where the field is steep, at the tab line, and hid the stress there); 0 bands
 * is the smooth ramp. A missing value is the named grey; an element clamped inside a grip is the grip's lighter grey (ADR-0063 amendment 4).
 * The side faces are darkened a little so the thickness reads; the top and bottom faces are the pure colour. The ramp has up to nine
 * stops and says how many, so the five of the Classic rainbow are drawn as they are (ADR-0063 amendment 1). With Lighting on (the default
 * since ADR-0063 amendment 2, the look of the mockup the founder chose) a key light up and to the left of the camera, moving with it, a
 * weaker fill from the right and a little shine shade every face: a face turned to the viewer keeps about its colour, a side turned away
 * falls to half of it, so the part reads as a solid. Lighting off is the exact colours: a colour on the plate is the legend's.
 */

/** The float written where the package wrote no value (a node no element touches): any real value is above it. */
export const NO_VALUE = -1e30;
export const MISSING_GRAY = "#3a3f3b";
/** The float written at every corner of an element clamped inside a grip, below NO_VALUE, and the grip's grey it is drawn in: its zero
 * strain and stress are the clamp's, not a result (ADR-0063 amendment 4). */
export const IN_GRIP = -3e30;
export const GRIP_GRAY = "#6d7277";
const STOP_COUNT = 9; // the most stops a ramp may have; `uCount` says how many it has

const vertexShader = /* glsl */ `
  attribute float value;
  varying float vValue;
  varying vec3 vNormal;
  varying vec3 vViewNormal;
  void main() {
    vValue = value;
    vNormal = normal;
    vViewNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

const fragmentShader = /* glsl */ `
  uniform float uMin;
  uniform float uMax;
  uniform vec3 uStops[${STOP_COUNT}];
  uniform float uCount;
  uniform float uLit;
  uniform float uBands;
  uniform vec3 uMissing;
  uniform vec3 uGrip;
  varying float vValue;
  varying vec3 vNormal;
  varying vec3 vViewNormal;

  vec3 rampAt(float t) {
    float p = clamp(t, 0.0, 1.0) * (uCount - 1.0);
    vec3 color = uStops[0];
    for (int i = 0; i < ${STOP_COUNT - 1}; i++) {
      float lo = float(i);
      if (lo < uCount - 1.0 && p >= lo && p <= lo + 1.0) color = mix(uStops[i], uStops[i + 1], p - lo);
    }
    return color;
  }

  void main() {
    float flatFace = step(0.5, abs(vNormal.z));
    float shade = mix(0.78, 1.0, flatFace);
    float shine = 0.0;
    if (uLit > 0.5) {
      // in the camera's frame: x right, y up, z toward the viewer; the lights ride with the camera, so every view is lit alike
      vec3 n = normalize(gl_FrontFacing ? vViewNormal : -vViewNormal);
      vec3 key = normalize(vec3(-0.42, 0.62, 0.72));
      vec3 fill = normalize(vec3(0.7, -0.25, 0.65));
      shade = 0.55 + 0.5 * max(dot(n, key), 0.0) + 0.12 * max(dot(n, fill), 0.0);
      shine = 0.08 * pow(max(dot(n, normalize(key + vec3(0.0, 0.0, 1.0))), 0.0), 38.0);
    }
    if (vValue < -2.0e30) {
      gl_FragColor = vec4(uGrip * shade + shine, 1.0);
      return;
    }
    if (vValue < -1.0e29) {
      gl_FragColor = vec4(uMissing * shade + shine, 1.0);
      return;
    }
    float t = clamp((vValue - uMin) / max(uMax - uMin, 1.0e-30), 0.0, 1.0);
    vec3 color;
    if (uBands > 0.5) {
      float f = t * uBands;
      float band = min(floor(f), uBands - 1.0);
      color = rampAt((band + 0.5) / uBands);
    } else {
      color = rampAt(t);
    }
    gl_FragColor = vec4(color * shade + shine, 1.0);
  }`;

export type FieldScale = { min: number; max: number; stops: string[]; bands: number; /** a light from the viewer's side (ADR-0063 amendment 1) */ lit?: boolean };

function vec(hex: string): THREE.Vector3 { const [r, g, b] = hexToRgb(hex); return new THREE.Vector3(r, g, b); } // raw sRGB: the shader writes it as is

/** One material for the whole run; `applyScale` moves the ends, the ramp and the bands without a new program. */
export function fieldMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    vertexShader, fragmentShader, side: THREE.DoubleSide,
    uniforms: {
      uMin: { value: 0 }, uMax: { value: 1 }, uBands: { value: 0 }, uCount: { value: 7 }, uLit: { value: 0 },
      uStops: { value: Array.from({ length: STOP_COUNT }, () => new THREE.Vector3(0.5, 0.5, 0.5)) },
      uMissing: { value: vec(MISSING_GRAY) }, uGrip: { value: vec(GRIP_GRAY) },
    },
  });
}

export function applyScale(material: THREE.ShaderMaterial, scale: FieldScale): void {
  material.uniforms.uMin.value = scale.min;
  material.uniforms.uMax.value = scale.max;
  material.uniforms.uBands.value = scale.bands;
  material.uniforms.uLit.value = scale.lit ? 1 : 0;
  const count = Math.min(STOP_COUNT, Math.max(2, scale.stops.length));
  material.uniforms.uCount.value = count;
  const stops = material.uniforms.uStops.value as THREE.Vector3[];
  for (let i = 0; i < STOP_COUNT; i++) {
    const [r, g, b] = hexToRgb(scale.stops[Math.min(i, count - 1)]);
    stops[i].set(r, g, b);
  }
}
