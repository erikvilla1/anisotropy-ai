import * as THREE from "three";
import { hexToRgb } from "@/lib/studio-colors";

/**
 * The results material (ADR-0063): the graphics card colours every fragment from one float per vertex, the package's value there,
 * and the scale's ends and ramp. Unlit, so no light skews a colour: a colour on the plate is the legend's colour for that value.
 * Bands cut the ramp into equal steps of the legend, with an isoline drawn one pixel wide at every step boundary (`fwidth`, so the
 * line is as wide on a zoomed-out plate as on a zoomed-in one); 0 bands is the smooth ramp. A missing value is the named grey.
 * The side faces are darkened a little so the thickness reads; the top and bottom faces are the pure colour.
 */

/** The float written where the package wrote no value (a node no element touches): any real value is above it. */
export const NO_VALUE = -1e30;
export const MISSING_GRAY = "#3a3f3b";
const ISOLINE = "#0c0e0d"; // the background's colour, so a line reads as a cut through the ramp
const STOP_COUNT = 7;

const vertexShader = /* glsl */ `
  attribute float value;
  varying float vValue;
  varying vec3 vNormal;
  void main() {
    vValue = value;
    vNormal = normal;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }`;

const fragmentShader = /* glsl */ `
  uniform float uMin;
  uniform float uMax;
  uniform vec3 uStops[${STOP_COUNT}];
  uniform float uBands;
  uniform float uIsoline;
  uniform vec3 uMissing;
  uniform vec3 uIsoColor;
  varying float vValue;
  varying vec3 vNormal;

  vec3 rampAt(float t) {
    float p = clamp(t, 0.0, 1.0) * float(${STOP_COUNT - 1});
    vec3 color = uStops[0];
    for (int i = 0; i < ${STOP_COUNT - 1}; i++) {
      float lo = float(i);
      if (p >= lo && p <= lo + 1.0) color = mix(uStops[i], uStops[i + 1], p - lo);
    }
    return color;
  }

  void main() {
    float flatFace = step(0.5, abs(vNormal.z));
    float shade = mix(0.78, 1.0, flatFace);
    if (vValue < -1.0e29) {
      gl_FragColor = vec4(uMissing * shade, 1.0);
      return;
    }
    float t = clamp((vValue - uMin) / max(uMax - uMin, 1.0e-30), 0.0, 1.0);
    vec3 color;
    if (uBands > 0.5) {
      float f = t * uBands;
      float band = min(floor(f), uBands - 1.0);
      color = rampAt((band + 0.5) / uBands);
      float toBoundary = min(fract(f), 1.0 - fract(f));
      float pixel = max(fwidth(f), 1.0e-7);
      float halfWidth = 0.5 * uIsoline * pixel;
      float line = 1.0 - smoothstep(halfWidth, halfWidth + pixel, toBoundary);
      // No line at the scale's two ends. The 1e-3 of a band keeps a face whose value sits exactly at an end (a gripped tab at the
      // largest displacement) from catching rounding noise as a speckle of line pixels.
      if (f < halfWidth + pixel + 1.0e-3 || f > uBands - halfWidth - pixel - 1.0e-3) line = 0.0;
      color = mix(color, uIsoColor, line * flatFace);
    } else {
      color = rampAt(t);
    }
    gl_FragColor = vec4(color * shade, 1.0);
  }`;

export type FieldScale = { min: number; max: number; stops: string[]; bands: number };

function vec(hex: string): THREE.Vector3 { const [r, g, b] = hexToRgb(hex); return new THREE.Vector3(r, g, b); } // raw sRGB: the shader writes it as is

/** One material for the whole run; `applyScale` moves the ends, the ramp and the bands without a new program. */
export function fieldMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    vertexShader, fragmentShader, side: THREE.DoubleSide,
    uniforms: {
      uMin: { value: 0 }, uMax: { value: 1 }, uBands: { value: 0 }, uIsoline: { value: 1.2 },
      uStops: { value: Array.from({ length: STOP_COUNT }, () => new THREE.Vector3(0.5, 0.5, 0.5)) },
      uMissing: { value: vec(MISSING_GRAY) }, uIsoColor: { value: vec(ISOLINE) },
    },
  });
}

export function applyScale(material: THREE.ShaderMaterial, scale: FieldScale): void {
  material.uniforms.uMin.value = scale.min;
  material.uniforms.uMax.value = scale.max;
  material.uniforms.uBands.value = scale.bands;
  const stops = material.uniforms.uStops.value as THREE.Vector3[];
  for (let i = 0; i < STOP_COUNT; i++) {
    const [r, g, b] = hexToRgb(scale.stops[Math.min(i, scale.stops.length - 1)]);
    stops[i].set(r, g, b);
  }
}
